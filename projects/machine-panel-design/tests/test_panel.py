import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from panel.audit import audit_qet
from panel.build import build,outputs,redline,terminals
from panel.calculator import InputError,calculate,heat_balance,sccr,validate
from panel.drawing import render
from panel.simulation import FillingLine,Inputs,demo

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/panel.json').read_text())

class HandCalculations(unittest.TestCase):
    def setUp(self):self.d=copy.deepcopy(DATA)

    def test_weakest_hand_case_and_ties(self):
        # 10, 5, 5 -> 5 kA. A control-only 1 kA marking is excluded.
        cs=[dict(tag=t,scope=s,sccr_ka=v,sccr_basis='hand case',sccr_source='test') for t,s,v in [('Q','power',10),('K','power',5),('OL','power',5),('PLC','control',1)]]
        r=sccr(cs,4);self.assertEqual(r['panel_ka'],5);self.assertEqual(r['limiting_tags'],['K','OL']);self.assertTrue(r['adequate_for_assumed_fault'])

    def test_low_interrupt_rating_caps_panel(self):
        cs=copy.deepcopy(self.d['components']);next(c for c in cs if c['tag']=='Q2')['sccr_ka']=3
        self.assertEqual(sccr(cs,4)['panel_ka'],3);self.assertFalse(sccr(cs,4)['adequate_for_assumed_fault'])

    def test_fault_equal_rating_is_adequate(self):
        self.assertTrue(sccr(self.d['components'],5)['adequate_for_assumed_fault']);self.assertFalse(sccr(self.d['components'],5.01)['adequate_for_assumed_fault'])

    def test_area_heat_and_fan_hand_case(self):
        # W=.4 H=.6 D=.2 -> A=.24+.24+.08=.56; kA=3.08.
        # Q=30.8 W -> rise=10 K. 40->45 C: surface=15.4,
        # residual=15.4; V=3.1*15.4/5=9.548; *1.25=11.935.
        t=self.d['thermal'];r=heat_balance(30.8,t)
        for key,value in [('exposed_area_m2',.56),('conductance_w_k',3.08),('natural_rise_k',10),('natural_internal_c',50),('active_cooling_w',15.4),('required_airflow_m3h',9.548),('required_airflow_with_margin_m3h',11.935)]:self.assertAlmostEqual(r[key],value,places=8)

    def test_passive_cooling_needs_no_fan(self):
        r=heat_balance(3.08,self.d['thermal']);self.assertEqual(r['required_airflow_m3h'],0);self.assertEqual(r['active_cooling_w'],0)

    def test_equal_ambient_requires_refrigeration(self):
        self.d['thermal']['ambient_c']=45;r=heat_balance(30,self.d['thermal']);self.assertIsNone(r['required_airflow_m3h']);self.assertEqual(r['active_cooling_w'],30);self.assertFalse(r['fan_sufficient'])

    def test_hotter_ambient_includes_heat_gain(self):
        self.d['thermal']['ambient_c']=50;r=heat_balance(30,self.d['thermal']);self.assertAlmostEqual(r['active_cooling_w'],45.4);self.assertIsNone(r['required_airflow_m3h'])

    def test_supplied_design_hand_totals(self):
        r=calculate(self.d)
        self.assertAlmostEqual(r['thermal']['heat_w'],34.8934666667)
        self.assertAlmostEqual(r['thermal']['fan_internal_c'],44.2339810031)
        self.assertAlmostEqual(r['dc']['load_w'],19.2568)
        self.assertEqual(r['sccr']['limiting_tags'],['K1','OL1'])

    def test_terminal_purchase_quantity_does_not_multiply_assembly_heat(self):
        a=calculate(self.d)['thermal']['heat_w'];next(c for c in self.d['components'] if c['tag']=='X2')['quantity']=26
        self.assertEqual(calculate(self.d)['thermal']['heat_w'],a)

    def test_full_load_supply_efficiency_hand_case(self):
        ps=next(c for c in self.d['components'] if c['tag']=='PS1');self.assertAlmostEqual(ps['heat_w'],60/.9-60)

class InvalidInputs(unittest.TestCase):
    def setUp(self):self.d=copy.deepcopy(DATA)
    def test_missing_power_rating_is_error(self):
        self.d['components'][0]['sccr_ka']=None
        with self.assertRaises(InputError):calculate(self.d)
    def test_nonfinite_negative_or_bool_heat_rejected(self):
        for v in [float('nan'),float('inf'),-1,True]:
            with self.subTest(v=v):
                self.d['components'][0]['heat_w']=v
                with self.assertRaises(InputError):calculate(self.d)
    def test_zero_enclosure_dimension_rejected(self):
        self.d['thermal']['width_m']=0
        with self.assertRaises(InputError):calculate(self.d)
    def test_wrong_supply_system_rejected(self):
        self.d['supply']['system']='delta'
        with self.assertRaises(InputError):calculate(self.d)
    def test_insufficient_voltage_rejected(self):
        self.d['components'][0]['voltage_v']=120
        with self.assertRaises(InputError):calculate(self.d)
    def test_unknown_source_rejected(self):
        self.d['components'][0]['heat_source']='missing'
        with self.assertRaises(InputError):calculate(self.d)
    def test_duplicate_component_rejected(self):
        self.d['components'].append(self.d['components'][0])
        with self.assertRaises(InputError):calculate(self.d)
    def test_unknown_scope_rejected(self):
        self.d['components'][0]['scope']='ignored'
        with self.assertRaises(InputError):calculate(self.d)
    def test_control_rating_must_be_explicitly_excluded(self):
        next(c for c in self.d['components'] if c['tag']=='A1')['sccr_ka']=5
        with self.assertRaises(InputError):calculate(self.d)
    def test_unknown_terminal_rejected(self):
        self.d['wires'][0]['b']='Q0:nonexistent'
        with self.assertRaises(InputError):calculate(self.d)
    def test_empty_power_circuit_rejected(self):
        with self.assertRaises(InputError):sccr([],1)

class DrawingAgreement(unittest.TestCase):
    def setUp(self):self.text,_=render(DATA)
    def test_native_has_five_sheets_and_real_conductors(self):
        r=audit_qet(DATA,self.text);self.assertEqual(r['sheets'],5);self.assertEqual(r['conductors'],79)
    def test_changed_drawing_heat_is_detected(self):
        root=ET.fromstring(self.text);root.find('.//elementInformation[@name="heat_w"]').text='999'
        with self.assertRaisesRegex(InputError,'heat_w'):audit_qet(DATA,ET.tostring(root,encoding='unicode'))
    def test_changed_drawing_sccr_is_detected(self):
        root=ET.fromstring(self.text);root.find('.//elementInformation[@name="sccr_ka"]').text='100'
        with self.assertRaisesRegex(InputError,'sccr_ka'):audit_qet(DATA,ET.tostring(root,encoding='unicode'))
    def test_changed_wire_endpoint_is_detected(self):
        root=ET.fromstring(self.text);w=root.find('./diagram/conductors/conductor');w.set('terminal2','2')
        with self.assertRaises(InputError):audit_qet(DATA,ET.tostring(root,encoding='unicode'))
    def test_missing_wire_is_detected(self):
        root=ET.fromstring(self.text);cs=root.find('./diagram/conductors');cs.remove(cs[0])
        with self.assertRaises(InputError):audit_qet(DATA,ET.tostring(root,encoding='unicode'))
    def test_changed_visible_part_is_detected(self):
        root=ET.fromstring(self.text)
        for t in root.findall('./collection/category/element/definition/description/text'):
            if t.get('text')=='FAZ-C6/3-NA':t.set('text','WRONG-PART');break
        with self.assertRaises(InputError):audit_qet(DATA,ET.tostring(root,encoding='unicode'))
    def test_checked_in_reports_and_previews_are_current(self):
        build(ROOT,check=True)
    def test_stale_generated_report_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'data').mkdir()
            for name in ['panel.json','revision-a.json']:(root/'data'/name).write_text((ROOT/'data'/name).read_text())
            build(root);(root/'reports/bom.csv').write_text('stale')
            with self.assertRaisesRegex(ValueError,'bom.csv'):build(root,check=True)
    def test_every_field_terminal_has_a_connection(self):
        for t in terminals(DATA):self.assertTrue(t['connected_to'],t)
    def test_revision_keeps_failed_baseline_and_added_parts(self):
        a=json.loads((ROOT/'data/revision-a.json').read_text());r=calculate(a)
        self.assertGreater(r['thermal']['natural_internal_c'],45);self.assertFalse(r['thermal']['fan_sufficient'])
        diff=redline(a,DATA)
        for t in ['B1','EF1','F5']:self.assertIn('ADD,'+t+',component',diff)
    def test_layout_envelopes_fit_and_do_not_overlap(self):
        cs={c['tag']:c for c in DATA['components']};rect=[]
        for tag,(x,y) in DATA['layout']['placements'].items():
            w,h=cs[tag]['width_mm'],cs[tag]['height_mm'];self.assertLessEqual(x+w,400);self.assertLessEqual(y+h,600)
            for ot,ox,oy,ow,oh in rect:self.assertFalse(x<ox+ow and x+w>ox and y<oy+oh and y+h>oy,(tag,ot))
            rect.append((tag,x,y,w,h))

    def test_components_clear_cable_duct(self):
        cs={c['tag']:c for c in DATA['components']}
        for tag,(x,y) in DATA['layout']['placements'].items():
            w,h=cs[tag]['width_mm'],cs[tag]['height_mm']
            for ox,oy,ow,oh in DATA['layout']['ducts']:
                self.assertFalse(x<ox+ow and x+w>ox and y<oy+oh and y+h>oy,tag)

    def test_plc_input_burden_included(self):
        a=next(c for c in DATA['components'] if c['tag']=='A1')
        self.assertAlmostEqual(a['heat_w'],2.88+26.4*(2*.006+5*.005))
        self.assertEqual(a['heat_w'],a['dc_load_w'])

class ReleaseTests(unittest.TestCase):
    def test_review_manifest_matches_checked_in_artifacts(self):
        from panel.release import check
        check(ROOT)

    def test_changed_pdf_fails_release_check(self):
        from panel.release import record,check,FILES
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for file in FILES:
                dest=root/file;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/file).read_bytes())
            record(root)
            with (root/'drawings/bottle-filler.pdf').open('ab') as out:out.write(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):check(root)

class SequenceTests(unittest.TestCase):
    def test_fill_cycle_and_recovery(self):
        events=demo();self.assertTrue(events[0]['Y1']);self.assertTrue(events[1]['Y2']);self.assertFalse(events[1]['Y1']);self.assertEqual(events[3]['bottles'],1);self.assertEqual(events[5]['state'],'fault');self.assertEqual(events[6]['state'],'idle')
    def test_each_hardwired_inhibit_removes_outputs(self):
        for fault in [Inputs(stop_ok=False),Inputs(enable_ok=False),Inputs(overload=True)]:
            line=FillingLine();line.step(0,Inputs(start=True,feedback=True));out=line.step(.1,fault)
            self.assertFalse(out['Y1'] or out['Y2'] or out['Y3'])
    def test_reset_does_not_restart(self):
        l=FillingLine();l.step(0,Inputs(stop_ok=False));r=l.step(0,Inputs(reset=True));self.assertEqual(r['state'],'idle');self.assertFalse(r['Y1'])
    def test_held_start_cannot_restart_after_reset(self):
        l=FillingLine();l.step(0,Inputs(start=True,feedback=True));l.step(0,Inputs(start=True,stop_ok=False));r=l.step(0,Inputs(start=True,reset=True));self.assertEqual(r['state'],'fault')
    def test_lost_bottle_aborts_fill(self):
        l=FillingLine();l.step(0,Inputs(start=True,feedback=True));l.step(0,Inputs(bottle=True));r=l.step(.1,Inputs());self.assertEqual(r['state'],'fault');self.assertFalse(r['Y2'])
    def test_missing_contactor_feedback_times_out(self):
        l=FillingLine();l.step(0,Inputs(start=True));r=l.step(.6,Inputs());self.assertEqual(r['state'],'fault');self.assertFalse(r['Y1'])
    def test_negative_or_nan_timestep_rejected(self):
        for dt in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):FillingLine().step(dt,Inputs())

if __name__=='__main__':unittest.main()
