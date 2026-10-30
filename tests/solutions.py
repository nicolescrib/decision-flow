"""Scripted solutions for every puzzle level.

Each solution places pins, releases the flow, and optionally drags a pin
along waypoints at a fixed speed, the way a player would with the mouse.
The level tests replay these to prove every level can still be won with
three stars after physics or level changes.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Sequence, Tuple

import numpy as np

from levels import LEVELS
from puzzle import RUNNING, Puzzle

# (kind, x, y, strength)
PinSpec = Tuple[str, float, float, int]
# (pin index, start tick, waypoints, pixels per tick)
DragSpec = Tuple[int, int, Sequence[Tuple[float, float]], float]

SOLUTIONS: Dict[int, Tuple[List[PinSpec], List[DragSpec]]] = {
    0: ([], []),
    1: ([("pull", 300, 40, 2)], [(0, 200, [(560, 40), (625, 215)], 2.0)]),
    2: ([("push", 191, 99, 1)], []),
    3: ([("pull", 200, 220, 2)], [(0, 260, [(400, 90), (600, 90), (600, 92), (450, 150), (450, 300), (600, 350)], 2.0)]),
    4: ([("push", 150, 188, 2), ("pull", 320, 78, 2)], []),
    5: ([("pull", 160, 340, 2)], [(0, 260, [(330, 300), (330, 110), (520, 110), (640, 220)], 2.0)]),
    6: ([("pull", 200, 220, 2)], [(0, 260, [(300, 150), (620, 120), (622, 120), (710, 220), (640, 320)], 2.0)]),
    7: ([("push", 95, 186, 2), ("push", 119, 215, 1)], []),
    8: ([("pull", 180, 220, 2)], [(0, 260, [(180, 40), (650, 40), (650, 110), (652, 110), (720, 220), (650, 330)], 2.0)]),
    9: ([("pull", 370, 330, 2)], [(0, 280, [(370, 300), (180, 290), (150, 200), (90, 80), (92, 80), (250, 60),
                                             (370, 50), (372, 50), (500, 60), (650, 80)], 2.0)]),
}


def play(index: int, max_ticks: int = 2500, seed: int = 0) -> Puzzle:
    random.seed(seed)
    np.random.seed(seed)
    pins, drags = SOLUTIONS[index]
    puzzle = Puzzle(LEVELS[index])
    for kind, x, y, strength in pins:
        pin = puzzle.place_pin(kind, x, y)
        assert pin is not None, f"cannot place {kind} pin at {(x, y)}"
        puzzle.change_strength(pin, strength - pin.strength)
    puzzle.release()

    tracks = [(pin_index, start, list(points), speed) for pin_index, start, points, speed in drags]
    while puzzle.state == RUNNING and puzzle.simulator.tick_count < max_ticks:
        tick = puzzle.simulator.tick_count
        for pin_index, start, points, speed in tracks:
            if tick < start or not points:
                continue
            pin = puzzle.pins[pin_index]
            tx, ty = points[0]
            distance = math.hypot(tx - pin.x, ty - pin.y)
            if distance <= speed:
                pin.x, pin.y = points.pop(0)
            else:
                pin.x += (tx - pin.x) / distance * speed
                pin.y += (ty - pin.y) / distance * speed
        puzzle.step()
    return puzzle
