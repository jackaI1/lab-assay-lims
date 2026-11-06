"""Only versioned, allowlisted public MIT-BIH files can be downloaded."""
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
from urllib.request import urlopen


def load_manifest():
    return json.loads(files('ecg_lifecycle').joinpath('manifest.json').read_text())


def verify_file(path, expected):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
        raise ValueError(f'checksum mismatch: {Path(path).name}; remove the corrupt cache file and retry')


def ensure_record(record, cache=None):
    manifest = load_manifest()
    if record not in manifest['records']:
        raise ValueError(f'unsupported record: {record}; choose 100, 201 or 203')
    root = Path(cache or os.environ.get('ECG_DATA_DIR', '.cache/mitdb'))
    root.mkdir(parents=True, exist_ok=True)
    for extension, digest in manifest['records'][record].items():
        path = root / f'{record}.{extension}'
        if path.exists():
            verify_file(path, digest)
            continue
        temporary = path.with_suffix(path.suffix + '.part')
        try:
            with urlopen(manifest['base_url'] + path.name, timeout=60) as response:
                temporary.write_bytes(response.read(10_000_001))
            verify_file(temporary, digest)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return root / record
