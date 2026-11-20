"""The PR2 power board driver, as in ROS 1 /etc/ros/noetic/robot.launch (power_node2).

Publishes /power_board/state and the board's diagnostics; /power_board/control switches the three
motor breakers (used by the dashboard's breaker buttons).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('address', default_value='10.68.0.50',
                              description='IP address of the power board'),
        Node(package='pr2_power_board', executable='power_node2', name='power_board',
             parameters=[{'address': LaunchConfiguration('address')}], respawn=True),
    ])
