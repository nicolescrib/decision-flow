import random
import unittest

import numpy as np

from levels import AMBER, CYAN
from simulator import ROLE_GOAL, ROLE_SOURCE, Simulator, Void, Wall


def seeded(seed=3):
    random.seed(seed)
    np.random.seed(seed)


class SandboxTests(unittest.TestCase):
    def test_units_are_conserved(self):
        seeded()
        simulator = Simulator()
        simulator.create_default_graph()
        simulator.add_random_node()
        start = simulator.total_units
        for tick in range(500):
            simulator.tick()
            if tick == 200:
                simulator.remove_random_node()
            if tick == 300:
                simulator.toggle_pressure_inverted()
        self.assertAlmostEqual(simulator.total_units, start, places=6)


class PuzzlePhysicsTests(unittest.TestCase):
    def make(self):
        simulator = Simulator(width=400, height=200)
        simulator.damping = 0.965
        simulator.max_speed = 5.0
        return simulator

    def test_voids_destroy_particles_and_count_them(self):
        seeded()
        simulator = self.make()
        simulator.add_node("S", units=30, pressure=1.5, capacity=30, radius=10, x=50, y=100, role=ROLE_SOURCE)
        simulator.voids = [Void(250, 100, radius=15, pressure=-3.0)]
        for _ in range(600):
            simulator.tick()
        self.assertGreater(simulator.lost_units, 0)
        self.assertEqual(simulator.total_units + simulator.lost_units, 30)

    def test_particles_never_end_up_inside_walls(self):
        seeded()
        simulator = self.make()
        simulator.add_node("S", units=40, pressure=1.5, capacity=40, radius=10, x=50, y=100, role=ROLE_SOURCE)
        simulator.add_node("G", units=0, pressure=-3.0, capacity=40, radius=12, x=350, y=100, role=ROLE_GOAL)
        wall = Wall(190, 40, 20, 120)
        simulator.walls = [wall]
        for _ in range(400):
            simulator.tick()
            for x, y in simulator.particle_positions:
                self.assertFalse(wall.x < x < wall.x + wall.w and wall.y < y < wall.y + wall.h)

    def test_colored_goal_only_takes_its_own_color(self):
        seeded()
        simulator = self.make()
        simulator.add_node("G", units=0, pressure=-2.0, capacity=10, radius=12, x=200, y=100, role=ROLE_GOAL, color=CYAN)
        simulator._append_particles([[200, 100], [201, 100]], [[0, 0], [0, 0]], [AMBER, CYAN])
        simulator.tick()
        self.assertEqual(simulator.nodes["G"].units, 1)
        self.assertEqual(list(simulator.particle_colors), [AMBER])

    def test_full_goal_goes_quiet(self):
        simulator = self.make()
        simulator.add_node("G", units=5, pressure=-2.0, capacity=5, radius=12, x=200, y=100, role=ROLE_GOAL)
        self.assertEqual(simulator.effective_pressure(simulator.nodes["G"]), 0.0)

    def test_predict_path_heads_for_the_goal(self):
        simulator = self.make()
        simulator.add_node("S", units=10, pressure=1.5, capacity=10, radius=10, x=50, y=100, role=ROLE_SOURCE)
        simulator.add_node("G", units=0, pressure=-2.0, capacity=10, radius=12, x=350, y=100, role=ROLE_GOAL)
        path = simulator.predict_path(simulator.nodes["S"])
        end_x, end_y = path[-1]
        self.assertLess(abs(end_x - 350) + abs(end_y - 100), 25)


if __name__ == "__main__":
    unittest.main()
