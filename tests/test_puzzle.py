import unittest

from levels import GoalSpec, Level, SourceSpec
from puzzle import DESIGN, FAILED, RUNNING, WON, Puzzle


def level(**overrides):
    spec = dict(
        name="Test", hint="", sources=[SourceSpec(100, 220, 12)], goals=[GoalSpec(600, 220, 10)],
        walls=[(300, 100, 20, 200)], pins={"pull": 1, "push": 1}, three_star_lost=0, two_star_lost=2,
    )
    spec.update(overrides)
    return Level(**spec)


class PuzzleTests(unittest.TestCase):
    def test_pin_inventory_is_limited(self):
        puzzle = Puzzle(level())
        self.assertIsNotNone(puzzle.place_pin("pull", 200, 50))
        self.assertIsNone(puzzle.place_pin("pull", 220, 50))
        self.assertEqual(puzzle.pins_left("pull"), 0)
        self.assertEqual(puzzle.pins_left("push"), 1)

    def test_pins_cannot_go_in_walls_or_on_sources(self):
        puzzle = Puzzle(level())
        self.assertIsNone(puzzle.place_pin("pull", 310, 200))
        self.assertIsNone(puzzle.place_pin("pull", 100, 220))
        self.assertIsNotNone(puzzle.place_pin("pull", 600, 220))  # rings are fine

    def test_restart_keeps_pins_and_resets_flow(self):
        puzzle = Puzzle(level())
        puzzle.place_pin("push", 200, 50)
        puzzle.release()
        for _ in range(50):
            puzzle.step()
        puzzle.restart()
        self.assertEqual(puzzle.state, DESIGN)
        self.assertEqual(len(puzzle.pins), 1)
        self.assertIs(puzzle.simulator.pins, puzzle.pins)
        self.assertEqual(puzzle.sources[0].units, 12)

    def test_release_toggles_pause(self):
        puzzle = Puzzle(level())
        puzzle.release()
        self.assertEqual(puzzle.state, RUNNING)
        puzzle.release()
        self.assertNotEqual(puzzle.state, RUNNING)

    def test_strength_is_clamped_and_sets_pressure_sign(self):
        puzzle = Puzzle(level())
        pull = puzzle.place_pin("pull", 200, 50)
        push = puzzle.place_pin("push", 200, 350)
        puzzle.change_strength(pull, 10)
        puzzle.change_strength(push, -10)
        self.assertEqual((pull.strength, push.strength), (3, 1))
        self.assertLess(pull.pressure, 0)
        self.assertGreater(push.pressure, 0)

    def test_running_out_of_flow_fails(self):
        puzzle = Puzzle(level(sources=[SourceSpec(100, 220, 12)], goals=[GoalSpec(600, 220, 10)], walls=[]))
        puzzle.simulator.nodes["S1"].units = 5
        puzzle.release()
        puzzle.step()
        self.assertEqual(puzzle.state, FAILED)

    def test_filling_every_ring_wins_with_stars_from_losses(self):
        puzzle = Puzzle(level(walls=[]))
        puzzle.release()
        while puzzle.state == RUNNING and puzzle.simulator.tick_count < 2000:
            puzzle.step()
        self.assertEqual(puzzle.state, WON)
        self.assertEqual(puzzle.stars, 3)

        puzzle.simulator.lost_units = 2
        self.assertEqual(puzzle._stars(), 2)
        puzzle.simulator.lost_units = 3
        self.assertEqual(puzzle._stars(), 1)


if __name__ == "__main__":
    unittest.main()
