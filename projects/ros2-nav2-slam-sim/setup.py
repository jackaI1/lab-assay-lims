from glob import glob
from setuptools import setup

setup(
    name='lab_patrol', version='0.1.0', packages=['lab_patrol'],
    data_files=[('share/ament_index/resource_index/packages', ['resource/lab_patrol']),
                ('share/lab_patrol', ['package.xml']),
                *[(f'share/lab_patrol/{folder}', glob(f'{folder}/*'))
                  for folder in ['launch', 'config', 'worlds', 'models/lab_bot']]],
    install_requires=['setuptools', 'PyYAML'], tests_require=['pytest'],
    zip_safe=True, maintainer='Jack Lai', maintainer_email='jacklai1132@gmail.com',
    description='Test-lab mapping, localization and patrol evaluation', license='Apache-2.0',
    entry_points={'console_scripts': ['patrol = lab_patrol.waypoints:main',
                                     'pose_logger = lab_patrol.pose_logger:main']},
)
