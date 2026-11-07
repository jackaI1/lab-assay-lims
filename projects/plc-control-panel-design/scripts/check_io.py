#!/usr/bin/env python3
"""Check actual KiCad-exported net nodes against the pinned PLC interface."""
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def check(root=ROOT):
 errors=[]
 source=(root/'design/source-line.st').read_text()
 expected={}
 for direction,block in re.findall(r'VAR_(INPUT|OUTPUT)\s+(.*?)\s+END_VAR',source,re.S):
  for tag in re.findall(r'^\s*(\w+)\s*:\s*BOOL\s*;',block,re.M): expected[tag]=direction.lower()
 rows=list(csv.DictReader((root/'design/io.csv').read_text().splitlines()))
 for key in ('tag','plc_ref','terminal','wire'):
  vals=[r[key] for r in rows]
  if len(set(vals))!=len(vals): errors.append('duplicate '+key)
 if {r['tag']:r['direction'] for r in rows}!=expected: errors.append('I/O list differs from source interface')
 for direction in ('input','output'):
  tree=ET.parse(root/f'design/03_{direction}s.xml')
  nets={n.get('name','').lstrip('/'): {(x.get('ref'),x.get('pin')) for x in n.findall('node')} for n in tree.findall('.//nets/net')}
  components={c.get('ref'):c.findtext('value') for c in tree.findall('.//components/comp')}
  for r in (x for x in rows if x['direction']==direction):
   if components.get(r['plc_ref'])!=r['tag']: errors.append(r['tag']+': PLC channel missing or wrong')
   if not {(r['plc_ref'],'2'),(r['terminal'],'1')} <= nets.get(r['wire'],set()): errors.append(r['tag']+': wire does not join PLC and terminal')
   if (r['terminal'],'2') not in nets.get('FIELD_'+r['tag'],set()): errors.append(r['tag']+': field side missing')
 return errors
if __name__=='__main__':
 errors=check()
 print('\n'.join(errors) if errors else 'OK: 15 PLC tags connected to unique terminals and wires')
 sys.exit(bool(errors))
