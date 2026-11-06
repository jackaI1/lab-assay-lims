"""Command-line interface. Every command works locally except snapshot."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

from .compare import compare_snapshots, render_report
from .lookup import lookup
from .snapshot import build_snapshot, load_snapshot, save_snapshot
from .source import ApiClient, BASE_URL, read_release, utc_now


def parser():
    root = argparse.ArgumentParser(description='CPIC learning project, not clinical decision support.')
    commands = root.add_subparsers(dest='command', required=True)
    api = commands.add_parser('snapshot', help='Download all tracked public API rows into a dated snapshot')
    api.add_argument('--output', type=Path, help='New filename; default uses current UTC timestamp')
    release = commands.add_parser('import-release', help='Import an official CPIC .sql.gz export without executing SQL')
    release.add_argument('dump', type=Path)
    release.add_argument('--release-tag', required=True)
    release.add_argument('--source-url', required=True)
    release.add_argument('--output', type=Path, required=True)
    diff = commands.add_parser('compare', help='Write a source-linked Markdown change report')
    diff.add_argument('before', type=Path)
    diff.add_argument('after', type=Path)
    diff.add_argument('--output', type=Path)
    diff.add_argument('--json', action='store_true', help='Emit structured changes instead of Markdown')
    query = commands.add_parser('lookup', help='Exact phenotype lookup from a saved snapshot')
    query.add_argument('snapshot', type=Path)
    query.add_argument('--drug', required=True, help='Exact CPIC drug name or drug ID')
    query.add_argument('--phenotype', action='append', required=True, metavar='GENE=PHENOTYPE')
    query.add_argument('--population', help='Exact CPIC population, if required')
    stats = commands.add_parser('stats', help='Print reproducible counts from a saved snapshot')
    stats.add_argument('snapshot', type=Path)
    return root


def _write_or_print(text, output):
    if output:
        with output.open('x', encoding='utf-8') as stream:
            stream.write(text.rstrip('\n') + '\n')
        print(str(output))
    else:
        print(text)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command in {'snapshot', 'import-release'}:
            started = utc_now()
            if args.command == 'snapshot':
                data, requests = ApiClient().fetch_all()
                source = {'kind': 'api', 'url': BASE_URL, 'requests': requests}
                output = args.output or Path('cpic-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
            else:
                if not args.source_url.startswith('https://files.cpicpgx.org/'):
                    raise ValueError('release source must be an official files.cpicpgx.org HTTPS URL')
                data = read_release(args.dump)
                with args.dump.open('rb') as stream:
                    checksum = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(65536), b''):
                        checksum.update(chunk)
                source = {'kind': 'release-export', 'url': args.source_url,
                          'release_tag': args.release_tag, 'download_sha256': checksum.hexdigest()}
                output = args.output
            save_snapshot(build_snapshot(data, source, started), output)
            print(str(output))
        elif args.command == 'compare':
            old, new = load_snapshot(args.before), load_snapshot(args.after)
            text = (json.dumps(compare_snapshots(old, new), indent=2, ensure_ascii=False)
                    if args.json else render_report(old, new))
            _write_or_print(text, args.output)
        elif args.command == 'lookup':
            phenotypes = {}
            for item in args.phenotype:
                gene, separator, phenotype = item.partition('=')
                gene, phenotype = gene.strip(), phenotype.strip()
                if not separator or not gene or not phenotype or gene.casefold() in {g.casefold() for g in phenotypes}:
                    raise ValueError('each phenotype must be a unique non-empty GENE=PHENOTYPE')
                phenotypes[gene] = phenotype
            result = lookup(load_snapshot(args.snapshot), args.drug, phenotypes, args.population)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == 'stats':
            s = load_snapshot(args.snapshot)
            print(json.dumps({'source': s['source']['kind'], 'captured_at': s['captured_at'],
                              'pair_rows': len(s['tables']['pair']),
                              'active_pairs': sum(not p['removed'] and p['cpiclevel'] != 'Retired' for p in s['tables']['pair']),
                              'recommendation_rows': len(s['tables']['recommendation']),
                              'guidelines': len(s['tables']['guideline']),
                              'drugs': len(s['tables']['drug']),
                              'guideline_publications': len(s['tables']['publication'])}, indent=2))
        return 0
    except (OSError, URLError, ValueError, KeyError, TypeError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2
