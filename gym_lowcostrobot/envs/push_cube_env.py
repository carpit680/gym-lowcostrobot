import time
import numpy as np

import mujoco
import mujoco.viewer

from gymnasium import spaces

from gym_lowcostrobot.rewards import proximity_reward

from gym_lowcostrobot.envs.base_env import BaseEnv


class PushCubeEnv(BaseEnv):
    def __init__(
        self,
        xml_path="assets/scene_one_cube.xml",
        image_state=None,
        action_mode="joint",
        render_mode=None
    ):
        super().__init__(
            xml_path=xml_path,
            image_state=image_state,
            action_mode=action_mode,
            render_mode=render_mode
        )

        # Define the action space and observation space
        if self.action_mode == "ee":
            self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(3,), dtype=np.float32)
        else:
            self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(5,), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.data.xpos.flatten().shape[0] + 3,),
            dtype=np.float32,
        )

        self.threshold_distance = 0.26

    def reset(self, seed=None, options=None):
        # We need the following line to seed self.np_random
        super().reset(seed=seed)
        self.data.joint("red_box_joint").qpos[:3] = [
            self.np_random.random() * 0.2,
            self.np_random.random() * 0.2,
            0.01,
        ]
        mujoco.mj_step(self.model, self.data)

        self.target_pos = np.array([self.np_random.random() * 0.2, self.np_random.random() * 0.2, 0.01])
        self.step_start = time.time()
        self.current_step = 0

        info = self.get_info()

        return self.current_state(), info

    def current_state(self):
        return np.concatenate([self.data.xpos.flatten(), self.target_pos], dtype=np.float32)

    def reward(self):
        cube_id = self.model.body("box").id
        cube_pos = self.data.geom_xpos[cube_id]
        return proximity_reward(cube_pos, self.target_pos)

    def step(self, action):
        # Perform the action and step the simulation
        self.base_step_action_nograsp(action)

        # Compute the reward based on the distance
        distance = self.reward()
        reward = -distance

        # Check if the target position is reached
        terminated = distance < self.threshold_distance

        # Return the next observation, reward, terminated flag, and additional info
        next_observation = self.current_state()

        # Check if the episode is timed out, fill info dictionary
        info = self.get_info()

        return next_observation, reward, terminated, False, info
