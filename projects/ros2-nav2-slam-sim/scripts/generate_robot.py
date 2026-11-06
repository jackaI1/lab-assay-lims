#!/usr/bin/env python3
"""A small differential-drive SDF robot with CPU ray lidar and encoder odometry."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def robot():
    parts = ['''<?xml version="1.0"?><sdf version="1.6"><model name="lab_bot">
<link name="base_link"><pose>0 0 0.16 0 0 0</pose>
<inertial><mass>5</mass><inertia><ixx>0.05</ixx><iyy>0.06</iyy><izz>0.08</izz></inertia></inertial>
<collision name="base"><geometry><box><size>0.32 0.24 0.12</size></box></geometry></collision>
<visual name="base"><geometry><box><size>0.32 0.24 0.12</size></box></geometry></visual>
<sensor name="lidar" type="ray"><pose>0 0 0.12 0 0 0</pose><always_on>true</always_on><update_rate>10</update_rate>
<ray><scan><horizontal><samples>360</samples><resolution>1</resolution><min_angle>-3.14159265359</min_angle><max_angle>3.14159265359</max_angle></horizontal></scan>
<range><min>0.12</min><max>12</max><resolution>0.01</resolution></range>
<noise><type>gaussian</type><mean>0</mean><stddev>0.005</stddev></noise></ray>
<plugin name="laser" filename="libgazebo_ros_ray_sensor.so"><ros><remapping>~/out:=scan</remapping></ros>
<output_type>sensor_msgs/LaserScan</output_type><frame_name>laser</frame_name></plugin></sensor></link>''']
    for side, y in [('left', 0.16), ('right', -0.16)]:
        parts.append(f'''<link name="{side}_wheel"><pose>0 {y} 0.09 1.57079632679 0 0</pose>
<inertial><mass>0.3</mass><inertia><ixx>0.001</ixx><iyy>0.001</iyy><izz>0.001</izz></inertia></inertial>
<collision name="wheel"><geometry><cylinder><radius>0.09</radius><length>0.04</length></cylinder></geometry>
<surface><friction><ode><mu>1</mu><mu2>1</mu2><fdir1>0 0 1</fdir1></ode></friction></surface></collision>
<visual name="wheel"><geometry><cylinder><radius>0.09</radius><length>0.04</length></cylinder></geometry></visual></link>
<joint name="{side}_joint" type="revolute"><parent>base_link</parent><child>{side}_wheel</child>
<axis><xyz>0 1 0</xyz><use_parent_model_frame>true</use_parent_model_frame><limit><lower>-1e16</lower><upper>1e16</upper></limit></axis></joint>''')
    for x in [-0.12, 0.12]:
        parts.append(f'''<link name="caster_{str(x).replace('-', 'm')}"><pose>{x} 0 0.05 0 0 0</pose>
<inertial><mass>0.05</mass><inertia><ixx>0.0001</ixx><iyy>0.0001</iyy><izz>0.0001</izz></inertia></inertial>
<collision name="ball"><geometry><sphere><radius>0.05</radius></sphere></geometry><surface><friction><ode><mu>0</mu><mu2>0</mu2></ode></friction></surface></collision></link>
<joint name="caster_joint_{str(x).replace('-', 'm')}" type="fixed"><parent>base_link</parent><child>caster_{str(x).replace('-', 'm')}</child></joint>''')
    parts.append('''<plugin name="drive" filename="libgazebo_ros_diff_drive.so"><update_rate>30</update_rate>
<left_joint>left_joint</left_joint><right_joint>right_joint</right_joint><wheel_separation>0.32</wheel_separation><wheel_diameter>0.18</wheel_diameter>
<max_wheel_torque>10</max_wheel_torque><max_wheel_acceleration>2</max_wheel_acceleration>
<odometry_source>0</odometry_source><publish_odom>true</publish_odom><publish_odom_tf>true</publish_odom_tf>
<odometry_frame>odom</odometry_frame><robot_base_frame>base_link</robot_base_frame></plugin>
<plugin name="truth" filename="libgazebo_ros_p3d.so"><ros><remapping>odom:=ground_truth</remapping></ros>
<body_name>base_link</body_name><frame_name>world</frame_name><update_rate>30</update_rate><gaussian_noise>0</gaussian_noise></plugin>
</model></sdf>''')
    return '\n'.join(parts) + '\n'


if __name__ == '__main__':
    (ROOT / 'models/lab_bot/model.sdf').write_text(robot())
