import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FIELDS = ('id', 'family', 'date_received', 'event', 'device_related', 'recurrence_harm', 'eu_serious', 'public_health_threat', 'unanticipated', 'hazard_id')
EVENTS = {'death', 'serious_injury', 'malfunction', 'other'}
BOOLS = ('device_related', 'recurrence_harm', 'eu_serious', 'public_health_threat', 'unanticipated')
FDA = 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-803/subpart-E/section-803.50'
EU = 'https://eur-lex.europa.eu/eli/reg/2017/745/oj/eng'

def normalize(rows):
    result, seen = [], set()
    for n, source in enumerate(rows, 2):
        row = {k: str(source.get(k, '')).strip() for k in FIELDS}
        if not all(row.values()):
            raise ValueError(f'row {n}: all fields are required')
        if row['id'] in seen:
            raise ValueError(f'row {n}: duplicate id {row["id"]}')
        seen.add(row['id'])
        row['date_received'] = date.fromisoformat(row['date_received']).isoformat()
        row['event'] = row['event'].lower()
        if row['event'] not in EVENTS:
            raise ValueError(f'row {n}: invalid event')
        for k in BOOLS:
            if row[k].lower() not in ('yes', 'no', '1', '0'):
                raise ValueError(f'row {n}: invalid {k}')
            row[k] = row[k].lower() in ('yes', '1')
        result.append(row)
    return result

def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def redcap_export(url, token, opener=urlopen):
    """Export flat records from a REDCap project using its official API."""
    if not url.startswith('https://'):
        raise ValueError('REDCap API URL must use HTTPS')
    body = urlencode({'token': token, 'content': 'record', 'format': 'json', 'type': 'flat', 'rawOrLabel': 'raw', 'returnFormat': 'json'}).encode()
    request = Request(url, data=body, method='POST')
    with opener(request, timeout=30) as response:
        records = json.load(response)
    if not isinstance(records, list):
        raise ValueError('REDCap export did not return a record list')
    return records

def decisions(row):
    # Inputs are screening facts, not a determination of causality or exemptions.
    if row['device_related'] and row['event'] in ('death', 'serious_injury'):
        fda = ('potentially reportable', 30, '21 CFR 803.50(a)(1)')
    elif row['event'] == 'malfunction' and row['recurrence_harm']:
        fda = ('potentially reportable', 30, '21 CFR 803.50(a)(2)')
    else:
        fda = ('review, criteria not met by supplied facts', None, '21 CFR 803.50(a)(1)-(2)')
    if row['eu_serious'] and row['device_related']:
        if row['public_health_threat']:
            eu = ('potentially reportable', 2, 'EU MDR Article 87(4)')
        elif row['event'] == 'death' or (row['event'] == 'serious_injury' and row['unanticipated']):
            eu = ('potentially reportable', 10, 'EU MDR Article 87(5)')
        else:
            eu = ('potentially reportable', 15, 'EU MDR Article 87(3)')
    else:
        eu = ('review, criteria not met by supplied facts', None, 'EU MDR Article 87(1)(a), 87(2)')
    out = {}
    for name, item, link in [('FDA', fda, FDA), ('EU', eu, EU)]:
        status, days, clause = item
        out[name] = {'decision': status, 'days': days, 'due_date': (date.fromisoformat(row['date_received']) + timedelta(days=days)).isoformat() if days else None, 'clause': clause, 'source': link}
    return out

def trend(rows, exposure, baseline_months=3, weight=0.3):
    """Poisson rate chart and variance-adjusted EWMA; baseline is frozen."""
    counts = defaultdict(int)
    for row in rows:
        counts[(row['family'], row['date_received'][:7])] += 1
    groups = defaultdict(dict)
    for record in exposure:
        family, month = record['family'].strip(), record['month'].strip()
        date.fromisoformat(month + '-01')
        units = int(record['units'])
        if not family or units <= 0 or month in groups[family]:
            raise ValueError('exposure needs unique family/month and positive units')
        groups[family][month] = units
    missing = set(counts) - {(f, m) for f, months in groups.items() for m in months}
    if missing:
        raise ValueError(f'complaints missing exposure: {sorted(missing)}')
    output = []
    for family, months in sorted(groups.items()):
        ordered = sorted(months)
        if len(ordered) <= baseline_months:
            raise ValueError(f'{family}: need baseline and monitoring months')
        base = ordered[:baseline_months]
        rate = sum(counts[(family, m)] for m in base) / sum(months[m] for m in base)
        if rate == 0:
            raise ValueError(f'{family}: baseline must contain complaints')
        z, variance = rate, 0.0
        for m in ordered[baseline_months:]:
            units, count = months[m], counts[(family, m)]
            observed = count / units
            z = weight * observed + (1 - weight) * z
            variance = weight ** 2 * rate / units + (1 - weight) ** 2 * variance
            ucl = rate + 3 * math.sqrt(rate / units)
            ewma_ucl = rate + 3 * math.sqrt(variance)
            output.append({'family': family, 'month': m, 'complaints': count, 'units': units, 'rate_per_1000': observed * 1000, 'baseline_per_1000': rate * 1000, 'ucl_per_1000': ucl * 1000, 'ewma_per_1000': z * 1000, 'ewma_ucl_per_1000': ewma_ucl * 1000, 'signal': observed > ucl or z > ewma_ucl})
    return output

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
