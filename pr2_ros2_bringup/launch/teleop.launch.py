"""Joystick teleop of the base and the grippers, like IAI's ROS 1 pr2_teleop_joy_ds4.launch: a DS4
on /dev/input/js0 through joy_linux.

- Base: L1 deadman, R1 run, right stick translates, left stick turns, L2 (head button) holds the
  base at 0. Publishes on /base_controller/command (needs base_controller running).
- Grippers (ROS 1 teleop_gripper, both grippers together, no deadman): button 0 opens (0.08 m),
  button 3 closes (-100), both with unlimited effort, sent with every joy message while held.
  Publishes on /r_gripper_controller/command and /l_gripper_controller/command.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    grippers = [
        Node(
            package='pr2_ros2_bringup',
            executable='pr2_teleop_gripper.py',
            name=f'teleop_gripper_{side}',
            parameters=[{'open_button': 0, 'close_button': 3}],
            remappings=[('command', f'/{prefix}_gripper_controller/command')],
            output='screen')
        for side, prefix in [('right', 'r'), ('left', 'l')]
    ]
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
    ] + grippers)
