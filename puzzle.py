from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from levels import Level
from simulator import ROLE_GOAL, ROLE_SOURCE, Node, Pin

DESIGN = "design"     # pins can be placed; the sources are still closed
RUNNING = "running"
PAUSED = "paused"
WON = "won"
FAILED = "failed"

PIN_KINDS = ("pull", "push")
PIN_PRESSURE_PER_STRENGTH = 2.0
MAX_PIN_STRENGTH = 3
PIN_RADIUS = 9.0

# Ticks the board must sit still, with nothing left to emit, before the
# player is nudged that the flow has settled.
SETTLE_TICKS = 90


class Puzzle:
    """Rules for one level: pin placement, the run state, and win/lose/stars.

    Pins survive restarts so the player can iterate on a layout.
    """

    def __init__(self, level: Level) -> None:
        self.level = level
        self.pins: List[Pin] = []
        self.restart()

    # ---------------------------------------------------------------- set-up

    def restart(self) -> None:
        self.simulator = self.level.build()
        self.simulator.pins = self.pins
        self.state = DESIGN
        self.stars = 0
        self.settled = False
        self._still_ticks = 0

    def pins_left(self, kind: str) -> int:
        placed = sum(1 for pin in self.pins if pin.kind == kind)
        return self.level.pins.get(kind, 0) - placed

    def can_place(self, x: float, y: float) -> bool:
        if not (0.0 <= x <= self.simulator.width and 0.0 <= y <= self.simulator.height):
            return False
        if any(wall.contains(x, y, margin=PIN_RADIUS * 0.5) for wall in self.simulator.walls):
            return False
        # Pins may sit on rings (that is how a carried swarm is delivered) but
        # not on top of sources.
        return all(
            math.hypot(x - node.x, y - node.y) > node.radius + PIN_RADIUS
            for node in self.simulator.nodes.values() if node.role == ROLE_SOURCE
        )

    def place_pin(self, kind: str, x: float, y: float) -> Optional[Pin]:
        if self.state in (WON, FAILED) or self.pins_left(kind) <= 0 or not self.can_place(x, y):
            return None
        pin = Pin(x=x, y=y, pressure=0.0, kind=kind, strength=2)
        self._apply_strength(pin)
        self.pins.append(pin)
        return pin

    def move_pin(self, pin: Pin, x: float, y: float) -> bool:
        if self.state in (WON, FAILED) or not self.can_place(x, y):
            return False
        pin.x, pin.y = x, y
        return True

    def remove_pin(self, pin: Pin) -> None:
        if pin in self.pins:
            self.pins.remove(pin)

    def clear_pins(self) -> None:
        self.pins.clear()

    def change_strength(self, pin: Pin, delta: int) -> None:
        pin.strength = max(1, min(MAX_PIN_STRENGTH, pin.strength + delta))
        self._apply_strength(pin)

    @staticmethod
    def _apply_strength(pin: Pin) -> None:
        sign = -1.0 if pin.kind == "pull" else 1.0
        pin.pressure = sign * pin.strength * PIN_PRESSURE_PER_STRENGTH

    def pin_at(self, x: float, y: float) -> Optional[Pin]:
        for pin in reversed(self.pins):
            if math.hypot(x - pin.x, y - pin.y) <= PIN_RADIUS + 4.0:
                return pin
        return None

    # ----------------------------------------------------------------- state

    @property
    def sources(self) -> List[Node]:
        return [node for node in self.simulator.nodes.values() if node.role == ROLE_SOURCE]

    @property
    def goals(self) -> List[Node]:
        return [node for node in self.simulator.nodes.values() if node.role == ROLE_GOAL]

    @property
    def lost(self) -> int:
        return self.simulator.lost_units

    @property
    def is_over(self) -> bool:
        return self.state in (WON, FAILED)

    def release(self) -> None:
        """Open the sources (first press), then toggle pause."""
        if self.state in (DESIGN, PAUSED):
            self.state = RUNNING
        elif self.state == RUNNING:
            self.state = PAUSED

    def step(self) -> None:
        if self.state != RUNNING:
            return
        self.simulator.tick()
        self._check_outcome()
        self._check_settled()

    def _check_outcome(self) -> None:
        if all(goal.is_full for goal in self.goals):
            self.state = WON
            self.stars = self._stars()
            return
        if not self._can_still_win():
            self.state = FAILED

    def _can_still_win(self) -> bool:
        simulator = self.simulator
        supply: Dict[int, int] = {}
        for source in self.sources:
            color = source.color or 0
            supply[color] = supply.get(color, 0) + int(source.units)
        for color, count in zip(*np.unique(simulator.particle_colors, return_counts=True)):
            supply[int(color)] = supply.get(int(color), 0) + int(count)

        need_any = 0
        for goal in self.goals:
            missing = int(round(goal.capacity - goal.units))
            if goal.color is None:
                need_any += missing
            else:
                supply[goal.color] = supply.get(goal.color, 0) - missing
                if supply[goal.color] < 0:
                    return False
        return sum(supply.values()) >= need_any

    def _check_settled(self) -> None:
        velocities = self.simulator.particle_velocities
        emitting = any(source.units >= 1.0 for source in self.sources)
        still = not emitting and (len(velocities) == 0 or float(np.abs(velocities).max()) < 0.05)
        self._still_ticks = self._still_ticks + 1 if still else 0
        self.settled = self._still_ticks >= SETTLE_TICKS

    def _stars(self) -> int:
        if self.lost <= self.level.three_star_lost:
            return 3
        if self.lost <= self.level.two_star_lost:
            return 2
        return 1
