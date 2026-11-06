import argparse
import json
from pathlib import Path
from .build import build
from .calculator import calculate
from .simulation import demo


def main():
    p=argparse.ArgumentParser(description='Simulated bottle-filler panel study')
    p.add_argument('command',choices=['build','calculate','simulate','release'])
    p.add_argument('--check',action='store_true',help='fail on stale reports, previews or native drawing disagreement')
    p.add_argument('--regenerate-drawing',action='store_true',help='rebuild native QET after intentional data edits')
    p.add_argument('--input',type=Path,default=Path('data/panel.json'))
    args=p.parse_args()
    if args.command=='build':
        if args.regenerate_drawing:
            if args.check: p.error('--check cannot regenerate')
            from .drawing import render
            native,_=render(json.loads(args.input.read_text()))
            Path('drawings/bottle-filler.qet').write_text(native)
        result=build(Path('.'),args.check)
    elif args.command=='release':
        from .release import record
        result=record(Path('.'))
    elif args.command=='calculate': result=calculate(json.loads(args.input.read_text()))
    else: result=demo()
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__': main()
