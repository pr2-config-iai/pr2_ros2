"""Everything of the ROS 2 port that runs on c1 (pr2a), in one launch file.

- power_board.launch.py: power board driver; releasing the e-stop switches the breakers on and
  resets the motors (pr2_run_stop_auto_restart).
- diagnostics.launch.py: diagnostic aggregator and dashboard aggregator (for rqt_pr2_dashboard).
- pr2_ros2_control's pr2_control.launch.py: the EtherCAT motor chain under ros2_control, with
  robot_state_publisher and joint_state_broadcaster. Read-only unless commanding is enabled
  (decision D20); its arguments pass through, see `ros2 launch pr2_ros2_bringup pr2.launch.py -s`.

The Hokuyos are on c2: hokuyos.launch.py runs there.

    ros2 launch pr2_ros2_bringup pr2.launch.py
    ros2 launch pr2_ros2_bringup pr2.launch.py commanding_enabled:=true \\
        commanded_joints:=r_wrist_roll_joint,r_wrist_flex_joint
"""
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def include(package, launch_file):
    return IncludeLaunchDescription(PathJoinSubstitution([FindPackageShare(package), 'launch', launch_file]))


def generate_launch_description():
    return LaunchDescription([
        include('pr2_ros2_bringup', 'power_board.launch.py'),
        include('pr2_ros2_bringup', 'diagnostics.launch.py'),
        include('pr2_ros2_control', 'pr2_control.launch.py'),
    ])
