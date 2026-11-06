import argparse
import sys
from .evaluate import WARNING, evaluate, write_json


def main():
    parser = argparse.ArgumentParser(description=WARNING)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('evaluate', help='download and evaluate public MIT-BIH demonstration records')
    run.add_argument('--records', nargs='+', default=['100', '201', '203'])
    run.add_argument('--cache', default=None)
    run.add_argument('--output', default='build/benchmark.json')
    args = parser.parse_args()
    try:
        report = evaluate(args.records, args.cache)
        write_json(args.output, report)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Evaluation failed: {error}\n')
    print(WARNING)
    for record, row in report['records'].items():
        print(f"{record}: QRS sensitivity={row['qrs']['sensitivity']:.4f}, "
              f"PPV={row['qrs']['ppv']:.4f}; windows={row['window_counts']}")
    print(f'Results: {args.output}')


if __name__ == '__main__':
    main()
