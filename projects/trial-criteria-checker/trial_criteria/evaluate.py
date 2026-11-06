"""Evaluate isolated rules for a fictional record; never decide trial eligibility."""
import math
from decimal import Decimal
from .parser import LAB_UNITS

# Factors convert to g/L, cells/uL, umol/L or percent respectively.
SCALES = {'hemoglobin': {'g/dL': 10, 'g/L': 1},
          'anc': {'10^9/L': 1000, 'cells/uL': 1},
          'platelets': {'10^9/L': 1000, 'cells/uL': 1},
          'creatinine': {'mg/dL': 88.4, 'umol/L': 1}, 'hba1c': {'%': 1}}


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def evaluate(row, patient):
    def result(status, reason):
        return dict(row, status=status, evaluation_reason=reason)
    rule = row['rule']
    if rule is None or row['section'] not in ('inclusion', 'exclusion'):
        return result('unknown', 'No supported complete rule')
    if not isinstance(patient, dict):
        return result('unknown', 'Patient record must be an object')
    field = rule['field']
    value = patient.get(field)
    if field == 'diagnosis':
        terms = patient.get('diagnoses')
        if not isinstance(terms, list) or any(not isinstance(t, str) for t in terms):
            return result('unknown', 'No valid diagnosis term list')
        matched = rule['value'] in {t.lower().strip() for t in terms}
        if not matched and patient.get('diagnoses_complete') is not True:
            return result('unknown', 'Missing diagnosis is not evidence of absence')
    elif field == 'sex':
        if not isinstance(value, str) or value.lower() not in ('male', 'female'):
            return result('unknown', 'No supported sex value')
        matched = value.lower() == rule['value']
    else:
        threshold = rule['value']
        if field in LAB_UNITS:
            labs = patient.get('labs')
            lab = labs.get(field) if isinstance(labs, dict) else None
            if not isinstance(lab, dict) or not valid_number(lab.get('value')):
                return result('unknown', 'Missing or invalid lab observation')
            if rule.get('timepoint') and lab.get('timepoint') != rule['timepoint']:
                return result('unknown', 'Required lab timepoint is missing or different')
            scale = SCALES[field].get(lab.get('unit')) if isinstance(lab.get('unit'), str) else None
            if scale is None:
                return result('unknown', 'Missing or incompatible unit')
            # Decimal arithmetic preserves equality at converted threshold boundaries.
            value = Decimal(str(lab['value'])) * Decimal(str(scale))
            threshold = Decimal(str(threshold)) * Decimal(str(SCALES[field][rule['unit']]))
        if field not in LAB_UNITS and not valid_number(value):
            return result('unknown', 'Missing or invalid numeric value')
        op = rule['op']
        if op == 'between':
            matched = threshold[0] <= value <= threshold[1]
        elif op == '>=':
            matched = value >= threshold
        elif op == '<=':
            matched = value <= threshold
        elif op == '>':
            matched = value > threshold
        elif op == '<':
            matched = value < threshold
        else:
            matched = value == threshold
    acceptable = matched if row['section'] == 'inclusion' else not matched
    return result('met' if acceptable else 'not met',
                  'Compared supplied evidence; exclusion conditions are inverted')
