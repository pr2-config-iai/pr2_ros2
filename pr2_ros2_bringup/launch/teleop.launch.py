"""Joystick teleop of the base, like IAI's ROS 1 pr2_teleop_joy_ds4.launch (base part): a DS4 on
/dev/input/js0 through joy_linux, L1 deadman, R1 run, right stick translates, left stick turns,
L2 (head button) holds the base at 0.
Publishes on /base_controller/command (needs base_controller running)."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('joy_dev', default_value='/dev/input/js0'),
        Node(
            package='joy_linux',
            executable='joy_linux_node',
            name='joy',
            # As ROS 1's joy_node in pr2_bringup/pr2.launch: deadzone 0.12, autorepeat 10 Hz.
            parameters=[{'dev': LaunchConfiguration('joy_dev'), 'deadzone': 0.12, 'autorepeat_rate': 10.0}],
            output='screen'),
        Node(
            package='pr2_ros2_bringup',
            executable='pr2_teleop_base.py',
            remappings=[('cmd_vel', '/base_controller/command')],
            output='screen'),
    ])
