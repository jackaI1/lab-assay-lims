"""Fail CI if the complete Python/R workflow drops expected study outputs."""
import csv
import json
import re
from pathlib import Path
import sys

root = Path(sys.argv[1])
output = root/'demo/output'
manifest = json.loads((output/'manifest.json').read_text())
assert manifest['subjects_input']==120
assert manifest['subjects_released']==119
assert manifest['queries']==5
assert manifest['quarantined_records']==16
with (output/'redcap_queries.csv').open() as f:
    review = list(csv.DictReader(f))
with (output/'redcap_dictionary.csv').open() as f:
    fields = {r['Variable / Field Name']: r for r in csv.DictReader(f)}
assert len(review)==5
assert {q['rule'] for q in review}=={'CT','RANGE','REQUIRED','DATE_ORDER','DOSE'}
for q in review:
    assert q['status']=='OPEN'
    assert fields[q['field_name']]['Form Name']==q['form_name']
    with (output/f"staging/{q['domain']}.csv").open() as f:
        row = list(csv.DictReader(f))[int(q['source_row'])-2]
    assert q['record_id']==row['USUBJID']
    assert q['value']==row[q['variable']]
    assert q['redcap_repeat_instrument']==('' if q['domain']=='DM' else q['form_name'])
    assert q['redcap_repeat_instance']==('' if q['domain']=='DM' else row[q['domain']+'SEQ'])
assert json.loads((output/'roundtrip.json').read_text())['equal'] is True
for d in ['DM','VS','LB','AE','EX','DS']:
    assert (output/f'sdtm/{d}.csv').read_bytes()==(output/f'roundtrip_sdtm/{d}.csv').read_bytes()
for name in ['report.html','km.png','demographics.csv','cox.csv','ph_test.csv','analysis_population.csv','session-info.txt']:
    assert (root/'analysis'/name).stat().st_size>0, name
with (root/'analysis/analysis_population.csv').open() as f:
    rows = list(csv.DictReader(f))
assert len(rows)==119
assert len({r['USUBJID'] for r in rows})==119
assert {r['event'] for r in rows}=={'0','1'}
report = (root/'analysis/report.html').read_text()
images = re.findall(r'<img[^>]+src=[\"\']([^\"\']+)',report)
assert images and all(src.startswith('data:image/') for src in images), 'Report must embed its curve image'
assert '/Users/' not in report and '/home/runner/' not in report, 'Report leaked local paths'
print('Verified six domains, five dictionary-linked review queries, 119 analysis subjects and complete R report artifacts.')
