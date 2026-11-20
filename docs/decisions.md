# Decision log: porting the IAI PR2 to ROS 2

Decisions made while porting the PR2 drivers from ROS 1 Noetic to ROS 2 Jazzy, newest at the
bottom. Each entry says what we decided, why, what else we considered, and what follows from it.
Entries are not rewritten later; a decision that changes gets a new entry that supersedes the
old one.

Status values: **accepted**, **open** (still being discussed), **superseded by DNN**.

---

## D1: Run ROS 2 in a distrobox on c1, next to ROS 1

- **Status:** accepted (2026-11-19)
- **Context:** c1 (pr2a) runs Ubuntu 20.04 with ROS 1 Noetic and the PREEMPT_RT kernel that the
  EtherCAT loop needs. ROS 1 must stay usable while we port.
- **Decision:** ROS 2 Jazzy runs in a distrobox container (`ubuntu2404`, Ubuntu 24.04) on c1. The
  host's root filesystem is visible at `/run/host`, `/home/ease` and `/tmp` are shared with the
  host.
- **Alternatives:** upgrading the host OS (would end ROS 1 on the robot); a separate computer
  (EtherCAT is wired to c1).
- **Consequences:** the realtime loop needs capabilities inside the container (see D9, D11).
  Unprivileged host commands cannot be run from the container (`distrobox-host-exec` does not
  work); ROS 1 tools are run through the host's dynamic loader when needed. `~/.bashrc` sources
  ROS 1 in the container too, so `unset ROS_DISTRO ROS_PACKAGE_PATH` before sourcing Jazzy. c2
  (pr2b, Hokuyos) still has to be set up.

## D2: Forks in pr2-config-iai, one `ros-jazzy-main` branch per repo

- **Status:** accepted (2026-11-19)
- **Context:** the ROS 1 sources come from the upstream PR2 repos, partly via older forks in
  code-iai.
- **Decision:**
  - Every repo of the ROS 2 workspace is a fork in **pr2-config-iai** with a `ros-jazzy-main`
    branch, listed in [`pr2_ros2.repos`](../pr2_ros2.repos). `iai_pr2` stays in code-iai, which
    already had a jazzy branch.
  - Only jazzy branches are pushed from the ROS 2 work. The ROS 1 branches belong to the running
    robot and are handled separately.
  - Packages that are not ported yet get an `AMENT_IGNORE` file (the iai_pr2 convention), so the
    workspace always builds.
- **Consequences:** upstream remains as the `upstream` remote in each checkout.

## D3: Take eml from the ROS 1 release, not from Shadow Robot's refactor

- **Status:** accepted (2026-11-19)
- **Context:** the EtherCAT master library `eml` has no maintained upstream. Candidates:
  `ros-gbp/eml-release` (the Noetic release the robot runs) and `shadow-robot/eml` (a standalone
  refactor).
- **Decision:** fork `ros-gbp/eml-release` (`pr2-config-iai/eml-release`), start from tag
  `release/noetic/eml/1.8.15-7` and add an ament_cmake build. Its installed headers are identical
  to the ones the ROS 1 robot uses.
- **Alternatives:** Shadow's refactor moves all headers to `<eml/...>` and reformats every file,
  so any behaviour change would be hidden in the diff, and `ethercat_hardware` would need its
  includes changed in ~25 places.
- **Consequences:** eml is GPL-2.0-or-later; the Beckhoff license PDF is installed with it.

## D4: Port ethercat_hardware in place, staying as close to ROS 1 as possible

- **Status:** accepted (2026-11-19)
- **Decision:**
  - The realtime code paths are unchanged; only the ROS interface moves to rclcpp.
  - ROS 1 private parameters become dotted node parameters (`~l_gripper_motor/enable_ft_sensor` →
    `l_gripper_motor.enable_ft_sensor`); the full mapping is in `ethercat_hardware/CHANGELOG.rst`.
  - All timestamps use one `RCL_SYSTEM_TIME` clock (mixing clock types throws in rclcpp).
  - `pr2_mechanism_msgs` and `pr2_controller_manager` are not ported: ros2_control replaces them.
  - `read_only_check` is added as a hardware test tool (motors halted on every cycle).
- **Consequences:** the robot's `/etc/ros/noetic/ft*.yaml` must be converted to the new parameter
  layout before the F/T sensors are used. `motorconf` and `fingertip_pressure` are not ported yet.
- **Refs:** pr2_ethercat_drivers `bdaf388`, pr2_mechanism `1f8e06a`, eml `bfeee60`.

## D5: Share the ROS 1 interface lock

- **Status:** accepted (2026-11-19)
- **Context:** ROS 1 and ROS 2 run on the same machine and could both try to drive `ecat0`.
- **Decision:** ROS 2 takes the same lock as ROS 1 `pr2_ethercat`: an fcntl write lock on
  `/var/tmp/run/EtherCAT_<interface>.pid`, using the host's file under `/run/host` inside the
  container. Like ROS 1, the file is world-writable and removed on exit
  (`ethercat_hardware::InterfaceLock`).
- **Consequences:** whichever stack starts second refuses to run. To check whether ROS 1 is running,
  look at the lock or for the process `granted` (pr2-grant runs a copy of `pr2_ethercat` under that
  name).
- **Refs:** pr2_ethercat_drivers `4fdc7ff`, `b4d0a63`, `1b1708c`.

## D6: Validate everything against recorded ROS 1 behaviour

- **Status:** accepted (2026-11-20)
- **Decision:** before replacing a piece of ROS 1, record what ROS 1 does on the robot and compare
  the ROS 2 result against it. The first baseline (calibrated, e-stop pressed) is in
  `~/workspace/ros1_baseline/`: a bag with `/joint_states`, `/mechanism_statistics`,
  `/diagnostics`, `/tf`, plus a JSON summary.
- **Consequences so far:** actuator offsets and positions read by ROS 2 match ROS 1 exactly;
  `/joint_states` from ros2_control match for all 45 joints (offline replay: bit-identical).

## D7: ros2_control system wrapping ethercat_hardware and the ported PR2 transmissions

- **Status:** accepted (2026-11-20)
- **Context:** the PR2 has a wrist differential and a gripper linkage with passive finger joints.
  ros2_control's generic transmissions do not cover these.
- **Decision:**
  - A `hardware_interface::SystemInterface`, `pr2_ros2_control/Pr2EthercatSystem`, owns
    `EthercatHardware` and does one EtherCAT exchange per `read()`, as ROS 1 did per cycle.
  - The PR2 transmissions come from `pr2_mechanism_model`, ported unchanged, rather than being
    rewritten.
  - The transmissions stay in the URDF in their ROS 1 form; the plugin reads the full description
    from `/robot_description`, because a hardware component only sees its `<ros2_control>` block.
  - The `<ros2_control>` block lists the same 45 joints ROS 1 published.
- **Alternatives:** rewriting the transmissions as ros2_control transmission plugins (more code,
  and loses the bit-for-bit comparison with ROS 1).
- **Refs:** pr2_mechanism `a3d2bf3`, pr2_ethercat_drivers `af7c418`.

## D8: Calibration, for now, from the offsets stored on the motor boards

- **Status:** accepted (2026-11-20)
- **Context:** ROS 1's calibration controllers find each joint's reference switch and store the
  zero offset on the motor board, where it survives as long as the board keeps power (a computer
  reboot or the e-stop do not clear it).
- **Decision:**
  - The ROS 2 plugin uses the stored offsets and, like ROS 1's calibration controllers at
    startup, sets each joint's reference position from its URDF `<calibration>` edge (rising if
    present, else falling).
  - Joints whose transmission needs calibration (URDF calibration edge, or a gripper) but have no
    stored offset are listed as "Not calibrated" on activation.
  - After a full power cycle, calibrate by running the ROS 1 robot once.
- **Consequences:** a ROS 2 calibration routine is still needed (later step).

## D9: Our own realtime controller manager node

- **Status:** accepted (2026-11-20)
- **Decision:** `pr2_control_node` replaces `ros2_control_node`: same structure, 1 kHz, control
  thread at SCHED_FIFO maximum priority like ROS 1 `pr2_ethercat`, timed on `CLOCK_MONOTONIC`.
- **Why:** the control process needs a raw socket, locked memory and realtime priority. The binary
  that gets those privileges should be one of ours, not a system binary under `/opt/ros`.
- **Consequences:** how the privileges are granted is D11.

## D10: Read-only first, commanding as a separate step

- **Status:** accepted (2026-11-20)
- **Decision:** the first ros2_control milestone exports only state interfaces and halts the motors
  on every cycle; the component reports an error if any actuator reports being enabled. Commanding
  (effort command interfaces, motor reset, joint safety limits) comes next, after a separate
  discussion, and is first tested with the e-stop pressed.

## D11: How the realtime loop gets its privileges

- **Status:** open (2026-11-20)
- **Context:** `pr2_control_node` and `read_only_check` need `CAP_NET_RAW` (raw EtherCAT socket),
  `CAP_IPC_LOCK` (`mlockall`) and `CAP_SYS_NICE` (SCHED_FIFO). Today they get file capabilities via
  `sudo setcap`, which every rebuild removes. File capabilities also put the process in the dynamic
  loader's secure mode, which ignores `LD_LIBRARY_PATH`, so `pr2_control_node` carries an absolute
  RPATH built from the build environment. ROS 1 uses `pr2-grant`: a setuid-root helper that copies
  the program to `/var/tmp/granted`, sets file capabilities (including `CAP_NET_ADMIN`) on the copy
  and runs it.
- **Options:**
  - **A. Our own setuid launcher with ambient capabilities** (proposed). A small root-owned helper,
    installed once per container at `/usr/local/bin/pr2-rt-exec`, grants exactly the three
    capabilities as ambient capabilities, drops root and runs the program. It's used as the launch
    prefix.
    - No `setcap` after builds.
    - Ambient capabilities do not trigger secure mode, so the RPATH workaround can go.
    - Restricted to one group (mode 4750) and absolute paths. Grants fewer privileges than
      `pr2-grant`.
    - Cost: a one-time `sudo` install of a setuid-root binary, repeated if the container is
      recreated.
  - **B. Reuse the host's `pr2-grant`.** No new code, but it also grants `CAP_NET_ADMIN`, we have
    no source for it, it keeps file capabilities (so secure mode and the RPATH workaround stay) and
    its single copy path is shared with ROS 1.
  - **C. Run `sudo setcap` from the build.** Hides sudo inside the build, breaks wherever sudo
    needs a password, and keeps file capabilities.
  - **D. `sudo setpriv` as launch prefix.** sudo strips `LD_LIBRARY_PATH` and other environment
    variables, so the ROS environment breaks.
- **Decision:** _pending_.
