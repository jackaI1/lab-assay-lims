"""Conservative exact phenotype lookup. No genotype or activity-score inference."""
from .source import BASE_URL


def _normal(value):
    return value.strip().casefold()


def _normalized_map(values):
    normalized = {}
    for key, value in values.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError('gene maps must contain text keys and values')
        gene = _normal(key)
        if not gene or gene in normalized:
            raise ValueError('duplicate or empty normalized gene key')
        normalized[gene] = _normal(value)
    return normalized


def lookup(snapshot, drug, phenotypes, population=None):
    tables = snapshot['tables']
    query = _normalized_map(phenotypes)
    if not query or any(not k or not v for k, v in query.items()):
        raise ValueError('provide non-empty gene=phenotype values')
    drugs = [d for d in tables['drug'] if _normal(drug) in {_normal(d['name']), _normal(d['drugid'])}]
    no = {'status': 'no guideline',
          'reason': 'No exact supported phenotype guideline in this snapshot for the supplied inputs. '
                    'No gene, allele status, activity score or population was inferred.',
          'snapshot_captured_at': snapshot['captured_at']}
    if len(drugs) != 1:
        return no
    did = drugs[0]['drugid']
    candidates = []
    for row in tables['recommendation']:
        if row['drugid'] != did:
            continue
        # The phenotype map alone may conceal activity-score or allele requirements.
        # Only rows explicitly keyed by exactly the supplied phenotypes are supported.
        if (_normalized_map(row['phenotypes']) != query
                or _normalized_map(row['lookupkey']) != query
                or row['allelestatus']):
            continue
        active_genes = {_normal(p['genesymbol']) for p in tables['pair']
                        if p['drugid'] == did and p['guidelineid'] == row['guidelineid']
                        and not p['removed'] and p['usedforrecommendation']
                        and _normal(p['cpiclevel'] or '') != 'retired'}
        if not set(query).issubset(active_genes):
            continue
        if population is None or _normal(row['population']) == _normal(population):
            candidates.append(row)
    if not candidates:
        return no
    populations = sorted({r['population'] for r in candidates})
    if population is None and len(populations) > 1:
        return {'status': 'needs population', 'populations': populations,
                'reason': 'Choose an exact CPIC population; no population was inferred.'}
    matches = []
    for row in candidates:
        guideline = next(g for g in tables['guideline'] if g['id'] == row['guidelineid'])
        citations = []
        for publication in tables['publication']:
            if publication['guidelineid'] == row['guidelineid']:
                citations.append({'title': publication['title'], 'year': publication['year'],
                                  'pmid': publication['pmid'], 'doi': publication['doi'],
                                  'url': ('https://pubmed.ncbi.nlm.nih.gov/' + str(publication['pmid']) + '/'
                                          if publication['pmid'] else publication['url'] or guideline['url'])})
        matches.append({'recommendation': row['drugrecommendation'], 'comments': row['comments'],
                        'implications': row['implications'], 'classification': row['classification'],
                        'population': row['population'], 'phenotypes': row['phenotypes'],
                        'guideline_url': guideline['url'], 'guideline_notes': guideline['notesonusage'],
                        'citations': citations, 'current_api_record': BASE_URL + 'recommendation?id=eq.' + str(row['id'])})
    return {'status': 'guideline', 'drug': drugs[0]['name'],
            'snapshot_captured_at': snapshot['captured_at'], 'matches': matches,
            'snapshot_source': {k: v for k, v in snapshot['source'].items()
                                if k in {'kind', 'url', 'release_tag', 'download_sha256'}},
            'notice': 'Learning project, not clinical decision support. Read the full guideline.'}
