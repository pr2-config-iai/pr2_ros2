#!/usr/bin/env python3
"""Run a command in the ROS 2 container on c2 (pr2b), from a launch file on c1 (decision D35).

ROS 2 launch has no machine tag like ROS 1's <machine>, so this stands in for it: the command runs
through `ssh <host> docker exec -i <container>` with the c1 environment's workspace,
ROS_DOMAIN_ID and ROS_AUTOMATIC_DISCOVERY_RANGE, and stops when this process stops.

    pr2b_run.py [--host pr2b] [--container ubuntu2404b] -- ros2 launch pr2_ros2_bringup hokuyos.launch.py

Stopping: docker exec does not end the command in the container when the ssh connection goes away,
so pr2b_run.sh (in the container) watches its stdin instead. On SIGINT or SIGTERM this process closes
that stdin, and pr2b_run.sh then stops the command with SIGINT. The same happens if this process
dies, since the pipe closes with it. ssh needs a key that works without a passphrase prompt
(BatchMode).
"""
import argparse
import os
import shlex
import signal
import subprocess
import sys
import threading

REMOTE_SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pr2b_run.sh')


def workspace_setup():
    """The setup.bash of the workspace this script was installed into (shared home, same path on c2)."""
    here = os.path.dirname(os.path.realpath(__file__))
    for candidate in (
            os.path.join(here, '..', '..', '..', 'setup.bash'),                  # <ws>/install/<pkg>/lib/<pkg>
            os.path.join(here, '..', '..', '..', '..', 'install', 'setup.bash')):  # <ws>/src/pr2_ros2/<pkg>/scripts
        if os.path.isfile(candidate):
            return os.path.normpath(candidate)
    sys.exit(f'pr2b_run: no workspace setup.bash found from {here}')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--host', default='pr2b')
    parser.add_argument('--container', default='ubuntu2404b')
    parser.add_argument('--stop-timeout', type=float, default=4.0,
                        help='seconds to wait for the remote command after asking it to stop')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('no command given')

    remote = ' '.join([
        'docker start', shlex.quote(args.container), '>/dev/null', '&&',
        'exec docker exec -i', '-u', shlex.quote(os.environ.get('USER', 'ease')),
        '-e', 'HOME=' + shlex.quote(os.path.expanduser('~')),
        shlex.quote(args.container), 'bash', shlex.quote(REMOTE_SCRIPT),
        shlex.quote(workspace_setup()),
        shlex.quote(os.environ.get('ROS_DOMAIN_ID', '')),
        shlex.quote(os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE', '')),
        *[shlex.quote(c) for c in command]])
    ssh = subprocess.Popen(['ssh', '-T', '-o', 'BatchMode=yes', args.host, remote], stdin=subprocess.PIPE)

    stopping = threading.Event()

    def stop(signum, frame):
        if not stopping.is_set():
            stopping.set()
            try:
                ssh.stdin.close()  # pr2b_run.sh sees EOF and stops the command
            except OSError:
                pass

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    while True:
        try:
            ssh.wait(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            pass
        if stopping.is_set():
            try:
                ssh.wait(timeout=args.stop_timeout)
            except subprocess.TimeoutExpired:
                print(f'pr2b_run: {args.host} did not stop within {args.stop_timeout} s, closing ssh',
                      file=sys.stderr)
                ssh.terminate()
                ssh.wait()
            break
    sys.exit(0 if stopping.is_set() else ssh.returncode)


if __name__ == '__main__':
    main()
