"""Generate a fictional, randomized two-arm trial. No clinical records are read."""
from datetime import date, timedelta
from pathlib import Path
import csv
import json
import random

HEADERS = {
    'subjects.csv': ['sid','age','sex','race','arm','randomization','last_contact','death_date'],
    'vitals.csv': ['sid','test','value','unit','visit','date'],
    'labs.csv': ['sid','value','unit','visit','date'],
    'events.csv': ['sid','term','severity','serious','start','end'],
    'exposure.csv': ['sid','treatment','dose','start','end'],
    'disposition.csv': ['sid','status','date'],
}


def generate(folder: Path, n=120, seed=2026, issues=True):
    if n < 20:
        raise ValueError('At least 20 synthetic subjects are required')
    rng = random.Random(seed)
    rows = {name: [] for name in HEADERS}
    allocations = ['A' if i % 2 else 'P' for i in range(1,n+1)]
    rng.shuffle(allocations)
    for i in range(1, n+1):
        sid = f'{i:04d}'
        arm = allocations[i-1]
        start = date(2025,1,1) + timedelta(days=rng.randrange(60))
        age = rng.randrange(25,81)
        sex = rng.choice(['F','M'])
        # Fictional exponential failure times, with administrative censoring.
        scale = (270 if arm == 'A' else 190) * (1.012 ** (55-age))
        duration = max(35, round(rng.expovariate(1/scale)))
        contact = rng.randrange(180,366)
        death = start + timedelta(days=duration) if duration <= contact else None
        end = death or start + timedelta(days=contact)
        treatment = 'ACTIVE' if arm == 'A' else 'PLACEBO'
        rows['subjects.csv'].append(dict(zip(HEADERS['subjects.csv'], [sid,age,sex,rng.choice(['WHITE','ASIAN','BLACK OR AFRICAN AMERICAN']),arm,str(start),str(end),str(death) if death else ''])))
        for visit, day in enumerate([0,14,28],1):
            when = str(start+timedelta(days=day))
            for test, mu in [('SYSBP',125),('DIABP',78)]:
                rows['vitals.csv'].append(dict(zip(HEADERS['vitals.csv'],[sid,test,round(rng.gauss(mu,9),1),'mmHg',visit,when])))
            rows['labs.csv'].append(dict(zip(HEADERS['labs.csv'],[sid,round(rng.gauss(100,15),1),'mg/dL',visit,when])))
        if i % 3 == 0:
            rows['events.csv'].append(dict(zip(HEADERS['events.csv'],[sid,'Headache','MILD','N',str(start+timedelta(days=7)),str(start+timedelta(days=9))])))
        rows['exposure.csv'].append(dict(zip(HEADERS['exposure.csv'],[sid,treatment,10 if arm=='A' else 0,str(start),str(start+timedelta(days=27))])))
        rows['disposition.csv'].append(dict(zip(HEADERS['disposition.csv'],[sid,'DEATH' if death else 'COMPLETED',str(end)])))
    if issues:
        rows['subjects.csv'][0]['sex'] = 'X'
        rows['vitals.csv'][6]['value'] = 400  # subject 2
        rows['labs.csv'][6]['unit'] = ''  # subject 3
        rows['events.csv'][1]['end'] = '2020-01-01'  # subject 6
        rows['exposure.csv'][3]['dose'] = -10  # subject 4
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, records in rows.items():
        with (folder/name).open('w', newline='') as f:
            writer = csv.DictWriter(f, HEADERS[name], lineterminator='\n')
            writer.writeheader()
            writer.writerows(records)
    (folder/'provenance.json').write_text(json.dumps(dict(synthetic_only=True,generator='clinical_pipeline.synthetic',seed=seed,subjects=n,intentional_issues=issues),indent=2)+'\n')
