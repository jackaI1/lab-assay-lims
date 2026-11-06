"""Start one simulator and either mapping or saved-map navigation."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('lab_patrol'))
    nav = Path(get_package_share_directory('nav2_bringup'))
    slam = Path(get_package_share_directory('slam_toolbox'))
    mapping, seed, map_file = [LaunchConfiguration(k) for k in ['mapping', 'seed', 'map']]
    common = {'use_sim_time': 'true', 'params_file': str(share / 'config/nav2.yaml'),
              'autostart': 'true', 'use_composition': 'False'}
    return LaunchDescription([
        DeclareLaunchArgument('mapping', default_value='true'),
        DeclareLaunchArgument('seed', default_value='7'),
        DeclareLaunchArgument('map', default_value='/tmp/lab-map.yaml'),
        ExecuteProcess(cmd=['gzserver', '--verbose', '--seed', seed, str(share / 'worlds/lab.world'),
                            '-s', 'libgazebo_ros_init.so', '-s', 'libgazebo_ros_factory.so'], output='log'),
        Node(package='gazebo_ros', executable='spawn_entity.py', output='log',
             arguments=['-entity', 'lab_bot', '-file', str(share / 'models/lab_bot/model.sdf'), '-z', '0.01']),
        Node(package='tf2_ros', executable='static_transform_publisher',
             arguments=['0', '0', '0.12', '0', '0', '0', 'base_link', 'laser'],
             parameters=[{'use_sim_time': True}], output='log'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(slam / 'launch/online_async_launch.py')),
             launch_arguments={'use_sim_time': 'true', 'slam_params_file': str(share / 'config/slam.yaml')}.items(),
             condition=IfCondition(mapping)),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(nav / 'launch/localization_launch.py')),
             launch_arguments={**common, 'map': map_file}.items(), condition=UnlessCondition(mapping)),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(nav / 'launch/navigation_launch.py')),
             launch_arguments=common.items()),
    ])
