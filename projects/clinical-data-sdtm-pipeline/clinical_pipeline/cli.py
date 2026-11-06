"""Command-line entry point."""
import argparse
import json
from pathlib import Path
from .pipeline import run
from .synthetic import generate


def main():
    parser = argparse.ArgumentParser(description='Generate and review a fictional clinical trial')
    sub = parser.add_subparsers(dest='command',required=True)
    demo = sub.add_parser('demo',help='Generate synthetic source and run the full Python pipeline')
    demo.add_argument('--output',type=Path,default=Path('build/demo'))
    demo.add_argument('--subjects',type=int,default=120)
    demo.add_argument('--seed',type=int,default=2026)
    demo.add_argument('--clean',action='store_true',help='Do not plant the five review errors')
    process = sub.add_parser('run',help='Process source CSVs from the synthetic generator')
    process.add_argument('--source',type=Path,required=True)
    process.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command=='demo':
            if args.output.exists():
                raise ValueError('Output directory already exists; choose a fresh directory')
            generate(args.output/'source',n=args.subjects,seed=args.seed,issues=not args.clean)
            result = run(args.output/'source',args.output/'output')
        else:
            result = run(args.source,args.output)
        print(json.dumps(result,indent=2))
    except (ValueError,FileNotFoundError,json.JSONDecodeError) as exc:
        parser.exit(2,f'Pipeline stopped: {exc}\n')


if __name__=='__main__':
    main()
