"""Public ISIC source provenance and checksum-verified, bounded downloads."""

import hashlib
import json
import re
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://api.isic-archive.com/api/v2/"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/"


def read_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "clinical-image-quality-gate/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        blob = response.read(20_000_001)
    if len(blob) > 20_000_000:
        raise ValueError("source exceeds download size limit")
    return blob


def source_record(image: dict) -> dict:
    if not image["public"] or image["copyright_license"] != "CC-BY-NC":
        raise ValueError("only public, explicitly CC-BY-NC HAM10000 images are supported")
    clinical = image["metadata"]["clinical"]
    diagnosis = clinical["diagnosis_3"]
    if diagnosis not in ("Nevus", "Melanoma, NOS") or not clinical.get("lesion_id"):
        raise ValueError("source needs a supported diagnosis and lesion group")
    return {
        "isic_id": image["isic_id"],
        "lesion_id": clinical["lesion_id"],
        "label": int(diagnosis == "Melanoma, NOS"),
        "diagnosis": diagnosis,
        "url": image["files"]["full"]["url"],
        "license": "CC-BY-NC-4.0",
        "license_url": LICENSE_URL,
        "attribution": image["attribution"],
        "source": API + "images/" + image["isic_id"] + "/",
        "collection": 212,
    }


def load_manifest(path: str | Path) -> list[dict]:
    records = json.loads(Path(path).read_text())
    if not records:
        raise ValueError("empty manifest")
    ids, lesions, hashes = set(), set(), set()
    for r in records:
        if r["isic_id"] in ids or r["lesion_id"] in lesions or r["sha256"] in hashes:
            raise ValueError("duplicate source, lesion or image checksum in manifest")
        ids.add(r["isic_id"])
        lesions.add(r["lesion_id"])
        hashes.add(r["sha256"])
        if not re.fullmatch(r"ISIC_\d{7}", r["isic_id"]):
            raise ValueError("invalid image ID")
        if not re.fullmatch(r"[a-f0-9]{64}", r["sha256"]):
            raise ValueError("invalid checksum")
        if r["license"] != "CC-BY-NC-4.0" or r["collection"] != 212:
            raise ValueError("unexpected licence or collection")
        if r["label"] not in (0, 1):
            raise ValueError("unsupported label")
        u = urllib.parse.urlparse(r["url"])
        if u.scheme != "https" or u.hostname != "isic-archive.s3.amazonaws.com":
            raise ValueError("unexpected image host")
    return records


def download(records: list[dict], directory: str | Path) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    def one(r):
        path = directory / (r["isic_id"] + ".jpg")
        blob = path.read_bytes() if path.exists() else read_url(r["url"])
        if hashlib.sha256(blob).hexdigest() != r["sha256"]:
            raise ValueError(f"checksum mismatch for {r['isic_id']}; remove cache and retry")
        if not path.exists():
            tmp = path.with_suffix(".tmp")
            try:
                tmp.write_bytes(blob)
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(one, records))


def freeze_manifest(path: str | Path, per_class: int = 180) -> None:
    """Explicit source-refresh operation. Normal runs always use the checked-in snapshot."""
    if per_class < 5:
        raise ValueError("at least 5 unique lesions per class are required for the split")
    path = Path(path)
    records, lesions = [], set()
    for diagnosis in ("Nevus", "Melanoma, NOS"):
        query = urllib.parse.urlencode(
            {"collections": 212, "limit": 100, "query": f'diagnosis_3:"{diagnosis}"'}
        )
        url, count = API + "images/search/?" + query, 0
        while url and count < per_class:
            page = json.loads(read_url(url))
            for image in page["results"]:
                r = source_record(image)
                if r["lesion_id"] in lesions:
                    continue
                lesions.add(r["lesion_id"])
                records.append(r)
                count += 1
                if count == per_class:
                    break
            url = page["next"]
        if count != per_class:
            raise ValueError("not enough unique lesions to create the requested manifest")
    directory = Path(path).parent / "images"
    directory.mkdir(parents=True, exist_ok=True)
    for r in records:
        blob = read_url(r["url"])
        r["sha256"] = hashlib.sha256(blob).hexdigest()
        (directory / (r["isic_id"] + ".jpg")).write_bytes(blob)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=".manifest-", suffix=".json", delete=False
    ) as candidate:
        temporary = Path(candidate.name)
    try:
        temporary.write_text(json.dumps(records, indent=2) + "\n")
        load_manifest(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
