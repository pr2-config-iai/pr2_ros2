"""The gripper action servers, as ROS 1's pr2_default_controllers.launch started them: one
pr2_gripper_action node per gripper in the controller's namespace, so the action is
/r_gripper_controller/gripper_action (and l_), commanding /<ns>/command and following /<ns>/state.

The controllers (r_gripper_controller, l_gripper_controller in pr2_ros2_control's
controllers.yaml) are spawned separately; they need r_gripper_joint and l_gripper_joint in
commanded_joints.
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='pr2_gripper_action',
            executable='pr2_gripper_action',
            name='gripper_action_node',
            namespace=f'{side}_gripper_controller',
            output='screen')
        for side in ['r', 'l']
    ])
