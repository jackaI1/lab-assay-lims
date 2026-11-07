import csv
import io
import json
from pathlib import Path
from .calculator import calculate
from .drawing import render


def csv_text(rows, fields):
    f=io.StringIO(newline='');w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows);return f.getvalue()


def terminals(data):
    result=[]
    for s in data['sheets']:
        for i in s['instances']:
            if i['tag'] not in ('X0','X1','X2','PE'): continue
            for p in i['pins']:
                ep=i['id']+':'+p['name']
                connections=[w for w in data['wires'] if w['sheet']==s['number'] and ep in (w['a'],w['b'])]
                result.append(dict(strip=i['tag'],terminal=p['name'],sheet=s['number'],side=p['side'],
                    nets='; '.join(w['net'] for w in connections),
                    connected_to='; '.join(w['b'] if w['a']==ep else w['a'] for w in connections),
                    conductor='14 AWG Cu' if i['tag'] in ('X0','X1','PE') else '18 AWG Cu'))
    return result


def outputs(data):
    r=calculate(data);qet,svgs=render(data)
    bom=[{k:c[k] for k in ('tag','quantity','part','description','location','heat_w','heat_source','sccr_ka','sccr_basis','sccr_source')} for c in data['components']]
    out={'reports/calculations.json':json.dumps(r,indent=2,allow_nan=False)+'\n',
         'reports/bom.csv':csv_text(bom,list(bom[0])),
         'reports/layout.csv':csv_text([dict(tag=tag,x_mm=xy[0],y_mm=xy[1],width_mm=next(c['width_mm'] for c in data['components'] if c['tag']==tag),height_mm=next(c['height_mm'] for c in data['components'] if c['tag']==tag)) for tag,xy in data['layout']['placements'].items()],['tag','x_mm','y_mm','width_mm','height_mm']),
         'reports/terminals.csv':csv_text(terminals(data),['strip','terminal','sheet','side','nets','connected_to','conductor'])}
    t=r['thermal']; sc=r['sccr'];dc=r['dc']
    out['reports/calculations.md']=f'''# Revision {data['revision']} calculation record

Simulation study, not a certified panel rating. Rebuild with `python3 -m panel build`.

| Result | Value |
| --- | ---: |
| SCCR, conservative weakest component | {sc['panel_ka']:.1f} kA rms symmetrical at {data['supply']['line_v']} V |
| Limiting components | {', '.join(sc['limiting_tags'])} |
| Assumed available fault | {sc['available_fault_ka']:.1f} kA |
| Adequate for assumed fault | {sc['adequate_for_assumed_fault']} |
| Internal heat, including fan | {t['heat_w']:.3f} W |
| Exposed area (rear/bottom excluded) | {t['exposed_area_m2']:.3f} m2 |
| Natural temperature rise | {t['natural_rise_k']:.3f} K |
| Internal temperature without ventilation at {t['ambient_c']:g} C ambient | {t['natural_internal_c']:.3f} C |
| Heat to remove at {t['limit_c']:g} C target | {t['active_cooling_w']:.3f} W |
| Required delivered air flow, including 25% allowance | {t['required_airflow_with_margin_m3h']:.3f} m3/h |
| Selected fan + outlet delivered flow | {t['fan_delivered_m3h']:g} m3/h |
| Selected fan sufficient | {t['fan_sufficient']} |
| Predicted internal temperature with fan | {t['fan_internal_c']:.3f} C |
| 24 V DC load / supply capacity | {dc['load_w']:.3f} / {dc['capacity_w']:g} W |

Heat entries are assembly totals, including terminal-strip quantities. Manufacturer losses are taken at rated load without I-squared scaling; the power-supply entry uses typical full-load efficiency, not a guaranteed upper bound. External motor and valve heat is excluded, but their DC demand is included in the supply budget. See [methods and inputs](../docs/design.md) and [sources](../docs/sources.md).

## Internal heat ledger

| Tag | W | Source key |
| --- | ---: | --- |
'''+''.join(f"| {x['tag']} | {x['watts']:.3f} | {x['source']} |\n" for x in r['heat_breakdown'])
    out['docs/sources.md']='# Input sources\n\nRetrieved 2026-11-05. Values are transcribed from manufacturer publications; scenario entries are explicitly authored assumptions. Distributor links below host manufacturer-authored datasheets. No private records are used.\n\n'+''.join(f"## {k}\n\n[{v['locator']}]({v['url']})\n\n{v['note']}\n\n" for k,v in data['sources'].items())
    out['docs/sources.md']=out['docs/sources.md'].rstrip()+'\n'
    return qet,{**out,**svgs}


def redline(before, after):
    a={c['tag']:c for c in before['components']};b={c['tag']:c for c in after['components']}
    rows=[]
    for tag in sorted(a.keys()|b.keys()):
        if tag not in a: rows.append(dict(change='ADD',tag=tag,field='component',before='',after=b[tag]['part']))
        elif tag not in b: rows.append(dict(change='DELETE',tag=tag,field='component',before=a[tag]['part'],after=''))
        else:
            for key in sorted(a[tag]):
                if a[tag][key]!=b[tag][key]:rows.append(dict(change='MODIFY',tag=tag,field=key,before=a[tag][key],after=b[tag][key]))
    for k in after['thermal']:
        if before['thermal'].get(k)!=after['thermal'][k]:rows.append(dict(change='MODIFY',tag='THERMAL',field=k,before=before['thermal'].get(k),after=after['thermal'][k]))
    return csv_text(rows,['change','tag','field','before','after'])


def build(root, check=False):
    from .audit import audit_qet
    data=json.loads((root/'data/panel.json').read_text())
    qet,files=outputs(data)
    native=root/'drawings/bottle-filler.qet'
    if not native.exists():
        if check: raise ValueError('missing native drawing')
        files['drawings/bottle-filler.qet']=qet
    else:
        audit_qet(data,native.read_text())
    old=json.loads((root/'data/revision-a.json').read_text())
    baseline,old_files=outputs(old)
    files['drawings/revisions/revision-a.qet']=baseline
    files['drawings/revisions/A-to-B.csv']=redline(old,data)
    files['drawings/revisions/layout-B-redline.svg']=files['drawings/05.svg']
    # A failed passive-cooling design iteration is preserved for review.
    files['drawings/revisions/calculations-a.json']=old_files['reports/calculations.json']
    stale=[]
    for path,text in files.items():
        dest=root/path
        if check:
            if not dest.exists() or dest.read_text()!=text: stale.append(path)
        else:
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
    if check and (root/'drawings/bottle-filler.pdf').exists():
        from .release import check as check_release
        check_release(root)
    if stale: raise ValueError('stale generated files: '+', '.join(stale))
    result=audit_qet(data,(files.get('drawings/bottle-filler.qet') or native.read_text()))
    return {**result,**calculate(data)['thermal']}
