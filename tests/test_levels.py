import unittest

from levels import LEVELS
from puzzle import WON
from tests.solutions import SOLUTIONS, play


class LevelTests(unittest.TestCase):
    def test_every_level_has_a_solution(self):
        self.assertEqual(sorted(SOLUTIONS), list(range(len(LEVELS))))

    def test_every_level_is_winnable_with_three_stars(self):
        for index, level in enumerate(LEVELS):
            with self.subTest(level=level.name):
                puzzle = play(index)
                self.assertEqual(puzzle.state, WON)
                self.assertEqual(puzzle.stars, 3)

    def test_levels_have_spare_flow(self):
        for level in LEVELS:
            with self.subTest(level=level.name):
                self.assertGreaterEqual(level.supply, level.need)
                self.assertLessEqual(level.three_star_lost, level.two_star_lost)
                self.assertLessEqual(level.two_star_lost, level.supply - level.need)


if __name__ == "__main__":
    unittest.main()
