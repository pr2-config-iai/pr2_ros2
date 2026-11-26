"""Base and tilt Hokuyo lasers. Port of the urg_node part of pr2_bringup/pr2-c2.launch.

The lasers are USB-attached to c2 (pr2b), so this must run on c2. The host's
/etc/ros/sensors symlinks are reachable inside distrobox under /run/host.
EtherCAT is not needed; without it the tilt laser simply does not tilt.

The tilt laser was not used with ROS 1, so its driver only starts with tilt_laser:=true.

    ros2 launch pr2_ros2_bringup hokuyos.launch.py   # on c2, in the ubuntu2404b container
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

SENSORS = '/run/host/etc/ros/sensors'


def generate_launch_description():
    base_port = LaunchConfiguration('base_port')
    tilt_port = LaunchConfiguration('tilt_port')

    return LaunchDescription([
        DeclareLaunchArgument('base_port', default_value=f'{SENSORS}/base_hokuyo'),
        DeclareLaunchArgument('tilt_port', default_value=f'{SENSORS}/tilt_hokuyo'),
        DeclareLaunchArgument('tilt_laser', default_value='false',
                              description='Also start the tilt laser driver (unused with ROS 1)'),

        Node(
            package='urg_node', executable='urg_node_driver', name='base_hokuyo_node',
            output='screen',
            remappings=[('scan', 'base_scan')],
            parameters=[{
                'serial_port': base_port,
                'laser_frame_id': 'base_laser_link',  # ROS 1 param was 'frame_id'
                'angle_min': -2.2689,
                'angle_max': 2.2689,
                'publish_intensity': False,
            }],
        ),
        Node(
            package='urg_node', executable='urg_node_driver', name='tilt_hokuyo_node',
            condition=IfCondition(LaunchConfiguration('tilt_laser')),
            output='screen',
            remappings=[('scan', 'tilt_scan')],
            parameters=[{
                'serial_port': tilt_port,
                'laser_frame_id': 'laser_tilt_link',
                'angle_min': -0.829,
                'angle_max': 0.829,
                'publish_intensity': True,
            }],
        ),
    ])
