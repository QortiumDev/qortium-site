#!/usr/bin/env python3
"""Publish a directory to QDN (Qortal/Qortium) through a remote node, signing
the transaction LOCALLY so the private key never leaves this machine.

Pipeline:
  1. zip the directory contents (index.html must be at the top for WEBSITE/APP)
  2. POST <node>/arbitrary/<service>/<name>/<identifier>/zip  -> unsigned tx
     (the node stores the uploaded data; query params set title/description/...)
  3. POST <node>/arbitrary/compute  -> unsigned tx with a valid mempow nonce
  4. sign the nonced bytes locally (qortal_local_sign) -> signed tx
  5. POST <node>/transactions/process  -> broadcast  (skipped with --no-broadcast)

The only secret-touching step is local signing, delegated to the audited
qortal_local_sign module in this same folder. No key is ever sent to the node.
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
import zipfile
from pathlib import Path

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


def post_text(url: str, body: str, timeout: int) -> requests.Response:
    return requests.post(
        url, data=body.encode("utf-8"),
        headers={"Content-Type": "text/plain"}, timeout=timeout,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node", required=True, help="base node URL, e.g. https://ext-node.qortal.link")
    ap.add_argument("--service", default="WEBSITE")
    ap.add_argument("--name", required=True, help="registered name (publisher)")
    ap.add_argument("--identifier", default="default", help="'default' = default identifier")
    ap.add_argument("--path", required=True, help="directory to publish (its contents are zipped)")
    ap.add_argument("--title")
    ap.add_argument("--description")
    ap.add_argument("--category")
    ap.add_argument("--fee", help="fee in QORT (omit to let the node use its default)")
    ap.add_argument("--no-broadcast", action="store_true", help="stop before /transactions/process")
    ap.add_argument("--timeout", type=int, default=240)
    signer._add_key_args(ap)
    args = ap.parse_args()

    node = args.node.rstrip("/")
    ident = "" if args.identifier in ("", "default", None) else args.identifier
    path_part = f"/{ident}" if ident else ""
    publish_url = f"{node}/arbitrary/{args.service}/{args.name}{path_part}/zip"

    params = {}
    if args.title:
        params["title"] = args.title
    if args.description:
        params["description"] = args.description
    if args.category:
        params["category"] = args.category.upper()
    if args.fee is not None:
        params["fee"] = str(int(round(float(args.fee) * 100_000_000)))

    # Resolve the signing seed up front so a bad password fails before upload.
    seed = signer.resolve_seed(args)
    addr = signer.qortal_address_from_seed(seed)
    print(f"[1/5] signing identity: {addr}", file=sys.stderr)

    b64 = zip_dir_to_base64(Path(args.path))
    print(f"[2/5] zipped {args.path} -> {len(b64)} base64 chars; POST {publish_url}", file=sys.stderr)
    r = requests.post(publish_url, params=params, data=b64.encode("ascii"),
                      headers={"Content-Type": "text/plain"}, timeout=args.timeout)
    if r.status_code != 200:
        raise SystemExit(f"build failed: HTTP {r.status_code}: {r.text[:500]}")
    unsigned = r.text.strip().strip('"')
    print(f"[2/5] unsigned tx: {len(unsigned)} chars", file=sys.stderr)

    print("[3/5] computing mempow nonce (POST /arbitrary/compute)...", file=sys.stderr)
    rc = post_text(f"{node}/arbitrary/compute", unsigned, args.timeout)
    if rc.status_code != 200 or not rc.text.strip():
        raise SystemExit(f"compute failed: HTTP {rc.status_code}: {rc.text[:500]}")
    nonced = rc.text.strip().strip('"')

    # Best-effort decode to show what we're about to sign/broadcast.
    try:
        rd = post_text(f"{node}/transactions/decode", nonced, 60)
        if rd.status_code == 200:
            d = rd.json()
            fee = d.get("fee")
            print(f"[4/5] decoded tx: type={d.get('type')} creator={d.get('creatorAddress', d.get('creatorPublicKey'))} fee={fee}", file=sys.stderr)
    except Exception:
        pass

    signed = signer.sign_transaction(seed, nonced)
    print(f"[4/5] signed locally: {len(signed)} chars", file=sys.stderr)

    if args.no_broadcast:
        print("[5/5] --no-broadcast set; NOT submitting.", file=sys.stderr)
        print(signed)
        return 0

    # Public-node reverse proxies often return 502/504 after timing out while the
    # node validates a large arbitrary tx, even though the submission may still be
    # accepted. Retry a few times; a clear rejection (e.g. invalid signature,
    # nonce/PoW) is fatal and not retried.
    print("[5/5] broadcasting (POST /transactions/process)...", file=sys.stderr)
    last = ""
    for attempt in range(1, 4):
        rp = post_text(f"{node}/transactions/process", signed, args.timeout)
        body = rp.text.strip()
        if rp.status_code == 200:
            print(f"BROADCAST OK (attempt {attempt}): {body}")
            return 0
        last = f"HTTP {rp.status_code}: {body[:300]}"
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
