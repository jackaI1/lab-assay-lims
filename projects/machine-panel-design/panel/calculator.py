"""Conservative UL508A SB weakest-component study and enclosure heat balance.

This subset does NOT apply current-limiting/series/transformer exceptions. It
reports a study value, never a UL listing or permission to energize hardware.
"""
import math


class InputError(ValueError):
    pass


def number(value, name, minimum=0, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float,int)) or not math.isfinite(value):
        raise InputError(f'{name} must be a finite number')
    if value < minimum or (positive and value == minimum):
        raise InputError(f'{name} outside allowed range')
    return value


def validate(data):
    if data.get('revision') not in ('A','B'):
        raise InputError('unsupported revision')
    supply=data['supply'];number(supply['line_v'],'line_v',positive=True)
    number(supply['available_fault_ka'],'available_fault_ka')
    if supply['system']!='grounded-wye' or supply['phase']!=3:
        raise InputError('this breaker selection supports only grounded-wye three-phase supply')
    tags=set()
    for c in data['components']:
        if c['tag'] in tags: raise InputError('duplicate component '+c['tag'])
        tags.add(c['tag'])
        if c['scope'] not in ('power','control','earth','passive'): raise InputError('unknown SCCR scope')
        number(c['heat_w'],c['tag']+' heat');number(c['dc_load_w'],c['tag']+' DC load')
        number(c['quantity'],c['tag']+' quantity',positive=True)
        if int(c['quantity'])!=c['quantity']: raise InputError('quantity must be integral')
        for key in ('heat_source','sccr_source'):
            if c[key] not in data['sources']: raise InputError('uncited input '+c['tag'])
        if c['scope']=='power':
            number(c['sccr_ka'],c['tag']+' SCCR',positive=True)
            number(c['voltage_v'],c['tag']+' rated voltage',positive=True)
            if c['voltage_v'] < supply['line_v']: raise InputError('voltage rating too low: '+c['tag'])
            if not c['sccr_basis']: raise InputError('missing SCCR basis')
        elif c['sccr_ka'] is not None:
            raise InputError('excluded component must have null SCCR: '+c['tag'])
    t=data['thermal']
    for key in ('width_m','height_m','depth_m','k_w_m2k','air_factor'):
        number(t[key],key,positive=True)
    for key in ('ambient_c','limit_c'): number(t[key],key,minimum=-273.15)
    number(t['airflow_margin'],'airflow_margin',minimum=1)
    number(t['fan_delivered_m3h'],'fan_delivered_m3h')
    if t['source'] not in data['sources'] or t['assumptions_source'] not in data['sources']:
        raise InputError('uncited thermal method')
    if t['fan_tag'] not in tags and (t['fan_tag'] is not None or t['fan_delivered_m3h']!=0): raise InputError('fan not in BOM')
    refs={s['number']:{i['id']:i for i in s['instances']} for s in data['sheets']}
    seen=set()
    for w in data['wires']:
        for endpoint in ('a','b'):
            id,pin=w[endpoint].split(':',1)
            if id not in refs[w['sheet']] or pin not in [p['name'] for p in refs[w['sheet']][id]['pins']]:
                raise InputError('unknown wire endpoint '+w[endpoint])
        key=(w['sheet'],*sorted([w['a'],w['b']]))
        if key in seen: raise InputError('duplicate wire')
        seen.add(key)
        if w['a']==w['b']: raise InputError('wire connects pin to itself')
    for s in data['sheets']:
        ids=[i['id'] for i in s['instances']]
        if len(ids)!=len(set(ids)): raise InputError('duplicate drawing instance')
        for i in s['instances']:
            if i['tag'] is not None and i['tag'] not in tags: raise InputError('unknown drawing component')


def sccr(components, available_ka):
    candidates=[c for c in components if c['scope']=='power']
    if not candidates: raise InputError('no power circuit ratings')
    for c in candidates: number(c['sccr_ka'],c['tag']+' SCCR',positive=True)
    number(available_ka,'available fault')
    rating=min(c['sccr_ka'] for c in candidates)
    return dict(panel_ka=rating,limiting_tags=sorted(c['tag'] for c in candidates if c['sccr_ka']==rating),
                available_fault_ka=available_ka,adequate_for_assumed_fault=rating>=available_ka,
                included=[dict(tag=c['tag'],ka=c['sccr_ka'],basis=c['sccr_basis'],source=c['sccr_source']) for c in candidates],
                excluded=[dict(tag=c['tag'],reason=c['sccr_basis']) for c in components if c['scope']!='power'])


def heat_balance(loss_w, t):
    number(loss_w,'loss_w')
    for k in ('width_m','height_m','depth_m','k_w_m2k','air_factor'): number(t[k],k,positive=True)
    for k in ('ambient_c','limit_c'): number(t[k],k,minimum=-273.15)
    number(t['airflow_margin'],'airflow_margin',minimum=1)
    number(t['fan_delivered_m3h'],'fan_delivered_m3h')
    # Deliberately omit rear and bottom of a wall-mounted enclosure. This is
    # conservative exposed geometry, not a claim of IEC TR 60890 verification.
    w,h,d=t['width_m'],t['height_m'],t['depth_m']
    area=w*h+2*d*h+w*d
    conductance=area*t['k_w_m2k']
    delta=t['limit_c']-t['ambient_c']
    residual=max(0,loss_w-conductance*delta)
    flow=t['air_factor']*residual/delta if delta>0 else None
    required=flow*t['airflow_margin'] if flow is not None else None
    cooled=t['ambient_c']+loss_w/(conductance+t['fan_delivered_m3h']/t['air_factor'])
    return dict(heat_w=loss_w,exposed_area_m2=area,conductance_w_k=conductance,
                natural_rise_k=loss_w/conductance,natural_internal_c=t['ambient_c']+loss_w/conductance,
                surface_loss_at_limit_w=conductance*delta,active_cooling_w=residual,
                required_airflow_m3h=flow,required_airflow_with_margin_m3h=required,
                fan_delivered_m3h=t['fan_delivered_m3h'],fan_sufficient=required is not None and t['fan_delivered_m3h']>=required,
                fan_internal_c=cooled,mode='refrigeration required' if delta<=0 else 'ambient-air cooling',
                ambient_c=t['ambient_c'],limit_c=t['limit_c'])


def calculate(data):
    validate(data)
    # heat_w is an assembly total, never multiplied by purchase quantity.
    heat=math.fsum(c['heat_w'] for c in data['components'] if c['location']!='field')
    dc=math.fsum(c['dc_load_w'] for c in data['components'])
    return dict(revision=data['revision'],sccr=sccr(data['components'],data['supply']['available_fault_ka']),
                thermal=heat_balance(heat,data['thermal']),dc=dict(load_w=dc,load_a=dc/24,capacity_w=60,spare_w=60-dc,adequate=dc<=60),
                heat_breakdown=[dict(tag=c['tag'],watts=c['heat_w'],basis=c['heat_basis'],source=c['heat_source']) for c in data['components'] if c['location']!='field'],
                caveat='Simulation study, not a UL listing. No series-rating or current-limiting uplift. Thermal inputs include explicit allowances and typical efficiency.')
