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

## D26: Controllers are restarted before halted motors are released

- **Status:** accepted (2026-11-24); settles the first open point of D23
- **Context:** the wrist velocity controller kept integrating while the motors were halted (the
  wrist moved by hand left +0.47 Nm on the flex at release). ROS 1 `pr2_controller_manager::update()`
  restarted every running controller in the realtime loop when the motors came back from a halt
  (`!isHalted() && motors_previously_halted_`), and `JointVelocityController::starting()` set the
  command to 0 and reset the PID. ros2_control's controller manager has no such hook.
- **Decision:**
  - With commanding enabled, a reset while the commanded transmissions' actuators are halted does
    not reach the boards at once. The hardware component asks `pr2_control_node` through
    `MotorReleaseGate` (its own small library, so the plugin and the node share one instance).
  - The node restarts the active controllers that claim command interfaces with one
    `switch_controller()` (the same names in the deactivate and activate lists; the controller
    manager does both in one realtime cycle), then the component resets the motors. If the restart
    fails, they stay halted. Broadcasters are not restarted, so `/joint_states` keeps going.
  - "Halted" is ROS 1's definition (board off or in error) but only for the actuators that may be
    enabled; with only the wrist commanded, ROS 1's check over all actuators would never clear.
  - Jazzy's `pid_controller` keeps the integral across a restart by default (`save_i_term: true`); the
    wrist controller sets it to false. Its restart starts from the current velocity and drops the old
    reference, as ROS 1's command reset to 0.
- **Verified on the robot:** the wrist was moved by hand with the e-stop pressed; the controller's
  output grew to roll +0.78 Nm, flex up to the 1 Nm clamp. On the e-stop release the output went to
  0 one sample before the motors were enabled; the measured efforts stayed at about 0 and the wrist
  did not move. The roll sequence afterwards worked (+0.80 and -0.71 rad at 0.29 rad/s); starting
  from a zero integral, the flex sagged 0.08 rad while its integral built up against the gripper's
  weight (ROS 1 restarted the same way).
- **Also seen:** with the boards off, the joint efforts stay at the last value measured while they
  were enabled (-0.48/+0.50 Nm, then -1.0 Nm, both matching the last enabled moments), which is the
  "effort while off" point of D23.

## D27: Right arm velocity control; velocity over one sample again by default

- **Status:** accepted (2026-11-24); supersedes the default of D22 (the window stays as an option)
- **Context:** after the wrist (D23), velocity control for the whole right arm, one joint at a time.
  The first elbow test with D22's 10-sample velocity oscillated within 0.3 s.
- **Decision:**
  - `velocity_window` defaults to 1 again: ROS 1's velocity, one encoder count per cycle (0.04 to
    0.16 rad/s steps). With 10 samples the elbow's velocity loop (p 6, WG's calibration gain)
    oscillated at the sample rate, the effort swinging to the 3 Nm clamp and the velocity to
    ±0.77 rad/s, until the watchdog halted it. The same test with 1 sample was stable (efforts 0 to
    1.2 Nm). The window's delay (about N/2 ms) is the cause, not the gain; the quantization is noise
    far above what the arm can follow. `velocity_window:=N` stays for plots; for control, test it.
  - `r_arm_velocity_controller` (`pid_controller`, all 7 right arm joints, not started by the launch):
    arm joints with WG's calibration velocity gains (the PIDs that ran on every PR2), the wrist as D23;
    outputs clamped to the effort limit (3 Nm arm, 1 Nm wrist at `max_effort_fraction` 0.1), integrals
    to the calibration clamp, `conditional_integration`, `save_i_term: false` (D26). Provisional.
  - `tools/velocity_step_test.py` (installed): holds every joint of a velocity controller at 0, moves
    one (hold, +v, hold, -v, hold), then halts the motors. It halts at once if the moved joint is too
    fast or leaves start ±0.5 rad or its soft limits (minus 0.1), if another controlled joint moves
    more than 0.15 rad or 0.3 rad/s, if anything else moves, or if `/joint_states` stops.
- **Verified on the robot** (±0.2 rad/s for 1.5 s, forearm roll ±0.3 for 2 s; reached velocity in
  the easy / hard direction, effort):
  - forearm roll 0.26 / 0.18 rad/s, 0.1 to 0.5 Nm;
  - elbow flex 0.08 (bend) / 0.04 (straighten), 0.6 to 0.9 Nm;
  - upper arm roll 0.18 (+) / 0.08 (-), 0.25 to 0.7 Nm; it crept 0.02 rad while held afterwards;
  - shoulder lift 0.078 (down) / 0.072 (up), about 1.1 Nm both ways, the same with the arm
    stretched out (elbow -0.22): the counterbalance compensates the lever, if anything slightly over;
  - shoulder pan 0.15 (forward) / 0.07 (back out), 0.5 / 1.0 Nm; it coasted 0.04 rad after stopping.
  - Held joints drifted at most 0.033 rad (upper arm roll, the joint most loaded by the springs).
    Nothing oscillated. The 10 s hold of the whole arm: drift at most 0.0002 rad.
- **Open:** the calibration gains are P-dominated (i 0 to 1) and reach only a third to nine tenths of
  the reference against friction and the springs, which depend on direction and pose. A velocity
  controller needs a real integral; to be tuned per joint. Unpowered, the springs move the arm
  towards its limits between tests (upper arm roll up, wrist flex to a limit). Beyond a soft limit,
  `enforceSafety` pushes back with the whole effort limit, as ROS 1 (the wrist flex at +0.078 got
  -1 Nm the whole time without moving).

## D28: Arm velocity control with WG's trajectory gains, at 30 % effort

- **Status:** accepted (2026-11-24); continues D27
- **Context:** with WG's calibration gains (D27) every arm joint reached only a third to nine tenths
  of its velocity reference: friction (about 1 Nm), the counterbalance springs and the cables load the
  joints differently per direction and pose, and a velocity PI with i 0.2 to 6 builds up the torque
  for that far too slowly; after a stop its integral stays and must unwind at the next reversal.
- **Decision:**
  - A velocity PI is a position PD on the integrated reference: velocity p = position d, velocity
    i = position p, and with the one-sample velocity the integral is exactly the distance moved. So
    `r_arm_velocity_controller` keeps `pid_controller` and uses WG's arm trajectory gains
    (`pr2_arm_controllers.yaml`, also IAI's `pr2_whole_body_controller.yaml`) that way. With
    conditional integration the "setpoint" is dragged along while the output is at the clamp, which
    is the anti-windup we want. No custom controller for now.
  - Gains (velocity p / i): elbow flex 4 / 700, forearm roll 6 / 300, upper arm roll 6 / 1000, wrist
    flex and roll 4 / 300 (all WG's); shoulder lift 25 / 400 and shoulder pan 18 / 800 (a third of
    WG's i; the lift's p raised for damping). `save_i_term: false` (D26).
  - Tests at `max_effort_fraction:=0.3` (9 Nm arm, 3 Nm wrist): at 0.1 the shoulders saturated from
    1 Hz on and the wrist flex could not always lift the gripper. The controller's output and
    integral clamps must equal the hardware limit: conditional integration only stops at its own
    clamp, so with a larger clamp the integral would wind up unnoticed. The config is written for 0.3.
  - `velocity_window` stays 1 for control. With 3 samples (about 1 ms more delay) the upper arm roll
    (i 1000, little inertia, the highest natural frequency) oscillated while held and the watchdog
    halted it; with 1 the same test was calm.
  - `velocity_step_test.py --sine`: velocity sines with fade in and out, amplitude ratio and lag per
    frequency. Giskard's braking windows of 0.1 to 0.5 s at up to 1 rad/s mean 4 to 20 rad/s^2, i.e.
    content up to about 1 to 5 Hz.
- **Verified on the robot** (±0.2 rad/s; steps of 1.5 s, sines of 0.25 to 2 Hz):
  - steps: every joint within 1 to 5 % of the distance, at the reference from the second 0.25 s on,
    both directions alike; stops within a few mrad and 0.02 to 0.4 s; held joints still within 1 mrad;
    no creep against the springs (upper arm roll before: 0.02 rad).
  - sines at 30 %: wrist flex and roll, forearm roll: amplitude ratio 0.97 to 1.00 and 2 to 16 deg
    lag up to 2 Hz, far below their clamps. Shoulder lift (p 25): 0.99 to 1.04 up to 1 Hz, 1.19 at
    2 Hz (1.33 with p 15). Shoulder pan (p 18): 1.00 to 1.02 up to 0.5 Hz, 1.15 at 1 Hz, about 1.3
    at 1.5 Hz, and at 2 Hz 9 Nm (the clamp) for a fifth of the time with 61 deg lag; p 30 hardly
    changed that and doubled the noise, so it stays at 18.
- **Known limits:**
  - The shoulders resonate between 1 and 2 Hz. For the lift more damping (p) helps partly; part of
    the overshoot is inherent to the structure (the reference also drives the p term). For the pan p
    hardly helps, which suggests compliance between the motor (where the encoder is) and the arm;
    not proven. Until then Giskard should keep the pan's accelerations moderate (braking windows of
    about 0.5 s and more).
  - Torque ripple from the velocity quantization: while a joint moves, its reading jumps by one count
    per cycle in about a third of the samples, which gives p × step per jump (shoulder lift at p 25:
    2.1 Nm, 0.7 Nm std; audible). None while a joint is still.
  - Dropped packets: about one every 4 to 5 min whether the arm moves or not (21 of 22 outside the
    tests; 17 in 91 min on the NIC), each a frame with a CRC error and a 5 ms stall; the NIC counted
    the same rate under ROS 1 since boot. A physical layer issue (cable, connector or noise), not a
    software one. The diagnostics' "Lost Links" (uninitialised, also upstream) and "Halt motors
    service count" (counted cycles) are fixed.
- **Next:** record positions and efforts at 1 kHz in the component; with that, a velocity observer
  that predicts from the commanded torque (no window delay) and acceleration feedforward, in a
  custom controller if needed (with a command timeout for Giskard); a sine run on the pan with a
  different i to tell a controller resonance from a mechanical one; then the left arm and the head.

## D29: The left arm uses the right arm's velocity gains

- **Status:** accepted (2026-11-26)
- **Context:** D28 tuned the right arm only. WG used the same arm gains on both sides, and whether
  the shoulder resonance is the same on the other arm says something about its cause.
- **Decision:** `l_arm_velocity_controller` (not started by the launch) is `r_arm_velocity_controller`
  with the `l_` joints: same gains and clamps, for `max_effort_fraction:=0.3`. It claims none of the
  right arm's joints, so both can run together.
- **Verified on the robot** (left arm alone commanded, launched through `pr2_ros2_bringup`'s
  `pr2.launch.py`; same tests as D28: ±0.2 rad/s, steps of 1.5 s, sines of 0.5 to 2 Hz, one joint
  at a time from the wrist up, no watchdog halt):
  - steps: every joint 0.292 to 0.298 rad of 0.3 rad (97 to 99 %), both directions alike; stops
    within 4 mrad; held joints within 2.4 mrad.
  - sines, amplitude ratio (lag) at 0.5 / 1 / 2 Hz: wrist roll 1.00 / 0.97 / 0.94 (3 to 15 deg),
    wrist flex 0.99 / 0.99 / 0.98 (4 to 13 deg), forearm roll 1.00 / 1.00 / 0.99 (3 to 14 deg),
    elbow 0.98 / 1.04 / 1.06 (3 to 15 deg), upper arm roll 0.97 / 1.03 / 1.07 (3 to 8 deg); position
    errors within 7 mrad. The elbow's and upper arm roll's velocity errors reach 0.2 rad/s at 5 mrad
    position error, i.e. quantization ripple (D28), not tracking.
  - shoulders at 0.5 / 1 / 1.5 / 2 Hz: lift 1.01 / 1.10 / 1.25 / 1.19 (4 to 50 deg); pan 1.02 / 1.17
    / 1.33 / 0.76, at 2 Hz at the 9 Nm clamp with 77 deg lag. The same as the right arm (lift 1.19 at
    2 Hz, pan 1.15 at 1 Hz, about 1.3 at 1.5 Hz, clamp at 2 Hz).
- **Consequences:** the gains hold for both arms. The shoulder resonance near 1.5 Hz is the same on
  both, so it is not a defect of one arm: it comes from the controller or the arm design. The pan
  sine with a different i (D28's next steps) can tell those apart and can run on either arm. Giskard's
  limits from D28 apply to both arms. Next for velocity control: that test, the 1 kHz recording,
  then the head.

## D30: The shoulder pan is a PI on a compliant arm; acceleration feedforward next

- **Status:** accepted (2026-11-26)
- **Context:** both shoulder pans overshoot near 1.5 Hz (D28, D29). Open was whether that is the
  controller or the arm. A PI on a rigid inertia J has its peak at √(i/J), so the peak should move
  with i; a mechanical resonance would not.
- **Tests** (left pan, p 18, i set at runtime with the motors halted and set back to 800; sines at
  0.5 to 2 Hz, ±0.2 rad/s, then ±0.1 rad/s at i 800):
  - amplitude ratio at 0.75 / 1 / 1.25 / 1.5 Hz: i 800 1.11 / 1.18 / 1.35 / 1.33, i 400 1.17 / 1.42 /
    1.52 / 1.22, i 200 1.33 / 1.50 / 1.31 / 0.97. The peak moves down with i, but less than √i, and
    gets higher instead of better damped. At ±0.2 rad/s the pan reaches the 9 Nm clamp from 1.25 Hz
    (i 800, i 400) and the ratios above that are the clamp's.
  - The arm's impedance (fundamental of effort over that of velocity, per frequency, below the
    clamp) is the same under all three i within about 0.3 kg m², so it describes the arm. Its
    apparent inertia rises from 2.7 kg m² at 0.5 Hz to 4.9 kg m² at 2 Hz, and its damping from 3.4 to
    about 16 Nm s/rad: not a rigid body.
- **Model:** two masses through a spring and damper, seen from the motor (where the encoder is):
  Z(s) = Jm s + bm + (k + c s) Jl s / (Jl s² + c s + k). Least squares over the unclamped points:
  Jl 2.7 kg m², k about 850 Nm/rad, c 18 Nm s/rad, bm 3.4 Nm s/rad, so the arm's own resonance is
  near 2.8 Hz (above the tested range, extrapolated). The fit puts almost no inertia on the motor
  side; that split is not well determined. Relative error 5 % (rigid inertia: 16 %).
- **Check on new data** (i 800, ±0.1 rad/s, below the clamp up to 1.5 Hz): measured 1.04 / 1.23 /
  1.33 / 1.58 at 0.5 / 1 / 1.25 / 1.5 Hz against the model's 1.03 / 1.17 / 1.32 / 1.58. At 1.75 and
  2 Hz the clamp was reached again (10 to 14 % of the time). The measured lag is 5 to 17 deg above the
  model's (no delays in the model). The damping rose to 5 Nm s/rad at half the amplitude: part of the
  friction is Coulomb, about 0.4 to 0.5 Nm.
- **Decision:**
  - Up to about 1.25 Hz the overshoot is the PI's own (on this inertia p 18 / i 800 give ζ ≈ 0.2;
    even a rigid arm would show 1.17 at 1 Hz). Above that the compliance and the clamp dominate;
    without the clamp the model has about 1.85 at 2 Hz.
  - The gains stay (D28). More p helps the model only somewhat (p 40: peak 1.5 instead of 2.1) and
    doubled the noise on the right arm.
  - Next: a velocity controller with acceleration feedforward (J a, plus viscous and Coulomb
    friction) and a command timeout. In the model, feedforward of 2.7 a + 3.4 v takes the peak from
    2.1 to about 1.3 and keeps the ratio at 1.0 to 1.02 up to 1 Hz. `pid_controller`'s feedforward
    scales the velocity reference only, so this needs its own controller; the 1 kHz recording should
    come first to measure the delays the model leaves out.
- **Consequences for Giskard:** each rad/s² costs the pan about 2.7 Nm (about 4 to 5 Nm near
  1.5 Hz). Its URDF limit of 30 Nm allows about 9.5 rad/s² at 1 rad/s; at `max_effort_fraction` 0.3
  (9 Nm) about 2 rad/s². Braking windows of 0.1 to 0.5 s at 1 rad/s ask for 4 to 20 rad/s², so the
  pan's acceleration limit has to come from its effort limit, not from the braking window alone.
- **Note:** the impedance fit and the model were scratch scripts on the CSVs from
  `velocity_step_test.py --csv`; not yet in the repository.

## D31: Torso and head under velocity control at 60 % effort

- **Status:** accepted (2026-11-26)
- **Context:** after the arms (D28, D29) the torso and the head. Same approach: WG's trajectory gains
  in velocity form (velocity p = position d, velocity i = position p), one group at a time, only
  that group in `commanded_joints`, `velocity_step_test.py` with its watchdog.
- **Decision:**
  - `torso_velocity_controller`: p 1e6, i 1e7 (WG `pr2_torso_controller.yaml`: p 1e7, d 1e6; N and
    m/s), clamps ±6000 N. `head_velocity_controller`: pan p 2, i 25, clamps ±0.79 Nm; tilt p 3,
    i 100, clamps ±10.8 Nm (WG `pr2_head_controller.yaml`: pan p 25 d 2, tilt p 100 d 3; their small
    position integrals, an integral of an integral here, are left out). `save_i_term: false` (D26).
    Not started by the launch.
  - Both need `max_effort_fraction:=0.6`, so each runs in a launch of its own (the fraction is
    global): at 0.3 the torso could not lift itself (1 mm in 1.5 s at the 3000 N clamp) and the head
    tilt could not lift the head out of its down stop. The head pan's clamp stays at 0.3 of its
    limit: a clamp below the hardware limit cannot wind up.
  - For the head, `velocity_step_test.py --keep-running` (new): only a watchdog trip halts. A halt,
    and the restart that clears the integral on the next release (D26), drops the head onto a stop.
- **Verified on the robot:**
  - Torso (±10 mm/s, 15 mm steps): about 2600 N of friction both ways plus about 1200 N of weight
    against going up; up at 10 mm/s takes about 3800 N, down about −1400 N. It holds itself with the
    motor off. At i 3.3e6 (a third) 87 to 93 % of the steps and sines 0.95 / 0.88 / 0.82 at
    0.25 / 0.5 / 1 Hz; at i 1e7 93 % both ways, at speed within 0.06 s, stops within 0.1 s and
    0.3 mm, sines 0.99 at all three with at most 0.5 mm position error and 4630 N.
  - Head tilt: the head is top-heavy. With the motors off it rests on a stop (down at 1.45 rad, past
    the URDF limit 1.396 and the soft limit 1.296). Its weight torque crosses zero near 0.35 rad and
    grows towards both ends: about 7 Nm near 1.2 to 1.3 rad, 4 to 6 Nm at −0.3 rad; friction 1 to
    1.8 Nm. On a release from the stop the soft limit safety (k_velocity 3, i.e. 15 Nm, limited by
    the effort fraction) lifts it to about 1.32 rad in 0.15 s (1.7 rad/s); at 0.3 its 5.4 Nm only
    balanced the head at 1.43 rad. Moving into range at i 33 went in stick-slip jumps (a −0.32 rad/s
    spike halted it; the head fell back onto the stop); at WG's i 100 smoothly. Steps ±0.2 rad/s:
    108 % up, 97 % down. The whole soft range (−0.34 to 1.27 rad) at 0.1 rad/s: smooth, at most
    7.1 Nm. Sines 0.97 / 0.87 / 0.70 / 0.01 at 0.25 / 0.5 / 1 / 2 Hz with about 40 mrad position
    error: each reversal has to swing the integral across twice the friction, about 30 mrad at
    i 100, and the 2 Hz swing (±16 mrad) stays inside that.
  - Head pan: steps 80 % at i 8, 91 to 93 % at i 25; sines 0.90 / 0.91 / 0.97 / 0.82 (6 to 67 deg) with
    14 to 18 mrad position error and up to 0.72 Nm (friction about 0.3 Nm).
  - Both head joints read velocity in steps of 0.105 rad/s (10000 pulses per motor revolution,
    reductions 6 and 5.86; the boards' encoder reduction is not part of it): 0.2 to 0.3 Nm of ripple
    per count at these p.
- **Known limits:** after a move the integral keeps the last force while friction holds the joint
  (torso up to about 1200 N, i.e. motor current for nothing). The head's tracking is limited by
  friction. A halt drops the head.
- **Next:** in the custom controller (D30), besides acceleration feedforward: friction compensation in
  the direction of the reference (torso about 2600 N, head tilt 1 to 1.8 Nm, pan 0.3 Nm), gravity
  compensation for the head tilt as a function of position (from the curve above), and a slow leak
  of the integral at standstill.

## D32: The base controller and odometry ported from ROS 1, with joystick teleop

- **Status:** accepted (2026-11-26)
- **Context:** the base and a joystick next, before acceleration feedforward (D30). The ROS 1
  driver drives well, so the goal is the same behaviour, not new control. The reference is what
  the ROS 1 robot runs: `pr2_fixes` (noetic-devel), whose `pr2_mechanism_controllers` sources are
  identical to the fork's HEAD and whose `pr2_base_controller2.yaml` is IAI's, not WG's.
- **Decision:**
  - `pr2_mechanism_controllers` (fork pr2_controllers, `ros-jazzy-main`) builds only
    `Pr2BaseController2` and `Pr2Odometry`, as ros2_control controllers, with all messages. The
    control and odometry math is ROS 1's line for line. Noetic's `Pid::computeCommand(error,
    error_dot, dt)` and `MultiChannelTransferFunctionFilter` are reproduced (`ros1_compat.h`):
    the ROS 2 Pid clamps and integrates differently.
  - Values of the ROS 1 robot, written out in `controllers.yaml` (`base_controller`,
    `base_odometry`; not started by the launch): casters position PD p 100, d 8 front / 12 back;
    wheels p 100, **d 11** (WG: 5) on IAI's call order (p on the rolling the steering error causes,
    d on the speed error); **feedforward 0.005 m/s, 0.025 rad/s**; limits 1.0 m/s, 2.0 rad/s,
    2.0 m/s² and rad/s², timeout 0.2 s; 0.5/0.5 velocity filters; odometry as `pr2_odometry.yaml`
    (100 Hz, tf off). Run with `max_effort_fraction:=1.0` and the 12 caster and wheel joints in
    `commanded_joints`.
  - Differences from ROS 1 (asked for or accepted): (1) on activation the casters keep their
    angle (ROS 1 turned them to 0 or π at the first zero command); kept while the port is new,
    may go back. (2) After activation a new command is needed (ROS 1 ramped towards the last
    command from before the restart for up to the timeout): a bug fix. (3) Deactivation zeroes the
    efforts (ROS 1's controller manager did that every cycle). (4) The unused caster velocity
    controllers are not created. A NaN guard and activation resets I had added were removed again:
    ROS 1 already zeroes NaN components.
  - Calibration: every joint has the state interface `calibrated` (1 when calibrated or not in
    need of it), worked out when the hardware is configured. Both controllers claim it for the
    casters and refuse to activate (lifecycle FAILURE, they stay inactive) if one is not, as ROS 1
    refused to load.
  - Teleop (`pr2_ros2_bringup teleop.launch.py`): `joy_linux` (deadzone 0.12, repeat 10 Hz, as the
    ROS 1 robot's `joy_node`) and `pr2_teleop_base.py`, the base part of ROS 1 `teleop_pr2` with
    IAI's DS4 settings: L1 deadman, R1 run, right stick translates (axes 4/3), left stick turns
    (axis 0), 0.5/0.5/0.8 and run 1.0/1.0/1.4, L2 holds the base at 0 (ROS 1's head mode),
    repeated stamps and a joystick silent for 0.5 s count as a released deadman. Not
    `teleop_twist_joy`: its turbo button drives alone, ROS 1's run button did not. Unlike ROS 1 one
    zero is sent on release.
- **Verified:**
  - Offline: unit tests of the Pid and filter replicas and the kinematics; with `mock_components`
    the efforts for forward, sideways and turning commands match the ROS 1 formulas by hand
    (4.443 Nm; −113.9/91.9 and 157.08; 19.33/−76.01 and −78.54), uncalibrated casters are refused.
    A reviewer pass against the ROS 1 sources (Pid and filter checked against the Noetic binaries,
    the SVD bit-identical, interface order in ros2_control 4.50) found no math error; its findings
    (teleop head mode, calibration only known after activation, ERROR vs FAILURE, joystick deadzone,
    small differences) are fixed.
  - On the robot (all casters calibrated, standing still: odometry exactly 0): 0.01 m/s sideways
    turns all casters to 90° (±2 mrad) and moves 3.3 cm at 0.0115 m/s (0.015 commanded with the
    feedforward: a P on wheel speed leaves a friction error); 0.05 rad/s turns them to ±45°/135°
    first, the base waits about 1.2 s, then turns at 0.052 to 0.06 rad/s. A turn at 0.3 rad/s
    (0.30 measured) stopped by the odometry at 90° ends at 91.5° (the 2 rad/s² ramp), looked like
    90°, within 4 mm of the spot. 0.1 m/s for 5 s: 0.480 m forward, 0.481 m back to within 1 mm,
    measured 47 to 47.5 cm (1 to 2 % more in the odometry, as ROS 1 with the same
    `wheel_radius_multiplier` 1.0). Driving with the joystick feels like ROS 1.
- **Known limits / next:** no mux on `/base_controller/command` yet (ROS 1 had one between teleop
  and navigation); the head mode only holds the base, there is no head control from the joystick;
  decide later whether the casters go back to ROS 1's start behaviour; watch the 1 to 2 %
  odometry offset.

## D33: The gripper controllers and action servers ported from ROS 1, with joystick teleop

- **Status:** accepted (2026-11-26)
- **Context:** after the base (D32), the grippers. As there, the goal is ROS 1's behaviour. ROS 1
  ran `pr2_mechanism_controllers/Pr2GripperController` per gripper (`pr2_gripper_controllers.yaml`:
  p 10000, d 1000), a `pr2_gripper_action` node in each controller's namespace
  (`pr2_default_controllers.launch`), and IAI's DS4 teleop added two `pr2_teleop/teleop_gripper`
  nodes.
- **Decision:**
  - `Pr2GripperController` (pr2_controllers fork, library `pr2_mechanism_controllers_gripper`) as
    a ros2_control controller, ROS 1's update line for line: Noetic Pid on the gap error with
    `-velocity` as error derivative, dt since the previous update, effort limited to the command's
    `max_effort` when >= 0, state (`JointControllerState`) every 10th update. Activation holds the
    current gap with zero effort (ROS 1 `starting()`), so a gripper is limp after a start or an
    e-stop release (D26 restarts it) until it gets a command. Registered as `r_gripper_controller`
    and `l_gripper_controller` in `controllers.yaml`, not started by the launch; they need
    `r_gripper_joint,l_gripper_joint` in `commanded_joints` (otherwise the hardware refuses the
    effort interface and activation fails).
  - Same differences as the base controller: activation needs `<joint>/calibrated` (FAILURE
    otherwise; ROS 1 refused to load), an uncalibrated update writes 0, deactivation zeroes the
    effort; the command goes through a RealtimeBuffer.
  - `pr2_gripper_action` ported to rclcpp_action, same names, parameters and goal logic, started by
    `pr2_ros2_bringup grippers.launch.py`. Differences forced by ROS 2 actions, accepted: a goal
    replaced by a new one, or dropped because the controller tracks another setpoint, ends ABORTED
    (ROS 1: PREEMPTED); a cancel for a goal that already finished does nothing (ROS 1 then sent the
    stop command, leaving the gripper limp); after dropping a goal for another setpoint the state
    message is not evaluated further (ROS 1 tried to finish the goal again, which actionlib refused).
  - Teleop: `pr2_teleop_gripper.py`, ROS 1 `teleop_gripper` unchanged (open 0.08, close -100, both
    with max_effort -1, sent with every joy message while held, no deadman), started twice by
    `teleop.launch.py` with IAI's buttons (0 opens, 3 closes, both grippers together).
- **Verified:**
  - Offline (`mock_components`): efforts 90, 50, -30, -510 N for the four limit cases match the
    formula; state at 100 Hz; uncalibrated joint refused; the action's success, feedback,
    replacement, cancel (with ROS 1's stop command), other-setpoint abort after the 1 s grace, stall
    abort after 0.1 s, no stall with max_effort 0, 5 s watchdog; teleop buttons.
  - On the robot (both grippers calibrated from the offsets on their WG06 boards, r -54.65,
    l -60.75): at 20 N both open and close at about 35 to 40 mm/s and settle within 0.2 mm (40 and
    80 mm); closed empty they stop at a 1 mm gap pressing about 10 N (p times the error). Goals
    succeed 10 mm before the target (ROS 1's `goal_threshold` 0.01), the controller then finishes
    the move. Closing further than the fingers can go aborts as stalled after 0.1 s and keeps
    pressing with the goal's effort (ROS 1 sends no stop on a stall). The joystick works on both
    grippers; its unlimited close commands about -1e6 N, which the URDF limit (1000 N), the safety
    controller and the motor board's current limit bring down to -169 N on both, as the same chain
    did in ROS 1.
- **Known limits / next:** no ROS 2 gripper calibration yet (the offsets on the boards are used,
  D8).

## D34: One launch file starts every controller, at effort fraction 1.0

- **Status:** accepted (2026-11-26); supersedes D31's "each runs in a launch of its own" and the
  per-group `max_effort_fraction` of D28 and D31 for normal operation
- **Context:** the controllers were spawned by hand, one group per launch, because
  `max_effort_fraction` is one value for all joints and the groups were tested at different ones
  (arms 0.3, torso and head 0.6, base 1.0).
- **Decision:**
  - `pr2_ros2_bringup pr2.launch.py` starts everything that runs on c1: power board, diagnostics,
    the motor chain with commanding enabled for the 31 joints that have a controller (all actuated
    joints but `laser_tilt_mount_joint`), the eight controllers (both arms, torso, head, base,
    odometry, both grippers) with one spawner each, the gripper action servers and the joystick
    teleop. Once every spawner has exited it logs `PR2 is ready`, or names the controllers that did
    not start. Arguments `start_controllers`, `teleop`, `commanding_enabled`, `commanded_joints`
    and `max_effort_fraction` keep single-group tests and read-only runs possible.
  - `max_effort_fraction` 1.0 for all joints (as ROS 1, which had no such limit). The arm, torso and
    head controllers keep their own output and integral clamps (9 / 3 Nm, 6000 N, 0.79 / 10.8 Nm),
    which are now below the hardware limit, where conditional integration cannot wind up (D31). What
    changes is `enforceSafety`: beyond a soft limit or a velocity limit it can push with the full
    URDF effort (arm 30 Nm instead of 9, head tilt up to its k_velocity bound of 15 Nm instead of
    10.8).
  - `joint_state_broadcaster` gets the 45 joints and position, velocity and effort explicitly. With
    both lists empty it claims every state interface that exists when it is configured, including
    those `pid_controller` exports for chaining; with all spawners starting at once it was
    configured after the arm, torso and head controllers, and the controller manager then refused
    the D26 restart ("preceding controller joint_state_broadcaster is currently active"), so the
    motors stayed halted on release. Reproduced with `mock_components` (a `pid_controller` spawned
    before the broadcaster); with the explicit list the same restart succeeds and `/joint_states`
    is unchanged.
  - The controller manager's console warning per overrun is off (`overruns.print_warnings: false`);
    `pr2_control_node`'s "Realtime Control Loop" diagnostic still counts them, as ROS 1 did.
- **Findings:**
  - With all controllers running a cycle goes over 1 ms about a dozen times a minute (before: about
    once). The EtherCAT round trip is ROS 1's (670 us average, about 930 us per-second maximum,
    D19; `ecat0` is at 100 Mbit with interrupt coalescing already minimal), the controllers add
    about 38 us on average (joint_state_broadcaster 15.6, arms 5 to 6, odometry 3.9, head 3.5,
    base 2.0, grippers under 1; at most about 130 us), so more of the round trip's tail crosses
    1 ms. An overrun cycle lasts 1.0x ms and the next starts at once; the loop stays at 1003 Hz
    (ROS 1 halts below 750 Hz). The 5.6 ms ones are the dropped frames of D28.
  - `pid_controller` (4.43) takes the measured velocity as its reference on activation
    (`set_current_state_as_first_setpoint`, default true) and writes no command while its reference
    is NaN; references do not time out. So after the launch or a release the arms, torso and head
    hold the velocity they had at that moment.
- **Verified on the robot:** `PR2 is ready` with all eight controllers active; on the e-stop release
  the restart and the motor release went through, and over the next 3 s no joint moved (arms at
  most 0.4 Nm, torso 8.6 N, head tilt 3.5 Nm at 1.308 rad after the soft limit safety lifted it);
  the joystick drove the base and opened and closed both grippers.
- **Known limits:** a joint still moving at the release (e.g. sagging on its springs) keeps that
  velocity until a reference arrives, and a reference stays until the next one; both want the
  command timeout of the custom controller (D30).

## D35: The base Hokuyo on c2, started over ssh from the one launch file

- **Status:** accepted (2026-11-26)
- **Context:** both Hokuyos (UTM-30LX) are plugged into c2 (pr2b), which now runs Jazzy in its own
  distrobox container, `ubuntu2404b`, with `ros-jazzy-urg-node`. ROS 1 started them from
  `pr2_bringup/pr2-c2.launch` through a `<machine>` tag; ROS 2 launch has no machine tag. The tilt
  laser was not used with ROS 1 (nothing at IAI commands `laser_tilt_controller`).
- **Decision:**
  - `hokuyos.launch.py` keeps ROS 1's parameters (`/base_scan`, frame `base_laser_link`, ±2.2689
    rad, no intensities). The tilt laser's driver only starts with `tilt_laser:=true`, unlike ROS
    1, which always ran it; `laser_tilt_controller` stays unported for now.
  - `pr2.launch.py` starts it on c2 (`hokuyos`, default true) through
    `pr2_ros2_bringup/scripts/pr2b_run.py`: `ssh pr2b docker start ubuntu2404b && docker exec -i
    ... pr2b_run.sh <workspace setup.bash> <ROS_DOMAIN_ID> <discovery range> ros2 launch ...`, with
    c1's workspace (the same path, home is shared) and discovery settings. `docker exec` leaves the
    command running when its client goes away, so `pr2b_run.sh` watches its stdin and stops the
    command with SIGINT at EOF; `pr2b_run.py` closes that stdin on SIGINT or SIGTERM, and it closes
    by itself if `pr2b_run.py` dies. ssh has to work without a prompt (BatchMode).
  - `pr2_analyzers.yaml` gets ROS 1's Lasers group back, with Base Hokuyo only
    (`find_and_remove_prefix: base_hokuyo_node`, 2 items); ROS 2's urg_node reports the same names
    ("Hardware Status", "Laser Scan topic status").
- **Alternatives:** `ssh -t` with `distrobox enter` (a closed connection leaves the command
  running in the container); starting `hokuyos.launch.py` on c2 by hand (still possible with
  `hokuyos:=false`).
- **Findings:** the container's `/home/ease` was read-only (no ROS log directory) after c2 booted:
  dockerd started before the `bg` NFS mount of `c1:/home`, so the container bound the directory
  of the root export underneath, and c1 exports `/` read-only. Restarting the container (`distrobox
  stop ubuntu2404b`) fixes it; to stop it coming back after every c2 boot, docker has to wait for
  the mount (e.g. `RequiresMountsFor=/home` on docker.service, needs sudo on c2; not done).
- **Verified:** `pr2b_run.py` stopped a dummy on c2 on SIGINT, SIGTERM and SIGKILL, and a c1 launch
  stopped a c2 launch and its child cleanly on Ctrl-C, with nothing left on c2. On the robot, from
  `pr2.launch.py`: `/base_scan` at 40.1 Hz on c1, stamps 1.5 ms old on arrival (c1 and c2 clocks
  agree), 1041 beams, plausible ranges, `base_laser_link` 0.275 m ahead of and 0.252 m above
  `base_link`; urg_node reports "Sensor works well." and 0 retrieve errors, and Lasers / Base
  Hokuyo is OK on the dashboard aggregator.
