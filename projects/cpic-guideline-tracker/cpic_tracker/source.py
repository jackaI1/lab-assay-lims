"""Read public CPIC tables through PostgREST or an official release export."""
import csv
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = 'https://api.cpicpgx.org/v1/'
COLUMNS = {
    'pair': 'pairid genesymbol drugid guidelineid usedforrecommendation cpiclevel removed',
    'drug': 'drugid name guidelineid',
    'guideline': 'id name url genes notesonusage',
    'recommendation': ('id guidelineid drugid implications drugrecommendation classification '
                       'phenotypes activityscore allelestatus lookupkey population comments'),
    'publication': 'id guidelineid title authors year pmid doi url',
}
ORDER = {'pair': 'pairid', 'drug': 'drugid', 'guideline': 'id',
         'recommendation': 'id', 'publication': 'id'}
JSON_FIELDS = {'implications', 'phenotypes', 'activityscore', 'allelestatus', 'lookupkey'}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ApiClient:
    """GET only; exact counts detect truncation, not transaction consistency."""
    def __init__(self, opener=urlopen, page_size=500):
        if page_size < 1:
            raise ValueError('page size must be positive')
        self.opener = opener
        self.page_size = page_size

    def fetch_table(self, table):
        columns = COLUMNS[table].replace(' ', ',')
        rows, evidence, offset, expected = [], [], 0, None
        while True:
            params = {'select': columns, 'order': ORDER[table] + '.asc',
                      'limit': self.page_size, 'offset': offset}
            if table == 'publication':
                params['guidelineid'] = 'not.is.null'
            url = BASE_URL + table + '?' + urlencode(params)
            request = Request(url, headers={'Accept': 'application/json', 'Prefer': 'count=exact',
                                           'User-Agent': 'cpic-guideline-tracker/1'})
            with self.opener(request, timeout=45) as response:
                body = response.read()
                content_range = response.headers.get('Content-Range', '')
            page = json.loads(body)
            if not isinstance(page, list) or not all(isinstance(r, dict) for r in page):
                raise ValueError(f'{table}: expected an array of objects')
            match = re.fullmatch(r'(?:(\d+)-(\d+)|\*)/(\d+)', content_range)
            if not match:
                raise ValueError(f'{table}: missing exact Content-Range count')
            total = int(match[3])
            if expected is not None and expected != total:
                raise ValueError(f'{table}: count changed during download; discard and retry later')
            expected = total
            if page:
                if match[1] is None or int(match[1]) != offset or int(match[2]) != offset + len(page) - 1:
                    raise ValueError(f'{table}: inconsistent page range')
            elif total != offset:
                raise ValueError(f'{table}: empty page before all rows received')
            evidence.append({'url': url, 'retrieved_at': utc_now(), 'content_range': content_range,
                             'sha256': hashlib.sha256(body).hexdigest(), 'rows': len(page)})
            rows.extend(page)
            offset += len(page)
            if offset > total:
                raise ValueError(f'{table}: received more rows than advertised')
            if offset == total:
                return rows, evidence

    def fetch_all(self):
        data, evidence = {}, []
        for table in COLUMNS:
            data[table], pages = self.fetch_table(table)
            evidence.extend(pages)
        return data, evidence


def _copy_value(value):
    if value == r'\N':
        return None
    escapes = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '\\': '\\'}
    # PostgreSQL COPY text encoding, including octal and hex sequences.
    def decode(match):
        token = match[1]
        if token.startswith('x'):
            return chr(int(token[1:], 16))
        if token[0] in '01234567':
            return chr(int(token, 8))
        return escapes.get(token, token)
    return re.sub(r'\\(x[0-9A-Fa-f]{1,2}|[0-7]{1,3}|.)', decode, value)


def _typed(column, value):
    if value is None:
        return None
    if column in {'id', 'pairid', 'guidelineid', 'year'}:
        return int(value)
    if column in {'removed', 'usedforrecommendation'}:
        if value not in {'t', 'f'}:
            raise ValueError('invalid boolean in release')
        return value == 't'
    if column in JSON_FIELDS:
        return json.loads(value)
    if column in {'genes', 'authors'}:
        if not value.startswith('{') or not value.endswith('}'):
            raise ValueError('invalid text array in release')
        return next(csv.reader([value[1:-1]], escapechar='\\')) if value != '{}' else []
    return value


def read_release(path, require_all=True):
    """Parse selected COPY blocks as data. Never execute SQL or start a database."""
    data, table, seen, in_copy = {}, None, set(), False
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            match = re.match(r'COPY cpic\.(\w+) \(([^)]+)\) FROM stdin;', line)
            if match:
                if in_copy:
                    raise ValueError('new COPY header before previous block terminator')
                in_copy = True
                table = match[1] if match[1] in COLUMNS else None
                columns = match[2].split(', ')
                if table:
                    if table in seen:
                        raise ValueError('duplicate COPY block: ' + table)
                    if not set(COLUMNS[table].split()).issubset(columns):
                        raise ValueError('release schema missing columns: ' + table)
                    seen.add(table)
                    data[table] = []
            elif line == '\\.\n':
                table = None
                in_copy = False
            elif table:
                values = line.rstrip('\n').split('\t')
                if len(values) != len(columns):
                    raise ValueError('invalid COPY row: ' + table)
                raw = dict(zip(columns, values))
                row = {c: _typed(c, _copy_value(raw[c])) for c in COLUMNS[table].split()}
                if table != 'publication' or row['guidelineid'] is not None:
                    data[table].append(row)
    if in_copy or (require_all and set(data) != set(COLUMNS)):
        raise ValueError('incomplete release export')
    return data
