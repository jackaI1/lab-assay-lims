"""REDCap-compatible dictionary and offline repeat-instrument CSV round trip."""
from .pipeline import SPEC, QUERY_COLUMNS, day, number

REVIEW_COLUMNS = QUERY_COLUMNS + [
    'record_id', 'form_name', 'redcap_repeat_instrument',
    'redcap_repeat_instance', 'field_name', 'source_derivation',
]


def query_worklist(domains, queries):
    """Locate generated queries in pre-quarantine rows, keeping readable values.

    Source rows count CSV records starting at 2 (the header is record 1).
    Repeat instances use original domain sequence numbers, never visit numbers
    or positions in released data. This worksheet is not a REDCap query import.
    """
    result = []
    for query in queries:
        domain, variable = query['domain'], query['variable']
        row = domains[domain][int(query['source_row']) - 2]
        form = domain.lower()
        result.append(dict(
            query, record_id=row['USUBJID'], form_name=form,
            redcap_repeat_instrument='' if domain == 'DM' else form,
            redcap_repeat_instance='' if domain == 'DM' else row[domain + 'SEQ'],
            field_name=f'{form}_{variable.lower()}',
            source_derivation=SPEC[domain]['fields'][variable]['source'],
        ))
    return result

DICTIONARY_COLUMNS = [
    'Variable / Field Name','Form Name','Section Header','Field Type','Field Label',
    'Choices, Calculations, OR Slider Labels','Field Note','Text Validation Type OR Show Slider Number',
    'Text Validation Min','Text Validation Max','Identifier?','Branching Logic (Show field only if...)',
    'Required Field?','Custom Alignment','Question Number (surveys only)',
    'Matrix Group Name','Matrix Ranking?','Field Annotation',
]


def dictionary():
    def entry(name, form, label):
        row = dict.fromkeys(DICTIONARY_COLUMNS,'')
        row.update({'Variable / Field Name':name,'Form Name':form,'Field Type':'text','Field Label':label,'Required Field?':'y'})
        return row
    result = [entry('record_id','dm','Synthetic subject record ID')]
    for d, spec in SPEC.items():
        for v, f in spec['fields'].items():
            row = entry(f'{d.lower()}_{v.lower()}',d.lower(),f['label'])
            row['Required Field?'] = 'y' if f['required'] else ''
            row['Field Note'] = f"SDTM {d}.{v}; source: {f['source']}"
            if f['terms']:
                row['Field Type'] = 'dropdown'
                row['Choices, Calculations, OR Slider Labels'] = ' | '.join(f'{i}, {term}' for i,term in enumerate(f['terms'],1))
            else:
                row['Text Validation Type OR Show Slider Number'] = {'date':'date_ymd','integer':'integer','float':'number'}.get(f['type'],'')
            row['Text Validation Min'] = str(f.get('minimum',''))
            row['Text Validation Max'] = str(f.get('maximum',''))
            result.append(row)
    return result


def choices(field):
    text = field['Choices, Calculations, OR Slider Labels']
    return dict(part.strip().split(', ',1) for part in text.split('|')) if text else {}


def encode(domains, dd):
    fields = {r['Variable / Field Name']:r for r in dd}
    records = []
    for d, rows in domains.items():
        for row in rows:
            record = dict(record_id=row['USUBJID'],redcap_repeat_instrument='' if d=='DM' else d.lower(),
                          redcap_repeat_instance='' if d=='DM' else row[d+'SEQ'])
            for v, value in row.items():
                name = f'{d.lower()}_{v.lower()}'
                mapping = {label:code for code,label in choices(fields[name]).items()}
                if value and mapping and value not in mapping:
                    raise ValueError(f'Unknown choice for {name}')
                record[name] = mapping.get(value,value)
            records.append(record)
    return records


def decode(records, dd):
    byform = {}
    for field in dd:
        if field['Variable / Field Name']!='record_id':
            byform.setdefault(field['Form Name'],[]).append(field)
    result = {d:[] for d in SPEC}
    seen = set()
    for record in records:
        form = record.get('redcap_repeat_instrument','') or 'dm'
        instance = record.get('redcap_repeat_instance','')
        rid = record.get('record_id','')
        if not rid or form not in byform:
            raise ValueError('Missing record ID or unknown repeating instrument')
        if (form=='dm' and instance) or (form!='dm' and (not instance.isdigit() or int(instance)<1)):
            raise ValueError('Invalid repeat instance')
        key = (rid,form,instance)
        if key in seen:
            raise ValueError('Duplicate REDCap record/instance')
        seen.add(key)
        row = {}
        for field in byform[form]:
            name = field['Variable / Field Name']
            value = record.get(name,'')
            if not value and field['Required Field?']=='y':
                raise ValueError(f'Required REDCap value: {name}')
            opts = choices(field)
            if value and opts:
                if value not in opts:
                    raise ValueError(f'Invalid choice for {name}: {value}')
                value = opts[value]
            validation = field['Text Validation Type OR Show Slider Number']
            if value and validation=='date_ymd' and not day(value):
                raise ValueError(f'Invalid date for {name}')
            if value and validation in ['integer','number']:
                n = number(value)
                if n is None or (validation=='integer' and int(n)!=n):
                    raise ValueError(f'Invalid number for {name}')
                lo,hi = field['Text Validation Min'],field['Text Validation Max']
                if (lo and n<float(lo)) or (hi and n>float(hi)):
                    raise ValueError(f'Out of range for {name}')
            row[name[len(form)+1:].upper()] = value
        d = form.upper()
        if row['USUBJID']!=rid or row['DOMAIN']!=d or (d!='DM' and row[d+'SEQ']!=instance):
            raise ValueError('Record identity differs from SDTM identity')
        for other, fields in byform.items():
            if other!=form and any(record.get(f['Variable / Field Name'],'') for f in fields):
                raise ValueError('Fields from multiple instruments in one record')
        result[d].append(row)
    ids = {r['USUBJID'] for r in result['DM']}
    if any(r['USUBJID'] not in ids for d in result for r in result[d]):
        raise ValueError('Repeated record has no demographic record')
    return result
