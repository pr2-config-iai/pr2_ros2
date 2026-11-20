"""Diagnostics and dashboard aggregation, as in ROS 1 pr2_bringup/pr2.launch.

- diag_agg (diagnostic_aggregator): /diagnostics -> /diagnostics_agg, /diagnostics_toplevel_state
- pr2_dashboard_aggregator: motors, power board, battery, wifi -> /dashboard_agg

Both feed rqt_pr2_dashboard:  ros2 run rqt_pr2_dashboard rqt_pr2_dashboard
"""
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    analyzers = PathJoinSubstitution([FindPackageShare('pr2_ros2_bringup'), 'config', 'pr2_analyzers.yaml'])
    return LaunchDescription([
        Node(package='diagnostic_aggregator', executable='aggregator_node', name='diag_agg',
             parameters=[analyzers]),
        Node(package='pr2_dashboard_aggregator', executable='dashboard_aggregator.py',
             name='pr2_dashboard_aggregator'),
    ])
