"""Emit native, connected QElectroTech XML and matching review SVGs.

Symbols are original functional symbols with terminal names, not imported pictures.
QET's legacy numeric terminal references remain supported by version 0.100.
"""
import html
import json
import textwrap
import uuid
import xml.etree.ElementTree as ET


def uid(key):
    return '{' + str(uuid.uuid5(uuid.NAMESPACE_URL, 'machine-panel-design/' + key)) + '}'


def node(parent, tag, **attrs):
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})


class Canvas:
    def __init__(self, parent):
        self.parent = parent
        self.svg = []

    def text(self, x, y, text, size=10, color='black'):
        node(self.parent, 'text', x=x, y=y, text=text, size=size, color=color)
        self.svg.append(f'<text x="{x}" y="{y}" font-size="{size*1.3}" fill="{color}">{html.escape(text)}</text>')

    def line(self, x1, y1, x2, y2, color='black', dash=False):
        style = f'line-style:{"dashed" if dash else "normal"};line-weight:normal;filling:none;color:{color}'
        node(self.parent, 'line', x1=x1, y1=y1, x2=x2, y2=y2, end1='none', end2='none', antialias='false', style=style)
        self.svg.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="1.3"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def rect(self, x, y, w, h, color='black'):
        node(self.parent, 'rect', x=x, y=y, width=w, height=h, antialias='false', style=f'line-style:normal;line-weight:normal;filling:none;color:{color}')
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{color}"/>')

    def ellipse(self, x, y, w, h):
        node(self.parent, 'ellipse', x=x, y=y, width=w, height=h, antialias='true', style='line-style:normal;line-weight:normal;filling:none;color:black')
        self.svg.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="none" stroke="black"/>')


def symbol(canvas, inst, component):
    w, h = inst['width'], inst['height']
    kind = inst['kind']
    canvas.rect(0, 0, w, h)
    label=inst['label'] or inst['tag'] or inst['id']
    if kind=='port':
        for j,line in enumerate(textwrap.wrap(label,17)):canvas.text(7,13+j*12,line,8)
    else:canvas.text(7,18,label,10)
    if component and kind != 'layout' and inst.get('show_caption',True):
        for i, line in enumerate(textwrap.wrap(component['part'], 24)):
            canvas.text(0, h+14+i*12, line, 7)
        if component['scope'] == 'power':
            canvas.text(0, h+42, f"{component['sccr_ka']:g} kA; {component['heat_w']:.2f} W", 7)
    for p in inst['pins']:
        left = p['side'] == 'left'
        canvas.line(p['x'], p['y'], 0 if left else w, p['y'])
        canvas.text(3 if left else w-48, p['y']-5, p['name'], 7)
    if kind in ('no', 'nc', 'switch3', 'switch2', 'overload'):
        rows = min(len([p for p in inst['pins'] if p['side']=='left']),len([p for p in inst['pins'] if p['side']=='right']))
        for j in range(rows):
            y = 42+28*j
            canvas.line(0, y, 62, y)
            canvas.line(62, y, 82, y-10)
            canvas.line(85, y, w, y)
            if kind == 'nc': canvas.line(77,y-14,87,y+2)
            if kind == 'overload': canvas.rect(61,y-8,22,15)
    if kind == 'terminal':
        for p in [p for p in inst['pins'] if p['side']=='left']: canvas.line(0,p['y'],w,p['y'])
    if kind in ('coil','valve','lamp','motor','fan'):
        canvas.ellipse(w/2-14,25,28,28)
        canvas.text(w/2-8,45,{'coil':'K','valve':'V','lamp':'X','motor':'M','fan':'F'}[kind],9)
    if kind == 'psu': canvas.text(48,54,'AC/DC',8)
    if kind == 'fuse':
        canvas.line(35,42,w-35,42);canvas.rect(52,35,26,14)


def orthogonal(points):
    result = [points[0]]
    for p in points[1:]:
        a=result[-1]
        if a[0]!=p[0] and a[1]!=p[1]: result.append([p[0],a[1]])
        if result[-1]!=p: result.append(p)
    return result


def render(data):
    root = ET.Element('project', {'title':data['title'],'version':'0.100','folioSheet':'false'})
    node(root,'properties')
    new=node(root,'newdiagrams');node(new,'border',cols=24,colsize=60,rows=13,rowsize=80,displayrows='false',displaycols='false');node(new,'inset',author='Jack Lai',folio='%id/%total')
    collection=node(root,'collection');category=node(collection,'category',name='filling-line');names=node(category,'names');node(names,'name',lang='en').text='Filling line (original functional symbols)'
    comps={c['tag']:c for c in data['components']}
    svgs={}
    for sheet in data['sheets']:
        n=sheet['number']
        diagram=node(root,'diagram',title=sheet['title'],version='0.100',cols=24,colsize=60,rows=13,rowsize=80,displayrows='false',displaycols='false',order=n,author='Jack Lai',date='2026-11-05',folio='%id/%total',filename='bottle-filler',revision=data['revision'])
        node(diagram,'defaultconductor',type='multi',color='black',num='')
        elements=node(diagram,'elements');conductors=node(diagram,'conductors')
        svg=[]; endpoints={}; tids={}; count=0
        instances=list(sheet['instances'])
        if n==5:
            for tag,(x,y) in data['layout']['placements'].items():
                c=comps[tag]
                instances.append(dict(id='LAY-'+tag,tag=tag,x=x+100,y=y+90,width=c['width_mm'],height=c['height_mm'],pins=[],kind='layout',label=tag))
            for tag,(x,y) in data['layout']['door'].items():
                c=comps[tag];instances.append(dict(id='DOOR-'+tag,tag=tag,x=x+650,y=y+150,width=30,height=30,pins=[],kind='layout',label=tag))
            for tag,(x,y) in data['layout']['side'].items():
                instances.append(dict(id='SIDE-'+tag,tag=tag,x=x+1080,y=y+90,width=117,height=117,pins=[],kind='layout',label=tag))
        # A native annotation element holds the border, notes, and mechanical drawing.
        annotation=dict(id='NOTES-'+str(n),tag=None,x=0,y=0,width=1440,height=1040,pins=[],kind='notes',label='')
        for inst in instances+[annotation]:
            name=f'{n:02d}-{inst["id"]}.elmt'
            embedded=node(category,'element',name=name)
            definition=node(embedded,'definition',type='element',version='0.100',width=max(40,inst['width']+40),height=inst['height']+100,hotspot_x=20,hotspot_y=20,orientation='dyyy')
            ns=node(definition,'names');node(ns,'name',lang='en').text=inst['id']
            node(definition,'informations').text='Original functional symbol. See data/panel.json and docs/design.md.'
            desc=node(definition,'description');c=Canvas(desc)
            if inst['kind']=='notes':
                c.text(35,38,f"BOTTLE FILLER / {n:02d} / {sheet['title']}",18)
                c.text(35,68,f"Revision {data['revision']} | Jack Lai | Simulation / engineering study | 2026-11-05",10)
                for j,text in enumerate(sheet['notes']): c.text(35,850+j*25,text,10)
                c.line(35,825,1390,825);c.text(35,1025,'Reference conductors by net name across sheets. Crossings have no junction unless they share a terminal.',9)
                if n==5:
                    c.rect(100,90,400,600);c.text(100,720,'Backplate: 400 W x 600 H; enclosure depth 200',11)
                    for y in data['layout']['rails_y']:
                        c.line(135,y+90,470,y+90,dash=True)
                    for x,y,w,h in data['layout']['ducts']: c.rect(x+100,y+90,w,h,'gray')
                    c.rect(650,90,400,600);c.text(650,720,'Door: 400 W x 600 H; bond to PE',11)
                    c.rect(1080,90,200,600);c.text(1080,720,'Side: 200 D x 600 H',11)
                    if data['revision']=='B':
                        c.text(1105,300,'EF1 OUT',11);c.text(1105,470,'EF2 OUT',11);c.text(1105,665,'B1 IN',11)
                    c.text(660,450,'Minimum reserved wiring zones:',11);c.text(660,478,'power left / DC right of centre duct',10)
                    c.text(660,506,'PS1: 40 mm top, 20 mm bottom',10)
                    c.text(660,534,'Bottom cable entry; 25 mm duct',10)

                    if data['revision']=='B':
                        c.rect(1090,500,150,160,'red');c.rect(1115,155,127,127,'red');c.rect(1115,325,127,127,'red');c.rect(390,515,28,95,'red');c.text(1090,785,'B: added fan + outlet + F5',10,'red')
            else: symbol(c,dict(inst,show_caption=n in (1,2)),comps.get(inst['tag']))
            el=node(elements,'element',x=inst['x'],y=inst['y'],type='embed://filling-line/'+name,orientation=0,uuid=uid(f'{n}/{inst["id"]}'))
            info=node(el,'elementInformations')
            meta={'label':inst['tag'] or inst['id'],'machine_id':inst['id']}
            if inst['tag']:
                comp=comps[inst['tag']]
                meta.update(part=comp['part'],heat_w=str(comp['heat_w']),sccr_ka=str(comp['sccr_ka']),scope=comp['scope'],quantity=str(comp['quantity']))
            for key,val in meta.items(): node(info,'elementInformation',name=key,show=1).text=val
            terms=node(el,'terminals');node(el,'inputs')
            for p in inst['pins']:
                orientation=3 if p['side']=='left' else 1
                # Instance x/y identify the element-side docking point, 4 units
                # inward from the definition's conductor-side terminal point.
                node(terms,'terminal',x=p['x']+(4 if orientation==3 else -4),y=p['y'],orientation=orientation,id=count)
                node(desc,'terminal',x=p['x'],y=p['y'],orientation='w' if orientation==3 else 'e',name=p['name'],uuid=uid(name+'/'+p['name']))
                key=inst['id']+':'+p['name'];endpoints[key]=[inst['x']+p['x'],inst['y']+p['y']];tids[key]=count;count+=1
            svg.append(f'<g transform="translate({inst["x"]},{inst["y"]})">'+''.join(c.svg)+'</g>')
        for wire in (w for w in data['wires'] if w['sheet']==n):
            a,b=endpoints[wire['a']],endpoints[wire['b']]
            points=orthogonal([a]+wire['via']+[b])
            con=node(conductors,'conductor',terminal1=tids[wire['a']],terminal2=tids[wire['b']],type='multi',num=wire['net'],color='black',x=0,y=0)
            for p,q in zip(points,points[1:]):
                dx,dy=q[0]-p[0],q[1]-p[1]
                if dx or dy: node(con,'segment',length=dx or dy,orientation='horizontal' if dx else 'vertical')
            path='M'+' L'.join(f'{p[0]},{p[1]}' for p in points)
            svg.append(f'<path d="{path}" fill="none" stroke="black" stroke-width="1.4"/>')
            for p in [a,b]: svg.append(f'<circle cx="{p[0]}" cy="{p[1]}" r="2.1" fill="black"/>')
            if len(points)==2:
                x=(a[0]+b[0])/2;y=a[1]-5
                svg.append(f'<text x="{x}" y="{y}" font-size="9" fill="#444">{html.escape(wire["net"])}</text>')
        svgs[f'drawings/{n:02d}.svg']='<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1040" viewBox="0 0 1440 1040"><rect width="1440" height="1040" fill="white"/><g font-family="Arial, sans-serif">'+''.join(svg)+'</g></svg>\n'
    ET.indent(root,space='  ')
    return "<?xml version='1.0' encoding='UTF-8'?>\n"+ET.tostring(root,encoding='unicode',xml_declaration=False)+'\n',svgs
