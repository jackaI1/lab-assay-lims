import subprocess
import sys

from drone_identity.identity import Authority, SoftwareKeyStore


def test_cli_provisions_real_certificates_and_refuses_overwrite(tmp_path):
    target = tmp_path / 'store'
    result = subprocess.run([sys.executable, '-m', 'drone_identity.cli', 'provision', '--store', str(target)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert Authority(target).validate(SoftwareKeyStore(target / 'pilot').certificate(), 'client') == 'pilot'
    again = subprocess.run([sys.executable, '-m', 'drone_identity.cli', 'provision', '--store', str(target)],
                           capture_output=True, text=True)
    assert again.returncode != 0
    assert 'empty' in again.stderr
