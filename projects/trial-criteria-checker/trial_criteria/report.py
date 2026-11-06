"""Portable JSON and HTML, with original text beside every outcome."""
import html
import json
import re
from collections import Counter
from .parser import parse_criteria
from .evaluate import evaluate


def build_report(snapshot, patient):
    if not isinstance(patient, dict) or patient.get('fictional') is not True:
        raise ValueError('Only explicitly fictional records are accepted; set fictional: true')
    studies = []
    counts = Counter({'met':0,'not met':0,'unknown':0})
    for study in snapshot['studies']:
        p = study['protocolSection']
        ident = p['identificationModule']
        nct_id = ident['nctId']
        if not re.fullmatch(r'NCT\d{8}', nct_id):
            raise ValueError('Invalid study identifier')
        text = p.get('eligibilityModule',{}).get('eligibilityCriteria','')
        rows = [evaluate(r,patient) for r in parse_criteria(text)]
        counts.update(r['status'] for r in rows)
        studies.append(dict(nct_id=nct_id,title=ident.get('briefTitle',nct_id),
                            url='https://clinicaltrials.gov/study/'+nct_id,
                            status=p.get('statusModule',{}).get('overallStatus','unknown'),
                            criteria=rows,missing_criteria=not bool(text.strip())))
    return dict(patient=patient,studies=studies,counts=dict(counts),
                retrieved_at=snapshot['retrieved_at'],requests=snapshot.get('requests',[]),
                warning='Fictional patient demonstration. No overall eligibility decision. Unparsed criteria require human review.')


def render_html(report):
    esc = lambda x: html.escape(str(x),quote=True)
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>Trial criteria checker: fictional patient report</title>',
             '<style>body{font:17px/1.6 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#162a32;background:#fafbf9}h1,h2{line-height:1.2}table{border-collapse:collapse;width:100%;margin:1rem 0}td,th{border:1px solid #bcc9ce;padding:.65rem;text-align:left;vertical-align:top}th{background:#e6eeec}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf1f0;padding:1rem}code{white-space:pre-wrap}a{color:#075985}.unknown{color:#755200}.met{color:#11603a}.not-met{color:#9c2626}.scroll{overflow-x:auto}small{display:block}</style>',
             '<h1>Trial criteria checker</h1><p><strong>'+esc(report['warning'])+'</strong></p>',
             '<p>Saved public records retrieved '+esc(report['retrieved_at'])+'. Recruitment status can change.</p>',
             '<p>Outcomes describe individual criteria: '+esc(report['counts'])+'. A “met” row never establishes trial eligibility.</p>',
             '<details><summary>Fictional input record</summary><pre>'+esc(json.dumps(report['patient'],indent=2))+'</pre></details>']
    if 'benchmark' in report:
        b = report['benchmark']
        pct = lambda v: 'undefined' if v is None else f'{v:.1%}'
        parts += ['<h2>Parsing measurement</h2><p>On '+str(b['study_count'])+' selected studies: '+str(b['true_positives'])+' correct rules, '+str(b['false_positives'])+' incorrect rules, '+str(b['false_negatives'])+' missed reference rules. Precision '+pct(b['precision'])+'; recall '+pct(b['recall'])+'.</p>',
                  '<p>Precision asks how many emitted rules were exact. Recall asks how many labelled rules were found. These measure parsing, not clinical decisions. The sample was labelled by direct reading during development and has no independent clinical review. No sex reference rules occur in this sample.</p>',
                  '<details><summary>Full measurement and misses</summary><pre>'+esc(json.dumps(b,indent=2))+'</pre></details>']
    for study in report['studies']:
        parts += ['<h2><a href="'+esc(study['url'])+'">'+esc(study['nct_id'])+'</a>: '+esc(study['title'])+'</h2>',
                  '<p>Saved recruitment status: '+esc(study['status'])+'</p>']
        if study['missing_criteria']:
            parts += ['<p>Unknown: no eligibility criteria text in this record.</p>']
        parts += ['<div class="scroll"><table><thead><tr><th>Source sentence</th><th>Structured rule</th><th>Fictional result</th></tr></thead><tbody>']
        for row in study['criteria']:
            parts += ['<tr><td>'+esc(row['sentence'])+'<small>'+esc(row['section'])+'; offsets '+str(row['start'])+':'+str(row['end'])+'</small></td><td><code>'+esc(json.dumps(row['rule'],ensure_ascii=False))+'</code><small>'+esc(row['parse_reason'])+'</small></td><td class="'+esc(row['status'].replace(' ','-'))+'"><strong>'+esc(row['status'])+'</strong><small>'+esc(row['evaluation_reason'])+'</small></td></tr>']
        parts += ['</tbody></table></div>']
    parts += ['<h2>Source requests</h2><ul>']
    for url in report['requests']:
        parts += ['<li>'+esc(url)+'</li>']
    parts += ['</ul></html>']
    return '\n'.join(parts)+'\n'


def render_markdown(report):
    """GitHub-readable companion, without needing to download HTML."""
    esc = lambda x: html.escape(str(x),quote=True).replace('|','&#124;').replace('\n',' ')
    parts = ['# Fictional patient report', '', report['warning'], '',
             'Public records retrieved: '+report['retrieved_at'], '',
             'Individual criterion outcomes: '+esc(report['counts'])+'. These are not a trial eligibility decision.', '',
             '## Fictional input', '', '```json', json.dumps(report['patient'],indent=2), '```', '']
    if 'benchmark' in report:
        b = report['benchmark']
        pct = lambda v: 'undefined' if v is None else f'{v:.1%}'
        parts += ['## Parsing measurement', '',
                  f"{b['true_positives']} exact rules; {b['false_positives']} incorrect rules; {b['false_negatives']} missed reference rules. Precision: {pct(b['precision'])}; recall: {pct(b['recall'])}.", '',
                  'This small development sample is not held out or clinically reviewed. It has no sex reference rules. See [metrics.json](metrics.json) for per-field counts and misses.', '']
    for study in report['studies']:
        parts += ['## ['+study['nct_id']+']('+study['url']+'): '+esc(study['title']), '',
                  'Saved status: '+esc(study['status'])+'.', '']
        if study['missing_criteria']:
            parts += ['Unknown: no eligibility criteria text in this record.', '']
        parts += ['| Exact source sentence | Rule and source offsets | Result |', '| --- | --- | --- |']
        for row in study['criteria']:
            rule = json.dumps(row['rule'],ensure_ascii=False) if row['rule'] else 'Unparsed'
            parts += ['| '+esc(row['sentence'])+' | '+esc(rule)+'; '+esc(row['section'])+' '+str(row['start'])+':'+str(row['end'])+' | **'+row['status']+'**: '+esc(row['evaluation_reason'])+' |']
        parts += ['']
    return '\n'.join(parts).rstrip()+'\n'
