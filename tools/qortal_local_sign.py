#!/usr/bin/env python3
"""Local, offline signer for Qortal / Qortium transactions.

Self-contained: depends only on `cryptography` and `bcrypt`. Copy this single
file into any project that needs to sign without handing a private key to a
node. It never makes a network call and never sends the key anywhere.

Why this exists
---------------
The node's POST /transactions/sign takes {privateKey, transactionBytes} — i.e.
you would have to send your private key to whatever node you target. When that
node is a public/remote node, that leaks the key. The node simply Ed25519-signs
the unsigned transaction bytes and appends the 64-byte signature, so we can do
the identical operation here on the machine that holds the key.

Signing model (matches Qortal core /transactions/sign):
    message   = base58_decode(unsigned_transaction_bytes)   # no signature yet
    signature = Ed25519_sign(seed32, message)                # 64 bytes
    signed    = message + signature
    output    = base58_encode(signed)

The key (a 32-byte Ed25519 seed) can come from:
  * a Qortal/Qortium wallet-backup JSON + password (decrypted locally here), or
  * a base58 private key string (32-byte seed, or 64-byte secret key — the
    first 32 bytes are the seed).

Subcommands
-----------
  address   derive address + public key (no signing)
  key       print the base58 32-byte private seed (explicit; for safe storage)
  sign      sign unsigned transaction bytes -> signed transaction bytes
  verify    verify a signed transaction's trailing signature against a pubkey
  selftest  offline consistency checks (no wallet/secret needed)

Examples
--------
  # Derive the address from a wallet backup (confirms password is right):
  python3 qortal_local_sign.py address --wallet backup.json --password-file pw.txt

  # Sign unsigned tx bytes (base58) read from stdin, key from a wallet backup:
  echo "<unsignedTxBase58>" | python3 qortal_local_sign.py sign \
      --wallet backup.json --password-file pw.txt

  # Sign with a base58 private key instead:
  python3 qortal_local_sign.py sign --tx "<unsignedTxBase58>" --private-key "<b58key>"

Security notes
--------------
  * Prefer --password-file / --private-key-file over passing secrets as args
    (process args are visible to other users via `ps`).
  * `key` is the only command that prints the private seed; everything else
    keeps it in memory only.
  * Store any decrypted key file with `chmod 600` and OUTSIDE any repo.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# --- Qortal wallet KDF constants (must match the wallet format exactly) ------
B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
B58_SET = set(B58_ALPHABET.decode("ascii"))
STATIC_SALT = "4ghkVQExoneGqZqHTMMhhFfxXsVg2A75QeS1HCM5KAih"
STATIC_BCRYPT_SALT = b"$2a$11$IxVE941tXVUD4cW0TNVm.O"
KDF_THREADS = 16

PRIVATE_KEY_BYTES = 32
MASTER_SEED_BYTES = 64
WALLET_VERSION_MASTER_SEED = 2   # encryptedSeed is a 64-byte master seed
WALLET_VERSION_PRIVATE_KEY = 3   # encryptedSeed is a 32-byte private seed


# --- Base58 -----------------------------------------------------------------
def b58encode(raw: bytes) -> str:
    if not raw:
        return "1"
    n = int.from_bytes(raw, "big")
    out = bytearray()
    while n > 0:
        n, r = divmod(n, 58)
        out.append(B58_ALPHABET[r])
    pad = 0
    for byte in raw:
        if byte == 0:
            pad += 1
        else:
            break
    return (B58_ALPHABET[0:1] * pad + out[::-1]).decode("ascii")


def b58decode(value: str) -> bytes:
    text = (value or "").strip()
    if not text:
        return b""
    n = 0
    for ch in text:
        if ch not in B58_SET:
            raise ValueError("Invalid Base58 string")
        n = n * 58 + B58_ALPHABET.index(ord(ch))
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n > 0 else b""
    pad = 0
    for ch in text:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + raw


# --- Key derivation / addresses --------------------------------------------
def qortal_hub_kdf(value: str) -> bytes:
    """Reproduce the wallet-backup KDF (bcrypt over sha512 chunks)."""
    import bcrypt

    text = str(value or "")
    if not text:
        raise ValueError("KDF input is empty.")
    parts = []
    for i in range(KDF_THREADS):
        msg = (STATIC_SALT + text + str(i)).encode("utf-8")
        sha = hashlib.sha512(msg).digest()
        import base64
        b64_72 = base64.b64encode(sha).decode("ascii")[:72]
        pw = (b64_72.encode("utf-8") + b"\x00")[:72]
        parts.append(bcrypt.hashpw(pw, STATIC_BCRYPT_SALT).decode("utf-8"))
    final_input = (STATIC_SALT + "".join(parts)).encode("utf-8")
    return hashlib.sha512(final_input).digest()


def seed_to_public_key(seed: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    if len(seed) != PRIVATE_KEY_BYTES:
        raise ValueError("Ed25519 seed must be exactly 32 bytes.")
    return (
        Ed25519PrivateKey.from_private_bytes(seed)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )


def qortal_address_from_seed(seed: bytes) -> str:
    public_key = seed_to_public_key(seed)
    public_key_hash = hashlib.sha256(public_key).digest()
    account_hash = hashlib.new("ripemd160", public_key_hash).digest()
    address_without_checksum = bytes([58]) + account_hash
    checksum = hashlib.sha256(
        hashlib.sha256(address_without_checksum).digest()
    ).digest()[:4]
    return b58encode(address_without_checksum + checksum)


def derive_address_seed(master_seed: bytes, address_index: int = 0) -> bytes:
    if len(master_seed) != MASTER_SEED_BYTES:
        raise ValueError("Master seed must be exactly 64 bytes.")
    if address_index < 0:
        raise ValueError("Address index must be >= 0.")
    nonce = int(address_index).to_bytes(4, "big", signed=False)
    nonce_seed = nonce + master_seed + nonce
    first_hash = hashlib.sha512(nonce_seed).digest()
    return hashlib.sha512(first_hash + nonce_seed).digest()[:PRIVATE_KEY_BYTES]


def decode_private_key_input(private_key: str) -> bytes:
    decoded = b58decode(str(private_key or "").strip())
    if len(decoded) == PRIVATE_KEY_BYTES * 2:  # 64-byte secret key -> use seed
        return decoded[:PRIVATE_KEY_BYTES]
    if len(decoded) != PRIVATE_KEY_BYTES:
        raise ValueError("Private key must decode to exactly 32 or 64 bytes.")
    return decoded


# --- Wallet decryption ------------------------------------------------------
def _require_str(wallet: Dict[str, Any], key: str) -> str:
    value = wallet.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Wallet file must include non-empty {key}.")
    return value.strip()


def _require_int(wallet, key) -> int:
    value = wallet.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Wallet file must include a numeric {key}.") from None


def decrypt_wallet_to_seed(wallet: Dict[str, Any], password: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    version = _require_int(wallet, "version")
    if version not in (WALLET_VERSION_MASTER_SEED, WALLET_VERSION_PRIVATE_KEY):
        raise ValueError(f"Unsupported wallet version: {version}.")

    kdf_threads = _require_int(wallet, "kdfThreads")
    if kdf_threads != KDF_THREADS:
        raise ValueError(f"Unsupported wallet kdfThreads: {kdf_threads}.")

    address0 = _require_str(wallet, "address0")
    encrypted_seed = b58decode(_require_str(wallet, "encryptedSeed"))
    salt = b58decode(_require_str(wallet, "salt"))
    iv = b58decode(_require_str(wallet, "iv"))
    stored_mac = b58decode(_require_str(wallet, "mac"))

    if len(salt) != 32:
        raise ValueError("Wallet salt must decode to 32 bytes.")
    if len(iv) != 16:
        raise ValueError("Wallet IV must decode to 16 bytes.")
    if len(encrypted_seed) == 0 or len(encrypted_seed) % 16 != 0:
        raise ValueError("Wallet encryptedSeed length is invalid.")

    key = qortal_hub_kdf(str(password or ""))
    encryption_key = key[:32]
    mac_key = key[32:63]
    computed_mac = hmac.new(mac_key, encrypted_seed, hashlib.sha512).digest()
    if not hmac.compare_digest(computed_mac, stored_mac):
        raise ValueError("Incorrect wallet password.")

    decryptor = Cipher(algorithms.AES(encryption_key), modes.CBC(iv)).decryptor()
    payload = decryptor.update(encrypted_seed) + decryptor.finalize()

    if version == WALLET_VERSION_PRIVATE_KEY:
        if len(payload) != PRIVATE_KEY_BYTES:
            raise ValueError("Version 3 payload must be 32 bytes.")
        seed = payload
    else:
        if len(payload) != MASTER_SEED_BYTES:
            raise ValueError("Version 2 payload must be 64 bytes.")
        seed = derive_address_seed(payload, 0)

    if qortal_address_from_seed(seed) != address0:
        raise ValueError("Password unlocked data, but address0 did not match.")
    return seed


# --- Signing ----------------------------------------------------------------
def sign_message(seed: bytes, message: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if len(seed) != PRIVATE_KEY_BYTES:
        raise ValueError("Ed25519 seed must be exactly 32 bytes.")
    return Ed25519PrivateKey.from_private_bytes(seed).sign(message)


# --- ARBITRARY transactions need a special "bytes for signing" ---------------
# For most Qortal transactions the signing bytes equal the unsigned serialized
# bytes (the base transformer just strips the trailing signature). ARBITRARY
# overrides this: its toBytesForSigning OMITS the 1-byte dataType flag and, for
# RAW_DATA, signs sha256(data) instead of the data. So we must parse the
# unsigned bytes and rebuild the signing form. A byte-exact round-trip of the
# re-serialized toBytes vs. the input guards against any layout mistake.
TX_TYPE_ARBITRARY = 10
SIGNATURE_LEN = 64
# The shared transaction header is treated as an opaque prefix (copied verbatim
# into both toBytes and toBytesForSigning), so only its LENGTH matters here:
#   Qortal:  type(4)+timestamp(8)+groupId(4)+reference(64)+creatorPublicKey(32) = 112
#   Qortium: same but the fork dropped the 64-byte reference                     =  48
# We auto-detect which by picking the length whose re-serialized toBytes
# reproduces the input byte-for-byte (the round-trip guard), so the same signer
# works for both chains without a flag.
_ARB_HEADER_LEN = 4 + 8 + 4 + 64 + 32
_ARB_HEADER_CANDIDATES = (4 + 8 + 4 + 64 + 32, 4 + 8 + 4 + 32)  # Qortal, Qortium


def _take(buf: bytes, off: int, n: int):
    if n < 0 or off + n > len(buf):
        raise ValueError("transaction bytes truncated")
    return buf[off:off + n], off + n


def _take_u32(buf: bytes, off: int):
    chunk, off = _take(buf, off, 4)
    return int.from_bytes(chunk, "big"), off


def _take_lenpref(buf: bytes, off: int):
    """Read an INT-length-prefixed field; return (full_segment, body, new_off)."""
    n, after_len = _take_u32(buf, off)
    body, after_body = _take(buf, after_len, n)
    return buf[off:after_body], body, after_body


def _parse_arbitrary(buf: bytes, header_len: int = _ARB_HEADER_LEN) -> dict:
    if int.from_bytes(buf[:4], "big") != TX_TYPE_ARBITRARY:
        raise ValueError("Not an ARBITRARY transaction (type != 10).")
    off = 0
    header, off = _take(buf, off, header_len)
    nonce, off = _take(buf, off, 4)
    name, _, off = _take_lenpref(buf, off)
    identifier, _, off = _take_lenpref(buf, off)
    method, off = _take(buf, off, 4)
    secret, _, off = _take_lenpref(buf, off)
    compression, off = _take(buf, off, 4)
    pay_count, after_count = _take_u32(buf, off)
    if pay_count != 0:
        raise NotImplementedError("ARBITRARY payments are not supported by this signer.")
    payments = buf[off:after_count]
    off = after_count
    service, off = _take(buf, off, 4)
    is_raw, off = _take(buf, off, 1)
    data_seg, data_body, off = _take_lenpref(buf, off)
    size, off = _take(buf, off, 4)
    metadata, _, off = _take_lenpref(buf, off)
    fee, off = _take(buf, off, 8)
    signature = buf[off:]
    if len(signature) not in (0, SIGNATURE_LEN):
        raise ValueError(f"Unexpected trailing bytes ({len(signature)}); not 0 or 64.")
    return {
        "header": header, "nonce": nonce, "name": name, "identifier": identifier,
        "method": method, "secret": secret, "compression": compression,
        "payments": payments, "service": service, "is_raw": is_raw,
        "data_seg": data_seg, "data_body": data_body, "data_len_prefix": data_seg[:4],
        "size": size, "metadata": metadata, "fee": fee, "signature": signature,
    }


def _arbitrary_to_bytes(f: dict, signature: bytes = b"") -> bytes:
    """Re-serialize ArbitraryTransactionTransformer.toBytes (full wire form)."""
    return (f["header"] + f["nonce"] + f["name"] + f["identifier"] + f["method"]
            + f["secret"] + f["compression"] + f["payments"] + f["service"]
            + f["is_raw"] + f["data_seg"] + f["size"] + f["metadata"] + f["fee"]
            + signature)


def _arbitrary_to_bytes_for_signing(f: dict) -> bytes:
    """ArbitraryTransactionTransformer.toBytesForSigning: drop the dataType byte;
    sign the data hash (data as-is for DATA_HASH, sha256(data) for RAW_DATA)."""
    is_raw = f["is_raw"][0] != 0
    data_for_signing = hashlib.sha256(f["data_body"]).digest() if is_raw else f["data_body"]
    return (f["header"] + f["nonce"] + f["name"] + f["identifier"] + f["method"]
            + f["secret"] + f["compression"] + f["payments"] + f["service"]
            + f["data_len_prefix"] + data_for_signing + f["size"] + f["metadata"]
            + f["fee"])


def sign_arbitrary_transaction(seed: bytes, unsigned_tx_b58: str) -> str:
    buf = b58decode(unsigned_tx_b58.strip())
    # Auto-detect the header length (Qortal 112 / Qortium 48): accept the one
    # whose re-serialized toBytes reproduces the input byte-for-byte.
    f = None
    for hl in _ARB_HEADER_CANDIDATES:
        try:
            cand = _parse_arbitrary(buf, hl)
        except (ValueError, NotImplementedError):
            continue
        if _arbitrary_to_bytes(cand, cand["signature"]) == buf:
            f = cand
            break
    if f is None:
        raise RuntimeError("ARBITRARY round-trip failed for all header lengths; refusing to sign.")
    unsigned_portion = buf[:len(buf) - len(f["signature"])]
    signing_bytes = _arbitrary_to_bytes_for_signing(f)
    signature = sign_message(seed, signing_bytes)
    if not verify_signature(seed_to_public_key(seed), signing_bytes, signature):
        raise RuntimeError("Local self-verification of the signature failed.")
    return b58encode(unsigned_portion + signature)


def sign_transaction(seed: bytes, unsigned_tx_b58: str) -> str:
    """Sign unsigned transaction bytes; return base58 signed bytes.

    For ARBITRARY (type 10) the signing bytes differ from the wire bytes, so
    dispatch to the dedicated path. For other transaction types the base
    transformer signs the unsigned bytes as-is, so signed = message + signature.
    """
    message = b58decode(unsigned_tx_b58.strip())
    if not message:
        raise ValueError("Unsigned transaction bytes are empty.")
    if int.from_bytes(message[:4], "big") == TX_TYPE_ARBITRARY:
        return sign_arbitrary_transaction(seed, unsigned_tx_b58)
    signature = sign_message(seed, message)
    signed = message + signature
    # Self-check: the produced signature must verify against our own pubkey.
    if not verify_signature(seed_to_public_key(seed), message, signature):
        raise RuntimeError("Local self-verification of the signature failed.")
    return b58encode(signed)


def verify_signature(public_key: bytes, message: bytes, signature: bytes) -> bool:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
        return True
    except InvalidSignature:
        return False


# --- Key acquisition helpers (shared by subcommands) ------------------------
def _read_secret_file(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8").strip("\r\n")


def resolve_seed(args) -> bytes:
    """Get the 32-byte seed from whichever key source the user supplied."""
    if getattr(args, "private_key", None):
        return decode_private_key_input(args.private_key)
    if getattr(args, "private_key_file", None):
        return decode_private_key_input(_read_secret_file(args.private_key_file))
    if getattr(args, "accounts_file", None):
        addr = getattr(args, "account_address", None)
        if not addr:
            raise ValueError("--account-address is required with --accounts-file.")
        data = json.loads(Path(args.accounts_file).expanduser().read_text(encoding="utf-8"))
        accts = data if isinstance(data, list) else data.get("accounts", [])
        acct = next((a for a in accts
                     if a.get("accountAddress") == addr or a.get("address") == addr), None)
        if acct is None:
            raise ValueError(f"Account {addr} not found in {args.accounts_file}.")
        field = getattr(args, "account_key_field", "accountPrivateKey")
        if not acct.get(field):
            raise ValueError(f"Account {addr} has no '{field}'.")
        return decode_private_key_input(acct[field])
    if getattr(args, "wallet", None):
        wallet = json.loads(Path(args.wallet).expanduser().read_text(encoding="utf-8"))
        if not isinstance(wallet, dict):
            raise ValueError("Wallet file must contain a JSON object.")
        if args.password_file:
            password = _read_secret_file(args.password_file)
        elif args.password_env:
            password = os.environ.get(args.password_env, "")
            if not password:
                raise ValueError(f"Env var {args.password_env} is empty/unset.")
        else:
            password = getpass.getpass("Wallet password: ")
        return decrypt_wallet_to_seed(wallet, password)
    raise ValueError(
        "No key source. Pass --wallet (+ password) or --private-key / --private-key-file."
    )


def _add_key_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("key source (choose one)")
    g.add_argument("--wallet", help="path to a wallet-backup JSON file")
    g.add_argument("--password-file", help="file containing the wallet password")
    g.add_argument("--password-env", help="env var holding the wallet password")
    g.add_argument("--private-key", help="base58 private key (32- or 64-byte)")
    g.add_argument("--private-key-file", help="file containing a base58 private key")
    g.add_argument("--accounts-file", help="JSON accounts file (e.g. initial-minting-accounts.json)")
    g.add_argument("--account-address", help="account address to select from --accounts-file")
    g.add_argument("--account-key-field", default="accountPrivateKey",
                   help="field in the account record holding the base58 private key")


# --- Subcommands ------------------------------------------------------------
def cmd_address(args) -> int:
    seed = resolve_seed(args)
    print(f"address:    {qortal_address_from_seed(seed)}")
    print(f"public_key: {b58encode(seed_to_public_key(seed))}")
    return 0


def cmd_key(args) -> int:
    seed = resolve_seed(args)
    sys.stderr.write(
        "WARNING: printing the private seed. Redirect to a 0600 file outside any repo.\n"
    )
    print(b58encode(seed))
    return 0


def cmd_sign(args) -> int:
    seed = resolve_seed(args)
    unsigned = args.tx if args.tx else sys.stdin.read()
    unsigned = unsigned.strip()
    if not unsigned:
        raise ValueError("No unsigned transaction bytes (pass --tx or pipe via stdin).")
    print(sign_transaction(seed, unsigned))
    return 0


def cmd_verify(args) -> int:
    signed = (args.tx if args.tx else sys.stdin.read()).strip()
    raw = b58decode(signed)
    if len(raw) <= 64:
        raise ValueError("Signed transaction is too short to contain a signature.")
    message, signature = raw[:-64], raw[-64:]
    public_key = b58decode(args.public_key.strip())
    ok = verify_signature(public_key, message, signature)
    print("VALID" if ok else "INVALID")
    return 0 if ok else 1


def cmd_selftest(_args) -> int:
    # b58 round-trip (non-empty; empty<->"1" is the documented leading-zero edge)
    for sample in (b"\x01", b"\x00\x00\x01\x02", os.urandom(40), os.urandom(64)):
        assert b58decode(b58encode(sample)) == sample, "b58 round-trip failed"
    # deterministic seed -> sign/verify round-trip + tamper rejection
    seed = hashlib.sha256(b"qortal-local-sign-selftest").digest()
    addr = qortal_address_from_seed(seed)
    assert addr.startswith("Q"), f"address should start with Q, got {addr}"
    msg = b"the quick brown fox" * 4
    sig = sign_message(seed, msg)
    pub = seed_to_public_key(seed)
    assert verify_signature(pub, msg, sig), "valid signature rejected"
    assert not verify_signature(pub, msg + b"!", sig), "tampered message accepted"
    # non-ARBITRARY tx (type != 10): signed = message + 64-byte signature
    fake_unsigned = (99).to_bytes(4, "big") + msg
    signed = b58decode(sign_transaction(seed, b58encode(fake_unsigned)))
    assert signed[:-64] == fake_unsigned and len(signed[-64:]) == 64, "signed layout wrong"

    # synthetic ARBITRARY tx: round-trip + signing form drops the dataType byte
    def i32(n: int) -> bytes:
        return n.to_bytes(4, "big")

    def lp(b: bytes) -> bytes:
        return i32(len(b)) + b

    pub2 = seed_to_public_key(seed)
    reference = hashlib.sha512(b"ref").digest()[:64]  # 64-byte reference
    header = i32(TX_TYPE_ARBITRARY) + (1234567890).to_bytes(8, "big") + i32(0) + reference + pub2
    nonce, name, ident = i32(42), lp(b"Qortium"), lp(b"")
    method, secret, comp, payments = i32(0), lp(b""), i32(0), i32(0)
    service, is_raw = i32(200), b"\x00"  # DATA_HASH
    data_seg = lp(hashlib.sha256(b"content").digest())
    size, meta, fee = i32(123), lp(hashlib.sha256(b"m").digest()), (1_000_000).to_bytes(8, "big")
    unsigned = (header + nonce + name + ident + method + secret + comp + payments
                + service + is_raw + data_seg + size + meta + fee)
    f = _parse_arbitrary(unsigned)
    assert _arbitrary_to_bytes(f) == unsigned, "ARBITRARY round-trip failed"
    expected_signing = (header + nonce + name + ident + method + secret + comp
                        + payments + service + data_seg + size + meta + fee)
    assert _arbitrary_to_bytes_for_signing(f) == expected_signing, "ARBITRARY signing form wrong"
    arb_signed = b58decode(sign_transaction(seed, b58encode(unsigned)))
    assert arb_signed[:-64] == unsigned, "ARBITRARY signed should be unsigned+sig"
    assert verify_signature(pub2, expected_signing, arb_signed[-64:]), "ARBITRARY sig invalid"

    # Qortium variant: reference-less 48-byte header, must auto-detect
    q_header = i32(TX_TYPE_ARBITRARY) + (1234567890).to_bytes(8, "big") + i32(0) + pub2
    q_unsigned = (q_header + nonce + name + ident + method + secret + comp + payments
                  + service + is_raw + data_seg + size + meta + fee)
    q_signing = (q_header + nonce + name + ident + method + secret + comp + payments
                 + service + data_seg + size + meta + fee)
    q_signed = b58decode(sign_transaction(seed, b58encode(q_unsigned)))
    assert q_signed[:-64] == q_unsigned, "Qortium ARBITRARY signed should be unsigned+sig"
    assert verify_signature(pub2, q_signing, q_signed[-64:]), "Qortium ARBITRARY sig invalid"
    print(f"selftest OK  (sample address {addr})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline Qortal/Qortium transaction signer (no node contact).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_addr = sub.add_parser("address", help="derive address + public key")
    _add_key_args(p_addr)
    p_addr.set_defaults(func=cmd_address)

    p_key = sub.add_parser("key", help="print the base58 private seed (explicit)")
    _add_key_args(p_key)
    p_key.set_defaults(func=cmd_key)

    p_sign = sub.add_parser("sign", help="sign unsigned tx bytes -> signed tx bytes")
    _add_key_args(p_sign)
    p_sign.add_argument("--tx", help="unsigned transaction bytes (base58); else stdin")
    p_sign.set_defaults(func=cmd_sign)

    p_verify = sub.add_parser("verify", help="verify a signed tx's trailing signature")
    p_verify.add_argument("--tx", help="signed transaction bytes (base58); else stdin")
    p_verify.add_argument("--public-key", required=True, help="base58 public key")
    p_verify.set_defaults(func=cmd_verify)

    p_self = sub.add_parser("selftest", help="offline consistency checks")
    p_self.set_defaults(func=cmd_selftest)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
