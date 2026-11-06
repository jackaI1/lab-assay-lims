"""Local test CA and a deliberately software-only key-store boundary."""
from __future__ import annotations

import json
import os
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


class IdentityError(ValueError):
    pass


class KeyStore(Protocol):
    """Hardware adapters could implement these operations without exporting a key."""
    def certificate(self) -> bytes: ...
    def sign(self, challenge: bytes) -> bytes: ...
    def tls_context(self, ca_file: Path, *, server: bool = False) -> ssl.SSLContext: ...


def _private_write(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


class SoftwareKeyStore:
    """File permissions are the only protection; this is not a secure element."""
    def __init__(self, path: Path):
        self._path = Path(path)

    def certificate(self) -> bytes:
        return (self._path / 'cert.pem').read_bytes()

    def sign(self, challenge: bytes) -> bytes:
        key = serialization.load_pem_private_key((self._path / 'key.pem').read_bytes(), None)
        return key.sign(challenge)

    def tls_context(self, ca_file: Path, *, server: bool = False) -> ssl.SSLContext:
        purpose = ssl.Purpose.CLIENT_AUTH if server else ssl.Purpose.SERVER_AUTH
        context = ssl.create_default_context(purpose, cafile=str(ca_file))
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.verify_mode = ssl.CERT_REQUIRED
        # Python/OpenSSL needs a PEM file. A real hardware adapter would need a
        # provider/PKCS#11 integration, not this implementation.
        context.load_cert_chain(self._path / 'cert.pem', self._path / 'key.pem')
        return context


class Authority:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.ca = x509.load_pem_x509_certificate((self.root / 'ca.pem').read_bytes())

    def validate(self, pem: bytes, purpose: str, *, now: datetime | None = None) -> str:
        cert = x509.load_pem_x509_certificate(pem)
        try:
            cert.verify_directly_issued_by(self.ca)
        except (ValueError, TypeError, InvalidSignature) as exc:
            raise IdentityError('untrusted issuer') from exc
        now = now or datetime.now(timezone.utc)
        if not cert.not_valid_before_utc <= now < cert.not_valid_after_utc:
            raise IdentityError('expired or not yet valid certificate')
        try:
            revoked = json.loads((self.root / 'revoked.json').read_text())
            if not isinstance(revoked, list) or any(not isinstance(s, int) for s in revoked):
                raise ValueError('invalid revocation list')
        except (OSError, ValueError) as exc:
            raise IdentityError('unavailable revocation store') from exc
        if cert.serial_number in revoked:
            raise IdentityError('revoked certificate')
        expected = ExtendedKeyUsageOID.SERVER_AUTH if purpose == 'server' else ExtendedKeyUsageOID.CLIENT_AUTH
        try:
            if expected not in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
                raise IdentityError('wrong certificate purpose')
            role, = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
        except (x509.ExtensionNotFound, ValueError) as exc:
            raise IdentityError('missing purpose or role') from exc
        allowed = {'vehicle'} if purpose == 'server' else {'pilot', 'observer'}
        if role.value not in allowed:
            raise IdentityError('wrong certificate purpose or role')
        return role.value

    def revoke(self, pem: bytes) -> None:
        cert = x509.load_pem_x509_certificate(pem)
        revoked = json.loads((self.root / 'revoked.json').read_text())
        revoked.append(cert.serial_number)
        # Single local administrator; atomic replacement lets active sessions
        # recheck revocation without ever reading a partially written document.
        pending = self.root / 'revoked.pending'
        _private_write(pending, json.dumps(sorted(set(revoked))).encode())
        pending.replace(self.root / 'revoked.json')


def provision(root: Path) -> None:
    """Generate fresh disposable Ed25519 identities; never overwrite a store."""
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise FileExistsError('identity directory must be empty')
    root.chmod(0o700)
    ca_key = Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Simulation test CA')])
    ca = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=7))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
          .sign(ca_key, algorithm=None))
    _private_write(root / 'ca.pem', ca.public_bytes(serialization.Encoding.PEM))
    _private_write(root / 'ca-key.pem', ca_key.private_bytes(serialization.Encoding.PEM,
                   serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    _private_write(root / 'revoked.json', b'[]')
    for name, role in [('vehicle', 'vehicle'), ('pilot', 'pilot'), ('observer', 'observer'), ('expired', 'pilot')]:
        path = root / name
        path.mkdir(mode=0o700)
        key = Ed25519PrivateKey.generate()
        end = now - timedelta(hours=1) if name == 'expired' else now + timedelta(days=2)
        leaf_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name),
                                 x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, role)])
        cert = (x509.CertificateBuilder().subject_name(leaf_subject).issuer_name(ca.subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1)).not_valid_after(end)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
                .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), True)
                .add_extension(x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.SERVER_AUTH if role == 'vehicle' else ExtendedKeyUsageOID.CLIENT_AUTH]), False)
                .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False)
                .sign(ca_key, algorithm=None))
        _private_write(path / 'key.pem', key.private_bytes(serialization.Encoding.PEM,
                       serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        _private_write(path / 'cert.pem', cert.public_bytes(serialization.Encoding.PEM))
