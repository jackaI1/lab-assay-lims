"""Map source records, raise review queries and release traceable SDTM subsets."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
import csv
import html
import json
import math

from .synthetic import HEADERS

SPEC = json.loads(files('clinical_pipeline').joinpath('spec.json').read_text())
QUERY_COLUMNS = ['query_id','domain','source_file','source_row','USUBJID','variable','value','rule','severity','status','question']


def read_csv(path):
    with Path(path).open(newline='') as f:
        try:
            return list(csv.DictReader(f,strict=True))
        except csv.Error as exc:
            raise ValueError(f'{Path(path).name}: malformed CSV: {exc}') from exc


def write_csv(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, columns, lineterminator='\n', extrasaction='raise')
        w.writeheader()
        w.writerows(rows)


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def day(value):
    try:
        parsed = date.fromisoformat(value)
        return parsed if parsed.isoformat() == value else None
    except (ValueError, TypeError):
        return None


def study_day(value, start):
    if day(value) and day(start):
        delta = (day(value)-day(start)).days
        return str(delta+1 if delta >= 0 else delta)
    return ''


def map_sources(folder):
    folder = Path(folder)
    raw = {}
    for name, columns in HEADERS.items():
        path = folder / name
        if not path.exists():
            raise ValueError(f'Missing source file {name}')
        with path.open(newline='') as f:
            reader = csv.DictReader(f,strict=True)
            try:
                records = list(reader)
            except csv.Error as exc:
                raise ValueError(f'{name}: malformed CSV near line {reader.line_num}: {exc}') from exc
            if reader.fieldnames != columns:
                raise ValueError(f'Unexpected columns in {name}; expected {columns}')
            raw[name] = records
            if any(None in r or any(v is None for v in r.values()) for r in raw[name]):
                raise ValueError(f'Malformed CSV record in {name}')
    if not raw['subjects.csv']:
        raise ValueError('subjects.csv must contain subjects')
    starts = {r['sid']: r['randomization'] for r in raw['subjects.csv']}
    result = {d: [] for d in SPEC}
    for d, spec in SPEC.items():
        counts = Counter()
        for r in raw[spec['source']]:
            sid = r['sid']
            counts[sid] += 1
            row = dict(STUDYID='SYNTH01',DOMAIN=d,USUBJID='SYNTH01-'+sid)
            if d != 'DM':
                row[d+'SEQ'] = str(counts[sid])
            if d == 'DM':
                arm = {'A':'ACTIVE','P':'PLACEBO'}.get(r['arm'],r['arm'])
                end_ex = str(day(r['randomization'])+timedelta(days=27)) if day(r['randomization']) else ''
                row.update(SUBJID=sid,SITEID='SYNTH',AGE=r['age'],AGEU='YEARS',SEX=r['sex'],RACE=r['race'],
                           ARMCD=r['arm'],ARM=arm,ACTARMCD=r['arm'],ACTARM=arm,
                           RFSTDTC=r['randomization'],RFENDTC=r['death_date'] or r['last_contact'],
                           RFXSTDTC=r['randomization'],RFXENDTC=end_ex,
                           DTHFL='Y' if r['death_date'] else '',DTHDTC=r['death_date'])
            elif d == 'VS':
                row.update(VSTESTCD=r['test'],VSTEST={'SYSBP':'Systolic Blood Pressure','DIABP':'Diastolic Blood Pressure'}.get(r['test'],r['test']),
                           VSORRES=r['value'],VSORRESU=r['unit'],VSSTRESC=r['value'],VSSTRESN=r['value'],VSSTRESU=r['unit'],
                           VISITNUM=r['visit'],VSDTC=r['date'],VSDY=study_day(r['date'],starts.get(sid,'')))
            elif d == 'LB':
                n = number(r['value'])
                converted = n / 18.0182 if n is not None and r['unit']=='mg/dL' else n
                standard = f'{converted:.6f}' if converted is not None else r['value']
                flag = 'LOW' if converted is not None and converted < 3.9 else 'HIGH' if converted is not None and converted > 6.1 else 'NORMAL'
                row.update(LBTESTCD='GLUC',LBTEST='Glucose',LBORRES=r['value'],LBORRESU=r['unit'],
                           LBSTRESC=standard,LBSTRESN=standard,LBSTRESU='mmol/L',LBSTNRLO='3.9',LBSTNRHI='6.1',LBNRIND=flag,
                           VISITNUM=r['visit'],LBDTC=r['date'],LBDY=study_day(r['date'],starts.get(sid,'')))
            elif d == 'AE':
                row.update(AETERM=r['term'],AESEV=r['severity'],AESER=r['serious'],AESTDTC=r['start'],AEENDTC=r['end'])
            elif d == 'EX':
                row.update(EXTRT=r['treatment'],EXDOSE=r['dose'],EXDOSU='mg',EXDOSFRQ='QD',EXROUTE='ORAL',EXSTDTC=r['start'],EXENDTC=r['end'])
            elif d == 'DS':
                row.update(DSTERM=r['status'],DSDECOD=r['status'],DSCAT='DISPOSITION EVENT',DSSCAT='STUDY PARTICIPATION',DSSTDTC=r['date'])
            result[d].append(row)
    return result


def check_domains(domains):
    queries = []
    dm = {r['USUBJID']:r for r in domains['DM']}
    def query(d, i, row, variable, rule, question):
        queries.append(dict(query_id=f'Q{len(queries)+1:05d}',domain=d,source_file=SPEC[d]['source'],source_row=str(i+2),
                            USUBJID=row.get('USUBJID',''),variable=variable,value=row.get(variable,''),rule=rule,
                            severity='ERROR',status='OPEN',question=question))
    for d, rows in domains.items():
        keycols = ['USUBJID'] if d=='DM' else ['USUBJID',d+'SEQ']
        counts = Counter(tuple(r.get(k,'') for k in keycols) for r in rows)
        for i, row in enumerate(rows):
            def q(v, rule, message):
                query(d,i,row,v,rule,message)
            for v, f in SPEC[d]['fields'].items():
                value = row.get(v,'')
                if not value:
                    if f['required']:
                        q(v,'REQUIRED','Please provide the missing required value or confirm why it is unavailable.')
                    continue
                if f['terms'] and value not in f['terms']:
                    q(v,'CT','Please confirm a value from: '+', '.join(f['terms'])+'.')
                if f['type'] in ['integer','float']:
                    n = number(value)
                    if n is None or (f['type']=='integer' and n != int(n)):
                        q(v,'NUMERIC','Please confirm a finite '+f['type']+' value.')
                    elif ('minimum' in f and n<f['minimum']) or ('maximum' in f and n>f['maximum']):
                        q(v,'RANGE','Please review this value against the protocol range.')
                if f['type']=='date' and not day(value):
                    q(v,'DATE','Please supply a complete valid date in YYYY-MM-DD format.')
            if counts[tuple(row.get(k,'') for k in keycols)] > 1:
                q(keycols[-1],'DUPLICATE','Please resolve the duplicate record key; neither duplicate will be released.')
            if row.get('STUDYID')!='SYNTH01' or row.get('DOMAIN')!=d:
                q('DOMAIN','IDENTITY','Please confirm study and domain identifiers.')
            if d=='DM' and row.get('USUBJID') != 'SYNTH01-'+row.get('SUBJID',''):
                q('USUBJID','IDENTITY','Please reconcile the unique subject identifier with SUBJID.')
            subject = dm.get(row.get('USUBJID'))
            if subject is None:
                q('USUBJID','ORPHAN','Please link this record to an enrolled subject.')
                continue
            pairs = {'DM':('RFSTDTC','RFENDTC'),'AE':('AESTDTC','AEENDTC'),'EX':('EXSTDTC','EXENDTC')}
            if d in pairs:
                a,b = pairs[d]
                if day(row.get(a)) and day(row.get(b)) and day(row[b])<day(row[a]):
                    q(b,'DATE_ORDER','End precedes start. Please verify both dates against the source.')
            if d in ['VS','LB','AE','EX','DS']:
                dt = {'VS':'VSDTC','LB':'LBDTC','AE':'AESTDTC','EX':'EXSTDTC','DS':'DSSTDTC'}[d]
                if day(row.get(dt)) and day(subject.get('RFSTDTC')) and day(subject.get('RFENDTC')):
                    if not day(subject['RFSTDTC']) <= day(row[dt]) <= day(subject['RFENDTC']):
                        q(dt,'STUDY_WINDOW','Date is outside the subject observation period. Please verify.')
            if d in ['AE','EX']:
                start_col,end_col = pairs[d]
                if day(row.get(start_col)) and day(row.get(end_col)) and day(row[end_col])>=day(row[start_col]) and day(subject.get('RFENDTC')):
                    if day(row[end_col])>day(subject['RFENDTC']):
                        q(end_col,'STUDY_WINDOW','End date exceeds recorded follow-up. Please verify.')
            if d=='VS':
                expected_name = {'SYSBP':'Systolic Blood Pressure','DIABP':'Diastolic Blood Pressure'}.get(row.get('VSTESTCD'))
                if expected_name and row.get('VSTEST')!=expected_name:
                    q('VSTEST','TEST_NAME','Please reconcile the test name with the test code.')
                n = number(row.get('VSSTRESN'))
                low, high = (30,300) if row.get('VSTESTCD')=='SYSBP' else (20,200)
                if n is not None and not low<=n<=high:
                    q('VSSTRESN','RANGE','Please verify this implausible blood pressure result and its unit.')
            if d=='EX' and number(row.get('EXDOSE')) is not None and number(row['EXDOSE'])<0:
                q('EXDOSE','DOSE','Dose is negative. Please confirm the administered dose.')
            if d=='LB' and number(row.get('LBORRES')) is not None and number(row.get('LBSTRESN')) is not None:
                expected = number(row['LBORRES']) / 18.0182 if row.get('LBORRESU')=='mg/dL' else number(row['LBORRES'])
                if abs(number(row['LBSTRESN'])-expected)>0.00001:
                    q('LBSTRESN','CONVERSION','Please reconcile the original and standardized laboratory result.')
            if d=='DS':
                expected_status = 'DEATH' if subject.get('DTHFL')=='Y' else 'COMPLETED'
                if row.get('DSDECOD') in ['DEATH','COMPLETED'] and (row['DSDECOD']!=expected_status or row.get('DSSTDTC')!=subject.get('RFENDTC')):
                    q('DSSTDTC','ENDPOINT','Please reconcile disposition and demographic follow-up/death records.')
    ds_counts = Counter(r['USUBJID'] for r in domains['DS'])
    for i, row in enumerate(domains['DM']):
        if ds_counts[row['USUBJID']] != 1:
            query('DM',i,row,'RFENDTC','ENDPOINT','Please provide exactly one terminal disposition for this subject.')
        if row.get('DTHFL')=='Y' and row.get('DTHDTC')!=row.get('RFENDTC'):
            query('DM',i,row,'DTHDTC','ENDPOINT','Please reconcile death date with the reference end date.')
    return queries


def release(domains, queries):
    bad_rows = {(q['domain'],int(q['source_row'])-2) for q in queries}
    bad_subjects = {q['USUBJID'] for q in queries if q['domain'] in ['DM','DS']}
    accepted = {d: [] for d in domains}
    rejected = []
    for d, rows in domains.items():
        for i, row in enumerate(rows):
            if (d,i) in bad_rows or row['USUBJID'] in bad_subjects:
                rejected.append(dict(domain=d,source_file=SPEC[d]['source'],source_row=str(i+2),USUBJID=row['USUBJID'],
                                     reason='Subject-level query' if row['USUBJID'] in bad_subjects else 'Record-level query'))
            else:
                accepted[d].append(row)
    return accepted, rejected


def run(source, output):
    from .redcap import dictionary, encode, decode, query_worklist, DICTIONARY_COLUMNS, REVIEW_COLUMNS
    from .metadata import write_metadata
    source, output = Path(source), Path(output)
    provenance = json.loads((source/'provenance.json').read_text())
    if provenance.get('synthetic_only') is not True or provenance.get('generator')!='clinical_pipeline.synthetic':
        raise ValueError('This demonstration accepts only the documented synthetic generator provenance')
    if output.exists():
        raise ValueError('Output directory already exists; choose a fresh directory to avoid stale artifacts')
    mapped = map_sources(source)
    queries = check_domains(mapped)
    accepted, rejected = release(mapped, queries)
    if check_domains(accepted):
        raise ValueError('Released data failed integrity checks')
    if not accepted['DM']:
        raise ValueError('No eligible subjects remain after validation')
    output.mkdir(parents=True)
    for d in SPEC:
        write_csv(output/f'staging/{d}.csv',mapped[d],SPEC[d]['fields'])
        write_csv(output/f'sdtm/{d}.csv',accepted[d],SPEC[d]['fields'])
    write_csv(output/'query_log.csv',queries,QUERY_COLUMNS)
    write_csv(output/'redcap_queries.csv',query_worklist(mapped, queries),REVIEW_COLUMNS)
    write_csv(output/'quarantine.csv',rejected,['domain','source_file','source_row','USUBJID','reason'])
    dd = dictionary()
    write_csv(output/'redcap_dictionary.csv',dd,DICTIONARY_COLUMNS)
    records = encode(accepted,read_csv(output/'redcap_dictionary.csv'))
    columns = ['record_id','redcap_repeat_instrument','redcap_repeat_instance'] + [r['Variable / Field Name'] for r in dd if r['Variable / Field Name']!='record_id']
    write_csv(output/'redcap_records.csv',records,columns)
    recovered = decode(read_csv(output/'redcap_records.csv'),read_csv(output/'redcap_dictionary.csv'))
    if recovered != accepted:
        raise ValueError('REDCap round trip changed data')
    for d in SPEC:
        write_csv(output/f'roundtrip_sdtm/{d}.csv',recovered[d],SPEC[d]['fields'])
    (output/'roundtrip.json').write_text(json.dumps(dict(equal=True,records=len(records),method='local dictionary-driven CSV codec; no live REDCap server'),indent=2)+'\n')
    write_metadata(output)
    summary = dict(synthetic_only=True,subjects_input=len(mapped['DM']),subjects_released=len(accepted['DM']),queries=len(queries),
                   quarantined_records=len(rejected),domain_rows={d:len(r) for d,r in accepted.items()},
                   source_sha256={n:sha256((source/n).read_bytes()).hexdigest() for n in [*HEADERS,'provenance.json']},
                   spec_sha256=sha256(files('clinical_pipeline').joinpath('spec.json').read_bytes()).hexdigest())
    (output/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    items = ''.join('<tr>'+''.join('<td>'+html.escape(str(q[k]))+'</td>' for k in ['query_id','domain','USUBJID','rule','question'])+'</tr>' for q in queries)
    report = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Synthetic trial data quality</title>
<style>body{{font:17px system-ui;max-width:1100px;margin:3rem auto;padding:0 1rem}}td,th{{padding:.6rem;text-align:left;border-bottom:1px solid #ccc}}table{{border-collapse:collapse}}</style>
<h1>Synthetic trial data quality</h1><p>All records are fictional. This is a review workflow, not a regulatory validation certificate.</p>
<p>{summary['subjects_released']} / {summary['subjects_input']} subjects released. {len(queries)} open queries. {len(rejected)} records quarantined.</p>
<p>Every query remains OPEN until a reviewer checks the source. Nothing has been auto-corrected. Subject errors in DM or DS remove the subject from every released domain. Other errors remove only the affected record.</p>
<p><a href="redcap_queries.csv">Download the REDCap review worksheet</a> for dictionary field names, original repeat instances and source rows. Queried records are quarantined, so these locators refer to staging data and may be absent from the released REDCap export. The worksheet does not upload queries or track resolution in a live REDCap project.</p>
<p>The R analysis uses released DM and DS. Quarantined findings, events and doses are unavailable for safety summaries; this report does not declare the study ready for database lock.</p>
<table><thead><tr><th>Query</th><th>Domain</th><th>Subject</th><th>Rule</th><th>Review question</th></tr></thead><tbody>{items}</tbody></table>
<h2>Released rows</h2><pre>{html.escape(json.dumps(summary['domain_rows'],indent=2))}</pre>
<p>See query_log.csv, quarantine.csv, staging/ and manifest.json for source row references and SHA-256 fingerprints.</p></html>'''
    (output/'data_quality.html').write_text(report)
    return summary
