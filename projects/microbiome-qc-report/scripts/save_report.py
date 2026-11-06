#!/usr/bin/env python3
"""Save the small, auditable report outputs without disposable filtered reads."""
import argparse
from pathlib import Path
import shutil

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('source',type=Path)
parser.add_argument('destination',type=Path)
a=parser.parse_args()
a.destination.mkdir(parents=True,exist_ok=True)
allowed={'.tsv','.json','.txt','.html','.md','.png','.fasta','.rds'}
for p in a.source.iterdir():
    if p.is_file() and p.suffix in allowed:
        shutil.copy2(p,a.destination/p.name)
print(f'Saved report and tables to {a.destination}')
