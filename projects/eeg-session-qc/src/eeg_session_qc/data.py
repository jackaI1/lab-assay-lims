"""Only the three specified public baseline EDFs are used by the demo."""

import hashlib
import json
import urllib.request
from importlib.resources import files
from pathlib import Path

import mne


def download_demo(directory, manifest=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if manifest is None:
        manifest = json.loads(files("eeg_session_qc").joinpath("sources.json").read_text())
    paths = []
    for entry in manifest:
        path = directory / entry["file"]
        if not path.exists():
            temporary = path.with_suffix(".download")
            try:
                with urllib.request.urlopen(entry["url"], timeout=45) as response:
                    with temporary.open("wb") as output:
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != entry["sha256"]:
                    raise ValueError(f"Public source checksum mismatch: {path.name}")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(
                f"Cached source checksum mismatch: {path.name}; remove it to redownload"
            )
        paths.append(path)
    return paths


def read_edf(path):
    """MNE reads EDF physical units into volts; normalize the public channel names."""
    raw = mne.io.read_raw_edf(path, preload=True, infer_types=True, verbose=False)
    raw.rename_channels(lambda name: name.rstrip(".").capitalize())
    raw.pick("eeg", exclude=[])
    return raw
