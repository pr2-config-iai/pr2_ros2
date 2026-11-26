#!/usr/bin/env python3
"""Base part of ROS 1 pr2_teleop's teleop_pr2 (run with --deadman_no_publish, as IAI's
pr2_teleop_joy_ds4.launch did): while the deadman button is held, publish a Twist at 20 Hz from
three joystick axes, clamped to the maximum speeds, with the run speeds while the run button is
held too. With the head button held as well, ROS 1 moved the head and kept the base at 0: here
the base gets 0 (no head control yet). A Joy message with the same stamp as the previous one
counts as a released deadman (as in ROS 1), and so does a joystick that stops sending for
joy_msg_timeout. On release one zero is published (ROS 1: nothing; the base controller stopped
after its 0.2 s timeout), then nothing. Defaults are IAI's DS4 settings (joy_linux numbering)."""
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Joy


class TeleopBase(Node):
    def __init__(self):
        super().__init__('pr2_teleop_base')
        p = lambda name, value: self.declare_parameter(name, value).value
        self.axis_vx, self.axis_vy, self.axis_vw = p('axis_vx', 4), p('axis_vy', 3), p('axis_vw', 0)
        self.max_walk = (p('max_vx', 0.5), p('max_vy', 0.5), p('max_vw', 0.8))
        self.max_run = (p('max_vx_run', 1.0), p('max_vy_run', 1.0), p('max_vw_run', 1.4))
        self.deadman_button, self.run_button = p('deadman_button', 4), p('run_button', 5)
        self.head_button = p('head_button', 6)
        self.joy_timeout = p('joy_msg_timeout', 0.5)
        self.last_stamp = None
        self.repeated = False
        self.joy = None
        self.joy_time = None
        self.was_active = False
        self.pub = self.create_publisher(Twist, 'cmd_vel', 1)
        self.create_subscription(Joy, 'joy', self.on_joy, 10)
        self.create_timer(1.0 / p('rate', 20.0), self.on_timer)
        self.get_logger().info(
            f'deadman button {self.deadman_button}, run button {self.run_button}, head button '
            f'{self.head_button} (base held at 0); axes vx {self.axis_vx} '
            f'vy {self.axis_vy} vw {self.axis_vw}; max {self.max_walk}, run {self.max_run}')

    def on_joy(self, msg):
        stamp = (msg.header.stamp.sec, msg.header.stamp.nanosec)
        self.repeated = stamp == self.last_stamp
        self.last_stamp = stamp
        self.joy = msg
        self.joy_time = self.get_clock().now()

    @staticmethod
    def get(values, index):
        return values[index] if 0 <= index < len(values) else 0

    def on_timer(self):
        fresh = (self.joy is not None and
                 (self.get_clock().now() - self.joy_time).nanoseconds * 1e-9 <= self.joy_timeout)
        active = fresh and not self.repeated and self.get(self.joy.buttons, self.deadman_button) == 1
        if active:
            cmd = Twist()
            if self.get(self.joy.buttons, self.head_button) != 1:
                run = self.get(self.joy.buttons, self.run_button) == 1
                vx, vy, vw = self.max_run if run else self.max_walk
                clamp = lambda v, m: max(min(v, m), -m)
                cmd.linear.x = clamp(vx * self.get(self.joy.axes, self.axis_vx), vx)
                cmd.linear.y = clamp(vy * self.get(self.joy.axes, self.axis_vy), vy)
                cmd.angular.z = clamp(vw * self.get(self.joy.axes, self.axis_vw), vw)
            self.pub.publish(cmd)
        elif self.was_active:
            self.pub.publish(Twist())
            if not fresh:
                self.get_logger().warn('joystick silent: stopped the base')
        self.was_active = active


def main():
    rclpy.init()
    node = TeleopBase()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.was_active and rclpy.ok():
            node.pub.publish(Twist())
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
