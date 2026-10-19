from __future__ import annotations

import math
import random
import string
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# Node roles. "node" is the original sandbox node, which emits, absorbs, pulls
# and trades units with its neighbours depending on its pressure. Puzzle
# levels use the narrower "source" (only emits) and "goal" (only absorbs, and
# falls quiet once full) roles instead.
ROLE_NODE = "node"
ROLE_SOURCE = "source"
ROLE_GOAL = "goal"

# A field source with this colour acts on particles of every colour.
ANY_COLOR = -1


@dataclass
class Node:
    id: str
    units: float = 0.0
    pressure: float = 0.0
    capacity: float = 100.0
    radius: float = 4.0
    x: float = 0.0
    y: float = 0.0
    role: str = ROLE_NODE
    # Sources emit particles of this colour; goals only attract and accept it.
    # None means colour 0 for emission and "any colour" for goals.
    color: Optional[int] = None

    def clamp(self) -> None:
        self.units = max(0.0, min(self.units, self.capacity))

    @property
    def is_full(self) -> bool:
        return self.units >= self.capacity - 1e-9


@dataclass
class Pin:
    """A field-only influence: pushes or pulls particles but never holds units."""

    x: float
    y: float
    pressure: float
    kind: str = "pull"
    strength: int = 1


@dataclass
class Wall:
    """Axis-aligned rectangle that particles bounce off."""

    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float, margin: float = 0.0) -> bool:
        return (
            self.x - margin <= px <= self.x + self.w + margin
            and self.y - margin <= py <= self.y + self.h + margin
        )


@dataclass
class Void:
    """Destroys any particle it touches. Optionally orbits a fixed centre."""

    x: float
    y: float
    radius: float = 12.0
    pressure: float = -1.0
    orbit_radius: float = 0.0
    orbit_speed: float = 0.0   # radians per tick
    phase: float = 0.0
    cx: float = field(init=False)
    cy: float = field(init=False)

    def __post_init__(self) -> None:
        self.cx = self.x
        self.cy = self.y
        self.move_to_tick(0)

    def move_to_tick(self, tick: int) -> None:
        if self.orbit_radius <= 0.0:
            return
        angle = self.phase + self.orbit_speed * tick
        self.x = self.cx + math.cos(angle) * self.orbit_radius
        self.y = self.cy + math.sin(angle) * self.orbit_radius


class Simulator:
    MIN_NODE_RADIUS = 3.0
    MAX_NODE_RADIUS = 6.0
    BOUNDARY_MARGIN = 0.10
    MAX_PRESSURE = 6.0
    PARTICLE_RADIUS = 1.5

    # Global pressure-field modifiers (see effective_pressure / display_pressure).
    MIN_GAIN = 0.0
    MAX_GAIN = 3.0
    GAIN_STEP = 0.1

    # Default physics. Each is copied onto the instance so puzzle levels can
    # tune their own feel without affecting the sandbox.
    FORCE_CONSTANT = 40.0
    DAMPING = 0.92
    MIN_DISTANCE = 12.0
    EMISSION_CHARGE_RATE = 0.12
    EMISSION_SPEED = 1.5
    EMISSION_SPEED_JITTER = 0.5     # speed is scaled by a random factor in [1 - j, 1 + j]
    EMISSION_ANGLE_JITTER = 0.0     # radians either side of the launch direction
    WALL_RESTITUTION = 0.5
    PULL_RANGE = 25.0               # radius (sim units) from which negative-pressure nodes pull particles
    PULL_CHARGE_RATE = 0.12         # rate at which pull charge accumulates (mirrors emission)

    # Direct node-to-node pressure flow.
    FLOW_PRESSURE_THRESHOLD = 1.0   # |effective pressure| difference to trigger flow
    FLOW_RATE = 0.04                # units transferred per unit of pressure differential per tick
    FLOW_RANGE = 100.0              # max centre-to-centre distance (sim units) for direct flow

    def __init__(self, width: float = 500.0, height: float = 400.0) -> None:
        self.width = width
        self.height = height
        self.nodes: Dict[str, Node] = {}
        self.pins: List[Pin] = []
        self.walls: List[Wall] = []
        self.voids: List[Void] = []
        # Particles are stored as structure-of-arrays (positions/velocities as
        # Nx2 numpy arrays, colours as an N array) rather than a list of
        # objects so that the physics in tick() can be vectorized instead of
        # looped in pure Python.
        self.particle_positions: np.ndarray = np.empty((0, 2), dtype=np.float64)
        self.particle_velocities: np.ndarray = np.empty((0, 2), dtype=np.float64)
        self.particle_colors: np.ndarray = np.empty(0, dtype=np.int64)
        self.tick_count: int = 0
        self.total_units: float = 0.0
        # Units destroyed by voids. nodes + particles + lost_units is conserved.
        self.lost_units: int = 0
        # What happened during the last tick, for sound and visual effects:
        # ("absorb", node_id, x, y), ("lost", x, y) and ("emit", node_id).
        self.events: List[tuple] = []
        self._initial_units: Dict[str, float] = {}
        self._emission_charge: Dict[str, float] = {}
        # Global field modifiers applied on top of each node's authored pressure.
        self.pressure_gain: float = 1.0
        self.pressure_inverted: bool = False
        self._pull_charge: Dict[str, float] = {}

        self.force_constant = self.FORCE_CONSTANT
        self.damping = self.DAMPING
        self.min_distance = self.MIN_DISTANCE
        self.emission_charge_rate = self.EMISSION_CHARGE_RATE
        self.emission_speed = self.EMISSION_SPEED
        self.emission_speed_jitter = self.EMISSION_SPEED_JITTER
        self.emission_angle_jitter = self.EMISSION_ANGLE_JITTER
        self.wall_restitution = self.WALL_RESTITUTION
        self.max_speed: Optional[float] = None
        self.particle_repulsion = 0.0
        self.repulsion_range = 10.0

    def add_node(
        self,
        node_id: str,
        units: float = 0.0,
        pressure: float = 0.0,
        capacity: float = 100.0,
        radius: float = 4.0,
        x: float = 0.0,
        y: float = 0.0,
        role: str = ROLE_NODE,
        color: Optional[int] = None,
    ) -> None:
        node = Node(
            id=node_id, units=units, pressure=pressure, capacity=capacity, radius=radius, x=x, y=y,
            role=role, color=color,
        )
        if role == ROLE_NODE:
            # Set radius immediately from units so the node renders at the right size from frame one.
            t = max(0.0, min(1.0, units / max(capacity, 1.0)))
            node.radius = self.MIN_NODE_RADIUS + t * (self.MAX_NODE_RADIUS - self.MIN_NODE_RADIUS)
        self.nodes[node_id] = node
        self._initial_units[node_id] = units
        self._emission_charge[node_id] = 0.0
        self._pull_charge[node_id] = 0.0
        self._update_total_units()

    def reset(self) -> None:
        for node_id, node in self.nodes.items():
            node.units = self._initial_units.get(node_id, node.units)
            node.clamp()
        self.clear_particles()
        self._emission_charge = {node_id: 0.0 for node_id in self.nodes}
        self._pull_charge = {node_id: 0.0 for node_id in self.nodes}
        self.pressure_gain = 1.0
        self.pressure_inverted = False
        self.tick_count = 0
        self.lost_units = 0
        self.events = []
        for void in self.voids:
            void.move_to_tick(0)
        self._update_node_radii()

    def clear_particles(self) -> None:
        self.particle_positions = np.empty((0, 2), dtype=np.float64)
        self.particle_velocities = np.empty((0, 2), dtype=np.float64)
        self.particle_colors = np.empty(0, dtype=np.int64)
        self._update_total_units()

    def _append_particles(
        self,
        positions: "np.typing.ArrayLike",
        velocities: "np.typing.ArrayLike",
        colors: "Optional[np.typing.ArrayLike]" = None,
    ) -> None:
        new_positions = np.asarray(positions, dtype=np.float64).reshape(-1, 2)
        new_velocities = np.asarray(velocities, dtype=np.float64).reshape(-1, 2)
        if colors is None:
            new_colors = np.zeros(len(new_positions), dtype=np.int64)
        else:
            new_colors = np.asarray(colors, dtype=np.int64).reshape(-1)
        self.particle_positions = np.vstack([self.particle_positions, new_positions])
        self.particle_velocities = np.vstack([self.particle_velocities, new_velocities])
        self.particle_colors = np.concatenate([self.particle_colors, new_colors])

    def _keep_particles(self, keep: np.ndarray) -> None:
        self.particle_positions = self.particle_positions[keep]
        self.particle_velocities = self.particle_velocities[keep]
        self.particle_colors = self.particle_colors[keep]

    def _update_total_units(self) -> None:
        self.total_units = sum(node.units for node in self.nodes.values()) + len(self.particle_positions)

    def node_radius(self, node: Node) -> float:
        """Radius scaled by fill level, clamped to [MIN_NODE_RADIUS, MAX_NODE_RADIUS]."""
        t = node.units / max(node.capacity, 1.0)
        t = max(0.0, min(1.0, t))
        return self.MIN_NODE_RADIUS + t * (self.MAX_NODE_RADIUS - self.MIN_NODE_RADIUS)

    def _field_sign(self) -> float:
        return -1.0 if self.pressure_inverted else 1.0

    def effective_pressure(self, node: Node) -> float:
        """Pressure the physics actually uses: authored value scaled by the global
        gain and flipped when the field is inverted. A full goal goes quiet."""
        if node.role == ROLE_GOAL and node.is_full:
            return 0.0
        return node.pressure * self.pressure_gain * self._field_sign()

    def display_pressure(self, node: Node) -> float:
        """Pressure used only for node colouring: applies inversion (so colours
        flip with the field) but NOT gain (so roles stay legible at low gain)."""
        return node.pressure * self._field_sign()

    def set_pressure_gain(self, value: float) -> None:
        self.pressure_gain = max(self.MIN_GAIN, min(self.MAX_GAIN, value))

    def adjust_pressure_gain(self, delta: float) -> None:
        self.set_pressure_gain(self.pressure_gain + delta)

    def toggle_pressure_inverted(self) -> None:
        self.pressure_inverted = not self.pressure_inverted

    def _next_node_id(self) -> str:
        for letter in string.ascii_uppercase:
            if letter not in self.nodes:
                return letter
        index = 1
        while f"N{index}" in self.nodes:
            index += 1
        return f"N{index}"

    def _find_placement(self, radius: float, attempts: int = 200) -> Optional[Tuple[float, float]]:
        margin_x = self.width * self.BOUNDARY_MARGIN
        margin_y = self.height * self.BOUNDARY_MARGIN
        min_x, max_x = margin_x + radius, self.width - margin_x - radius
        min_y, max_y = margin_y + radius, self.height - margin_y - radius
        if min_x > max_x or min_y > max_y:
            return None

        for _ in range(attempts):
            x = random.uniform(min_x, max_x)
            y = random.uniform(min_y, max_y)
            if all(math.hypot(x - other.x, y - other.y) > radius + other.radius for other in self.nodes.values()):
                return x, y
        return None

    def add_random_node(self) -> bool:
        radius = random.uniform(self.MIN_NODE_RADIUS, self.MAX_NODE_RADIUS)
        placement = self._find_placement(radius)
        if placement is None:
            return False

        x, y = placement
        pressure = random.uniform(-self.MAX_PRESSURE, self.MAX_PRESSURE)
        units = radius + 10.0
        self.add_node(self._next_node_id(), units=units, pressure=pressure, capacity=100.0, radius=radius, x=x, y=y)
        return True

    def remove_random_node(self) -> Optional[str]:
        if not self.nodes:
            return None

        node_id = random.choice(list(self.nodes.keys()))
        node = self.nodes.pop(node_id)
        self._initial_units.pop(node_id, None)
        self._emission_charge.pop(node_id, None)
        self._pull_charge.pop(node_id, None)

        count = int(round(node.units))
        if count > 0:
            angles = np.random.uniform(0.0, 2.0 * math.pi, size=count)
            speeds = self.emission_speed * (0.5 + np.random.random(count))
            cos_a = np.cos(angles)
            sin_a = np.sin(angles)
            new_positions = np.column_stack((node.x + cos_a * node.radius, node.y + sin_a * node.radius))
            new_velocities = np.column_stack((cos_a * speeds, sin_a * speeds))
            self._append_particles(new_positions, new_velocities)

        self._update_total_units()
        return node_id

    # ------------------------------------------------------------------ field

    def field_sources(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Every point that pushes or pulls particles, as parallel arrays of
        positions (M x 2), effective pressures (M) and the particle colour each
        acts on (M, ANY_COLOR for all). Nodes come first, in insertion order."""
        sign = self._field_sign() * self.pressure_gain
        points: List[Tuple[float, float]] = []
        pressures: List[float] = []
        colors: List[int] = []
        for node in self.nodes.values():
            points.append((node.x, node.y))
            pressures.append(self.effective_pressure(node))
            goal_color = node.color if node.role == ROLE_GOAL and node.color is not None else ANY_COLOR
            colors.append(goal_color)
        for pin in self.pins:
            points.append((pin.x, pin.y))
            pressures.append(pin.pressure * sign)
            colors.append(ANY_COLOR)
        for void in self.voids:
            points.append((void.x, void.y))
            pressures.append(void.pressure * sign)
            colors.append(ANY_COLOR)
        return (
            np.array(points, dtype=np.float64).reshape(-1, 2),
            np.array(pressures, dtype=np.float64),
            np.array(colors, dtype=np.int64),
        )

    def _pressure_gradient(self, node: Node, color: int = 0) -> Tuple[float, float]:
        """Net push felt at a node's centre from every other field source."""
        positions, pressures, colors = self.field_sources()
        node_index = list(self.nodes.values()).index(node)
        gx = 0.0
        gy = 0.0
        for index in range(len(pressures)):
            if index == node_index or (colors[index] != ANY_COLOR and colors[index] != color):
                continue
            dx = node.x - positions[index, 0]
            dy = node.y - positions[index, 1]
            distance_sq = max(dx * dx + dy * dy, self.min_distance ** 2)
            factor = pressures[index] * self.force_constant / distance_sq
            gx += dx * factor
            gy += dy * factor
        return gx, gy

    def _integrate(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        colors: np.ndarray,
        sources: Tuple[np.ndarray, np.ndarray, np.ndarray],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Advance particles one tick under the given field: apply forces,
        move, then bounce off walls and the boundary. Returns new arrays."""
        source_positions, source_pressures, source_colors = sources
        if len(source_pressures):
            # delta has shape (particles, sources, 2): the offset from every source to every particle.
            delta = positions[:, np.newaxis, :] - source_positions[np.newaxis, :, :]
            distance_sq = np.maximum(np.sum(delta * delta, axis=2), self.min_distance ** 2)
            factor = source_pressures[np.newaxis, :] * self.force_constant / distance_sq
            if (source_colors != ANY_COLOR).any():
                acts = (source_colors[np.newaxis, :] == ANY_COLOR) | (source_colors[np.newaxis, :] == colors[:, np.newaxis])
                factor = factor * acts
            force = np.sum(delta * factor[:, :, np.newaxis], axis=1)
        else:
            force = np.zeros_like(velocities)

        if self.particle_repulsion > 0.0 and len(positions) > 1:
            # Short-range push between particles so a gathered cloud spreads
            # into a swarm instead of collapsing onto one point. O(N^2), which
            # is fine for the few hundred particles a puzzle level holds.
            offsets = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
            distance_sq = np.sum(offsets * offsets, axis=2)
            near = (distance_sq < self.repulsion_range ** 2) & (distance_sq > 0.0)
            strength = np.where(near, self.particle_repulsion / np.maximum(distance_sq, 1.0), 0.0)
            force = force + np.sum(offsets * strength[:, :, np.newaxis], axis=1)

        velocities = (velocities + force) * self.damping
        if self.max_speed is not None:
            speed = np.hypot(velocities[:, 0], velocities[:, 1])
            too_fast = speed > self.max_speed
            if too_fast.any():
                velocities[too_fast] *= (self.max_speed / speed[too_fast])[:, np.newaxis]
        previous = positions
        positions = positions + velocities

        for wall in self.walls:
            inside = (
                (positions[:, 0] > wall.x) & (positions[:, 0] < wall.x + wall.w)
                & (positions[:, 1] > wall.y) & (positions[:, 1] < wall.y + wall.h)
            )
            if not inside.any():
                continue
            # Bounce on the axis the particle crossed into the wall from.
            came_from_side = inside & ((previous[:, 0] <= wall.x) | (previous[:, 0] >= wall.x + wall.w))
            from_left = came_from_side & (previous[:, 0] <= wall.x)
            from_right = came_from_side & ~from_left
            positions[from_left, 0] = wall.x
            positions[from_right, 0] = wall.x + wall.w
            velocities[came_from_side, 0] *= -self.wall_restitution

            vertical = inside & ~came_from_side
            from_above = vertical & (previous[:, 1] <= wall.y + wall.h / 2.0)
            from_below = vertical & ~from_above
            positions[from_above, 1] = wall.y
            positions[from_below, 1] = wall.y + wall.h
            velocities[vertical, 1] *= -self.wall_restitution

        # Reflect particles off the boundary, damping and reversing the
        # velocity component perpendicular to the wall they hit.
        below_x = positions[:, 0] < 0.0
        above_x = positions[:, 0] > self.width
        positions[below_x, 0] = 0.0
        positions[above_x, 0] = self.width
        velocities[below_x | above_x, 0] *= -self.wall_restitution

        below_y = positions[:, 1] < 0.0
        above_y = positions[:, 1] > self.height
        positions[below_y, 1] = 0.0
        positions[above_y, 1] = self.height
        velocities[below_y | above_y, 1] *= -self.wall_restitution

        return positions, velocities

    def _apply_forces(self) -> None:
        if len(self.particle_positions) == 0:
            return
        self.particle_positions, self.particle_velocities = self._integrate(
            self.particle_positions, self.particle_velocities, self.particle_colors, self.field_sources()
        )

    def predict_path(self, node: Node, steps: int = 220) -> List[Tuple[float, float]]:
        """Where a particle emitted from `node` right now would travel, ignoring
        other particles. Stops when it is caught by a goal or a void, or comes
        to rest. Used to preview a level's flow before it is released."""
        color = node.color if node.color is not None else 0
        px, py, dx, dy = self._emission_launch(node, color)
        positions = np.array([[px, py]], dtype=np.float64)
        velocities = np.array([[dx * self.emission_speed, dy * self.emission_speed]], dtype=np.float64)
        colors = np.array([color], dtype=np.int64)
        sources = self.field_sources()
        path = [(px, py)]
        for _ in range(steps):
            positions, velocities = self._integrate(positions, velocities, colors, sources)
            x, y = float(positions[0, 0]), float(positions[0, 1])
            path.append((x, y))
            if any(math.hypot(x - v.x, y - v.y) <= v.radius for v in self.voids):
                break
            if any(
                other.role == ROLE_GOAL and not other.is_full
                and (other.color is None or other.color == color)
                and math.hypot(x - other.x, y - other.y) <= other.radius
                for other in self.nodes.values()
            ):
                break
            if abs(velocities[0, 0]) + abs(velocities[0, 1]) < 0.02:
                break
        return path

    # ------------------------------------------------------------- tick steps

    def _consume_voids(self) -> None:
        positions = self.particle_positions
        if len(positions) == 0 or not self.voids:
            return
        lost = np.zeros(len(positions), dtype=bool)
        for void in self.voids:
            dx = positions[:, 0] - void.x
            dy = positions[:, 1] - void.y
            lost |= dx * dx + dy * dy <= void.radius ** 2
        if lost.any():
            for x, y in positions[lost]:
                self.events.append(("lost", float(x), float(y)))
            self.lost_units += int(lost.sum())
            self._keep_particles(~lost)

    def _absorb_particles(self) -> None:
        positions = self.particle_positions
        if len(positions) == 0:
            return

        # Process nodes in order so that, like the original implementation, a
        # particle is absorbed by the first node (with room left) that reaches
        # it, and a node that fills up mid-tick stops absorbing further particles.
        absorbed_mask = np.zeros(len(positions), dtype=bool)
        for node in self.nodes.values():
            if node.role == ROLE_SOURCE:
                continue
            capacity_left = int(round(node.capacity - node.units))
            if capacity_left <= 0:
                continue

            dx = positions[:, 0] - node.x
            dy = positions[:, 1] - node.y
            in_range = (dx * dx + dy * dy <= node.radius ** 2) & ~absorbed_mask
            if node.role == ROLE_GOAL and node.color is not None:
                in_range &= self.particle_colors == node.color
            candidates = np.flatnonzero(in_range)
            if candidates.size == 0:
                continue

            take = min(candidates.size, capacity_left)
            absorbed_mask[candidates[:take]] = True
            node.units = min(node.capacity, node.units + take)
            if node.role == ROLE_GOAL:
                for index in candidates[:take]:
                    self.events.append(("absorb", node.id, float(positions[index, 0]), float(positions[index, 1])))

        if absorbed_mask.any():
            self._keep_particles(~absorbed_mask)

    def _emission_launch(self, node: Node, color: int = 0) -> Tuple[float, float, float, float]:
        gx, gy = self._pressure_gradient(node, color)
        magnitude = math.hypot(gx, gy)
        if magnitude < 1e-9:
            angle = random.uniform(0.0, 2.0 * math.pi)
            dx, dy = math.cos(angle), math.sin(angle)
        else:
            dx, dy = gx / magnitude, gy / magnitude

        return node.x + dx * node.radius, node.y + dy * node.radius, dx, dy

    def _emit_particles(self) -> None:
        # Emission is bounded by the (small) number of nodes, so this stays a
        # plain loop; new particles are batched into one array append below
        # rather than growing the particle arrays one row at a time.
        new_positions: List[Tuple[float, float]] = []
        new_velocities: List[Tuple[float, float]] = []
        new_colors: List[int] = []

        for node in self.nodes.values():
            pressure = self.effective_pressure(node)
            if node.role == ROLE_GOAL or pressure <= 0.0 or node.units < 1.0:
                self._emission_charge[node.id] = 0.0
                continue

            color = node.color if node.color is not None else 0
            charge = self._emission_charge.get(node.id, 0.0) + pressure * self.emission_charge_rate
            while charge >= 1.0 and node.units >= 1.0:
                node.units -= 1.0
                px, py, dx, dy = self._emission_launch(node, color)
                if self.emission_angle_jitter > 0.0:
                    turn = random.uniform(-self.emission_angle_jitter, self.emission_angle_jitter)
                    dx, dy = dx * math.cos(turn) - dy * math.sin(turn), dx * math.sin(turn) + dy * math.cos(turn)
                jitter = self.emission_speed_jitter
                speed = self.emission_speed * ((1.0 - jitter) + 2.0 * jitter * random.random())
                new_positions.append((px, py))
                new_velocities.append((dx * speed, dy * speed))
                new_colors.append(color)
                self.events.append(("emit", node.id))
                charge -= 1.0

            self._emission_charge[node.id] = charge

        if new_positions:
            self._append_particles(new_positions, new_velocities, new_colors)

    def _pull_particles(self) -> None:
        """Nodes with sufficient negative pressure actively pull nearby particles in."""
        positions = self.particle_positions
        if len(positions) == 0:
            return

        absorbed_mask = np.zeros(len(positions), dtype=bool)

        for node in self.nodes.values():
            pressure = self.effective_pressure(node)
            if node.role != ROLE_NODE or pressure >= 0.0 or node.units >= node.capacity:
                self._pull_charge[node.id] = 0.0
                continue

            charge = self._pull_charge.get(node.id, 0.0) + (-pressure) * self.PULL_CHARGE_RATE

            dx = positions[:, 0] - node.x
            dy = positions[:, 1] - node.y
            dist_sq = dx * dx + dy * dy
            pull_range_sq = self.PULL_RANGE ** 2

            while charge >= 1.0 and node.units < node.capacity:
                in_range = (dist_sq <= pull_range_sq) & ~absorbed_mask
                candidates = np.flatnonzero(in_range)
                if candidates.size == 0:
                    break
                closest = candidates[np.argmin(dist_sq[candidates])]
                absorbed_mask[closest] = True
                node.units = min(node.capacity, node.units + 1.0)
                charge -= 1.0

            self._pull_charge[node.id] = charge

        if absorbed_mask.any():
            self._keep_particles(~absorbed_mask)

    def _node_flow(self) -> None:
        """Directly transfer units between nearby sandbox nodes driven by pressure differential.

        When two nodes are within FLOW_RANGE and their effective-pressure difference
        exceeds FLOW_PRESSURE_THRESHOLD, units flow from the higher-pressure node to
        the lower-pressure one at a rate proportional to the difference.
        """
        nodes = [node for node in self.nodes.values() if node.role == ROLE_NODE]
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                dist = math.hypot(a.x - b.x, a.y - b.y)
                if dist > self.FLOW_RANGE:
                    continue
                pa = self.effective_pressure(a)
                pb = self.effective_pressure(b)
                # Flow goes from the higher-pressure node to the lower-pressure one.
                diff = pa - pb
                if abs(diff) < self.FLOW_PRESSURE_THRESHOLD:
                    continue
                amount = diff * self.FLOW_RATE
                # Clamp so we never take more than a node has or push past its capacity.
                if amount > 0:
                    amount = min(amount, a.units, b.capacity - b.units)
                else:
                    amount = max(amount, -b.units, -(a.capacity - a.units))
                a.units -= amount
                b.units += amount
                a.clamp()
                b.clamp()

    def _update_node_radii(self) -> None:
        """Resize every sandbox node so its radius reflects its current unit count."""
        for node in self.nodes.values():
            if node.role == ROLE_NODE:
                node.radius = self.node_radius(node)

    def tick(self) -> None:
        self.events = []
        if not self.nodes:
            return

        for void in self.voids:
            void.move_to_tick(self.tick_count)
        self._apply_forces()
        self._consume_voids()
        self._absorb_particles()
        self._pull_particles()
        self._emit_particles()
        self._node_flow()
        self._update_node_radii()

        self.tick_count += 1
        self._update_total_units()

    def get_snapshot(self) -> Dict[str, float]:
        return {node_id: node.units for node_id, node in self.nodes.items()}

    def create_default_graph(self) -> None:
        self.nodes.clear()
        self.clear_particles()
        self._initial_units.clear()
        self._emission_charge.clear()
        self._pull_charge.clear()
        self.pressure_gain = 1.0
        self.pressure_inverted = False

        for node_id, pressure in (("A", 4.0), ("B", 0.0), ("C", -4.0)):
            radius = random.uniform(self.MIN_NODE_RADIUS, self.MAX_NODE_RADIUS)
            placement = self._find_placement(radius)
            x, y = placement if placement is not None else (self.width / 2.0, self.height / 2.0)
            units = radius + 10.0
            self.add_node(node_id, units=units, pressure=pressure, capacity=120.0, radius=radius, x=x, y=y)


if __name__ == "__main__":
    simulator = Simulator()
    simulator.create_default_graph()
    for _ in range(10):
        simulator.tick()
        print(
            f"Tick {simulator.tick_count}: {simulator.get_snapshot()} "
            f"total={simulator.total_units:.1f} particles={len(simulator.particle_positions)}"
        )
