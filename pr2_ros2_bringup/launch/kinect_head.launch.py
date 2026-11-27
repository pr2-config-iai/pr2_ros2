"""The head Kinect (Kinect 360 on c2), port of IAI's ROS 1 iai_kinect_bringup.launch.

- freenect_launch's freenect.launch.py with the settings of the robot's ROS 1
  /etc/ros/noetic/freenect.launch: namespace kinect_head, the URDF's head_mount_kinect optical
  frames, the device's registration, no kinect_frames TF (the URDF has the frames), all of
  rgbd_launch's processing. image_mode 1 (SXGA) and compressedDepth png_level 2 for
  depth_registered/image_raw ("Default was 9 which chokes the framerate to 3 fps") were set on
  the ROS 1 parameter server before the launch; here they come from config/kinect_head_driver.yaml.
- kinect_mode_watchdog.py (iai_kinect_watchdog): sets image_mode back to 1 if it becomes 2.

Runs on c2, where the Kinect is plugged in (c2.launch.py, started from pr2.launch.py). By hand,
in c2's container:

    ros2 launch pr2_ros2_bringup kinect_head.launch.py
"""
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('freenect_launch'), 'launch', 'freenect.launch.py']),
            launch_arguments={
                'camera': 'kinect_head',
                'rgb_frame_id': 'head_mount_kinect_rgb_optical_frame',
                'depth_frame_id': 'head_mount_kinect_ir_optical_frame',
                'device_id': '#1',
                'depth_registration': 'true',
                'publish_tf': 'false',
                'driver_params_file': PathJoinSubstitution(
                    [FindPackageShare('pr2_ros2_bringup'), 'config', 'kinect_head_driver.yaml']),
            }.items()),
        Node(package='pr2_ros2_bringup', executable='kinect_mode_watchdog.py', name='kinect_mode_watchdog',
             output='screen'),
    ])
