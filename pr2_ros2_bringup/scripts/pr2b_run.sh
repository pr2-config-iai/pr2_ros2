#!/bin/bash
# Container side of pr2b_run.py (decision D35): runs in c2's ROS 2 container through docker exec -i.
#
#   pr2b_run.sh <workspace setup.bash> <ROS_DOMAIN_ID> <ROS_AUTOMATIC_DISCOVERY_RANGE> <command...>
#
# Starts the command with Jazzy, the workspace and c1's discovery settings, and stops it with SIGINT
# once stdin reaches EOF (pr2b_run.py on c1 closed it, or the ssh connection went away), because
# docker exec leaves the command running when its client goes away.
set -m  # job control: the background command gets SIGINT, not the ignored SIGINT of a plain bash job

ws_setup=$1 domain=$2 range=$3
shift 3

source /opt/ros/jazzy/setup.bash
source "$ws_setup"
if [ -n "$domain" ]; then export ROS_DOMAIN_ID=$domain; fi
if [ -n "$range" ]; then export ROS_AUTOMATIC_DISCOVERY_RANGE=$range; fi
# The output goes through a pipe to c1: no buffering, no colours.
export PYTHONUNBUFFERED=1 RCUTILS_LOGGING_BUFFERED_STREAM=0 RCUTILS_COLORIZED_OUTPUT=0

"$@" </dev/null &
pid=$!
echo "pr2b_run: started on $(hostname) (pid $pid): $*" >&2

# Wait for EOF on stdin, or for the command to end by itself.
while kill -0 "$pid" 2>/dev/null; do
  read -r -t 1 _
  status=$?
  if [ "$status" -le 128 ] && [ "$status" -ne 0 ]; then  # EOF (a timeout is > 128)
    echo "pr2b_run: c1 side closed, stopping $*" >&2
    kill -INT "$pid" 2>/dev/null
    break
  fi
done
wait "$pid"
