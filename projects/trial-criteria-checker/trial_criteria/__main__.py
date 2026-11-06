"""Run with python3 -m trial_criteria --help. No installation required."""
import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from .api import fetch_studies
from .benchmark import benchmark
from .report import build_report, render_html, render_markdown


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Source-linked public trial criteria. Fictional records only.')
    sub = parser.add_subparsers(dest='command',required=True)
    fetch = sub.add_parser('fetch',help='Download recruiting records from ClinicalTrials.gov')
    fetch.add_argument('--condition',default='')
    fetch.add_argument('--ids',nargs='+')
    fetch.add_argument('--limit',type=int,default=10)
    fetch.add_argument('--output',default='data/latest.json')
    measure = sub.add_parser('benchmark',help='Score parsing against published labels')
    measure.add_argument('--snapshot',default='data/studies.json')
    measure.add_argument('--labels',default='data/labels.json')
    measure.add_argument('--output',default='reports/metrics.json')
    report = sub.add_parser('report',help='Write portable HTML and JSON for a fictional patient')
    report.add_argument('--snapshot',default='data/studies.json')
    report.add_argument('--patient',default='examples/fictional_patient.json')
    report.add_argument('--labels',help='Optionally include benchmark on the same snapshot')
    report.add_argument('--output',default='reports/fictional_patient')
    args = parser.parse_args()
    try:
        if args.command == 'fetch':
            result = fetch_studies(args.condition,args.limit,args.ids)
            write(args.output,result)
            print(f"Saved {len(result['studies'])} public recruiting records to {args.output}")
        elif args.command == 'benchmark':
            result = benchmark(read(args.snapshot),read(args.labels))
            write(args.output,result)
            print(json.dumps({k:v for k,v in result.items() if k not in ('missed','incorrect')},indent=2))
        else:
            result = build_report(read(args.snapshot),read(args.patient))
            if args.labels:
                result['benchmark'] = benchmark(read(args.snapshot),read(args.labels))
            base = Path(args.output)
            write(base.with_suffix('.json'),result)
            base.with_suffix('.html').write_text(render_html(result),encoding='utf-8')
            base.with_suffix('.md').write_text(render_markdown(result),encoding='utf-8')
            print(json.dumps(result['counts'])+'; HTML: '+str(base.with_suffix('.html')))
    except (OSError,ValueError,KeyError,TypeError,URLError) as exc:
        parser.exit(2,'Error: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
