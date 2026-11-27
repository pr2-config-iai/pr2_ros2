"""The computer monitors of one PR2 computer, as in ROS 1 pr2_bringup/pr2.launch (c1) and
pr2-c2.launch (c2): pr2_computer_monitor's ntp_monitor, cpu_monitor and hd_monitor (D44).

pr2.launch.py includes this with computer:=c1 and c2.launch.py with computer:=c2. By hand, in that
computer's container:

    ros2 launch pr2_ros2_bringup computer_monitor.launch.py computer:=c1

Differences from ROS 1 (D44):
- ntp_monitor reads the output of ntpsec's ntpdate (Ubuntu 24.04).
- cpu_monitor has mpstat (sysstat), which ROS 1 lacked, so CPU usage is checked; c2's num_cores is
  32 (ROS 1: 12, but c2 has 32 cores).
- hd_monitor reads the drive temperatures from the kernel's hwmon sensors instead of an hddtemp
  daemon.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node

# Per computer: (ntp_monitor's node name and arguments, cpu_monitor's and hd_monitor's node names, num_cores)
COMPUTERS = {
    'c1': {
        'ntp': ('ntp_c1', ['0.de.pool.ntp.org', '--offset-tolerance', '50000', '--diag-hostname=c1']),
        'cpu': 'realtime_cpu_monitor',
        'hd': 'realtime_hd_monitor',
        'num_cores': 32.0,
    },
    'c2': {
        'ntp': ('ntp_c2', ['c1', '--diag-hostname=c2']),
        'cpu': 'realtime_cpu_monitor_c2',
        'hd': 'realtime_hd_monitor_c2',
        'num_cores': 32.0,
    },
}


def monitors(context):
    computer = LaunchConfiguration('computer').perform(context)
    if computer not in COMPUTERS:
        raise RuntimeError(f"computer must be one of {', '.join(COMPUTERS)}, not '{computer}'")
    c = COMPUTERS[computer]
    ntp_name, ntp_args = c['ntp']
    return [
        Node(package='pr2_computer_monitor', executable='ntp_monitor.py', name=ntp_name, arguments=ntp_args),
        Node(package='pr2_computer_monitor', executable='hd_monitor.py', name=c['hd'],
             arguments=[EnvironmentVariable('HOME', default_value='/home'), f'--diag-hostname={computer}']),
        Node(package='pr2_computer_monitor', executable='cpu_monitor.py', name=c['cpu'],
             arguments=[f'--diag-hostname={computer}'],
             parameters=[{
                 'check_core_temps': False,
                 'check_ipmi_tool': False,
                 'enforce_clock_speed': False,
                 'num_cores': c['num_cores'],
             }]),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('computer', description='c1 or c2'),
        OpaqueFunction(function=monitors),
    ])
