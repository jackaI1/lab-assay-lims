"""Download public recruiting study snapshots, without credentials."""
import json
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = 'https://clinicaltrials.gov/api/v2/studies'


def fetch_studies(condition='', limit=10, ids=None, opener=None):
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('limit must be an integer from 1 to 10000')
    if ids and (len(ids) > 100 or any(not re.fullmatch(r'NCT\d{8}', x) for x in ids)):
        raise ValueError('Use up to 100 valid NCT identifiers')
    opener = opener or urlopen
    studies, requests, seen_ids, seen_tokens = [], [], set(), set()
    token = None
    while len(studies) < limit:
        params = {'format':'json', 'filter.overallStatus':'RECRUITING',
                  'pageSize':min(100, limit-len(studies))}
        if condition:
            params['query.cond'] = condition
        if ids:
            params['filter.ids'] = ','.join(ids)
        if token:
            params['pageToken'] = token
        url = ENDPOINT + '?' + urlencode(params)
        requests.append(url)
        request = Request(url, headers={'Accept':'application/json', 'User-Agent':'trial-criteria-checker/1.0'})
        for attempt in range(3):
            try:
                with opener(request, timeout=30) as response:
                    body = response.read(20_000_001)
                if len(body) > 20_000_000:
                    raise ValueError('API page exceeds download limit')
                page = json.loads(body)
                break
            except HTTPError as exc:
                if exc.code not in (429,500,502,503,504) or attempt == 2:
                    raise
                time.sleep(2 ** attempt)
            except URLError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        if not isinstance(page, dict) or not isinstance(page.get('studies', []), list):
            raise ValueError('Unexpected API response structure')
        for study in page.get('studies', []):
            protocol = study['protocolSection']
            nct_id = protocol['identificationModule']['nctId']
            if not re.fullmatch(r'NCT\d{8}', nct_id):
                raise ValueError('Invalid identifier in API response')
            if protocol['statusModule']['overallStatus'] != 'RECRUITING':
                raise ValueError('API returned a study outside the recruiting filter')
            if nct_id not in seen_ids:
                # Keep only project inputs, excluding contacts, sites and unrelated API fields.
                identification = protocol['identificationModule']
                status = protocol['statusModule']
                studies.append({'protocolSection': {
                    'identificationModule': {key:identification[key] for key in ('nctId','briefTitle') if key in identification},
                    'statusModule': {key:status[key] for key in ('overallStatus','lastUpdatePostDateStruct') if key in status},
                    'eligibilityModule': {key:value for key,value in protocol.get('eligibilityModule',{}).items()
                                          if key in ('eligibilityCriteria','sex','minimumAge','maximumAge','healthyVolunteers')}
                }})
                seen_ids.add(nct_id)
            if len(studies) == limit:
                break
        if len(studies) == limit:
            break
        token = page.get('nextPageToken')
        if not token:
            break
        if token in seen_tokens:
            raise ValueError('API repeated a pagination token')
        seen_tokens.add(token)
    return {'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'requests':requests, 'studies':studies, 'source':'ClinicalTrials.gov v2 API'}
