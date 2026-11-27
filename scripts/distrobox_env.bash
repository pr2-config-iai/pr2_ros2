# Shell environment for a ROS 2 distrobox container (decisions D13, D15, D16 in docs/decisions.md).
#
# distrobox shares $HOME with the host and copies the host shell's whole environment into the
# container, and ~/.bashrc runs in both. Whatever the host sets up (ROS 1 workspaces, Python paths,
# libraries built for the host's Ubuntu) is not valid in the container. Source this file from
# ~/.bashrc in container shells, after anything host-specific has run, e.g. at the very end:
#
#   if [ -n "$CONTAINER_ID" ] && [ -f ~/ros2_ws/src/pr2_ros2/scripts/distrobox_env.bash ]; then
#     source ~/ros2_ws/src/pr2_ros2/scripts/distrobox_env.bash
#   fi
#
# ($CONTAINER_ID is set by distrobox.) Host-only lines that fail inside the container, such as
# sourcing ROS 1, are best wrapped in `if [ -z "$CONTAINER_ID" ]; then ... fi`.
#
# The workspace is the one this file is checked out in: <ws>/src/pr2_ros2/scripts/.

_pr2_ws=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)

# Search paths that only ROS and build setups set: in a container shell they can only come from
# the host, so start them from scratch and let Jazzy and the workspace set them again.
unset PYTHONPATH LD_LIBRARY_PATH LIBRARY_PATH CPATH PKG_CONFIG_PATH \
      CMAKE_PREFIX_PATH CMAKE_LIBRARY_PATH CMAKE_INCLUDE_PATH AMENT_PREFIX_PATH COLCON_PREFIX_PATH \
      LDFLAGS

# ROS 1 variables (ROS_DISTRO etc. would also confuse rosdep and ament).
unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION ROS_PACKAGE_PATH ROS_ROOT ROS_ETC_DIR \
      ROS_MASTER_URI ROS_IP ROS_HOSTNAME ROSLISP_PACKAGE_DIRECTORIES ROS_ENV_LOADER

# ROS 2 discovery on the local network, in the robot's own domain (decision D25). Other computers
# that should see the robot need ROS_DOMAIN_ID=1 too.
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export ROS_DOMAIN_ID=1

# PATH also holds the system directories, so only drop the host's ROS and build entries.
_pr2_path=""
IFS=: read -ra _pr2_entries <<< "$PATH"
for _pr2_entry in "${_pr2_entries[@]}"; do
  case "$_pr2_entry" in
    "" | /opt/ros/* | */devel | */devel/* | "$HOME"/local | "$HOME"/local/*) ;;
    *) case ":$_pr2_path:" in
         *":$_pr2_entry:"*) ;;                                  # drop duplicates
         *) _pr2_path=${_pr2_path:+$_pr2_path:}$_pr2_entry ;;
       esac ;;
  esac
done
export PATH=$_pr2_path

source /opt/ros/jazzy/setup.bash

# The workspace overlay, once it has been built.
if [ -f "$_pr2_ws/install/setup.bash" ]; then
  source "$_pr2_ws/install/setup.bash"
fi

# The CRAM venv (Giskard, ~/libs/cognitive_robot_abstract_machine), once it has been created. Last,
# so ROS and the workspace stay first on PYTHONPATH. A shell started from an active one (PATH and
# VIRTUAL_ENV inherited) activates it again instead of stacking it.
_pr2_venv="$HOME/libs/cram-env"
if [ -f "$_pr2_venv/bin/activate" ]; then
  unset VIRTUAL_ENV
  PATH=$(printf '%s' ":$PATH:" | sed "s|:$_pr2_venv/bin:|:|g; s|^:||; s|:$||")
  source "$_pr2_venv/bin/activate"
fi

unset _pr2_ws _pr2_venv _pr2_path _pr2_entries _pr2_entry
