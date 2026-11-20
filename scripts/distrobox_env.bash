# Shell environment for the ROS 2 distrobox container (decision D13 in docs/decisions.md).
#
# ~/.bashrc is shared with the host (Ubuntu 20.04, ROS 1 Noetic), and distrobox copies the host
# shell's environment into the container. Inside the container none of that is valid: ROS 1
# workspaces, and libraries/headers built for the host in ~/local. ~/.bashrc sources this file
# instead of the ROS 1 setup when $CONTAINER_ID is set:
#
#   if [ -n "$CONTAINER_ID" ]; then
#     [ -f ~/workspace/ros2_ws/src/pr2_ros2/scripts/distrobox_env.bash ] && \
#       source ~/workspace/ros2_ws/src/pr2_ros2/scripts/distrobox_env.bash
#   else
#     source ${HOME}/scripts/env20.setup
#   fi

# Drop path entries that belong to the host from a colon-separated variable.
_pr2_strip_host_entries() {
  local var=$1 out="" entry
  local -a entries
  IFS=: read -ra entries <<< "${!var}"
  for entry in "${entries[@]}"; do
    case "$entry" in
      "" | /opt/ros/noetic* | "$HOME"/workspace/*/devel* | "$HOME"/local | "$HOME"/local/* | \
      "$HOME"/better_pybullet/*) ;;
      *) out=${out:+$out:}$entry ;;
    esac
  done
  if [ -n "$out" ]; then export "$var=$out"; else unset "$var"; fi
}
for _pr2_var in PATH LD_LIBRARY_PATH LIBRARY_PATH CPATH PKG_CONFIG_PATH PYTHONPATH \
                CMAKE_PREFIX_PATH CMAKE_LIBRARY_PATH CMAKE_INCLUDE_PATH; do
  _pr2_strip_host_entries "$_pr2_var"
done
unset _pr2_var
unset -f _pr2_strip_host_entries

# ROS 1 variables (ROS_DISTRO etc. would also confuse rosdep and ament), and the host's -L~/local/lib.
unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION ROS_PACKAGE_PATH ROS_ROOT ROS_ETC_DIR \
      ROS_MASTER_URI ROS_IP ROS_HOSTNAME ROSLISP_PACKAGE_DIRECTORIES ROS_ENV_LOADER LDFLAGS

source /opt/ros/jazzy/setup.bash
