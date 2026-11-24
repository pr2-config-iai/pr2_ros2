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

- **Status:** accepted (2026-11-20)
- **Context:** `pr2_control_node` and `read_only_check` need `CAP_NET_RAW` (raw EtherCAT socket),
  `CAP_IPC_LOCK` (`mlockall`) and `CAP_SYS_NICE` (SCHED_FIFO). Until now they got file capabilities
  via `sudo setcap`, which every rebuild removes. File capabilities also put the process in the
  dynamic loader's secure mode, which ignores `LD_LIBRARY_PATH`, so `pr2_control_node` carried an
  absolute RPATH built from the build environment. ROS 1 uses `pr2-grant`: a setuid-root helper that
  copies the program to `/var/tmp/granted`, sets file capabilities (including `CAP_NET_ADMIN`) on the
  copy and runs it.
- **Options:**
  - **A. Our own setuid launcher with ambient capabilities.** A small root-owned helper, installed
    once per container, grants exactly the three capabilities as ambient capabilities, drops root
    and runs the program. It's used as the launch prefix.
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
- **Decision:** A, in `pr2_ros2_control/tools/`:
  - `pr2-rt-exec` (C, setuid root, `/usr/local/bin`, mode 4750, owner group only):
    - limits the bounding set to the three capabilities;
    - sets real, effective and saved uid/gid to the caller's;
    - raises the three as permitted, effective, inheritable and ambient capabilities;
    - execs the program, which must be given by absolute path.
  - `pr2-rt` (shell): resolves the program through `PATH` and carries `LD_LIBRARY_PATH` across in
    another variable, because glibc strips it from setuid programs. `pr2-rt-exec` restores it only
    after root has been dropped.
  - `install_pr2_rt.sh` installs both (one `sudo`).
  - Usage: the launch file's `prefix='pr2-rt'` (launch argument `rt_prefix`);
    `ros2 run --prefix pr2-rt ethercat_hardware read_only_check -i ecat0`.
- **Verified:** a process started through it runs as `ease` with exactly
  `cap_net_raw,cap_ipc_lock,cap_sys_nice` in every set (bounding included), keeps `LD_LIBRARY_PATH`,
  and cannot `sudo`. Read-only run on `ecat0`: SCHED_FIFO 99, `/joint_states` match ROS 1 for all
  45 joints, 0 dropped packets.
- **Consequences:**
  - The binaries carry no RPATH and no file capabilities.
  - Dropping the RPATH workaround also dropped the node's link to the plugin library. That link had
    hidden a plugin-loading problem, see D12.
  - `LD_LIBRARY_PATH` still contains ROS 1 entries (`~/.bashrc`) after the ROS 2 ones, so a library
    missing from ROS 2 could silently be taken from ROS 1 (several libraries share names). Not seen
    so far; the old RPATH excluded them.

## D12: Plugin classes in their own libraries

- **Status:** accepted (2026-11-20)
- **Context:** in ROS 1, `libethercat_hardware` contains both `EthercatHardware` and the device
  driver plugins (WG0X, WG014, ...), and `libpr2_mechanism_model` both `Robot` and the transmission
  plugins. class_loader assigns the plugin factories in a library to the loader that is active when
  the library is loaded. Our hardware component links both core libraries, so they are loaded while
  the hardware_interface loader loads it, and their factories end up owned by that loader. The
  device loader then fails with "no factory for WG014", the transmission loader with "no factory for
  SimpleTransmission". This only worked until now because `pr2_control_node` linked the plugin
  library (for its RPATH, D11), which loaded everything at process start, before any loader existed.
- **Decision:** the plugins move into separate libraries that nothing links:
  `libethercat_hardware_devices` and `libpr2_mechanism_model_transmissions`. The plugin XML files
  point at them. `pr2_ros2_control` recognises gripper transmissions by their URDF type instead of a
  `dynamic_cast`, so it doesn't need to link the transmission library.
- **Alternatives:** keep linking the plugin library into the node, which works only by load-order
  accident and breaks again with any other host process (e.g. a stock `ros2_control_node`).
- **Consequences:** anything that uses a device or transmission class directly (the unit tests)
  links the plugin library.

## D13: The container's shell environment comes from `scripts/distrobox_env.bash`

- **Status:** accepted (2026-11-20)
- **Context:** `~/.bashrc` is shared between the host and the container. Via `~/scripts/env20.setup`
  it sources the ROS 1 workspaces, and distrobox also copies the host shell's whole environment into
  the container. So the container had ROS 1 entries in `LD_LIBRARY_PATH`, `CMAKE_PREFIX_PATH`,
  `PYTHONPATH` etc. (some ROS 1 libraries have the same names as ours, e.g.
  `libethercat_hardware.so`), plus a Qt 5.5 built for the host in `~/local` via `LD_LIBRARY_PATH`,
  `CPATH` and `LDFLAGS=-L~/local/lib`. D1 worked around part of it with `unset ROS_DISTRO
  ROS_PACKAGE_PATH`; D11 noted the leftover `LD_LIBRARY_PATH` entries as a risk.
- **Decision:** `~/.bashrc` sources `env20.setup` only on the host. With `$CONTAINER_ID` set (the
  variable distrobox defines) it sources [`scripts/distrobox_env.bash`](../scripts/distrobox_env.bash)
  instead, which removes the host's entries (`/opt/ros/noetic`, `~/workspace/*/devel`, `~/local`)
  from the path variables, unsets the ROS 1 variables and `LDFLAGS`, and sources Jazzy. The script
  is versioned here; `~/.bashrc` only holds the switch (snippet at the top of the script).
- **Alternatives:** have `pr2-rt` strip the ROS 1 entries for the realtime process only (fixes one
  symptom; builds and every other ROS 2 process keep the polluted environment).
- **Verified:** a new shell inside the container has no ROS 1 or `~/local` entries left; full clean
  rebuild and all tests pass in it. The host branch of `~/.bashrc` is unchanged.
- **Consequences:**
  - Supersedes the `unset ROS_DISTRO ROS_PACKAGE_PATH` step from D1 and resolves the
    `LD_LIBRARY_PATH` risk noted in D11.
  - The workspace overlay (`install/setup.bash`) is still sourced by hand.
  - Shells that were already open in the container keep the old environment until reopened.

## D14: Dashboard and diagnostics keep the ROS 1 interfaces

- **Status:** accepted (2026-11-20)
- **Context:** `rqt_pr2_dashboard` shows motors, breakers, runstops, battery, diagnostics and the
  log. In ROS 1 it is fed by `pr2_dashboard_aggregator` (`/dashboard_agg`), `diag_agg`
  (diagnostic_aggregator with `pr2_bringup/config/pr2_analyzers.yaml`), `power_node2` (power board)
  and `ocean_server`/`power_monitor` (batteries, on c2).
- **Decision:**
  - Port `rqt_pr2_dashboard` (fork in pr2-config-iai) and `pr2_dashboard_aggregator` with the same
    topic and service names as ROS 1. `ethercat_hardware` publishes `~/motors_halted`, which is
    `/pr2_ethercat/motors_halted` as in ROS 1, because ros2_control names the hardware component's
    node after the `<ros2_control>` block (`pr2_ethercat`). Motor reset and halt will be
    `/pr2_ethercat/reset_motors` and `halt_motors`, the dashboard's defaults.
  - `pr2_ros2_bringup/launch/diagnostics.launch.py` starts `diag_agg` and the dashboard aggregator,
    as ROS 1 `pr2.launch` did.
  - The analyzer config only contains groups whose diagnostics ROS 2 publishes (Motors, plus the
    ros2_control controller manager under "Realtime Controllers"). Every expected item nobody
    publishes would hold the dashboard's diagnostics icon at error. The ROS 1 groups come back as
    their drivers are ported.
  - Jazzy's `GenericAnalyzer` only matches items through `startswith`/`contains`/`regex`; `expected`
    and `name` only add "Missing" placeholders. Every expected item must also match one of those.
  - `pr2_power_board` is ported as service definitions only for now, so the dashboard's breaker
    buttons have their service type. The power board driver comes later.
- **Consequences:** until the power board and battery drivers are ported, breakers, runstops and
  battery show as stale. The reset/halt buttons report that the services are missing until the
  commanding step (D10).

## D15: Container shells also source the workspace overlay

- **Status:** accepted (2026-11-20)
- **Decision:** `scripts/distrobox_env.bash` (D13) sources `~/workspace/ros2_ws/install/setup.bash`
  after Jazzy, if it exists, so every container shell can run the PR2 packages directly. Supersedes
  the "overlay is still sourced by hand" consequence of D13.
- **Consequences:** a package removed from the workspace stays on the paths of open shells until
  they are reopened (colcon warns about this when building).

## D16: The container environment script works on any machine

- **Status:** accepted (2026-11-20)
- **Context:** the dashboard machine pr2-ext also runs Jazzy in a distrobox next to its host setup,
  with the workspace in `~/ros2_ws`. The D13 script removed c1's host paths by name, so pr2-ext's
  leftovers (`~/lib/better_pybullet` in `PYTHONPATH`, plus an empty entry, i.e. the current
  directory) got through, and the workspace path was fixed to c1's.
- **Decision:** `scripts/distrobox_env.bash`
  - clears the search paths that only ROS and build setups set (`PYTHONPATH`, `LD_LIBRARY_PATH`,
    `CMAKE_PREFIX_PATH`, `AMENT_PREFIX_PATH`, `PKG_CONFIG_PATH`, `CPATH`, `LIBRARY_PATH`,
    `CMAKE_*_PATH`, `LDFLAGS`) instead of filtering them, since in a container shell they can only
    come from the host;
  - filters only `PATH` (drops `/opt/ros/*`, catkin `devel` and `~/local` entries, empty entries
    and duplicates);
  - finds the workspace from its own location (`<ws>/src/pr2_ros2/scripts/`).
  - Recommended use: source it at the end of `~/.bashrc` when `$CONTAINER_ID` is set, so it cleans
    up after everything host-specific. c1 keeps its existing switch (D13).
- **Consequences:** anything a container shell needs in those variables beyond Jazzy and the
  workspace has to be set after the script. Supersedes the filtering described in D13.

## D16: One motor reset at startup, as in ROS 1, while read-only

- **Status:** accepted (2026-11-20)
- **Context:** every motor board reports a timestamp jump for its first packet (the previous
  timestamp starts at 0), and the boards latch safety faults such as undervoltage from a pressed
  e-stop. ROS 1 `pr2_ethercat` clears both with one motor reset in its first cycle
  (`ec.update(true, false)`). Without it, ROS 2 showed "Timestamp jumped" on every board forever.
- **Decision:** `Pr2EthercatSystem` passes `reset=true` with the first EtherCAT exchange after
  `tryInit()`. Two cycles later every board gets `MODE_SAFETY_RESET` and its error flags are
  cleared. Unlike ROS 1, `halt` stays set on every cycle and the commands keep enable off, so no
  board leaves `MODE_OFF`. This narrows D10 ("nothing is sent") to "nothing that enables a motor".
- **Alternatives:** clearing only the software flags (differs from ROS 1, needs changes to
  `ethercat_hardware`); waiting for the commanding step's reset service.
- **Verified:** read-only with the e-stop pressed, the boards report "Safety Lockout: UNDERVOLTAGE"
  only, as in the ROS 1 recording.
- **Consequences:** halting on every cycle counts as a halt request each time ("Halt motors service
  count" grows by 1000/s; ROS 1 shows 0). To be cleaned up when halt/reset become services.

## D17: Power board driver ported, breakers switched only on request

- **Status:** accepted (2026-11-20)
- **Context:** with the e-stop released, the motor boards kept reporting undervoltage: the power
  board puts the three motor breakers into standby when the e-stop is pressed and does not turn
  them back on by itself. In ROS 1 they are re-enabled from the dashboard through `power_node2`.
- **Decision:**
  - Port `pr2_power_board/power_node2` like `ethercat_hardware` (D4): protocol code unchanged, ROS
    interface on rclcpp, ROS 1 names kept (`/power_board/control`, `/power_board/state`,
    `/diagnostics`). Fix ROS 1's no-op lock (see the package changelog).
  - `pr2_ros2_bringup/launch/power_board.launch.py` starts it (address 10.68.0.50, respawn) as ROS 1
    `robot.launch` did. Diagnostics get a "Power System" group (the battery items follow with the
    battery driver).
  - The driver sends status requests and, every 10 s like ROS 1, a fan command (duty 0 without
    battery data, breaker fields untouched). Breakers are only switched through
    `/power_board/control`, i.e. the dashboard's breaker buttons; the first switch is coordinated
    with the person at the robot.
- **Verified:** read-only: the board (serial 1002) reports 71.4 V input, all three breakers in
  standby (17 V), runstop flags false with the e-stop pressed; the dashboard aggregator marks the
  power board state valid.

## D18: Breakers on and motor reset when the e-stop is released, as in ROS 1

- **Status:** accepted (2026-11-20); supersedes the "breakers are only switched through the
  dashboard" part of D17.
- **Context:** after the breakers were switched on, all motor boards stayed in safety lockout
  (latched undervoltage). The one startup reset (D16) did not clear it. In ROS 1 nobody uses the
  dashboard for this: `pr2_run_stop_auto_restart` (started by `pr2_bringup/pr2.launch`) watches
  `power_board/state` and, when `run_stop` goes from false to true, sends `start` to breakers 0-2,
  waits 2 s and calls `pr2_ethercat/reset_motors`. Our hardware component had no such service.
- **Decision:**
  - `pr2_ros2_control` offers `~/reset_motors` and `~/halt_motors` (`std_srvs/Empty`, i.e.
    `/pr2_ethercat/...`, the names ROS 1 and the dashboard use). While read-only, a reset runs the
    same sequence as the startup reset and halt stays set on every cycle; halt is a no-op.
  - Port `pr2_run_stop_auto_restart` (fork `pr2_robot`, branch `ros-jazzy-main`, only this
    package; the others have `AMENT_IGNORE`) with unchanged behaviour. The ROS 1 callback waits and
    sleeps; the port runs that sequence in a worker thread so the executor can deliver the service
    responses.
  - `power_board.launch.py` starts it next to the power board. Releasing the e-stop is the request
    to power the motors, as in ROS 1.
- **Verified:** against fake services: nothing happens at startup, a release sends `start` to
  breakers 0-2 with the board serial and calls `reset_motors` 2 s later; clean exit on SIGINT.
  Hardware test pending.

## D19: Realtime loop diagnostics as in ROS 1; the timing matches ROS 1

- **Status:** accepted (2026-11-20)
- **Context:** the controller manager reported "bad periodicity" (1087-1128 Hz early in a run,
  1002 Hz later, huge deviation) and logged overruns of about 1 ms read time.
- **Findings:**
  - The EtherCAT round trip of this robot is about 650 us on average and up to about 930 us per
    second in ROS 1 as well (baseline bag: 630-645 us average, 1-s maximum 931 us, 10 overruns,
    "Last Control Loop Overrun Cause: ec: 1036.92us"). Occasional overruns of about 1 ms are the
    same as in ROS 1.
  - The periodicity error came from our first cycle: its measured period was the ~1 us since the
    loop started, and the controller manager keeps that statistic for the whole run.
  - Single long round trips (5.6 ms) coincided with a C++ build on c1.
- **Decision:**
  - `pr2_control_node` gives the first cycle the nominal period and publishes ROS 1's "Realtime
    Control Loop" status (same keys); the analyzer puts it under "Realtime Controllers".
  - ROS 1 halts the motors while the loop frequency over 600 ms is below 750 Hz and keeps that
    until a motor reset. That belongs in the hardware component (it halts and sees resets) and is
    added with commanding; until then it is only reported.
  - Avoid heavy builds on c1 while motors are commanded.
- **Verified:** periodicity 1000.000 Hz (deviation 0.53 Hz), average loop jitter 4.25 us
  (maximum 13 us; ROS 1: 4.63 us, 66 us), no overruns in the first minute.

## D20: Commanding the motors, step by step

- **Status:** accepted (2026-11-20)
- **Context:** ROS 1 `pr2_controller_manager::update` zeroes the joint efforts, runs the
  controllers, clamps each effort with `JointState::enforceLimits` (URDF effort and velocity limits,
  plus the position soft limits on calibrated joints) and propagates the efforts through the
  transmissions, which enables the actuators. `pr2_ethercat` halts the motors on request, on device
  errors and while the loop runs below 750 Hz, until a motor reset. ROS 1's calibration controller
  marks a joint calibrated without moving it when its board holds a saved zero offset.
- **Decision:**
  - Same chain in the hardware component: effort command interfaces; `write()` sets the joint
    efforts, runs `enforceSafety()` and the transmissions; `read()` sends them with the next
    EtherCAT exchange (one cycle, as ROS 1).
  - Halting as ROS 1, in the component: `~/halt_motors` latches until `~/reset_motors`; the loop
    frequency over 600 ms below `min_acceptable_rt_loop_frequency` (750 Hz) halts until a reset.
  - Calibration as ROS 1: saved board offset means calibrated. Joints with a `<calibration>`
    element that are not calibrated get no effort (ROS 2 calibration routine later).
  - Gates, read-only by default: `commanding_enabled` (false), `commanded_joints` (allowlist) and
    `max_effort_fraction` (extra clamp on the URDF effort limit). Joints not on the list get exactly
    zero effort after `enforceSafety()`, also when they share actuators with a listed joint (the
    wrist transmission drives roll and flex with the same two motors); actuators of unlisted
    transmissions stay disabled and are still checked never to report enabled.
  - Stages: (1) e-stop pressed: command path, halt, reset and the low-frequency halt verified
    without motor power; (2) e-stop released, first motion on `r_wrist_roll_joint` (continuous,
    least likely to hit anything; 10 Nm, 3.6 rad/s, `k_velocity` 2) with small efforts through
    `effort_controllers/JointGroupEffortController`; (3) joint velocity control, the goal: Jazzy's
    `pid_controller` (velocity reference, effort output) with the ROS 1
    `pr2_joint_velocity_controllers.yaml` gains (wrist roll p 4, i 25, i_clamp 100), checking that
    its integral clamp means the same as ROS 1's; port `JointVelocityController` if it does not.
    ROS 1 restarts running controllers when the motors come back from a halt; we need the same
    before stage 3.
  - Base, casters and grippers later (they need ROS 1's own controllers).

## D21: Stage 1 of D20 done; the effort chain is checked by a unit test

- **Status:** accepted (2026-11-20)
- **Context:** D20 stage 1 was to see the wrist boards receive enable and current with the e-stop
  pressed. That cannot happen: after a reset, `ethercat_hardware` finds boards in safety lockout
  (no motor power) and halts all motors again ("Motors halted soon after reset (device error)"),
  exactly as ROS 1. With the e-stop pressed the motors cannot be released at all.
- **Verified on the robot (e-stop pressed, `commanding_enabled`, `r_wrist_roll_joint`, 10%):**
  only `r_wrist_trans` (`r_wrist_r_motor`, `r_wrist_l_motor`) may be enabled; with 0.5 Nm commanded
  the motors stay halted until a reset and again after it (device error), 0 A programmed, the other
  31 boards untouched; a controller for `head_pan_joint` is refused ("not in commanded_joints");
  with `min_acceptable_rt_loop_frequency:=1100` the monitor halts ("realtime loop only ran at
  1001.7 Hz"), at 750 Hz it never did.
- **Decision:** the part from the commands to the actuators (`finishEffortCommands`) is tested
  without EtherCAT on the real PR2 model (`test/test_effort_chain.cpp`): wrist roll reaches both
  wrist motors and the flex gets 0, the 10% clamp, other actuators disabled, ROS 1's velocity
  braking above 3.6 rad/s, and a flex outside its soft limit stays at 0 (removing the zeroing makes
  that test fail with the -8 Nm ROS 1 would apply). Stage 2 sees the first real current.

## D22: Actuator velocity over a window of encoder samples

- **Status:** accepted (2026-11-20)
- **Context:** `ethercat_hardware` (as ROS 1) takes the actuator velocity as the encoder difference
  over one sample. With 1200 count encoders at 1 kHz one count per cycle is 0.04 to 0.16 rad/s at
  the joints (wrist 0.044, head 0.105, elbow flex 0.145, upper arm roll 0.160), so the velocity
  jumps in steps that size; the first wrist velocity runs read only 0.087 or 0.131 rad/s. Giskard
  reads only positions from `/joint_states`; the velocity matters for the velocity controllers and
  for plots.
- **Decision:** `pr2_ros2_control` replaces each actuator's velocity, before the transmissions, by the
  difference over the last `velocity_window` samples (default 10) of the raw encoder position
  (position plus zero offset, which a calibration does not shift), timed with the boards' sample
  timestamps. Exact at constant velocity, unaffected by a repeated sample from a dropped packet,
  allocation free; steps 10 times finer for about 5 ms of delay. `velocity_window:=1` is ROS 1.
  `ethercat_hardware` is unchanged (its own checks still see the single-sample value).
- **Verified:** unit tests (`test/test_velocity_window.cpp`); on the robot the wrist velocity now
  moves in 0.0044 rad/s steps, and reads exactly 0 at rest.

## D23: Stage 3 of D20, velocity control of the right wrist

- **Status:** accepted (2026-11-20)
- **Context:** effort steps on the roll alone (stage 2) turned only one wrist motor: roll and flex
  moved by equal and opposite amounts. The wrist is a differential; with 0 Nm on the flex nothing
  makes the stuck motor turn. The velocity gains in `pr2_controller_configuration` (and IAI's copy)
  are Willow Garage's and not trusted (no other group publishes its own); WG's calibration
  controllers are the velocity PIDs proven on the hardware (wrist p 3, i 0.2).
- **Results** (`pid_controller` on both wrist joints, flex reference 0, roll +-0.3 rad/s):
  - P only (p 4), 0.5 Nm and then 1 Nm limit: still one motor. Neither joint reached the limit; the
    two P terms balanced at about 0.6 Nm each with roll and flex both at 0.15 rad/s. A P-only
    velocity loop yields to a steady load.
  - p 4, i 5, 1 Nm limit, integral clamped to the limit with `conditional_integration`: pure roll,
    +0.78 and -0.70 rad at 0.29 rad/s (reached in about 1 s) while the flex moved 0.005 rad in total.
  - Jazzy's PID clamps its stored integral to `i_clamp` (ROS 1 without antiwindup integrates the
    error beyond the clamp); neither knows the hardware component's effort limit, so the clamps are
    set to it.
- **Decision:** `config/controllers.yaml` gets `r_wrist_velocity_controller` with these provisional
  gains (not started by the launch file); wrist joints are always velocity controlled together.
- **Open:** the integral winds up while the motors are halted (it integrated the wrist being moved
  by hand: +0.47 Nm on the flex at release) and holds about 0.5 Nm after a motion stops. Controllers
  need a reset when the motors are halted or released, before velocity control is used for real.
  A joint commanded outside its soft limit gets ROS 1's push back at the effort limit (seen at flex
  +0.08 rad: -1 Nm). The joint effort read while the boards are off does not match their measured
  currents; to check.

## D24: ROS 2 discovery limited to the local machine

- **Status:** accepted (2026-11-24)
- **Decision:** `scripts/distrobox_env.bash` exports `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, so
  ROS 2 nodes in container shells only discover nodes on the same machine.
- **Consequences:** the script is used on every machine (D16), so c1, c2 and pr2-ext each form their
  own ROS 2 graph: nodes on c2 (the Hokuyos) or a dashboard on another computer do not see c1's
  topics until they are connected some other way (for example `ROS_STATIC_PEERS`, or a different
  range). Shells started before the change, and the `ros2` daemon (`ros2 daemon stop`), keep the old
  setting.

## D25: ROS 2 discovery on the subnet, in domain 1

- **Status:** accepted (2026-11-24); supersedes D24
- **Context:** with `LOCALHOST` (D24), a dashboard on another computer no longer sees the robot.
- **Decision:** `scripts/distrobox_env.bash` exports `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` (the
  default, set explicitly) and `ROS_DOMAIN_ID=1`. Every machine using the script (c1, c2, pr2-ext)
  shares one graph again. Domain 1 keeps it apart from the other ROS 2 machines on the network,
  which use the default domain 0.
- **Consequences:** another computer (e.g. for the dashboard) needs `ROS_DOMAIN_ID=1`. Shells started
  before the change, and the `ros2` daemon (`ros2 daemon stop`), keep the old setting.
