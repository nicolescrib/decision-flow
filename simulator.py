from __future__ import annotations

import math
import random
import string
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Node:
    id: str
    units: float = 0.0
    pressure: float = 0.0
    capacity: float = 100.0
    radius: float = 4.0
    x: float = 0.0
    y: float = 0.0

    def clamp(self) -> None:
        self.units = max(0.0, min(self.units, self.capacity))


class Simulator:
    MIN_NODE_RADIUS = 3.0
    MAX_NODE_RADIUS = 6.0
    BOUNDARY_MARGIN = 0.10
    MAX_PRESSURE = 6.0
    PARTICLE_RADIUS = 1.5

    FORCE_CONSTANT = 40.0
    DAMPING = 0.92
    MIN_DISTANCE = 12.0
    EMISSION_CHARGE_RATE = 0.12
    EMISSION_SPEED = 1.5

    def __init__(self, width: float = 500.0, height: float = 400.0) -> None:
        self.width = width
        self.height = height
        self.nodes: Dict[str, Node] = {}
        # Particles are stored as structure-of-arrays (positions/velocities as
        # Nx2 numpy arrays) rather than a list of objects so that the physics
        # in tick() can be vectorized instead of looped in pure Python.
        self.particle_positions: np.ndarray = np.empty((0, 2), dtype=np.float64)
        self.particle_velocities: np.ndarray = np.empty((0, 2), dtype=np.float64)
        self.tick_count: int = 0
        self.total_units: float = 0.0
        self._initial_units: Dict[str, float] = {}
        self._emission_charge: Dict[str, float] = {}

    def add_node(
        self,
        node_id: str,
        units: float = 0.0,
        pressure: float = 0.0,
        capacity: float = 100.0,
        radius: float = 4.0,
        x: float = 0.0,
        y: float = 0.0,
    ) -> None:
        self.nodes[node_id] = Node(id=node_id, units=units, pressure=pressure, capacity=capacity, radius=radius, x=x, y=y)
        self._initial_units[node_id] = units
        self._emission_charge[node_id] = 0.0
        self._update_total_units()

    def reset(self) -> None:
        for node_id, node in self.nodes.items():
            node.units = self._initial_units.get(node_id, node.units)
            node.clamp()
        self.clear_particles()
        self._emission_charge = {node_id: 0.0 for node_id in self.nodes}
        self.tick_count = 0

    def clear_particles(self) -> None:
        self.particle_positions = np.empty((0, 2), dtype=np.float64)
        self.particle_velocities = np.empty((0, 2), dtype=np.float64)
        self._update_total_units()

    def _append_particles(self, positions: "np.typing.ArrayLike", velocities: "np.typing.ArrayLike") -> None:
        new_positions = np.asarray(positions, dtype=np.float64).reshape(-1, 2)
        new_velocities = np.asarray(velocities, dtype=np.float64).reshape(-1, 2)
        self.particle_positions = np.vstack([self.particle_positions, new_positions])
        self.particle_velocities = np.vstack([self.particle_velocities, new_velocities])

    def _update_total_units(self) -> None:
        self.total_units = sum(node.units for node in self.nodes.values()) + len(self.particle_positions)

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
        self.add_node(self._next_node_id(), units=0.0, pressure=pressure, capacity=100.0, radius=radius, x=x, y=y)
        return True

    def remove_random_node(self) -> Optional[str]:
        if not self.nodes:
            return None

        node_id = random.choice(list(self.nodes.keys()))
        node = self.nodes.pop(node_id)
        self._initial_units.pop(node_id, None)
        self._emission_charge.pop(node_id, None)

        count = int(round(node.units))
        if count > 0:
            angles = np.random.uniform(0.0, 2.0 * math.pi, size=count)
            speeds = self.EMISSION_SPEED * (0.5 + np.random.random(count))
            cos_a = np.cos(angles)
            sin_a = np.sin(angles)
            new_positions = np.column_stack((node.x + cos_a * node.radius, node.y + sin_a * node.radius))
            new_velocities = np.column_stack((cos_a * speeds, sin_a * speeds))
            self._append_particles(new_positions, new_velocities)

        self._update_total_units()
        return node_id

    def _pressure_gradient(self, node: Node) -> Tuple[float, float]:
        gx = 0.0
        gy = 0.0
        for other in self.nodes.values():
            if other is node:
                continue
            dx = node.x - other.x
            dy = node.y - other.y
            distance_sq = max(dx * dx + dy * dy, self.MIN_DISTANCE ** 2)
            factor = other.pressure * self.FORCE_CONSTANT / distance_sq
            gx += dx * factor
            gy += dy * factor
        return gx, gy

    def _apply_forces(self) -> None:
        positions = self.particle_positions
        if len(positions) == 0:
            return

        node_positions = np.array([[node.x, node.y] for node in self.nodes.values()], dtype=np.float64)
        node_pressures = np.array([node.pressure for node in self.nodes.values()], dtype=np.float64)

        # delta has shape (particles, nodes, 2): the offset from every node to every particle.
        delta = positions[:, np.newaxis, :] - node_positions[np.newaxis, :, :]
        distance_sq = np.maximum(np.sum(delta * delta, axis=2), self.MIN_DISTANCE ** 2)
        factor = node_pressures[np.newaxis, :] * self.FORCE_CONSTANT / distance_sq
        force = np.sum(delta * factor[:, :, np.newaxis], axis=1)

        velocities = (self.particle_velocities + force) * self.DAMPING
        positions = positions + velocities

        # Reflect particles off the boundary, damping and reversing the
        # velocity component perpendicular to the wall they hit.
        below_x = positions[:, 0] < 0.0
        above_x = positions[:, 0] > self.width
        positions[below_x, 0] = 0.0
        positions[above_x, 0] = self.width
        velocities[below_x | above_x, 0] *= -0.5

        below_y = positions[:, 1] < 0.0
        above_y = positions[:, 1] > self.height
        positions[below_y, 1] = 0.0
        positions[above_y, 1] = self.height
        velocities[below_y | above_y, 1] *= -0.5

        self.particle_positions = positions
        self.particle_velocities = velocities

    def _absorb_particles(self) -> None:
        positions = self.particle_positions
        if len(positions) == 0:
            return

        # Process nodes in order so that, like the original implementation, a
        # particle is absorbed by the first node (with room left) that reaches
        # it, and a node that fills up mid-tick stops absorbing further particles.
        absorbed_mask = np.zeros(len(positions), dtype=bool)
        for node in self.nodes.values():
            capacity_left = int(round(node.capacity - node.units))
            if capacity_left <= 0:
                continue

            dx = positions[:, 0] - node.x
            dy = positions[:, 1] - node.y
            in_range = (dx * dx + dy * dy <= node.radius ** 2) & ~absorbed_mask
            candidates = np.flatnonzero(in_range)
            if candidates.size == 0:
                continue

            take = min(candidates.size, capacity_left)
            absorbed_mask[candidates[:take]] = True
            node.units = min(node.capacity, node.units + take)

        if absorbed_mask.any():
            keep = ~absorbed_mask
            self.particle_positions = self.particle_positions[keep]
            self.particle_velocities = self.particle_velocities[keep]

    def _emission_launch(self, node: Node) -> Tuple[float, float, float, float]:
        gx, gy = self._pressure_gradient(node)
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

        for node in self.nodes.values():
            if node.pressure <= 0.0 or node.units < 1.0:
                self._emission_charge[node.id] = 0.0
                continue

            charge = self._emission_charge.get(node.id, 0.0) + node.pressure * self.EMISSION_CHARGE_RATE
            while charge >= 1.0 and node.units >= 1.0:
                node.units -= 1.0
                px, py, dx, dy = self._emission_launch(node)
                speed = self.EMISSION_SPEED * (0.5 + random.random())
                new_positions.append((px, py))
                new_velocities.append((dx * speed, dy * speed))
                charge -= 1.0

            self._emission_charge[node.id] = charge

        if new_positions:
            self._append_particles(new_positions, new_velocities)

    def tick(self) -> None:
        if not self.nodes:
            return

        self._apply_forces()
        self._absorb_particles()
        self._emit_particles()

        self.tick_count += 1
        self._update_total_units()

    def get_snapshot(self) -> Dict[str, float]:
        return {node_id: node.units for node_id, node in self.nodes.items()}

    def create_default_graph(self) -> None:
        self.nodes.clear()
        self.clear_particles()
        self._initial_units.clear()
        self._emission_charge.clear()

        for node_id, units, pressure in (("A", 40.0, 4.0), ("B", 20.0, 0.0), ("C", 0.0, -4.0)):
            radius = random.uniform(self.MIN_NODE_RADIUS, self.MAX_NODE_RADIUS)
            placement = self._find_placement(radius)
            x, y = placement if placement is not None else (self.width / 2.0, self.height / 2.0)
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
