"""Educational ODM/Define-style metadata; not schema-certified Define-XML."""
import xml.etree.ElementTree as ET
from .pipeline import SPEC, write_csv

ODM = 'http://www.cdisc.org/ns/odm/v1.3'
DEF = 'http://www.cdisc.org/ns/def/v2.1'
ET.register_namespace('',ODM)
ET.register_namespace('def',DEF)


def write_metadata(output):
    def child(parent, name, **attrs):
        return ET.SubElement(parent,f'{{{ODM}}}{name}',attrs)
    root = ET.Element(f'{{{ODM}}}ODM',dict(ODMVersion='1.3.2',FileOID='SYNTH01.METADATA',FileType='Snapshot',CreationDateTime='2025-01-01T00:00:00Z'))
    study = child(root,'Study',OID='SYNTH01')
    global_vars = child(study,'GlobalVariables')
    child(global_vars,'StudyName').text = 'Synthetic trial demonstration'
    child(global_vars,'StudyDescription').text = 'Fictional records; educational SDTM subset. Not a validated submission.'
    child(global_vars,'ProtocolName').text = 'SYNTH01'
    mdv = child(study,'MetaDataVersion',OID='MDV.SYNTH01',Name='Synthetic SDTM subset',Description='Define-XML-style metadata, not certified Define-XML')
    rows = []
    for d, spec in SPEC.items():
        group = child(mdv,'ItemGroupDef',OID=d,Name=d,Repeating='No' if d=='DM' else 'Yes',IsReferenceData='No',Domain=d)
        for order,(v,f) in enumerate(spec['fields'].items(),1):
            oid = f'{d}.{v}'
            child(group,'ItemRef',ItemOID=oid,OrderNumber=str(order),Mandatory='Yes' if f['required'] else 'No')
            item = child(mdv,'ItemDef',OID=oid,Name=v,DataType={'integer':'integer','float':'float','date':'date','text':'text'}[f['type']])
            child(child(item,'Description'),'TranslatedText',**{'xml:lang':'en'}).text = f['label']
            origin = ET.SubElement(item,f'{{{DEF}}}Origin',{'Type':'Derived' if any(t in f['source'] for t in ['constant',';',' if ',' minus ','compare',' + ']) else 'Collected'})
            child(child(origin,'Description'),'TranslatedText').text = f"{spec['source']}: {f['source']}"
            if f['terms']:
                child(item,'CodeListRef',CodeListOID=oid+'.CT')
                ct = child(mdv,'CodeList',OID=oid+'.CT',Name=f['label'],DataType='text')
                for term in f['terms']:
                    child(ct,'EnumeratedItem',CodedValue=term)
            rows.append(dict(domain=d,variable=v,label=f['label'],type=f['type'],required=str(f['required']),
                             source_file=spec['source'],source_derivation=f['source'],allowed_values=' | '.join(f['terms'])))
    ET.indent(root)
    ET.ElementTree(root).write(output/'define.xml',encoding='utf-8',xml_declaration=True)
    write_csv(output/'mapping_spec.csv',rows,['domain','variable','label','type','required','source_file','source_derivation','allowed_values'])
