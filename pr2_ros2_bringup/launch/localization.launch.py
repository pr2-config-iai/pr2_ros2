"""Map server and amcl, port of IAI's ROS 1 iai_pr2_bringup map.launch and amcl_node.xml (decision D36).

Runs on c2 like ROS 1's amcl (started there by c2.launch.py from pr2.launch.py). Needs the TF
odom_combined -> base_footprint, which robot_localization's ekf_node on c1 provides (pr2.launch.py),
and /base_scan. amcl publishes map -> odom_combined once it has an initial pose: set it with
RViz's "2D Pose Estimate" (/initialpose).

    ros2 launch pr2_ros2_bringup localization.launch.py [map:=<map yaml>]
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('pr2_ros2_bringup')
    return LaunchDescription([
        DeclareLaunchArgument(
            'map', default_value=PathJoinSubstitution([share, 'maps', 'pr2_apartment_map-07-09-2022.yaml']),
            description='Map yaml (default: the map of ROS 1 pr2_map_joy_amcl.launch)'),
        Node(
            package='nav2_map_server', executable='map_server', name='map_server', output='screen',
            parameters=[{'yaml_filename': LaunchConfiguration('map'), 'frame_id': 'map', 'topic_name': 'map'}]),
        Node(
            package='nav2_amcl', executable='amcl', name='amcl', output='screen',
            parameters=[PathJoinSubstitution([share, 'config', 'amcl.yaml'])]),
        # nav2 nodes are lifecycle nodes; this configures and activates them (ROS 1 nodes just ran).
        Node(
            package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager_localization',
            output='screen',
            parameters=[{'autostart': True, 'node_names': ['map_server', 'amcl']}]),
    ])
