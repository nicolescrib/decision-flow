from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from simulator import ROLE_GOAL, ROLE_SOURCE, Simulator, Void, Wall

BOARD_WIDTH = 740.0
BOARD_HEIGHT = 440.0

AMBER = 0
CYAN = 1


@dataclass
class SourceSpec:
    x: float
    y: float
    units: int
    pressure: float = 1.5
    color: int = AMBER


@dataclass
class GoalSpec:
    x: float
    y: float
    target: int
    pressure: float = -2.0
    radius: float = 16.0
    color: Optional[int] = None


@dataclass
class VoidSpec:
    x: float
    y: float
    radius: float = 16.0
    pressure: float = -1.5
    orbit_radius: float = 0.0
    orbit_speed: float = 0.0
    phase: float = 0.0


@dataclass
class Level:
    name: str
    hint: str
    sources: List[SourceSpec]
    goals: List[GoalSpec]
    walls: List[Tuple[float, float, float, float]] = field(default_factory=list)
    voids: List[VoidSpec] = field(default_factory=list)
    # How many pins of each kind ("pull", "push") the player may place.
    pins: Dict[str, int] = field(default_factory=dict)
    # Most particles that may fall into voids for three and two stars.
    three_star_lost: int = 0
    two_star_lost: int = 3

    @property
    def supply(self) -> int:
        return sum(source.units for source in self.sources)

    @property
    def need(self) -> int:
        return sum(goal.target for goal in self.goals)

    def build(self) -> Simulator:
        simulator = Simulator(width=BOARD_WIDTH, height=BOARD_HEIGHT)
        # Puzzle physics: less drag than the sandbox so streams carry momentum
        # and curve around pins, capped so particles cannot tunnel through walls.
        simulator.damping = 0.965
        simulator.max_speed = 5.0
        simulator.emission_speed = 3.0
        simulator.emission_speed_jitter = 0.08
        simulator.emission_angle_jitter = 0.06
        simulator.wall_restitution = 0.45
        simulator.particle_repulsion = 2.0
        simulator.repulsion_range = 16.0

        for index, source in enumerate(self.sources):
            simulator.add_node(
                f"S{index + 1}", units=source.units, pressure=source.pressure, capacity=source.units,
                radius=13.0, x=source.x, y=source.y, role=ROLE_SOURCE, color=source.color,
            )
        for index, goal in enumerate(self.goals):
            simulator.add_node(
                f"G{index + 1}", units=0.0, pressure=goal.pressure, capacity=goal.target,
                radius=goal.radius, x=goal.x, y=goal.y, role=ROLE_GOAL, color=goal.color,
            )
        simulator.walls = [Wall(*rect) for rect in self.walls]
        simulator.voids = [
            Void(v.x, v.y, radius=v.radius, pressure=v.pressure, orbit_radius=v.orbit_radius,
                 orbit_speed=v.orbit_speed, phase=v.phase)
            for v in self.voids
        ]
        return simulator


LEVELS: List[Level] = [
    Level(
        name="First Light",
        hint="Press SPACE to open the source and let the flow find the ring.",
        sources=[SourceSpec(110, 220, 24)],
        goals=[GoalSpec(630, 220, 20)],
    ),
    Level(
        name="Detour",
        hint="A wall blocks the way. Drag the PULL pin from the tray to bend the stream around it.",
        sources=[SourceSpec(110, 220, 26)],
        goals=[GoalSpec(630, 220, 20)],
        walls=[(360, 70, 20, 300)],
        pins={"pull": 1},
    ),
    Level(
        name="Event Horizon",
        hint="Voids swallow the flow for good. A PUSH pin can shield it. Scroll on a pin to change its strength.",
        sources=[SourceSpec(110, 220, 26)],
        goals=[GoalSpec(630, 220, 20)],
        voids=[VoidSpec(370, 220, radius=18)],
        pins={"push": 1},
        three_star_lost=1,
        two_star_lost=4,
    ),
    Level(
        name="Fork in the Road",
        hint="Two rings, one stream. Feed one, then move your pin to feed the other.",
        sources=[SourceSpec(100, 220, 34)],
        goals=[GoalSpec(600, 90, 15, pressure=-1.2), GoalSpec(600, 350, 15, pressure=-1.2)],
        voids=[VoidSpec(620, 220, radius=20, pressure=-1.0)],
        pins={"pull": 1},
        three_star_lost=1,
        two_star_lost=4,
    ),
    Level(
        name="Moonlet",
        hint="The void orbits the ring. Time your release, or guard the gap.",
        sources=[SourceSpec(100, 220, 32)],
        goals=[GoalSpec(470, 220, 25)],
        voids=[VoidSpec(470, 220, radius=15, pressure=-0.8, orbit_radius=80, orbit_speed=0.025, phase=3.14)],
        pins={"push": 1, "pull": 1},
        three_star_lost=2,
        two_star_lost=6,
    ),
    Level(
        name="Two Springs",
        hint="Both sources share one ring, but the upper spring is walled in.",
        sources=[SourceSpec(90, 80, 18), SourceSpec(90, 360, 18)],
        goals=[GoalSpec(640, 220, 32)],
        walls=[(220, 0, 20, 290), (420, 150, 20, 290)],
        voids=[VoidSpec(330, 400, radius=18)],
        pins={"pull": 1, "push": 1},
        three_star_lost=1,
        two_star_lost=3,
    ),
    Level(
        name="Sorting",
        hint="Rings only accept their own colour, and only pull on it. Uncross the streams.",
        sources=[SourceSpec(90, 120, 18, color=AMBER), SourceSpec(90, 320, 18, color=CYAN)],
        goals=[GoalSpec(640, 320, 15, color=AMBER), GoalSpec(640, 120, 15, color=CYAN)],
        walls=[(300, 205, 200, 30)],
        voids=[VoidSpec(560, 220, radius=16)],
        pins={"push": 1, "pull": 1},
        three_star_lost=1,
        two_star_lost=4,
    ),
    Level(
        name="The Narrows",
        hint="Thread the stream through the gap. Push pins make good banks.",
        sources=[SourceSpec(90, 220, 30)],
        goals=[GoalSpec(650, 220, 25)],
        walls=[(330, 0, 24, 196), (330, 244, 24, 196)],
        voids=[VoidSpec(250, 120, radius=16), VoidSpec(250, 320, radius=16)],
        pins={"push": 2},
        three_star_lost=1,
        two_star_lost=4,
    ),
    Level(
        name="Crossfire",
        hint="Two colours, two moons. Keep each stream on its own side.",
        sources=[SourceSpec(90, 110, 20, color=CYAN), SourceSpec(90, 330, 20, color=AMBER)],
        goals=[GoalSpec(650, 110, 16, color=AMBER), GoalSpec(650, 330, 16, color=CYAN)],
        voids=[
            VoidSpec(370, 220, radius=14, pressure=-0.8, orbit_radius=95, orbit_speed=0.02),
            VoidSpec(370, 220, radius=14, pressure=-0.8, orbit_radius=95, orbit_speed=0.02, phase=3.14),
        ],
        pins={"push": 1, "pull": 2},
        three_star_lost=2,
        two_star_lost=6,
    ),
    Level(
        name="Equilibrium",
        hint="Three rings and barely enough flow. Every particle is a decision.",
        sources=[SourceSpec(370, 400, 40)],
        goals=[GoalSpec(90, 80, 12, pressure=-1.2), GoalSpec(370, 50, 12, pressure=-1.2), GoalSpec(650, 80, 12, pressure=-1.2)],
        walls=[(200, 230, 340, 20)],
        voids=[VoidSpec(370, 160, radius=16, pressure=-1.0), VoidSpec(120, 330, radius=16), VoidSpec(620, 330, radius=16)],
        pins={"pull": 2, "push": 1},
        three_star_lost=1,
        two_star_lost=3,
    ),
]
