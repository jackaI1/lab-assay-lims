"""Compare source content by meaning, independent of regenerated row IDs."""
import json
from urllib.parse import urlencode

from .source import BASE_URL


def _key(table, row):
    if table == 'pair':
        return (row['genesymbol'], row['drugid'])
    if table == 'recommendation':
        return (row['guidelineid'], row['drugid'], row['population'],
                json.dumps(row['lookupkey'], sort_keys=True, ensure_ascii=False))
    return (row['drugid'] if table == 'drug' else row['id'],)


def _index(table, rows):
    result = {}
    for row in rows:
        key = _key(table, row)
        if key in result:
            raise ValueError('duplicate semantic key in ' + table + ': ' + str(key))
        result[key] = row
    return result


def _content(table, row):
    if row is None:
        return None
    ignored = {'pairid'} if table == 'pair' else {'id'} if table == 'recommendation' else set()
    return {k: v for k, v in row.items() if k not in ignored}


def _sources(table, row, tables):
    if row is None:
        return []
    gid = row['id'] if table == 'guideline' else row.get('guidelineid')
    guideline = next((g for g in tables['guideline'] if g['id'] == gid), None)
    if guideline:
        return [{'label': 'Source guideline: ' + guideline['name'], 'url': guideline['url']}]
    idfield = 'pairid' if table == 'pair' else 'drugid' if table == 'drug' else 'id'
    return [{'label': 'No linked guideline; current CPIC API source record',
             'url': BASE_URL + table + '?' + urlencode({idfield: 'eq.' + str(row[idfield])})}]


def compare_snapshots(old, new):
    changes = []
    for table in ('pair', 'recommendation', 'guideline', 'drug', 'publication'):
        before = _index(table, old['tables'][table])
        after = _index(table, new['tables'][table])
        for key in sorted(before.keys() | after.keys(), key=str):
            a, b = before.get(key), after.get(key)
            ca, cb = _content(table, a), _content(table, b)
            if ca == cb:
                continue
            sources = _sources(table, a, old['tables']) + _sources(table, b, new['tables'])
            sources = [dict(t) for t in {tuple(s.items()): None for s in sources}]
            fields = sorted(k for k in (ca or {}).keys() | (cb or {}).keys()
                            if (ca or {}).get(k) != (cb or {}).get(k))
            changes.append({'table': table, 'key': list(key),
                            'kind': 'added' if a is None else 'removed' if b is None else 'changed',
                            'fields': fields, 'before': ca, 'after': cb, 'sources': sources})
    return changes


def _inline(value):
    return str(value).replace('\n', ' ').replace('[', '\\[').replace(']', '\\]')


def render_report(old, new):
    changes = compare_snapshots(old, new)
    lines = ['# CPIC snapshot change report', '',
             'Learning project, not clinical decision support. These are source-data changes, '
             'not interpretations of medical significance.', '',
             f"Before: {old['source'].get('release_tag', old['source']['kind'])}; retrieved {old['captured_at']}",
             f"After: {new['source'].get('release_tag', new['source']['kind'])}; retrieved {new['captured_at']}", '',
             f'Total changed records: {len(changes)}', '',
             '| Table | Added | Removed | Changed |', '| --- | ---: | ---: | ---: |']
    for table in ('pair', 'recommendation', 'guideline', 'drug', 'publication'):
        counts = [sum(c['table'] == table and c['kind'] == kind for c in changes)
                  for kind in ('added', 'removed', 'changed')]
        lines.append(f'| {table} | ' + ' | '.join(map(str, counts)) + ' |')
    lines += ['', 'Recommendation keys include drug, guideline, population and the full gene lookup key. '
              'A key change appears as a removal and an addition. Regenerated recommendation IDs are ignored.', '',
              'Pairs without a CPIC-linked guideline link to their source record and are labelled explicitly.', '']
    if not changes:
        lines += ['No tracked content changes.', '']
    for change in changes:
        lines += [f"## {change['kind'].capitalize()}: {change['table']} {_inline(change['key'])}", '']
        for source in change['sources']:
            lines.append(f"[{_inline(source['label'])}]({source['url']})")
        lines += ['', 'Fields: ' + ', '.join(change['fields']), '']
        for label, row in [('Before', change['before']), ('After', change['after'])]:
            # Include changed fields only for updates; full row for additions/removals.
            shown = ({f: row.get(f) for f in change['fields']} if row is not None
                     and change['kind'] == 'changed' else row)
            lines += [label + ':', '', '```json', json.dumps(shown, ensure_ascii=False,
                                                           indent=2, sort_keys=True), '```', '']
    return '\n'.join(lines)
