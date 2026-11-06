"""Narrow full-criterion grammars. Unknown is the default, never a guess."""
import html
import re

DIAGNOSES = {
    'classic hairy cell leukemia', 'the variant of hairy cell leukemia',
    'acute promyelocytic leukemia', 'type 1 diabetes', 'type 2 diabetes',
    'diabetes', 'breast cancer', 'dementia',
}
LAB_NAMES = {
    'hemoglobin': 'hemoglobin', 'platelets': 'platelets',
    'absolute neutrophil count': 'anc', 'anc': 'anc',
    'creatinine': 'creatinine', 'hba1c': 'hba1c',
}
LAB_UNITS = {
    'hemoglobin': {'g/dL', 'g/L'},
    'platelets': {'10^9/L', 'cells/uL'}, 'anc': {'10^9/L', 'cells/uL'},
    'creatinine': {'mg/dL', 'umol/L'}, 'hba1c': {'%'},
}
NUM = r'\d+(?:\.\d+)?'
OP = r'(>=|<=|>|<|=|≥|≤)'
BULLET = re.compile(r'^(\s*)(?:[*•-]\s*|\d+\\?\.\s+)(.*)$')


def normalize(text):
    return re.sub(r'\s+', ' ', html.unescape(text).replace('\\', '')).strip().rstrip('.').strip()


def normalize_unit(unit):
    unit = unit.replace('µ', 'u').replace('μ', 'u').replace(' ', '')
    return {'x10^9/L': '10^9/L', '×10^9/L': '10^9/L',
            '/uL': 'cells/uL'}.get(unit, unit)


def _rule(field, op, value, unit=None):
    return dict(field=field, op=op, value=value, unit=unit)


def _parse(sentence):
    text = normalize(sentence)
    prefix = r'(?:age[d]?|adults?)\s*'
    m = re.fullmatch(prefix + OP + r'\s*(' + NUM + r')\s*years(?: old)?', text, re.I)
    if m:
        return _rule('age', {'≥': '>=', '≤': '<=', '=': '=='}.get(m[1], m[1]), float(m[2]), 'years')
    m = re.fullmatch(prefix + r'(' + NUM + r')\s*years(?: of age)? (?:or|and) older', text, re.I)
    if m:
        return _rule('age', '>=', float(m[1]), 'years')
    m = re.fullmatch(prefix + r'(' + NUM + r')\s*(?:to|-)\s*(' + NUM + r')\s*years', text, re.I)
    if m and float(m[1]) <= float(m[2]):
        return _rule('age', 'between', [float(m[1]), float(m[2])], 'years')
    m = re.fullmatch(r'(female|male)(?: participants?| subjects?| patients?)?(?: only)?', text, re.I)
    if m:
        return _rule('sex', '==', m[1].lower())
    term = re.sub(r'^(?:Patients with |Diagnosis of |A definite diagnosis of |Previously diagnosed with )', '', text, flags=re.I).lower()
    if term in DIAGNOSES:
        return _rule('diagnosis', 'contains', term)
    # This wrapper defines anemia by the threshold, rather than adding a second condition.
    text = re.sub(r'^Moderate to severe anemia \((hemoglobin .*)\)$', r'\1', text, flags=re.I)
    m = re.fullmatch(r'(' + '|'.join(LAB_NAMES) + r')\s*' + OP + r'\s*(' + NUM + r')\s*(.+?)' + r'( at screening/baseline)?', text, re.I)
    if m:
        field, op, number, unit, timepoint = m.groups()
        field = LAB_NAMES[field.lower()]
        unit = normalize_unit(unit)
        if unit in LAB_UNITS[field]:
            rule = _rule(field, {'≥': '>=', '≤': '<=', '=': '=='}.get(op, op), float(number), unit)
            if timepoint:
                rule['timepoint'] = 'screening/baseline'
            return rule
    return None


def parse_criteria(text):
    """Return every criterion sentence with exact Python string offsets and context.

    A multi-sentence or nested criterion is retained but never partially parsed.
    Headings are context, not criteria. Unknown sections cannot create rules.
    """
    blocks = []
    current = None
    section = 'unknown'
    scoped = False
    offset = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip('\r\n')
        bullet = BULLET.match(content)
        heading_text = (bullet[2] if bullet else content).strip().lstrip('#').strip().strip('*_')
        heading = re.fullmatch(r'\s*(?:key )?(inclusion|exclusion)(?: criteria)?\s*:?[ \t]*', heading_text, re.I)
        if heading:
            section = heading[1].lower()
            current = None
            scoped = bool(bullet and bullet[1])
        elif not content.strip():
            current = None
        else:
            if heading_text.rstrip().endswith(':') or re.fullmatch(r'(?:Cohort .+|.*\b(?:part|criteria))', heading_text.strip(), re.I) or content.lstrip().startswith(('**','__','#')):
                scoped = True
            if bullet:
                start = offset + bullet.start(2)
                indent = len(bullet[1].expandtabs(4))
                current = dict(start=start, end=offset+len(content), section=section, indent=indent, scoped=scoped)
                blocks.append(current)
            elif current is not None:
                current['end'] = offset + len(content)
            else:
                start = offset + len(content) - len(content.lstrip())
                if _parse(content.strip()) is None:
                    scoped = True
                current = dict(start=start, end=offset+len(content), section=section,
                               indent=len(content)-len(content.lstrip()), scoped=scoped)
                blocks.append(current)
        offset += len(line)
    base = {s: min((b['indent'] for b in blocks if b['section'] == s), default=0)
            for s in ('inclusion', 'exclusion', 'unknown')}
    rows = []
    for index, b in enumerate(blocks):
        criterion = text[b['start']:b['end']]
        context_end = b['end']
        for child in blocks[index+1:]:
            if child['section'] != b['section'] or child['indent'] <= b['indent']:
                break
            context_end = child['end']
        context = text[b['start']:context_end]
        has_children = context_end > b['end']
        pieces = list(re.finditer(r'.+?(?:[.!?](?=\s+[A-Z])|$)', criterion, re.S))
        pieces = [p for p in pieces if p[0].strip()]
        safe = b['section'] != 'unknown' and b['indent'] == base[b['section']] and len(pieces) == 1 and not b['scoped'] and not has_children
        for piece in pieces:
            raw = piece[0]
            start = b['start'] + piece.start() + len(raw)-len(raw.lstrip())
            end = b['start'] + piece.end() - (len(raw)-len(raw.rstrip()))
            sentence = text[start:end]
            rule = _parse(sentence) if safe else None
            reason = ('Supported complete criterion' if rule else
                      'Unsupported wording or contextual, nested, compound or unknown-section criterion')
            rows.append(dict(sentence=sentence, start=start, end=end, section=b['section'],
                             context=context, rule=rule, parse_reason=reason))
    return rows
