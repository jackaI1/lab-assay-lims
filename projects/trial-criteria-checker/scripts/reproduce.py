"""Rebuild or verify committed outputs. Runs offline, from repository root."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trial_criteria.benchmark import benchmark
from trial_criteria.report import build_report, render_html, render_markdown


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Fail if any saved output differs')
    args = parser.parse_args()
    read = lambda name: json.loads(Path(name).read_text(encoding='utf-8'))
    snapshot, labels = read('data/studies.json'), read('data/labels.json')
    metrics = benchmark(snapshot,labels)
    report = build_report(snapshot,read('examples/fictional_patient.json'))
    report['benchmark'] = metrics
    dump = lambda obj: json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    outputs = {'reports/metrics.json':dump(metrics),
               'reports/fictional_patient.json':dump(report),
               'reports/fictional_patient.html':render_html(report),
               'reports/fictional_patient.md':render_markdown(report)}
    for name, content in outputs.items():
        if args.check:
            if not Path(name).exists() or Path(name).read_text(encoding='utf-8') != content:
                parser.exit(1,'Saved output differs: '+name+'\n')
        else:
            Path(name).parent.mkdir(parents=True,exist_ok=True)
            Path(name).write_text(content,encoding='utf-8')
    print(json.dumps({k:metrics[k] for k in ('study_count','source_sentence_count','gold_rule_count',
          'true_positives','false_positives','false_negatives','precision','recall')},indent=2))
    print('Fictional outcomes: '+json.dumps(report['counts']))
    print('Saved outputs '+('match' if args.check else 'rebuilt'))


if __name__ == '__main__':
    main()
