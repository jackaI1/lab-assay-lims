"""Verified public downloads and the publisher's whole-image partitions."""

import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

import numpy as np
from PIL import Image
from skimage.measure import label
import tifffile


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("Unsafe archive path")
        for entry in z.infolist():
            if not entry.filename.startswith("__MACOSX/"):
                z.extract(entry, destination)


def download_dataset(root, sources):
    root = Path(root)
    manifest = json.loads(Path(sources).read_text())
    archives = root / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    for name, spec in manifest["archives"].items():
        path = archives / f"{name}.zip"
        if not path.exists():
            partial = path.with_suffix(".partial")
            try:
                urllib.request.urlretrieve(spec["url"], partial)
                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
        if sha256(path) != spec["sha256"]:
            raise ValueError(
                f"SHA256 mismatch: {path}; remove corrupt file and download again"
            )
        safe_extract(path, root)
    (root / "download_provenance.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return manifest


def decode_mask(mask):
    # Publisher's decoder uses channel 0 and equal-valued connected regions.
    first = np.asarray(mask)
    if first.ndim == 3:
        first = first[:, :, 0]
    if first.ndim != 2:
        raise ValueError("Expected a 2D mask or RGB annotation")
    return label(first, background=0, connectivity=2).astype(np.int32)


def verify_download(root):
    """Reject changed archives or extracted members, including split metadata."""
    root = Path(root)
    manifest = json.loads((root / "download_provenance.json").read_text())
    for name, spec in manifest["archives"].items():
        archive = root / "archives" / f"{name}.zip"
        if sha256(archive) != spec["sha256"]:
            raise ValueError(f"SHA256 mismatch: {archive}")
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if entry.is_dir() or entry.filename.startswith("__MACOSX/"):
                    continue
                target = (root / entry.filename).resolve()
                if not target.is_relative_to(root.resolve()):
                    raise ValueError("Unsafe archive path")
                with z.open(entry) as member:
                    expected = hashlib.file_digest(member, "sha256").hexdigest()
                if not target.is_file() or sha256(target) != expected:
                    raise ValueError(f"Extracted data changed: {entry.filename}")
    return manifest


def validate_splits(splits, available):
    seen = set()
    for name in ("training", "validation", "test"):
        members = splits[name]
        if not members or len(set(members)) != len(members):
            raise ValueError(f"Empty or duplicate partition: {name}")
        if seen.intersection(members):
            raise ValueError("Whole-image partitions overlap")
        if not set(members).issubset(available):
            raise ValueError(f"Missing image/mask pair in {name}")
        seen.update(members)


def load_splits(root):
    root = Path(root)
    splits = {
        name: [
            Path(line.strip()).stem
            for line in (root / "metadata" / f"{name}.txt").read_text().splitlines()
            if line.strip()
        ]
        for name in ("training", "validation", "test")
    }
    available = {p.stem for p in (root / "images").glob("*.tif")} & {
        p.stem for p in (root / "masks").glob("*.png")
    }
    validate_splits(splits, available)
    return splits


def load_pair(root, stem):
    root = Path(root)
    image = tifffile.imread(root / "images" / f"{stem}.tif")
    with Image.open(root / "masks" / f"{stem}.png") as mask:
        truth = decode_mask(np.asarray(mask))
    if image.ndim != 2 or image.shape != truth.shape:
        raise ValueError(f"Image and annotation shape mismatch: {stem}")
    return image, truth
