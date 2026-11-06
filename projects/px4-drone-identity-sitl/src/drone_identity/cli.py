import argparse
import asyncio
import logging
from pathlib import Path

from .controller import demo
from .gateway import serve
from .identity import provision


def main():
    parser = argparse.ArgumentParser(description="PX4 simulation controller identity demo")
    parser.add_argument("action", choices=["provision", "companion", "fly"])
    parser.add_argument("--credentials", type=Path, default=Path(".local/identity"))
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.action == "provision":
        provision(args.credentials)
        print(f"Created disposable demo identities in {args.credentials}")
    else:
        try:
            asyncio.run(serve(args.credentials, port=args.port) if args.action == "companion"
                        else demo(args.credentials, port=args.port))
        except KeyboardInterrupt:
            pass
