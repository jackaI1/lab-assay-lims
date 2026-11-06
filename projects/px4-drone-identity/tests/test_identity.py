import os
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from drone_identity.identity import Authority, IdentityError, SoftwareKeyStore, provision


def test_provisioned_certificate_proves_possession_and_hides_private_api(tmp_path):
    provision(tmp_path)
    store = SoftwareKeyStore(tmp_path / 'pilot')
    cert = x509.load_pem_x509_certificate(store.certificate())
    assert isinstance(cert.public_key(), Ed25519PublicKey)
    cert.public_key().verify(store.sign(b'challenge'), b'challenge')
    with pytest.raises(InvalidSignature):
        cert.public_key().verify(store.sign(b'challenge'), b'different')
    assert Authority(tmp_path).validate(store.certificate(), 'client') == 'pilot'
    assert os.stat(tmp_path / 'pilot' / 'key.pem').st_mode & 0o777 == 0o600
    assert os.stat(tmp_path / 'pilot').st_mode & 0o777 == 0o700


@pytest.mark.parametrize('name,reason', [('expired', 'expired'), ('observer', None), ('vehicle', 'purpose')])
def test_certificate_purpose_and_validity(tmp_path, name, reason):
    provision(tmp_path)
    cert = SoftwareKeyStore(tmp_path / name).certificate()
    if reason:
        with pytest.raises(IdentityError, match=reason):
            Authority(tmp_path).validate(cert, 'client')
    else:
        assert Authority(tmp_path).validate(cert, 'client') == 'observer'


def test_revocation_is_checked_on_every_use(tmp_path):
    provision(tmp_path)
    authority = Authority(tmp_path)
    cert = SoftwareKeyStore(tmp_path / 'pilot').certificate()
    assert authority.validate(cert, 'client') == 'pilot'
    authority.revoke(cert)
    with pytest.raises(IdentityError, match='revoked'):
        authority.validate(cert, 'client')


def test_wrong_issuer_and_missing_revocation_store_fail_closed(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    provision(a)
    provision(b)
    with pytest.raises(IdentityError, match='issuer'):
        Authority(a).validate(SoftwareKeyStore(b / 'pilot').certificate(), 'client')
    (a / 'revoked.json').unlink()
    with pytest.raises(IdentityError, match='revocation'):
        Authority(a).validate(SoftwareKeyStore(a / 'pilot').certificate(), 'client')


def test_expiry_is_rechecked_after_session_start(tmp_path):
    provision(tmp_path)
    cert = SoftwareKeyStore(tmp_path / 'pilot').certificate()
    with pytest.raises(IdentityError, match='expired'):
        Authority(tmp_path).validate(cert, 'client', now=datetime.now(timezone.utc) + timedelta(days=3))


def test_provision_never_overwrites_an_existing_identity(tmp_path):
    provision(tmp_path)
    original = (tmp_path / 'pilot' / 'key.pem').read_bytes()
    with pytest.raises(FileExistsError):
        provision(tmp_path)
    assert (tmp_path / 'pilot' / 'key.pem').read_bytes() == original
