import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .core import decisions, normalize, read_csv, redcap_export, sha, trend

def main():
    p = argparse.ArgumentParser(description='Screen synthetic complaints and produce a traceable surveillance record')
    p.add_argument('--complaints', help='CSV export (ignored with --redcap)')
    p.add_argument('--redcap', action='store_true', help='export records from REDCAP_API_URL using REDCAP_API_TOKEN')
    p.add_argument('--exposure', required=True)
    p.add_argument('--hazards', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--record-id', required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--owner', required=True)
    args = p.parse_args()
    if not args.redcap and not args.complaints:
        p.error('provide --complaints or --redcap')
    raw = redcap_export(os.environ['REDCAP_API_URL'], os.environ['REDCAP_API_TOKEN']) if args.redcap else read_csv(args.complaints)
    rows = normalize(raw)
    hazards = read_csv(args.hazards)
    hazard_map = {h['hazard_id']: h for h in hazards}
    if len(hazard_map) != len(hazards) or any(r['hazard_id'] not in hazard_map for r in rows):
        raise ValueError('hazard IDs must be unique and every complaint must link to one')
    trends = trend(rows, read_csv(args.exposure))
    record = {'record_control': {'id': args.record_id, 'revision': args.revision, 'owner': args.owner, 'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'draft, requires review', 'input_sha256': {'complaints': sha(args.complaints) if not args.redcap else 'REDCap export: snapshot hash below', 'normalized_records': __import__('hashlib').sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(), 'exposure': sha(args.exposure), 'hazards': sha(args.hazards)}}, 'limitations': 'Synthetic screening only. A qualified person must assess reportability, deadlines, exemptions, trends and risk controls. Not a submission or a compliant quality system.', 'trends': trends, 'events': [{'complaint': r, 'decisions': decisions(r), 'risk_file': hazard_map[r['hazard_id']]} for r in rows]}
    Path(args.output).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {args.output}: {len(rows)} complaints, {sum(t["signal"] for t in trends)} signals')

if __name__ == '__main__':
    main()
