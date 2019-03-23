# ! usr/bin/env python

import os

import numpy as np

import rospkg
import rospy
from cv_bridge import CvBridge
from gazebo_msgs.srv import DeleteModel, SpawnModel  # GetModelState,
from geometry_msgs.msg import Point, Pose, Quaternion
from open_manipulator_msgs.msg import KinematicsPose, OpenManipulatorState
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
from tf import TransformListener

base_dir = os.path.dirname(os.path.realpath(__file__))
overhead_orientation = Quaternion(
    x=-0.00142460053167, y=0.999994209902, z=-0.00177030764765, w=0.00253311793936
)


class OpenManipulatorRosInterface:
    def __init__(self):
        rospy.init_node("OpenManipulatorRosInterface")

        self.tf = TransformListener()
        self.bridge = CvBridge()
        self.joint_speeds = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_efforts = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.right_endpoint_position = [0, 0, 0]

        self.publisher_node()
        self.subscriber_node()
        self.init_robot_pose()

        rospy.on_shutdown(self._delete_target_block)

    def publish_node(self):
        self.pub_gripper_position = rospy.Publisher(
            "/open_manipulator/gripper_position/command", Float64, queue_size=1
        )
        self.pub_gripper_sub_position = rospy.Publisher(
            "/open_manipulator/gripper_sub_position/command", Float64, queue_size=1
        )
        self.pub_joint1_position = rospy.Publisher(
            "/open_manipulator/joint1_position/command", Float64, queue_size=1
        )
        self.pub_joint2_position = rospy.Publisher(
            "/open_manipulator/joint2_position/command", Float64, queue_size=1
        )
        self.pub_joint3_position = rospy.Publisher(
            "/open_manipulator/joint3_position/command", Float64, queue_size=1
        )
        self.pub_joint4_position = rospy.Publisher(
            "/open_manipulator/joint4_position/command", Float64, queue_size=1
        )

        self.joints_position_cmd = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.kinematics_cmd = [0.0, 0.0, 0.0]

    def subscribe_node(self):
        self.sub_joint_state = rospy.Subscriber(
            "/open_manipulator/joint_states", JointState, self.joint_state_callback
        )
        # joint position/velocity/effort
        self.sub_kinematics_pose = rospy.Subscriber(
            "/open_manipulator/gripper/kinematics_pose",
            KinematicsPose,
            self.kinematics_pose_callback,
        )
        self.sub_robot_state = rospy.Subscriber(
            "/open_manipulator/states", OpenManipulatorState, self.robot_state_callback
        )

        self.joint_names = [
            "gripper",
            "gripper_sub",
            "joint1",
            "joint2",
            "joint3",
            "joint4",
        ]
        self.joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_efforts = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        self.gripper_position = [0.0, 0.0, 0.0]  # [x, y, z] cartesian position
        self.gripper_orientiation = [0.0, 0.0, 0.0]  # [x, y, z, w] quaternion
        self.distance_threshold = 0.1

        self.moving_state = ""
        self.actuator_state = ""

    def joint_state_callback(self, msg):
        """Callback function of joint states subscriber.

        Args:
            msg (str): TODO: description
        """
        self.joints_states = msg
        self.joint_names = self.joints_states.name
        self.joint_positions = self.joints_states.position
        self.joint_velocities = self.joints_states.velocity
        self.joint_efforts = self.joints_states.effort
        # penalize jerky motion in reward for shaped reward setting.
        self.squared_sum_vel = np.linalg.norm(np.array(self.joint_velocities))

    def kinematics_pose_callback(self, msg):
        """Callback function of gripper kinematic pose subscriber.

        Args:
            msg (str): TODO: description
        """
        self.kinematics_pose = msg
        _gripper_position = self.kinematics_pose.pose.position
        self.gripper_position = [
            _gripper_position.x,
            _gripper_position.y,
            _gripper_position.z,
        ]
        _gripper_orientiation = self.kinematics_pose.pose.orientation
        self.gripper_orientiation = [
            _gripper_orientiation.x,
            _gripper_orientiation.y,
            _gripper_orientiation.z,
            _gripper_orientiation.w,
        ]

    def robot_state_callback(self, msg):
        """Callback function of robot state subscriber.

        Args:
            msg (str): TODO: description
        """
        self.moving_state = msg.open_manipulator_moving_state  # "MOVING" /
        # "STOPPED"
        self.actuator_state = msg.open_manipulator_actuator_state  #
        # "ACTUATOR_ENABLE" / "ACTUATOR_DISABLE"

    def get_joints_states(self):
        """Returns current joints states of robot including position,
        velocity, effort.

        Returns:
            Tuple of something (TODO)
        """
        return self.joint_positions, self.joint_velocities, self.joint_efforts

    def get_gripper_pose(self):
        """Returns gripper end effector position.

        Returns:
            Type: Description (TODO)
        """
        return self.gripper_position, self.gripper_orientiation

    def get_gripper_position(self):
        """Returns gripper end effector position.

        Returns:
            Tuple of something (TODO)
        """
        return self.gripper_position

    def set_joints_position(self, joints_angles):
        """Move joints using joint position command publishers.

        Args:
            joints_angles (type): Description (TODO)
        """
        # rospy.loginfo(Set joint position)
        self.pub_gripper_position.publish(joints_angles[0])
        self.pub_gripper_sub_position.publish(joints_angles[1])
        self.pub_joint1_position.publish(joints_angles[2])
        self.pub_joint2_position.publish(joints_angles[3])
        self.pub_joint3_position.publish(joints_angles[4])
        self.pub_joint4_position.publish(joints_angles[5])

    def _reset_gazebo_world(self):
        """Initialize randomly the state of robot agent and
        surrounding envs (including target obj.).
        """
        self._delete_target_block()

        self.pub_gripper_position.publish(np.random.uniform(0.0, 0.1))
        self.pub_joint1_position.publish(np.random.uniform(-0.1, 0.1))
        self.pub_joint2_position.publish(np.random.uniform(-0.1, 0.1))
        self.pub_joint3_position.publish(np.random.uniform(-0.1, 0.1))
        self.pub_joint4_position.publish(np.random.uniform(-0.1, 0.1))
        self._load_target_block()

    def init_robot_pose(self):
        """Description (TODO)"""
        self.pub_gripper_position.publish(np.random.uniform(0.0, 0.1))
        self.pub_joint1_position.publish(np.random.uniform(-0.1, 0.1))
        self.pub_joint2_position.publish(np.random.uniform(-0.1, 0.1))
        self.pub_joint3_position.publish(np.random.uniform(-0.1, 0.1))
        self.pub_joint4_position.publish(np.random.uniform(-0.1, 0.1))
        self._load_target_block()

    def _load_target_block(self):
        """Description (TODO)"""
        # Desciription why the below commented code exists (TODO)
        # block_pose = Pose(position=Point(x=0.6725, y=0.1265, z=0.7825))

        # TODO: No hard-coding
        block_reference_frame = "world"
        model_path = rospkg.RosPack().get_path("kair_algorithms") + "/urdf/"

        block_xml = ""  # Load Block URDF

        with open(model_path + "block/model.urdf", "r") as block_file:
            block_xml = block_file.read().replace("\n", "")

        rand_pose = Pose(
            position=Point(
                x=np.random.uniform(0.1, 0.15),
                y=np.random.uniform(0, 50.6),
                z=np.random.uniform(0.0, 0.1),
            ),
            orientation=overhead_orientation,
        )

        rospy.wait_for_service("/gazebo/spawn_urdf_model")

        try:
            spawn_urdf = rospy.ServiceProxy("/gazebo/spawn_urdf_model", SpawnModel)
            spawn_urdf("block", block_xml, "/", rand_pose, block_reference_frame)
        except rospy.ServiceException as e:
            rospy.logerr("Spawn URDF service call failed: {0}".format(e))

    def _delete_target_block(self):
        """This will be called on ROS Exit, deleting Gazebo models
        Do not wait for the Gazebo Delete Model service, since
        Gazebo should already be running. If the service is not
        available since Gazebo has been killed, it is fine to error out
        """
        try:
            delete_model = rospy.ServiceProxy("/gazebo/delete_model", DeleteModel)
            delete_model("block")
        except rospy.ServiceException as e:
            rospy.loginfo("Delete Model service call failed: {0}".format(e))
