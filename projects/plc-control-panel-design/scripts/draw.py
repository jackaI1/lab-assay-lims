#!/usr/bin/env python3
"""Generate editable KiCad schematic sheets from the documented design."""
import csv
import uuid
from pathlib import Path
P = Path(__file__).resolve().parents[1]
def ident(s): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'filling-panel/'+s))
def q(s): return '"'+str(s).replace('"', "'")+'"'
LIB='''(lib_symbols (symbol "Panel:Device" (pin_names (offset 0)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "X" (at 0 5.08 0) (effects (font (size 1 1)))) (property "Value" "Device" (at 0 -5.08 0) (effects (font (size 1 1))))
(symbol "Device_0_1" (rectangle (start -3.81 2.54) (end 3.81 -2.54) (stroke (width 0) (type default)) (fill (type background))))
(symbol "Device_1_1" (pin passive line (at -6.35 0 0) (length 2.54) (name "1" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1))))) (pin passive line (at 6.35 0 180) (length 2.54) (name "2" (effects (font (size 1 1)))) (number "2" (effects (font (size 1 1))))))))'''
class Sheet:
 def __init__(self,name,title):
  self.name=name; self.root=ident(name); self.items=[]; self.text(20,15,title)
 def text(self,x,y,t): self.items.append(f'(text {q(t)} (at {x} {y} 0) (effects (font (size 1.5 1.5)) (justify left bottom)) (uuid {ident(self.name+t)}))')
 def dev(self,ref,value,x,y,left,right):
  uid=ident(self.name+ref)
  self.items.append(f'''(symbol (lib_id "Panel:Device") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid}) (property "Reference" {q(ref)} (at {x} {y-4} 0) (effects (font (size 1 1)))) (property "Value" {q(value)} (at {x} {y+4} 0) (effects (font (size 1 1)))) (pin "1" (uuid {ident(uid+'1')})) (pin "2" (uuid {ident(uid+'2')})) (instances (project {q(self.name)} (path "/{self.root}" (reference {q(ref)}) (unit 1)))))''')
  for n,xx in [(left,x-6.35),(right,x+6.35)]:
   self.items.append(f'(label {q(n)} (at {xx} {y} 0) (effects (font (size 0.9 0.9)) (justify left bottom)) (uuid {ident(uid+n+str(xx))}))')
 def save(self): (P/'design'/f'{self.name}.kicad_sch').write_text(f'(kicad_sch (version 20231120) (generator eeschema) (uuid {self.root}) (paper "A3") {LIB} '+''.join(self.items)+')\n')
rows=list(csv.DictReader((P/'design/io.csv').open()))
for direction in ('input','output'):
 s=Sheet('03_'+direction+'s',direction.upper()+'S: PLC channel to field terminal | W = wire number')
 for i,r in enumerate(x for x in rows if x['direction']==direction):
  y=30+i*17; s.dev(r['plc_ref'],r['tag'],65,y,'PLC_'+r['tag'],r['wire']); s.dev(r['terminal'],'field terminal',155,y,r['wire'],'FIELD_'+r['tag'])
 s.text(20,195,'Equal labels are connected on this sheet. Field wiring and supply commons: see design notes.')
 s.save()
s=Sheet('01_power','01 | 120 VAC supply, disconnect and fused 24 VDC supply')
for i,(ref,val,a,b) in enumerate([('Q1','2-pole disconnect L','L_IN','L_Q'),('F1','2 A class CC','L_Q','L_F'),('PS1','24 V supply AC L','L_F','PS_INTERNAL'),('Q2','2-pole disconnect N','N_IN','N_Q'),('PS2','24 V supply AC N','N_Q','PS_INTERNAL'),('PE1','bond to enclosure','PE_IN','PE_PANEL'),('PS3','24 V supply +','PS_INTERNAL','P24'),('F2','2 A DC control','P24','P24_CTRL'),('F3','3 A DC actuators','P24','P24_ACT'),('PS4','24 V supply -','PS_INTERNAL','M24')]): s.dev(ref,val,80,30+i*16,a,b)
s.text(20,195,'Concept blocks: PS1/N/P/M are terminals of one isolated power supply, not internal connections.')
s.save()
s=Sheet('02_safety','02 | hardwired stop and actuator isolation, manual reset')
for i,(ref,val,a,b) in enumerate([('S10','E-stop NC channel 1','P24_CTRL','CH1'),('S11','E-stop NC channel 2','P24_CTRL','CH2'),('SR1','safety relay input 1','CH1','M24'),('SR2','safety relay input 2','CH2','M24'),('S1','manual reset NO','P24_CTRL','RESET'),('K11','K1 mirror NC feedback','RESET','RESET_FB'),('SR3','reset input','RESET_FB','M24'),('SR4','safety output NO','P24_CTRL','K1_COIL'),('K12','contactor coil 24 VDC','K1_COIL','M24'),('K13','contactor power NO','P24_ACT','P24_SAFE'),('K14','aux NO status','P24_CTRL','W104')]): s.dev(ref,val,80,30+i*14,a,b)
s.text(20,195,'Functional blocks: select safety relay and contactor with matching terminal diagrams before wiring.')
s.save()
s=Sheet('04_field','04 | field devices and loads; matching labels connect by name across sheets')
inputs=[('S2','Start NO'),('S3','Stop NO'),('S4','Reset NO'),('K15','K1 auxiliary NO'),('S5','Guard closed NO'),('B1','Tank level OK NO'),('B2','Bottle at fill NO'),('B3','Exit sensor NO'),('S6','Jam switch NO')]
for i,(r,(ref,val)) in enumerate(zip([x for x in rows if x['direction']=='input'],inputs)):
 s.dev(ref,val,70,30+i*16,'P24_CTRL','FIELD_'+r['tag'])
outputs=[('H1','Run lamp'),('K2','Conveyor interface relay'),('Y1','Fill valve solenoid'),('H2','Alarm lamp'),('H3','Batch done lamp'),('H4','Fill blocked lamp')]
for i,(r,(ref,val)) in enumerate(zip([x for x in rows if x['direction']=='output'],outputs)):
 s.dev(ref,val,220,30+i*16,'FIELD_'+r['tag'],'M24')
s.text(20,195,'PLC outputs source P24_SAFE; K2 switches a separately protected motor starter. Flyback suppression required.')
s.save()
