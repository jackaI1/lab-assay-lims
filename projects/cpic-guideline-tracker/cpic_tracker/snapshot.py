"""Versioned, validated, write-once snapshot files."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .source import COLUMNS, ORDER, JSON_FIELDS, utc_now


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def validate_tables(tables):
    if not isinstance(tables, dict) or set(tables) != set(COLUMNS):
        raise ValueError('snapshot must contain all five source tables')
    indexes = {}
    for name, columns in COLUMNS.items():
        rows = tables[name]
        if not isinstance(rows, list) or not rows:
            raise ValueError('empty or invalid table: ' + name)
        index = {}
        for row in rows:
            if not isinstance(row, dict) or not set(columns.split()).issubset(row):
                raise ValueError('missing source columns: ' + name)
            key = row[ORDER[name]]
            expected_type = str if name == 'drug' else int
            if type(key) is not expected_type or key in index:
                raise ValueError('duplicate or null source id: ' + name)
            index[key] = row
            for field in JSON_FIELDS.intersection(row):
                if (not isinstance(row[field], dict)
                        or not all(isinstance(k, str) and isinstance(v, str)
                                   for k, v in row[field].items())):
                    raise ValueError('invalid JSON object: ' + field)
                normalized_keys = [k.strip().casefold() for k in row[field]]
                if not all(normalized_keys) or len(set(normalized_keys)) != len(normalized_keys):
                    raise ValueError('duplicate or empty normalized gene key: ' + field)
            for field in {'removed', 'usedforrecommendation'}.intersection(row):
                if type(row[field]) is not bool:
                    raise ValueError('invalid boolean: ' + field)
            required_text = {'drug': ['name'], 'pair': ['genesymbol', 'drugid'],
                             'guideline': ['name', 'url'],
                             'recommendation': ['drugid', 'drugrecommendation', 'population'],
                             'publication': []}[name]
            if any(not isinstance(row[f], str) or not row[f].strip() for f in required_text):
                raise ValueError('invalid required text in ' + name)
            for field in {'genes', 'authors'}.intersection(row):
                if (not isinstance(row[field], list)
                        or not all(isinstance(v, str) for v in row[field])):
                    raise ValueError('invalid text array: ' + field)
            if 'cpiclevel' in row and row['cpiclevel'] is not None and not isinstance(row['cpiclevel'], str):
                raise ValueError('invalid CPIC level')
        indexes[name] = index
    for row in tables['guideline']:
        url = urlparse(row['url'] or '')
        if url.scheme not in {'https', 'http'} or not url.netloc:
            raise ValueError('guideline missing source URL')
    for name in ('pair', 'recommendation', 'publication', 'drug'):
        for row in tables[name]:
            gid = row['guidelineid']
            if name == 'recommendation' and type(gid) is not int:
                raise ValueError('recommendation requires a guideline reference')
            if gid is not None and gid not in indexes['guideline']:
                raise ValueError('unknown guideline reference in ' + name)
            if name in ('pair', 'recommendation') and row['drugid'] not in indexes['drug']:
                raise ValueError('unknown drug reference in ' + name)
    return tables


def _validate_envelope(snapshot):
    if not isinstance(snapshot.get('source'), dict) or not snapshot['source'].get('kind'):
        raise ValueError('snapshot requires source provenance')
    try:
        started = datetime.fromisoformat(snapshot['started_at'])
        captured = datetime.fromisoformat(snapshot['captured_at'])
        if started.tzinfo is None or captured.tzinfo is None or captured < started:
            raise ValueError('invalid retrieval window')
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('snapshot requires a valid dated retrieval window') from error


def build_snapshot(tables, source, started_at=None):
    validate_tables(tables)
    now = utc_now()
    return {'schema_version': 1, 'started_at': started_at or now, 'captured_at': now,
            'source': source, 'tables_sha256': digest(tables), 'tables': tables}


def load_snapshot(path):
    snapshot = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(snapshot, dict):
        raise ValueError('snapshot must be an object')
    if snapshot.get('schema_version') != 1:
        raise ValueError('unsupported snapshot schema')
    _validate_envelope(snapshot)
    validate_tables(snapshot['tables'])
    if digest(snapshot['tables']) != snapshot.get('tables_sha256'):
        raise ValueError('snapshot checksum mismatch')
    return snapshot


def save_snapshot(snapshot, path):
    _validate_envelope(snapshot)
    validate_tables(snapshot['tables'])
    if digest(snapshot['tables']) != snapshot['tables_sha256']:
        raise ValueError('snapshot checksum mismatch')
    # Exclusive creation protects dated evidence from accidental overwrite.
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(snapshot, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write('\n')
