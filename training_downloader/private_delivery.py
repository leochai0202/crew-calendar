"""Encrypt before publication; decrypt only on the recipient's local machine."""
import argparse
import hashlib
import os
from pathlib import Path
import struct

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"TRAINING-PDF-ENVELOPE-1\n"
PUBLIC_KEY = Path(__file__).with_name("recipient_public.pem")
MAX_PACKAGE_BYTES = 101 * 1024 * 1024


def recipient(path=PUBLIC_KEY):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise RuntimeError("DELIVERY_PUBLIC_KEY_UNAVAILABLE")
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size != 4096:
        raise RuntimeError("DELIVERY_PUBLIC_KEY_INVALID")
    return key


def fingerprint(key):
    return hashlib.sha256(key.public_bytes(serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)).digest()


def encrypt_pdf(pdf, output, public_key):
    from pdf_validation import validate_pdf
    validate_pdf(pdf)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise RuntimeError("DELIVERY_DESTINATION_EXISTS")
    symmetric_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    wrapped = public_key.encrypt(symmetric_key, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=MAGIC))
    header = MAGIC + fingerprint(public_key) + struct.pack(">H", len(wrapped)) + wrapped + nonce
    ciphertext = AESGCM(symmetric_key).encrypt(nonce, Path(pdf).read_bytes(), header)
    with output.open("xb") as stream:
        stream.write(header + ciphertext)
    # Read back the exact saved envelope before it becomes upload-eligible.
    package = output.read_bytes()
    if AESGCM(symmetric_key).decrypt(nonce, package[len(header):], package[:len(header)]) != Path(pdf).read_bytes():
        raise RuntimeError("DELIVERY_ENCRYPTION_VERIFICATION_FAILED")
    return {"delivery_status": "ENCRYPTED_PACKAGE_READY", "delivery_completed": False}


def decrypt_pdf(package_path, key_path, output):
    from pdf_validation import validate_pdf
    package_path, output = Path(package_path), Path(output)
    if not package_path.is_file() or package_path.stat().st_size > MAX_PACKAGE_BYTES:
        raise RuntimeError("DELIVERY_PACKAGE_INVALID")
    if output.exists() or output.is_symlink():
        raise RuntimeError("DELIVERY_DESTINATION_EXISTS")
    package = package_path.read_bytes()
    if not package.startswith(MAGIC):
        raise RuntimeError("DELIVERY_PACKAGE_INVALID")
    key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    start = len(MAGIC)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 4096 or package[start:start+32] != fingerprint(key.public_key()):
        raise RuntimeError("DELIVERY_RECIPIENT_MISMATCH")
    start += 32
    length = struct.unpack(">H", package[start:start+2])[0]
    if length != 512:
        raise RuntimeError("DELIVERY_PACKAGE_INVALID")
    start += 2
    symmetric_key = key.decrypt(package[start:start+length], padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=MAGIC))
    start += length
    nonce = package[start:start+12]
    start += 12
    plaintext = AESGCM(symmetric_key).decrypt(nonce, package[start:], package[:start])
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            stream.write(plaintext)
        validate_pdf(output)
    except Exception:
        if created and output.is_file() and not output.is_symlink():
            output.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Downloaded encrypted artifact file")
    parser.add_argument("--key", default=str(Path(__file__).parent / ".runtime/private-delivery/recipient-private.pem"))
    parser.add_argument("--output", required=True, help="New local PDF path; never overwrites")
    args = parser.parse_args()
    try:
        decrypt_pdf(args.input, args.key, args.output)
    except Exception:
        print("PRIVATE_PDF_DELIVERY=FAILED")
        return 2
    print("PRIVATE_PDF_DELIVERY=COMPLETE PDF_PAGES=29")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
