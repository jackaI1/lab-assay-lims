"""Disposable local certificate provisioning and mutual TLS contexts."""
import hashlib
import ipaddress
import json
import os
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def fingerprint(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


def provision(directory: Path) -> None:
    # Refuse reuse so a second invocation cannot silently replace trust anchors.
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SITL demo CA")])
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=7))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))
    (directory / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    for role in ("companion", "controller", "unlisted"):
        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, role)])
        builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(name)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=2))
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                   .add_extension(x509.ExtendedKeyUsage([
                       ExtendedKeyUsageOID.SERVER_AUTH if role == "companion"
                       else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False))
        if role == "companion":
            builder = builder.add_extension(x509.SubjectAlternativeName([
                x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
        cert = builder.sign(ca_key, hashes.SHA256())
        path = directory / f"{role}.key"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(key.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        (directory / f"{role}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        if role == "controller":
            (directory / "controllers.json").write_text(json.dumps([
                fingerprint(cert.public_bytes(serialization.Encoding.DER))]) + "\n")
    # The CA private key is deliberately never written to disk.


def context(directory: Path, role: str, *, server: bool = False) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH if server else ssl.Purpose.SERVER_AUTH,
                                     cafile=str(directory / "ca.pem"))
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_cert_chain(directory / f"{role}.pem", directory / f"{role}.key")
    return ctx
