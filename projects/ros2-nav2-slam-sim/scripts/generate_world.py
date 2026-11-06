#!/usr/bin/env python3
"""Generate only static geometry, never a map for the navigation stack."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def box_model(name, x, y, w, d, h):
    return f'''<model name="{name}"><static>true</static><pose>{x} {y} {h/2} 0 0 0</pose>
<link name="body"><collision name="collision"><geometry><box><size>{w} {d} {h}</size></box></geometry></collision>
<visual name="visual"><geometry><box><size>{w} {d} {h}</size></box></geometry>
<material><ambient>0.3 0.4 0.5 1</ambient></material></visual></link></model>'''


def world():
    boxes = yaml.safe_load((ROOT / 'config/layout.yaml').read_text())['boxes']
    return '''<?xml version="1.0"?><sdf version="1.6"><world name="lab">
<gravity>0 0 -9.81</gravity><physics type="ode"><max_step_size>0.001</max_step_size>
<real_time_update_rate>1000</real_time_update_rate></physics>
<model name="floor"><static>true</static><link name="floor">
<collision name="collision"><geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry></collision>
<visual name="visual"><geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry></visual>
</link></model>''' + ''.join(box_model(f'fixture_{i}', *b) for i, b in enumerate(boxes)) + '</world></sdf>\n'


if __name__ == '__main__':
    (ROOT / 'worlds/lab.world').write_text(world())
