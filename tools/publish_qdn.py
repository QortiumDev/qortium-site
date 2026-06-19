#!/usr/bin/env python3
"""Publish a directory to QDN (Qortal/Qortium) through a node, signing the
transaction LOCALLY so the private key never leaves this machine.

Pipeline:
  1. zip the directory contents (index.html must be at the top for WEBSITE/APP)
  2. POST <node>/arbitrary/<service>/<name>/<identifier>/zip  -> unsigned tx
     (the node stores the uploaded data; query params set title/description/...)
  3. POST <node>/arbitrary/compute  -> unsigned tx with a valid mempow nonce
  4. sign the nonced bytes locally (qortal_local_sign) -> signed tx
  5. POST <node>/transactions/process  -> broadcast  (skipped with --no-broadcast)

Transport: by default calls the node over HTTP directly. With --ssh-host, every
node call is proxied as `ssh <host> curl http://127.0.0.1:24891/...` with the
body piped over stdin — so the request reaches the node as its own localhost
(passing a localhost-only apiWhitelist) without opening any port. Build and
signing always happen locally; only the data + signed tx cross the link.

The only secret-touching step is local signing, delegated to the audited
qortal_local_sign module in this same folder. No key is ever sent to the node.
"""
from __future__ import annotations

import argparse
import base64
import io
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlencode

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qortal_local_sign as signer  # noqa: E402

NONCE_MARKERS = ("nonce", "pow", "proof", "mempow")


def zip_dir_to_base64(directory: Path) -> str:
    root = directory.resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root)))
    return base64.b64encode(buf.getvalue()).decode("ascii")


class Transport:
    """POST to the node either directly (HTTP) or via `ssh <host> curl`."""

    def __init__(self, base: str, ssh_host: str | None, api_key: str | None,
                 timeout: int, remote_api_key_file: str | None = None):
        self.base = base.rstrip("/")
        self.ssh_host = ssh_host
        self.api_key = api_key
        self.timeout = timeout
        # Path to an apikey.txt ON the ssh host; read there via $(cat ...) so the
        # key never reaches this machine. ssh transport only.
        self.remote_api_key_file = remote_api_key_file

    def _url(self, path: str, params: dict | None) -> str:
        url = self.base + path
        if params:
            url += "?" + urlencode(params)
        return url

    def post(self, path: str, body: str, content_type: str = "text/plain",
             params: dict | None = None) -> tuple[int, str]:
        url = self._url(path, params)
        data = body.encode("utf-8")
        if not self.ssh_host:
            headers = {"Content-Type": content_type}
            if self.api_key:
                headers["X-API-KEY"] = self.api_key
            r = requests.post(url, data=data, headers=headers, timeout=self.timeout)
            return r.status_code, r.text
        # ssh + curl; body over stdin (@-) so large base64 bodies are fine.
        curl = (f"curl -sS --max-time {self.timeout} -X POST {shlex.quote(url)} "
                f"--data-binary @- -H {shlex.quote('Content-Type: ' + content_type)} "
                f"-w {shlex.quote(chr(10) + '%{http_code}')}")
        if self.remote_api_key_file:
            # $(cat ...) is evaluated by the remote shell, so the key is read on
            # the host and interpolated there; it never touches this machine.
            curl += f" -H \"X-API-KEY: $(cat {shlex.quote(self.remote_api_key_file)})\""
        elif self.api_key:
            curl += f" -H {shlex.quote('X-API-KEY: ' + self.api_key)}"
        proc = subprocess.run(
            ["ssh", "-T", "-o", "BatchMode=yes", self.ssh_host, curl],
            input=data, capture_output=True, timeout=self.timeout + 30,
        )
        out = proc.stdout.decode("utf-8", "replace")
        nl = out.rfind("\n")
        if nl < 0:
            return 0, (out + proc.stderr.decode("utf-8", "replace"))
        try:
            return int(out[nl + 1:].strip()), out[:nl]
        except ValueError:
            return 0, out + proc.stderr.decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node", default="http://127.0.0.1:24891",
                    help="node base URL (from the node's own perspective when --ssh-host is used)")
    ap.add_argument("--ssh-host", help="proxy node calls as `ssh <host> curl ...` (reaches node as localhost)")
    ap.add_argument("--api-key", help="X-API-KEY header value (not needed for a localhost-whitelisted node)")
    ap.add_argument("--remote-api-key-file", help="path to apikey.txt ON the --ssh-host (read there via $(cat); never reaches this machine)")
    ap.add_argument("--service", default="WEBSITE")
    ap.add_argument("--name", required=True, help="registered name (publisher)")
    ap.add_argument("--identifier", default="default", help="'default' = default identifier")
    ap.add_argument("--path", required=True, help="directory to publish (its contents are zipped)")
    ap.add_argument("--title")
    ap.add_argument("--description")
    ap.add_argument("--category")
    ap.add_argument("--fee", help="fee in QORT (e.g. 0 for Qortium MemoryPoW, 0.01 for Qortal)")
    ap.add_argument("--no-broadcast", action="store_true", help="stop before /transactions/process")
    ap.add_argument("--timeout", type=int, default=240)
    signer._add_key_args(ap)
    args = ap.parse_args()

    tx = Transport(args.node, args.ssh_host, args.api_key, args.timeout,
                   remote_api_key_file=args.remote_api_key_file)
    ident = "" if args.identifier in ("", "default", None) else args.identifier
    publish_path = f"/arbitrary/{args.service}/{args.name}" + (f"/{ident}" if ident else "") + "/zip"

    params = {}
    if args.title:
        params["title"] = args.title
    if args.description:
        params["description"] = args.description
    if args.category:
        params["category"] = args.category.upper()
    if args.fee is not None:
        params["fee"] = str(int(round(float(args.fee) * 100_000_000)))

    # Resolve the signing seed up front so a bad password/key fails before upload.
    seed = signer.resolve_seed(args)
    addr = signer.qortal_address_from_seed(seed)
    via = f"ssh {args.ssh_host}" if args.ssh_host else "http"
    print(f"[1/5] signing identity: {addr}  (transport: {via})", file=sys.stderr)

    b64 = zip_dir_to_base64(Path(args.path))
    print(f"[2/5] zipped {args.path} -> {len(b64)} base64 chars; POST {publish_path}", file=sys.stderr)
    code, text = tx.post(publish_path, b64, params=params)
    if code != 200:
        raise SystemExit(f"build failed: HTTP {code}: {text[:500]}")
    unsigned = text.strip().strip('"')
    print(f"[2/5] unsigned tx: {len(unsigned)} chars", file=sys.stderr)

    print("[3/5] computing mempow nonce (POST /arbitrary/compute)...", file=sys.stderr)
    code, text = tx.post("/arbitrary/compute", unsigned)
    if code != 200 or not text.strip():
        raise SystemExit(f"compute failed: HTTP {code}: {text[:500]}")
    nonced = text.strip().strip('"')

    # Best-effort decode to show what we're about to sign/broadcast.
    try:
        dcode, dtext = tx.post("/transactions/decode", nonced)
        if dcode == 200:
            import json as _json
            d = _json.loads(dtext)
            print(f"[4/5] decoded tx: type={d.get('type')} "
                  f"creator={d.get('creatorAddress', d.get('creatorPublicKey'))} "
                  f"fee={d.get('fee')}", file=sys.stderr)
    except Exception:
        pass

    signed = signer.sign_transaction(seed, nonced)
    print(f"[4/5] signed locally: {len(signed)} chars", file=sys.stderr)

    if args.no_broadcast:
        print("[5/5] --no-broadcast set; NOT submitting.", file=sys.stderr)
        print(signed)
        return 0

    # Some reverse proxies return 502/504 after timing out while validating a
    # large arbitrary tx even though the submission was accepted. Retry; a clear
    # rejection (invalid signature, nonce/PoW) is fatal and not retried.
    print("[5/5] broadcasting (POST /transactions/process)...", file=sys.stderr)
    last = ""
    for attempt in range(1, 4):
        code, text = tx.post("/transactions/process", signed)
        body = text.strip()
        if code == 200:
            print(f"BROADCAST OK (attempt {attempt}): {body}")
            return 0
        last = f"HTTP {code}: {body[:300]}"
        low = body.lower()
        if "invalid signature" in low or any(m in low for m in NONCE_MARKERS):
            raise SystemExit(f"process rejected (fatal): {last}")
        print(f"  attempt {attempt} failed ({last}); retrying...", file=sys.stderr)
    raise SystemExit(
        f"process did not return 200 after retries: {last}\n"
        "The tx may still have been accepted — verify via /arbitrary/resources/search."
    )


if __name__ == "__main__":
    raise SystemExit(main())
