"""One reproducible command for tests, traceability and benchmark evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from ecg_lifecycle.evaluate import evaluate, write_json
from scripts.traceability import collect_tests, read_junit, render_matrix, validate


def percentage(value):
    return 'N/A' if value is None else f'{100 * value:.2f}%'


def report_markdown(benchmark, metadata, spec):
    lines = ['# Verification report', '',
             'Learning exercise only. No clinical release or conformity claim is made.', '',
             f"Run UTC: {metadata['generated_utc']}",
             f"Revision: `{metadata['revision']}`; working tree dirty: `{metadata['dirty']}`.",
             f"Execution: {metadata['run_url'] or 'local baseline; CI artifacts are the authoritative CI evidence'}.",
             f"Python: {metadata['python']}; platform: {metadata['platform']}.",
             f"Dependencies: `{json.dumps(metadata['packages'], sort_keys=True)}`.",
             f"Lifecycle input SHA-256: `{metadata['lifecycle_sha256']}`.",
             f"Lockfile SHA-256: `{metadata['lockfile_sha256']}`.", '',
             f"{metadata['tests_passed']} tests passed with no skips; "
             f"{len(spec['requirements'])} requirements and "
             f"{sum(len(r['controls']) for r in spec['risks'])} risk controls have executed verification.", '',
             '## Heartbeat detection', '',
             'One-to-one annotated beat matching, inclusive 150 ms tolerance. '
             'Sensitivity = TP/(TP+FN); PPV = TP/(TP+FP). No pooled clinical claim.', '',
             '| Record | TP | FP | FN | Sensitivity | PPV |', '| --- | --- | --- | --- | --- | --- |']
    for record, row in benchmark['records'].items():
        q = row['qrs']
        lines.append(f"| {record} | {q['tp']} | {q['fp']} | {q['fn']} | {percentage(q['sensitivity'])} | {percentage(q['ppv'])} |")
    lines += ['', '## Irregular windows compared with AFIB labels', '',
              'This is an exploratory AFIB proxy, not accuracy for general arrhythmia or a diagnostic test. '
              'Complete 30-second windows only. Mixed/unknown windows are excluded; abstentions are reported. '
              'Conservative sensitivity includes positive abstentions as false negatives. N/A means an empty denominator.', '',
              '| Record | TP | FP | FN | TN | Sensitivity | PPV | Excluded | Abstain + / - | Conservative sensitivity |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for record, row in benchmark['records'].items():
        q = row['afib_proxy']
        lines.append(f"| {record} | {q['tp']} | {q['fp']} | {q['fn']} | {q['tn']} | {percentage(q['sensitivity'])} | "
                     f"{percentage(q['ppv'])} | {q['excluded_mixed_or_unknown']} | "
                     f"{q['abstained_positive']} / {q['abstained_negative']} | {percentage(q['conservative_sensitivity'])} |")
    lines += ['', '| Record | Regular | Irregular | Insufficient | Omitted tail (s) |', '| --- | --- | --- | --- | --- |']
    for record, row in benchmark['records'].items():
        w = row['window_counts']
        lines.append(f"| {record} | {w['regular']} | {w['irregular']} | {w['insufficient_data']} | {row['omitted_tail_s']:.6f} |")
    lines += ['', '## Review disposition', '',
              'The heartbeat regression floor is >=90% sensitivity and PPV per selected full record, '
              'and >=98% on the first minute of record 100. These are engineering regression checks only. '
              'There is no clinical acceptance threshold for the irregular flag. Record 201 has poor AFIB-proxy PPV; '
              'record 203 has positive abstentions. Clinical use remains prohibited.', '',
              'The versioned source, all nine input SHA-256 hashes, method parameters and every window feature '
              'are in `benchmark.json` in the same evidence artifact. `junit.xml`, `traceability.md` and '
              '`verification.json` accompany this report. Regenerate with `uv run python -m scripts.verify`.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('build'))
    parser.add_argument('--update-docs', action='store_true', help='refresh committed local baseline snapshots')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Remove prior success evidence before starting; a failed run must not look green.
    for name in ['junit.xml', 'benchmark.json', 'traceability.md', 'verification.json', 'verification-report.md']:
        (args.output / name).unlink(missing_ok=True)
    subprocess.run([sys.executable, '-m', 'pytest', '-q',
                    f'--junitxml={args.output / "junit.xml"}'], check=True)
    spec_path = Path('docs/lifecycle.json')
    spec = json.loads(spec_path.read_text())
    results = read_junit(args.output / 'junit.xml')
    validate(spec, collect_tests(), results)
    matrix = render_matrix(spec)
    (args.output / 'traceability.md').write_text(matrix)
    benchmark = evaluate()
    # Same internal regression criteria as the integration test, also checked for this evaluation.
    if any(r['qrs'][k] < 0.90 for r in benchmark['records'].values() for k in ('sensitivity', 'ppv')):
        raise ValueError('full-record QRS regression floor failed')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())
    server, repo, run = (os.environ.get(k) for k in ('GITHUB_SERVER_URL', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID'))
    metadata = dict(status='passed', generated_utc=datetime.now(timezone.utc).isoformat(),
                    revision=revision, dirty=dirty, python=platform.python_version(), platform=platform.system(),
                    packages={p: version(p) for p in ('wfdb', 'numpy', 'scipy', 'pandas', 'pytest')},
                    lifecycle_sha256=hashlib.sha256(spec_path.read_bytes()).hexdigest(),
                    lockfile_sha256=hashlib.sha256(Path('uv.lock').read_bytes()).hexdigest(),
                    tests_passed=len(results), run_url=f'{server}/{repo}/actions/runs/{run}' if run else None)
    write_json(args.output / 'benchmark.json', benchmark)
    write_json(args.output / 'verification.json', metadata)
    (args.output / 'verification-report.md').write_text(report_markdown(benchmark, metadata, spec))
    if args.update_docs:
        shutil.copyfile(args.output / 'traceability.md', 'docs/traceability.md')
        shutil.copyfile(args.output / 'verification-report.md', 'docs/verification-report.md')
    print(f"Verified {len(results)} tests; evidence: {args.output}/verification-report.md")


if __name__ == '__main__':
    main()
