"""The battery servers (Ocean Server IBPS, four ports with four batteries each), as in ROS 1
pr2_bringup/pr2-c2.launch: ocean_battery_driver's ocean_server, respawning.

Runs on c2, where the battery boards are plugged in (c2.launch.py, started from pr2.launch.py). The
ports are the host's /etc/ros/sensors/battery0-3 links, seen in c2's container under /run/host.
By hand, in c2's container:

    ros2 launch pr2_ros2_bringup batteries.launch.py

Publishes battery/server2 and battery/server for power_monitor (on c1) and the IBPS and Smart
Battery diagnostics.
"""
from launch import LaunchDescription
from launch_ros.actions import Node

SENSORS = '/run/host/etc/ros/sensors'


def generate_launch_description():
    return LaunchDescription([
        Node(package='ocean_battery_driver', executable='ocean_server', name='ocean_server', respawn=True,
             parameters=[{
                 'number_of_ports': 4,
                 **{f'port{i}': f'{SENSORS}/battery{i}' for i in range(4)},
                 'debug_level': 0,
             }]),
    ])
