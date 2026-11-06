"""Check actual native drawing metadata and terminal-to-terminal conductors."""
import collections
import xml.etree.ElementTree as ET
from .calculator import InputError


def audit_qet(data, text):
    root=ET.fromstring(text)
    diagrams=root.findall('diagram')
    if len(diagrams)!=len(data['sheets']): raise InputError('drawing sheet count differs')
    components={c['tag']:c for c in data['components']}
    all_seen=set()
    for sheet,diagram in zip(data['sheets'],diagrams):
        if diagram.get('title')!=sheet['title']: raise InputError('sheet title differs')
        instances={i['id']:i for i in sheet['instances']}
        pin_map={};uuid_pins={};found=set()
        for e in diagram.findall('./elements/element'):
            meta={v.get('name'):v.text for v in e.findall('./elementInformations/elementInformation')}
            id=meta.get('machine_id')
            if not id: raise InputError('element without machine_id')
            # Annotation and mechanical-layout objects are also checked below.
            if id in found: raise InputError('duplicate drawing id')
            found.add(id)
            tag=meta.get('label')
            if tag in components:
                c=components[tag];all_seen.add(tag)
                for k in ('part','heat_w','sccr_ka','scope','quantity'):
                    if meta.get(k)!=str(c[k]): raise InputError(f'{id}: drawing {k} disagrees with calculation input')
            if id not in instances: continue
            i=instances[id]
            if (float(e.get('x')),float(e.get('y')))!=(i['x'],i['y']): raise InputError('drawing position differs: '+id)
            if tag!=(i['tag'] or id): raise InputError('drawing component tag differs')
            terms=e.findall('./terminals/terminal')
            if len(terms)!=len(i['pins']): raise InputError('drawing pin count differs')
            expected_pins={(p['x']+(4 if p['side']=='left' else -4),p['y']):p for p in i['pins']}
            for term in terms:
                position=(float(term.get('x')),float(term.get('y')))
                if position not in expected_pins: raise InputError('drawing terminal moved')
                pin=expected_pins.pop(position)
                if term.get('id') in pin_map: raise InputError('duplicate terminal id')
                pin_map[term.get('id')]=id+':'+pin['name']
            # Visible symbols must retain the actual part and values, not only metadata.
            path=e.get('type').replace('embed://','').split('/')
            definition=root.find(f"./collection/category[@name='{path[0]}']/element[@name='{path[1]}']/definition")
            if definition is None: raise InputError('missing embedded symbol')
            for terminal in definition.findall('./description/terminal'):
                if terminal.get('name') not in [p['name'] for p in i['pins']]: raise InputError('native terminal name differs')
                uuid_pins[(e.get('uuid'),terminal.get('uuid'))]=id+':'+terminal.get('name')
            visible=' '.join(t.get('text','') for t in definition.findall('./description/text'))
            if (i['tag'] or i['id']) not in visible and not i['label']: raise InputError('missing visible tag')
            if tag in components and sheet['number'] in (1,2):
                if components[tag]['part'].replace(' ','') not in visible.replace(' ',''): raise InputError('visible part differs')
        if not set(instances)<=found: raise InputError('missing schematic component')
        actual=[]
        for w in diagram.findall('./conductors/conductor'):
            try:
                if w.get('element1'):
                    a=uuid_pins[(w.get('element1'),w.get('terminal1'))]
                    b=uuid_pins[(w.get('element2'),w.get('terminal2'))]
                    if a.split(':',1)[1]!=w.get('terminalname1') or b.split(':',1)[1]!=w.get('terminalname2'): raise InputError('native terminal labels differ')
                else: a,b=pin_map[w.get('terminal1')],pin_map[w.get('terminal2')]
            except KeyError as ex: raise InputError('conductor references unknown pin') from ex
            actual.append((*sorted([a,b]),w.get('num')))
        expected=[(*sorted([w['a'],w['b']]),w['net']) for w in data['wires'] if w['sheet']==sheet['number']]
        if collections.Counter(actual)!=collections.Counter(expected): raise InputError('drawing wire endpoints/net labels disagree')
    drawn_required={c['tag'] for c in data['components'] if c['kind'] not in ('allowance','mechanical')}
    if not drawn_required<=all_seen: raise InputError('BOM component missing from drawing')
    return dict(sheets=len(diagrams),conductors=len(data['wires']),components=len(all_seen))
