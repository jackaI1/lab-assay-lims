"""Run the lab, provision test identities, or operate the companion."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .experiments import SCENARIOS, experiments
from .identity import Authority, SoftwareKeyStore, provision
from .px4 import Px4Link
from .transport import Client, Gateway


def main():
    parser = argparse.ArgumentParser(description='Simulation-only authenticated drone controller lab')
    commands = parser.add_subparsers(dest='action', required=True)
    setup = commands.add_parser('provision', help='generate fresh local test certificates and software keys')
    setup.add_argument('--store', type=Path, default=Path('.state'))
    revoke = commands.add_parser('revoke', help='revoke a local test identity immediately')
    revoke.add_argument('identity', choices=['pilot', 'observer', 'vehicle'])
    revoke.add_argument('--store', type=Path, default=Path('.state'))
    lab = commands.add_parser('experiments', help='launch real PX4/Gazebo and assert flight failsafes')
    lab.add_argument('--output', type=Path, default=Path('results'))
    lab.add_argument('--scenario', action='append', choices=SCENARIOS)
    serve = commands.add_parser('gateway', help='serve a running in-container PX4 instance')
    serve.add_argument('--store', type=Path, default=Path('.state'))
    serve.add_argument('--port', type=int, default=8443)
    controller = commands.add_parser('controller', help='send signed commands through the gateway')
    controller.add_argument('command', choices=['status', 'arm', 'disarm', 'takeoff', 'land'])
    controller.add_argument('--identity', choices=['pilot', 'observer'], default='pilot')
    controller.add_argument('--store', type=Path, default=Path('.state'))
    controller.add_argument('--port', type=int, default=8443)
    controller.add_argument('--seconds', type=float, default=15, help='maintain authenticated liveness for this long')
    args = parser.parse_args()
    try:
        if args.action == 'provision':
            provision(args.store)
            print('Created disposable test identities. Keep this directory private and untracked.')
        elif args.action == 'revoke':
            Authority(args.store).revoke(SoftwareKeyStore(args.store / args.identity).certificate())
        elif args.action == 'experiments':
            experiments(args.output, args.scenario or SCENARIOS)
        elif args.action == 'gateway':
            with Px4Link() as link:
                link.wait(lambda s: s['fresh'] and s['guard'] is not None, 30, 'PX4 ready')
                with Gateway(args.store, link, address=('127.0.0.1', args.port)) as gateway:
                    print(f'Gateway on {gateway.address}; Ctrl-C stops it.', flush=True)
                    while True:
                        time.sleep(1)
        elif args.action == 'controller':
            with Client(args.store, args.identity, ('127.0.0.1', args.port)) as client:
                with client.keepalive() as errors:
                    if args.command != 'status':
                        command = {'arm': (400, 1), 'disarm': (400, 0), 'takeoff': (22, 0), 'land': (21, 0)}[args.command]
                        print(json.dumps(client.command(*command, altitude=2 if args.command == 'takeoff' else 0)))
                    deadline = time.monotonic() + args.seconds
                    while time.monotonic() < deadline and not errors:
                        print(json.dumps(client.heartbeat()), flush=True)
                        time.sleep(1)
                    if errors:
                        raise RuntimeError(errors[0])
    except KeyboardInterrupt:
        return
    except (ValueError, OSError, RuntimeError, EOFError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
