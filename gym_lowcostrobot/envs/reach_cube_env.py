import os

import gymnasium as gym
import mujoco
import mujoco.viewer
import numpy as np
from gymnasium import spaces

from gym_lowcostrobot import ASSETS_PATH
from gym_lowcostrobot.envs.base_env import BaseRobotEnv


class ReachCubeEnv(BaseRobotEnv):
    """
    ## Description

    The robot has to reach a cube with its end-effector. The episode is terminated when the end-effector is within a
    threshold distance from the cube.

    ## Action space

    Two action modes are available: "joint" and "ee". In the "joint" mode, the action space is a 5-dimensional box
    representing the target joint angles.

    | Index | Action              | Type (unit) | Min  | Max |
    | ----- | ------------------- | ----------- | ---- | --- |
    | 0     | Shoulder pan joint  | Float (rad) | -1.0 | 1.0 |
    | 1     | Shoulder lift joint | Float (rad) | -1.0 | 1.0 |
    | 2     | Elbow flex joint    | Float (rad) | -1.0 | 1.0 |
    | 3     | Wrist flex joint    | Float (rad) | -1.0 | 1.0 |
    | 4     | Wrist roll joint    | Float (rad) | -1.0 | 1.0 |

    In the "ee" mode, the action space is a 3-dimensional box representing the target end-effector position and the
    gripper position.

    | Index | Action        | Type (unit) | Min  | Max |
    | ----- | ------------- | ----------- | ---- | --- |
    | 0     | X             | Float (m)   | -1.0 | 1.0 |
    | 1     | Y             | Float (m)   | -1.0 | 1.0 |
    | 2     | Z             | Float (m)   | -1.0 | 1.0 |

    ## Observation space

    The observation space is a dictionary containing the following subspaces:

    - `"arm_qpos"`: the joint angles of the robot arm in radians, shape (6,)
    - `"arm_qvel"`: the joint velocities of the robot arm in radians per second, shape (6,)
    - `"image_front"`: the front image of the camera of size (240, 320, 3)
    - `"image_top"`: the top image of the camera of size (240, 320, 3)
    - `"object_qpos"`: the position of the cube, as (x, y, z)

    Three observation modes are available: "image" (default), "state", and "both".

    | Key             | `"image"` | `"state"` | `"both"` |
    | --------------- | --------- | --------- | -------- |
    | `"arm_qpos"`    | ✓         | ✓         | ✓        |
    | `"arm_qvel"`    | ✓         | ✓         | ✓        |
    | `"image_front"` | ✓         |           | ✓        |
    | `"image_top"`   | ✓         |           | ✓        |
    | `"object_qpos"` |           | ✓         | ✓        |

    ## Reward

    The reward is the negative distance between the end-effector and the cube. The episode is terminated when the
    distance is less than a threshold.
    """

    def __init__(self, observation_mode="image", action_mode="joint", render_mode=None):
        super().__init__(
            xml_path=os.path.join(ASSETS_PATH, "scene_one_cube.xml"),
            observation_mode=observation_mode,
            action_mode=action_mode,
            render_mode=render_mode,
        )

        # Define the action space and observation space
        action_shape = {"joint": 5, "ee": 3}[action_mode]
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(action_shape,), dtype=np.float32)

        # Set the observations space
        observation_subspaces = {
            "arm_qpos": spaces.Box(low=-np.pi, high=np.pi, shape=(6,)),
            "arm_qvel": spaces.Box(low=-10.0, high=10.0, shape=(6,)),
        }
        if observation_mode in ["image", "both"]:
            observation_subspaces["image_front"] = spaces.Box(0, 255, shape=(240, 320, 3), dtype=np.uint8)
            observation_subspaces["image_top"] = spaces.Box(0, 255, shape=(240, 320, 3), dtype=np.uint8)
        if observation_mode in ["state", "both"]:
            observation_subspaces["object_qpos"] = spaces.Box(low=-10.0, high=10.0, shape=(3,))
        self.observation_space = gym.spaces.Dict(observation_subspaces)

        # Initialize the robot and target positions
        self.threshold_distance = 0.01
        self.object_low = np.array([-0.15, -0.15, 0.05])
        self.object_high = np.array([0.15, 0.15, 0.05])

    def reset(self, seed=None, options=None):
        # We need the following line to seed self.np_random
        super().reset(seed=seed, options=options)

        # Reset the robot to the initial position and sample the object position
        robot_qpos = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        object_pos = self.np_random.uniform(self.object_low, self.object_high)
        object_rot = np.array([1.0, 0.0, 0.0, 0.0])
        self.data.qpos[:13] = np.concatenate([robot_qpos, object_pos, object_rot])

        # Step the simulation
        mujoco.mj_forward(self.model, self.data)

        return self.get_observation(), {}

    def step(self, action):
        # Perform the action and step the simulation
        self.apply_action(action, block_gripper=True)

        # Get the new observation
        observation = self.get_observation()

        # Compute the distance between the cube and the end-effector
        cube_pos = self.data.joint("red_box_joint").qpos[:3]
        ee_pos = self.data.joint("gripper_opening").qpos[:3]
        distance = np.linalg.norm(cube_pos - ee_pos)

        # Compute the reward based on the distance
        reward = -distance

        # The episode is terminated if the distance is less than the threshold
        terminated = distance < self.threshold_distance

        return observation, reward, terminated, False, {}
