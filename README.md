# pr2_ros2

Workspace-level repository for porting the IAI PR2 from ROS 1 Noetic to ROS 2 Jazzy.

- [`pr2_ros2.repos`](pr2_ros2.repos): the repositories and branches that make up the ROS 2 workspace.
- [`docs/decisions.md`](docs/decisions.md): the decisions we make along the way and why.
- [`pr2_ros2_bringup`](pr2_ros2_bringup): launch files for the robot (so far: the Hokuyo lasers).

The motor chain under ros2_control lives in `pr2_ethercat_drivers/pr2_ros2_control`; see its README.

## Setup

ROS 2 runs in a distrobox container on c1 (pr2a), next to ROS 1 on the host (decision D1).

```bash
mkdir -p ~/workspace/ros2_ws/src && cd ~/workspace/ros2_ws/src
git clone -b ros-jazzy-main https://github.com/pr2-config-iai/pr2_ros2.git
vcs import < pr2_ros2/pr2_ros2.repos
cd ~/workspace/ros2_ws
unset ROS_DISTRO ROS_PACKAGE_PATH   # ~/.bashrc sources ROS 1, also inside the container
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -y
colcon build
```

## Status

| Part | State |
|---|---|
| Messages (`pr2_msgs`, `pr2_controllers_msgs`) | ported |
| EtherCAT (`eml`, `ethercat_hardware`) | ported; reads the robot exactly like ROS 1 |
| ros2_control (`pr2_ros2_control`) | read-only: `/joint_states` match ROS 1 for all 45 joints |
| Calibration | uses the offsets ROS 1 stored on the boards; no ROS 2 routine yet |
| Commanding motors, controllers | next |
| Hokuyos | launch file written; they are on c2, which is not set up yet |
| IMU, cameras, F/T sensors, motorconf | not started |

## Known issues on the ROS 1 side

- **The ROS 1 realtime loop does not use the `ethercat_hardware` built in `pr2_fixes`.**
  - `pr2-grant` gives the `pr2_ethercat` copy file capabilities, so the dynamic loader ignores
    `LD_LIBRARY_PATH`.
  - The binary's RPATH only contains `/opt/ros/noetic/lib`, so it loads the stock Noetic
    `libethercat_hardware.so`.
  - Seen in ROS 1's diagnostics (2026-11-20): `Timeout (us): 20000` and `Max PD Retries: 5`,
    instead of the 5000 µs / 40 retries from the "Change timeouts" commit `e861fde`.
  - Other `pr2_fixes` libraries that `pr2_ethercat` links directly are likely affected the same
    way. Controllers are not: they are loaded by full path.
