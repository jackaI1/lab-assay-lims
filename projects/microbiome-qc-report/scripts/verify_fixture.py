#!/usr/bin/env python3
import json
from pathlib import Path
from prepare import digest

root=Path('tests/fixture')
for name, expected in json.loads((root/'sha256.json').read_text()).items():
    if digest(root/name)!=expected:
        raise SystemExit(f'Fixture checksum mismatch: {name}')
print('All public fixture checksums match')
