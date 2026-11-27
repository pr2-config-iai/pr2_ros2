cmake_minimum_required(VERSION 3.8)
project(pr2_ros2_bringup)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
add_compile_options(-Wall -Wextra -Wpedantic)

# The IMU for the EKF, ignored while the base stands still (D43)
add_executable(imu_standstill_gate src/imu_standstill_gate.cpp)
target_link_libraries(imu_standstill_gate rclcpp::rclcpp ${nav_msgs_TARGETS} ${sensor_msgs_TARGETS})
install(TARGETS imu_standstill_gate DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY config launch maps DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/pr2_teleop_base.py scripts/pr2_teleop_gripper.py scripts/pr2b_run.py scripts/pr2b_run.sh
        scripts/kinect_mode_watchdog.py
        DESTINATION lib/${PROJECT_NAME})

ament_package()
