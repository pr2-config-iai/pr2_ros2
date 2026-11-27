#!/usr/bin/env python3
"""Monitors the image mode of the Kinect 360 and sets it to the right value if necessary.

Port of IAI's ROS 1 iai_kinect_watchdog/kinect_mode_watchdog.py: at 10 Hz, read image_mode of
/kinect_head/driver and set it back to 1 (SXGA) if it is 2 (VGA). ROS 1 did this with a
dynamic_reconfigure client, ROS 2 with the driver's parameter services.
"""
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.parameter_client import AsyncParameterClient

DRIVER = '/kinect_head/driver'


class KinectModeWatchdog(Node):
    def __init__(self):
        super().__init__('kinect_mode_watchdog')
        self.get_logger().info('Kinect mode watchdog node started')
        # Create a parameter client for the Kinect driver
        self.client = AsyncParameterClient(self, DRIVER)
        self.pending = None
        self.waiting_logged = False
        # Run the node at 10 Hz
        self.create_timer(0.1, self.check)

    def check(self):
        if self.pending is not None and not self.pending.done():
            return
        # ROS 1's client waited for the dynamic_reconfigure server before the loop started.
        if not self.client.services_are_ready():
            if not self.waiting_logged:
                self.get_logger().info(f'Waiting for the parameter services of {DRIVER}')
                self.waiting_logged = True
            return
        self.waiting_logged = False
        # Get the current configuration
        self.pending = self.client.get_parameters(['image_mode'], callback=self.got)

    def got(self, future):
        try:
            values = future.result().values
        except Exception as e:  # noqa: BLE001 (ROS 1: rospy.ServiceException)
            self.get_logger().warn(f'Failed to communicate with the driver parameter services: {e}')
            return
        # Check the image_mode parameter and change it if it's 2
        if values and values[0].integer_value == 2:
            self.pending = self.client.set_parameters([Parameter('image_mode', value=1)], callback=self.set_done)

    def set_done(self, future):
        try:
            result = future.result().results[0]
        except Exception as e:  # noqa: BLE001
            self.get_logger().warn(f'Failed to communicate with the driver parameter services: {e}')
            return
        if result.successful:
            self.get_logger().info('Changed image_mode from 2 to 1')
        else:
            self.get_logger().warn(f'Setting image_mode 1 failed: {result.reason}')


def main():
    rclpy.init()
    node = KinectModeWatchdog()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
