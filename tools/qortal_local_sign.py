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


def sign_transaction(seed: bytes, unsigned_tx_b58: str) -> str:
    """Sign unsigned transaction bytes; return base58 signed bytes.

    signed = message + 64-byte signature, exactly as the node returns.
    """
    message = b58decode(unsigned_tx_b58.strip())
    if not message:
        raise ValueError("Unsigned transaction bytes are empty.")
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
    # signed tx = message + 64-byte signature, signature trails
    fake_unsigned = b58encode(msg)
    signed = b58decode(sign_transaction(seed, fake_unsigned))
    assert signed[:-64] == msg and len(signed[-64:]) == 64, "signed layout wrong"
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
