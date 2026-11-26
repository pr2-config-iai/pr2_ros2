#!/usr/bin/env python3
# Copyright (c) 2008, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <ORGANIZATION> nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""ROS 2 port of pr2_teleop's teleop_gripper (C++ in ROS 1), unchanged in behaviour.

While the open button is held, every joy message sends the open command to `command`; else, while
the close button is held, the close command. Nothing is sent when neither is held, so the gripper
keeps the last command. Parameters (ROS 1 names and defaults): open_position 0.08,
open_max_effort -1 (unlimited), close_position -100, close_max_effort -1, open_button 1,
close_button 2.
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Joy

from pr2_controllers_msgs.msg import Pr2GripperCommand


class TeleopGripper(Node):
    def __init__(self):
        super().__init__('teleop_gripper')
        self.open_cmd = Pr2GripperCommand()
        self.open_cmd.position = float(self.declare_parameter('open_position', 0.08).value)
        self.open_cmd.max_effort = float(self.declare_parameter('open_max_effort', -1.0).value)
        self.close_cmd = Pr2GripperCommand()
        self.close_cmd.position = float(self.declare_parameter('close_position', -100.00).value)
        self.close_cmd.max_effort = float(self.declare_parameter('close_max_effort', -1.0).value)
        self.open_button = int(self.declare_parameter('open_button', 1).value)
        self.close_button = int(self.declare_parameter('close_button', 2).value)

        self.pub = self.create_publisher(Pr2GripperCommand, 'command', 1)
        self.sub = self.create_subscription(Joy, 'joy', self.joy_callback, 1)
        self.get_logger().debug('teleop_gripper started')

    def joy_callback(self, joy):
        self.get_logger().debug('Got a joy msg')
        if (len(joy.buttons) <= self.open_button or len(joy.buttons) <= self.close_button
                or self.open_button < 0 or self.close_button < 0):
            self.get_logger().error(
                f'Array lookup error: Joystick message has {len(joy.buttons)} elems. '
                f'Open Index [{self.open_button}]. Close Index [{self.close_button}]')
            return

        if joy.buttons[self.open_button] == 1:
            self.pub.publish(self.open_cmd)
            self.get_logger().debug('Opening')
        elif joy.buttons[self.close_button] == 1:
            self.pub.publish(self.close_cmd)
            self.get_logger().debug('Closing')


def main():
    rclpy.init()
    node = TeleopGripper()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
