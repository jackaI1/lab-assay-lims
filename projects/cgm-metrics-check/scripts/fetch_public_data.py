"""Fetch only the selected public CSV using ZIP byte ranges, never meal photos.

Run after installing the fetch extra. The source's units come from its public
column dictionary. No names, demographics, photos or other series are retained.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

from remotezip import RemoteZip

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://physionet.org/files/cgmacros/1.0.0/CGMacros_dateshifted365.zip'
MEMBER = 'CGMacros/CGMacros-001/CGMacros-001.csv'
SOURCE_SHA256 = '64cde6f844a1ac43ac7802ff2a1b793df88abced4db55dcb016ff74a952b4f8f'


def normalize(raw: bytes) -> bytes:
    """Select published timestamp and first glucose series by column position.

    UTC is a placeholder: the date-shifted source does not specify a timezone.
    No additional interpolation, rounding or resampling is performed.
    """
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('public source checksum changed; inspect before updating the pin')
    reader = csv.reader(io.StringIO(raw.decode('utf-8-sig')))
    next(reader)
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(['timestamp', 'glucose', 'unit'])
    for row in reader:
        if not row[2].strip():
            continue
        timestamp = datetime.fromisoformat(row[1]).replace(tzinfo=timezone.utc)
        writer.writerow([timestamp.isoformat(), row[2], 'mg/dL'])
    return output.getvalue().encode('utf-8')


def main():
    with RemoteZip(URL) as archive:
        raw = archive.read(MEMBER)
    normalized = normalize(raw)
    target = ROOT / 'data/cgmacros_001.csv'
    target.write_bytes(normalized)
    manifest = {
        'dataset': 'CGMacros version 1.0.0', 'doi': 'https://doi.org/10.13026/3z8q-x658',
        'url': URL, 'member': MEMBER, 'source_member_sha256': SOURCE_SHA256,
        'normalized_sha256': hashlib.sha256(normalized).hexdigest(),
        'timestamp_column_index': 1, 'glucose_column_index': 2,
        'unit': 'mg/dL', 'cadence_minutes': 1,
        'timezone_assumption': 'UTC placeholder; source timezone unknown, dates already shifted by publisher',
        'processing': 'Published processed minute-resolution series. Original sensor wear and upstream filling cannot be audited from this CSV. No further filling or resampling.',
        'license': 'CC BY-NC-SA 4.0',
        'license_url': 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
        'attribution': 'Gutierrez-Osuna, R., Kerr, D., Mortazavi, B., & Das, A. (2025). CGMacros: a scientific dataset for personalized nutrition and diet monitoring (version 1.0.0). PhysioNet.',
    }
    (ROOT / 'data/provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Fetched {len(normalized.splitlines()) - 1} published rows; SHA256 {manifest["normalized_sha256"]}')


if __name__ == '__main__':
    main()
