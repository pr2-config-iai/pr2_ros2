"""Everything of the ROS 2 port that runs on c1 (pr2a), in one launch file.

- power_board.launch.py: power board driver; releasing the e-stop switches the breakers on and
  resets the motors (pr2_run_stop_auto_restart).
- diagnostics.launch.py: diagnostic aggregator and dashboard aggregator (for rqt_pr2_dashboard).
- pr2_ros2_control's pr2_control.launch.py: the EtherCAT motor chain under ros2_control, with
  robot_state_publisher and joint_state_broadcaster. Here with commanding enabled for every joint
  that has a controller, at max_effort_fraction 1.0 (D34; the controllers' own clamps limit the
  arms, torso and head as tested).
- The controllers, each with its own spawner (a spawner stops at its first failure, so one
  uncalibrated joint does not keep the others from starting):
  r_arm_velocity_controller, l_arm_velocity_controller, torso_velocity_controller,
  head_velocity_controller (velocity references on /<name>/reference, limp until the first one),
  base_controller, base_odometry, r_gripper_controller, l_gripper_controller.
- grippers.launch.py: the gripper action servers.
- teleop.launch.py: the joystick (DS4 on /dev/input/js0): base and grippers.
- hokuyos.launch.py, on c2 (pr2b), where the lasers are plugged in: started over ssh in c2's
  container ubuntu2404b by pr2b_run.py, which stops it again with this launch (D35). Only the base
  laser by default; tilt_laser:=true adds the tilt laser.

Once every spawner has finished, a "PR2 is ready" line says so, or names the controllers that
did not start.

    ros2 launch pr2_ros2_bringup pr2.launch.py
    # one group only, e.g. for velocity_step_test.py:
    ros2 launch pr2_ros2_bringup pr2.launch.py start_controllers:=false teleop:=false \\
        commanded_joints:=head_pan_joint,head_tilt_joint max_effort_fraction:=0.6
    # read-only:
    ros2 launch pr2_ros2_bringup pr2.launch.py commanding_enabled:=false start_controllers:=false
    # without c2 (then hokuyos.launch.py can be started there by hand):
    ros2 launch pr2_ros2_bringup pr2.launch.py hokuyos:=false
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, LogInfo, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackagePrefix, FindPackageShare

BASE_JOINTS = [f'{c}_caster_{j}_joint' for c in ['bl', 'br', 'fl', 'fr'] for j in ['l_wheel', 'r_wheel', 'rotation']]
ARM_JOINTS = [f'{s}_{j}_joint' for s in ['r', 'l'] for j in ['shoulder_pan', 'shoulder_lift', 'upper_arm_roll',
                                                             'elbow_flex', 'forearm_roll', 'wrist_flex', 'wrist_roll']]
# Every joint one of the controllers below commands (all actuated joints but laser_tilt_mount_joint).
COMMANDED_JOINTS = BASE_JOINTS + ARM_JOINTS + ['torso_lift_joint', 'head_pan_joint', 'head_tilt_joint',
                                               'r_gripper_joint', 'l_gripper_joint']
CONTROLLERS = ['r_arm_velocity_controller', 'l_arm_velocity_controller', 'torso_velocity_controller',
               'head_velocity_controller', 'base_controller', 'base_odometry',
               'r_gripper_controller', 'l_gripper_controller']


def launch_file(package, name):
    return PathJoinSubstitution([FindPackageShare(package), 'launch', name])


def ready_message(spawners):
    """One event handler per spawner; after the last one has exited, log whether all succeeded."""
    exit_codes = {}

    def on_exit(name):
        def handler(event, context):
            exit_codes[name] = event.returncode
            if len(exit_codes) < len(spawners):
                return None
            failed = [n for n in CONTROLLERS if exit_codes.get(n) != 0]
            if not failed:
                return LogInfo(msg='=== PR2 is ready: all %d controllers are active. ===' % len(CONTROLLERS))
            return LogInfo(msg='=== PR2 is up, but these controllers did not start: %s (see the spawner '
                               'errors above). ===' % ', '.join(failed))
        return handler

    return [RegisterEventHandler(OnProcessExit(target_action=spawner, on_exit=on_exit(name)))
            for name, spawner in zip(CONTROLLERS, spawners)]


def generate_launch_description():
    controllers_yaml = PathJoinSubstitution([FindPackageShare('pr2_ros2_control'), 'config', 'controllers.yaml'])
    start_controllers = IfCondition(LaunchConfiguration('start_controllers'))
    spawners = [
        Node(
            package='controller_manager',
            executable='spawner',
            name=f'spawner_{name}',
            arguments=[name, '--controller-manager', '/controller_manager', '--param-file', controllers_yaml],
            condition=start_controllers,
            output='screen')
        for name in CONTROLLERS
    ]
    return LaunchDescription([
        DeclareLaunchArgument('commanding_enabled', default_value='true',
                              description='Accept effort commands (otherwise read-only, motors halted)'),
        DeclareLaunchArgument('commanded_joints', default_value=','.join(COMMANDED_JOINTS),
                              description='Comma separated joints that may be commanded (default: all with a controller)'),
        DeclareLaunchArgument('max_effort_fraction', default_value='1.0',
                              description='Extra limit on commanded efforts, as a fraction of the URDF limit'),
        DeclareLaunchArgument('start_controllers', default_value='true',
                              description='Spawn the arm, torso, head, base and gripper controllers'),
        DeclareLaunchArgument('teleop', default_value='true',
                              description='Start the joystick teleop (base and grippers)'),
        DeclareLaunchArgument('hokuyos', default_value='true',
                              description='Start hokuyos.launch.py on c2 (pr2b) over ssh'),
        DeclareLaunchArgument('tilt_laser', default_value='false',
                              description='With hokuyos: also the tilt laser (unused with ROS 1)'),
        IncludeLaunchDescription(launch_file('pr2_ros2_bringup', 'power_board.launch.py')),
        IncludeLaunchDescription(launch_file('pr2_ros2_bringup', 'diagnostics.launch.py')),
        IncludeLaunchDescription(
            launch_file('pr2_ros2_control', 'pr2_control.launch.py'),
            launch_arguments={
                'commanding_enabled': LaunchConfiguration('commanding_enabled'),
                'commanded_joints': LaunchConfiguration('commanded_joints'),
                'max_effort_fraction': LaunchConfiguration('max_effort_fraction'),
            }.items()),
        *spawners,
        *ready_message(spawners),
        IncludeLaunchDescription(launch_file('pr2_ros2_bringup', 'grippers.launch.py'), condition=start_controllers),
        IncludeLaunchDescription(launch_file('pr2_ros2_bringup', 'teleop.launch.py'),
                                 condition=IfCondition(LaunchConfiguration('teleop'))),
        ExecuteProcess(
            name='pr2b_hokuyos',
            cmd=[PathJoinSubstitution([FindPackagePrefix('pr2_ros2_bringup'), 'lib', 'pr2_ros2_bringup', 'pr2b_run.py']),
                 '--', 'ros2', 'launch', 'pr2_ros2_bringup', 'hokuyos.launch.py',
                 ['tilt_laser:=', LaunchConfiguration('tilt_laser')]],
            condition=IfCondition(LaunchConfiguration('hokuyos')),
            output='screen'),
    ])
