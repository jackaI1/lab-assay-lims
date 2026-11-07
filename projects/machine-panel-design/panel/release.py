"""Bind the visually reviewed QET PDF to the exact native file and data."""
import hashlib
import json

FILES=('data/panel.json','drawings/bottle-filler.qet','drawings/bottle-filler.pdf')

def hashes(root):
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES}

def record(root):
    from .audit import audit_qet
    data=json.loads((root/'data/panel.json').read_text())
    audit_qet(data,(root/'drawings/bottle-filler.qet').read_text())
    pdf=(root/'drawings/bottle-filler.pdf').read_bytes()
    if not pdf.startswith(b'%PDF-') or (b'QElectroTech' not in pdf and 'QElectroTech'.encode('utf-16-be') not in pdf): raise ValueError('expected a native QElectroTech PDF export')
    result=dict(revision=data['revision'],exporter='QElectroTech 0.100.0',pages=5,sha256=hashes(root))
    (root/'drawings/release.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def check(root):
    manifest=json.loads((root/'drawings/release.json').read_text())
    if manifest['sha256']!=hashes(root): raise ValueError('reviewed PDF/data/native drawing changed; re-export, inspect and run python3 -m panel release')
    return manifest
