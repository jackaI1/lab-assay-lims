"""Exact span and rule matching against published manually written references."""
import json
from collections import Counter
from .parser import parse_criteria


def _key(item):
    return json.dumps({k:item[k] for k in ('nct_id','start','end','section','rule')},sort_keys=True)


def score(predicted, gold):
    predictions, references = Counter(map(_key,predicted)), Counter(map(_key,gold))
    tp = sum((predictions & references).values())
    fp = sum((predictions - references).values())
    fn = sum((references - predictions).values())
    fields = sorted({i['rule']['field'] for i in predicted+gold})
    by_field = {}
    for field in fields:
        p = Counter(_key(i) for i in predicted if i['rule']['field'] == field)
        g = Counter(_key(i) for i in gold if i['rule']['field'] == field)
        hit = sum((p & g).values())
        by_field[field] = dict(gold=sum(g.values()), predicted=sum(p.values()), correct=hit,
                              precision=hit/sum(p.values()) if p else None,
                              recall=hit/sum(g.values()) if g else None)
    return dict(true_positives=tp,false_positives=fp,false_negatives=fn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                by_field=by_field,
                missed=[json.loads(k) for k in (references-predictions).elements()],
                incorrect=[json.loads(k) for k in (predictions-references).elements()])


def benchmark(snapshot, labels):
    gold, predicted = [], []
    studies = {s['protocolSection']['identificationModule']['nctId']:s for s in snapshot['studies']}
    sentence_count = unknown_count = 0
    for sample in labels['studies']:
        nct_id = sample['nct_id']
        text = studies[nct_id]['protocolSection']['eligibilityModule']['eligibilityCriteria']
        for annotation in sample['annotations']:
            if text[annotation['start']:annotation['end']] != annotation['text']:
                raise ValueError('Label no longer matches snapshot: '+nct_id)
            for rule in annotation['rules']:
                gold.append(dict(nct_id=nct_id,start=annotation['start'],end=annotation['end'],
                                 section=annotation['section'],rule=rule))
        for row in parse_criteria(text):
            sentence_count += 1
            if row['rule'] is None:
                unknown_count += 1
            else:
                predicted.append(dict(nct_id=nct_id,**{k:row[k] for k in ('start','end','section','rule')}))
    return dict(score(predicted,gold),study_count=len(labels['studies']),
                source_sentence_count=sentence_count,unparsed_sentence_count=unknown_count,
                gold_rule_count=len(gold),predicted_rule_count=len(predicted),
                method='Exact match on study, source offsets, section, field, operator, value, unit and qualifiers. Development sample, not held-out validation.')
