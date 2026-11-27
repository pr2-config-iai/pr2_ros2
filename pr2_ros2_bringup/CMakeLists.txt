cmake_minimum_required(VERSION 3.8)
project(pr2_ros2_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch maps DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/pr2_teleop_base.py scripts/pr2_teleop_gripper.py scripts/pr2b_run.py scripts/pr2b_run.sh
        scripts/kinect_mode_watchdog.py
        DESTINATION lib/${PROJECT_NAME})

ament_package()
