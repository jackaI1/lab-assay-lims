#!/usr/bin/env python3
"""Download checksum-locked public reads and retain matching raw read pairs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def download(url, target, md5):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and digest(target, 'md5') == md5:
        return target
    part = target.with_suffix(target.suffix + '.part')
    try:
        with urllib.request.urlopen(url, timeout=120) as src, open(part, 'wb') as dst:
            while block := src.read(1024 * 1024):
                dst.write(block)
        if digest(part, 'md5') != md5:
            raise ValueError(f'Checksum mismatch: {target.name}')
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return target


def records(path):
    with gzip.open(path, 'rt') as f:
        while header := f.readline():
            seq, plus, qual = (f.readline().rstrip('\n') for _ in range(3))
            if not header.startswith('@') or not plus.startswith('+') or not seq or len(seq) != len(qual):
                raise ValueError(f'Malformed FASTQ: {path}')
            if any(ord(q) < 33 or ord(q) > 74 for q in qual):
                raise ValueError('Expected Phred+33 quality values in range 0..41')
            yield header.rstrip('\n'), seq, plus, qual


def read_id(header):
    return header.split()[0].removesuffix('/1').removesuffix('/2')


def subset_pair(forward, reverse, outputs, limit):
    from contextlib import ExitStack
    from itertools import zip_longest
    n = 0
    with ExitStack() as stack:
        out = [stack.enter_context(gzip.GzipFile(filename='', mode='wb', fileobj=stack.enter_context(open(p, 'wb')), mtime=0)) for p in outputs]
        for a, b in zip_longest(records(forward), records(reverse)):
            if a is None or b is None or read_id(a[0]) != read_id(b[0]):
                raise ValueError('FASTQ mates do not match')
            for writer, rec in zip(out, (a, b)):
                writer.write(('\n'.join(rec) + '\n').encode())
            n += 1
            if n >= limit:
                break
    if not n:
        raise ValueError('Empty read pair')
    return n


def prepare(limit, output):
    if limit < 1:
        raise ValueError('pairs must be positive')
    source = json.loads(Path('data/sources.json').read_text())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows, provenance = [], []
    # Bound concurrent transfers and their buffers; each target has one owner.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {sample['sample']: [pool.submit(download, u,
                   Path('data/cache') / f"{sample['run']}_{i+1}.fastq.gz", md5)
                   for i, (u, md5) in enumerate(zip(sample['urls'], sample['md5']))]
                   for sample in source['samples']}
        downloaded = {name: [f.result() for f in jobs] for name, jobs in futures.items()}
    for sample in source['samples']:
        name = sample['sample']
        paths = downloaded[name]
        targets = [output / f'{name}_R{i+1}.fastq.gz' for i in range(2)]
        count = subset_pair(*paths, targets, limit)
        rows.append([name, sample['type'], sample['run'], *(str(p.resolve()) for p in targets)])
        provenance.append({**sample, 'pairs_retained': count, 'selection': 'first N pairs, no quality-based selection',
                           'subset_sha256': [digest(p) for p in targets]})
        print(f'{name}: {count} raw pairs retained', flush=True)
    with open(output / 'samples.tsv', 'w') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(['sample', 'type', 'run', 'forward', 'reverse'])
        writer.writerows(rows)
    (output / 'provenance.json').write_text(json.dumps({'study': source['study'], 'samples': provenance}, indent=2)+'\n')
    tax = source['taxonomy']
    download(tax['url'], 'data/reference/rdp_train_set_18.fa.gz', tax['md5'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pairs', type=int, default=12000)
    parser.add_argument('--output', default='data/raw')
    args = parser.parse_args()
    prepare(args.pairs, args.output)
