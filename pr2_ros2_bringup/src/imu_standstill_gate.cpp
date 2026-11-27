// imu_standstill_gate: the torso IMU for robot_localization's EKF, ignored while the base stands
// still (D43).
//
// ROS 1's robot_pose_ekf applied the odometry and the IMU in one update; at standstill the
// odometry's variance (1e-12) outweighed the IMU's, so the gyro drift never turned the heading of
// a standing robot. robot_localization predicts to each measurement's stamp in between, which adds
// about 1e-4 of yaw rate variance, so each message overwrites the yaw rate and about half of the
// IMU's drift reaches the filtered yaw, whatever variances the two report.
//
// This node republishes torso_lift_imu/data on torso_lift_imu/data_ekf. When the odometry at the
// IMU message's stamp reports standstill (all velocities within 1e-8, Pr2Odometry's own
// standstill condition, under which it reports variance 1e-12), the orientation variance is set to
// still_orientation_variance so the EKF ignores that message. Otherwise the message is passed on
// unchanged. Without odometry (none received, or none within odom_timeout of the IMU stamp) it is
// also passed on unchanged: robot_pose_ekf then used the IMU alone too.

#include <cmath>
#include <deque>
#include <memory>

#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"

namespace
{
constexpr double kStillVelocity = 1e-8;  // Pr2Odometry's standstill threshold

class ImuStandstillGate : public rclcpp::Node
{
public:
  ImuStandstillGate()
  : Node("imu_standstill_gate")
  {
    still_variance_ = declare_parameter("still_orientation_variance", 1e3);
    history_ = rclcpp::Duration::from_seconds(declare_parameter("history", 2.0));
    odom_timeout_ = rclcpp::Duration::from_seconds(declare_parameter("odom_timeout", 1.0));

    pub_ = create_publisher<sensor_msgs::msg::Imu>("torso_lift_imu/data_ekf", 10);
    odom_sub_ = create_subscription<nav_msgs::msg::Odometry>(
      "base_odometry/odom", 10,
      [this](nav_msgs::msg::Odometry::ConstSharedPtr msg) {onOdom(*msg);});
    imu_sub_ = create_subscription<sensor_msgs::msg::Imu>(
      "torso_lift_imu/data", 10,
      [this](sensor_msgs::msg::Imu::UniquePtr msg) {onImu(std::move(msg));});
  }

private:
  struct OdomState
  {
    rclcpp::Time stamp;
    bool still;
  };

  void onOdom(const nav_msgs::msg::Odometry & msg)
  {
    const auto & v = msg.twist.twist;
    const bool still = std::fabs(v.linear.x) <= kStillVelocity &&
      std::fabs(v.linear.y) <= kStillVelocity && std::fabs(v.angular.z) <= kStillVelocity;
    const rclcpp::Time stamp(msg.header.stamp, RCL_ROS_TIME);
    if (!odom_.empty() && stamp < odom_.back().stamp) {
      odom_.clear();  // time jumped back (e.g. a bag restarted)
    }
    odom_.push_back({stamp, still});
    while (odom_.size() > 1 && stamp - odom_.front().stamp > history_) {
      odom_.pop_front();
    }
  }

  void onImu(sensor_msgs::msg::Imu::UniquePtr msg)
  {
    const rclcpp::Time stamp(msg->header.stamp, RCL_ROS_TIME);
    // The latest odometry at or before the IMU stamp (the oldest one if the IMU is older still).
    const OdomState * at = nullptr;
    for (auto it = odom_.rbegin(); it != odom_.rend(); ++it) {
      at = &*it;
      if (it->stamp <= stamp) {
        break;
      }
    }
    const bool odom_active = at && stamp - at->stamp <= odom_timeout_;
    if (odom_active && at->still) {
      msg->orientation_covariance[0] = still_variance_;
      msg->orientation_covariance[4] = still_variance_;
      msg->orientation_covariance[8] = still_variance_;
    }
    pub_->publish(std::move(msg));
  }

  double still_variance_;
  rclcpp::Duration history_{0, 0};
  rclcpp::Duration odom_timeout_{0, 0};
  std::deque<OdomState> odom_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr pub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
};
}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ImuStandstillGate>());
  rclcpp::shutdown();
  return 0;
}
