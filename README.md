# pr2_ros2

Workspace-level repository for porting the IAI PR2 from ROS 1 Noetic to ROS 2 Jazzy.

- [`pr2_ros2.repos`](pr2_ros2.repos): the repositories and branches that make up the ROS 2 workspace.
- [`docs/decisions.md`](docs/decisions.md): the decisions we make along the way and why.
- [`pr2_ros2_bringup`](pr2_ros2_bringup): launch files and config for the robot (so far: the Hokuyo
  lasers, the power board, diagnostics and dashboard aggregation, the controllers and teleop).

## Running

On c1, in a container shell, one launch file starts everything that runs there (D34): the power
board (with the e-stop auto restart), the diagnostic and dashboard aggregators, the motor chain
with commanding enabled for every joint that has a controller (effort fraction 1.0), the arm,
torso, head, base, odometry and gripper controllers, the gripper action servers and the joystick
teleop, the odometry filter, and, over ssh on c2, the base Hokuyo (D35), map server and amcl
(D36) and the head Kinect (D37). It logs `PR2 is ready` once every controller is
active; the motors stay halted until the e-stop is released.

```bash
ros2 launch pr2_ros2_bringup pr2.launch.py
ros2 launch pr2_ros2_bringup pr2.launch.py start_controllers:=false teleop:=false \
    commanded_joints:=head_pan_joint,head_tilt_joint max_effort_fraction:=0.6   # one group, for tests
ros2 launch pr2_ros2_bringup pr2.launch.py commanding_enabled:=false start_controllers:=false  # read-only
ros2 launch pr2_ros2_bringup pr2.launch.py hokuyos:=false localization:=false kinect:=false  # without c2
ros2 launch pr2_ros2_bringup pr2.launch.py -s                 # all arguments
```

The Hokuyos are on c2, in the container `ubuntu2404b`; `pr2.launch.py` starts `c2.launch.py` there
(Hokuyos, map server, amcl, head Kinect) through ssh (`pr2b_run.py`). By hand, with `hokuyos:=false
localization:=false kinect:=false` on c1: `ros2 launch pr2_ros2_bringup c2.launch.py` on c2. The
Kinect publishes under `/kinect_head` (ROS 1's topics); its 9.8 MB point clouds reach c1 at about
3 Hz only, so use the images across machines (D37). Localization: set
the initial pose with RViz's "2D Pose Estimate"; RViz's Map display needs Durability Policy
Transient Local (D36). The dashboard runs anywhere: `ros2 run rqt_pr2_dashboard rqt_pr2_dashboard`.

The motor chain under ros2_control lives in `pr2_ethercat_drivers/pr2_ros2_control`; see its README.

## Setup

ROS 2 runs in a distrobox container on c1 (pr2a), next to ROS 1 on the host (decision D1), and in
one on c2 (pr2b), `ubuntu2404b`, for the Hokuyos (D35; it needs `ros-jazzy-urg-node`, `ros-jazzy-nav2-amcl`,
`ros-jazzy-nav2-map-server`, `ros-jazzy-nav2-lifecycle-manager`, `libfreenect-dev`,
`ros-jazzy-camera-info-manager`, `ros-jazzy-image-proc`, `ros-jazzy-depth-image-proc`,
`ros-jazzy-image-transport-plugins`, and ssh from c1 to `pr2b` without a
prompt). c1's container needs `ros-jazzy-robot-localization`. Both use the same workspace, since the home directory is shared.

`~/.bashrc` is shared with the host, and distrobox copies the host's environment into the
container. To get a clean Jazzy environment with the workspace in container shells (decisions D13,
D16), add this at the end of `~/.bashrc`, adjusting the path to the workspace:

```bash
if [ -n "$CONTAINER_ID" ] && [ -f ~/workspace/ros2_ws/src/pr2_ros2/scripts/distrobox_env.bash ]; then
  source ~/workspace/ros2_ws/src/pr2_ros2/scripts/distrobox_env.bash
fi
```

Host-only lines that fail in the container, such as sourcing ROS 1, are best wrapped in
`if [ -z "$CONTAINER_ID" ]; then ... fi`. (Already done on c1.) Then, in a new container shell:

```bash
mkdir -p ~/workspace/ros2_ws/src && cd ~/workspace/ros2_ws/src
git clone -b ros-jazzy-main https://github.com/pr2-config-iai/pr2_ros2.git
vcs import < pr2_ros2/pr2_ros2.repos
cd ~/workspace/ros2_ws
rosdep install --from-paths src --ignore-src -y
colcon build
src/pr2_ethercat_drivers/pr2_ros2_control/tools/install_pr2_rt.sh   # once: realtime launcher (D11), needs sudo
```

## Status

| Part | State |
|---|---|
| Messages (`pr2_msgs`, `pr2_controllers_msgs`) | ported |
| EtherCAT (`eml`, `ethercat_hardware`) | ported; reads the robot exactly like ROS 1 |
| ros2_control (`pr2_ros2_control`) | `/joint_states` match ROS 1 for all 45 joints; velocity as ROS 1 by default, over N samples optional (D22, D27); velocity control of both arms (30 % effort), torso and head (60 %) with WG's trajectory gains (D27 to D31); the base controller and odometry ported from ROS 1, joystick teleop (D32); the gripper controllers and action servers ported from ROS 1, joystick open and close (D33); one launch starts all controllers, action servers and the joystick (D34) |
| Calibration | uses the offsets ROS 1 stored on the boards; no ROS 2 routine yet |
| Commanding motors, controllers | gated effort commanding (D20); right wrist under velocity control verified with provisional gains (D23); controllers restarted before halted motors are released, as ROS 1 (D26, verified with all controllers in D34); the velocity controllers start at zero velocity and hold zero velocity 0.2 s after the last reference (D40); ROS 1's trajectory controllers and `point_head_action` not needed (D39) |
| Dashboard (`rqt_pr2_dashboard`, aggregators) | ported; motors and diagnostics live, breakers and runstops from the power board, battery from `power_monitor` (D38) |
| Hokuyos | base laser running on c2, started from `pr2.launch.py`, diagnostics in Lasers (D35); tilt laser driver optional (`tilt_laser:=true`), `laser_tilt_controller` not ported |
| Power board | ported (`power_board.launch.py`); state, diagnostics and the dashboard breaker buttons verified; releasing the e-stop switches the breakers on and resets the motors (`pr2_run_stop_auto_restart`), verified: all motor boards OK, motors halted |
| Localization | map server and amcl (nav2) on c2, ROS 1's map and parameters; robot_localization EKF on c1 in place of robot_pose_ekf, odometry only (D36) |
| Head Kinect (`freenect_stack`, on c2) | ported, with rgbd_launch's processing and ROS 1's settings and watchdog, started from `pr2.launch.py`; registered point cloud at 10 Hz with the `depth_image_proc` fix of our `image_pipeline` fork (D37); no calibration (as ROS 1) |
| Batteries (`ocean_battery_driver` on c2, `power_monitor` on c1) | ported, started from `pr2.launch.py`; all 4 IBPS and their diagnostics in Power System, `power_state` from the advanced estimator (D38); port 3 reports no batteries (as it would in ROS 1) |
| IMU (`microstrain_3dmgx2_imu`), other cameras, F/T sensors, motorconf | not started |

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
