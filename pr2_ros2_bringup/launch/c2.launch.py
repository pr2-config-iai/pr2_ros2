"""Everything of the ROS 2 port that runs on c2 (pr2b), like ROS 1's pr2_bringup/pr2-c2.launch.

pr2.launch.py on c1 starts this through pr2b_run.py (D35); by hand, in c2's container:

    ros2 launch pr2_ros2_bringup c2.launch.py [hokuyos:=true] [tilt_laser:=false] [localization:=true] [kinect:=true] \\
        [batteries:=true]

- hokuyos.launch.py: the base laser (and the tilt laser with tilt_laser:=true).
- localization.launch.py: map server and amcl (D36), as IAI's ROS 1 amcl ran on c2.
- kinect_head.launch.py: the head Kinect driver, its processing and the mode watchdog (D37).
- batteries.launch.py: the battery servers (ocean_server, D38).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def launch_file(name):
    return PathJoinSubstitution([FindPackageShare('pr2_ros2_bringup'), 'launch', name])


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('hokuyos', default_value='true', description='Start the Hokuyo drivers'),
        DeclareLaunchArgument('tilt_laser', default_value='false',
                              description='With hokuyos: also the tilt laser (unused with ROS 1)'),
        DeclareLaunchArgument('localization', default_value='true', description='Start map server and amcl'),
        DeclareLaunchArgument('kinect', default_value='true', description='Start the head Kinect'),
        DeclareLaunchArgument('batteries', default_value='true', description='Start the battery servers'),
        IncludeLaunchDescription(launch_file('hokuyos.launch.py'),
                                 launch_arguments={'tilt_laser': LaunchConfiguration('tilt_laser')}.items(),
                                 condition=IfCondition(LaunchConfiguration('hokuyos'))),
        IncludeLaunchDescription(launch_file('localization.launch.py'),
                                 condition=IfCondition(LaunchConfiguration('localization'))),
        IncludeLaunchDescription(launch_file('kinect_head.launch.py'),
                                 condition=IfCondition(LaunchConfiguration('kinect'))),
        IncludeLaunchDescription(launch_file('batteries.launch.py'),
                                 condition=IfCondition(LaunchConfiguration('batteries'))),
    ])
