from __future__ import annotations

import math
import random
import string
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


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


@dataclass
class Particle:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0


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
        self.particles: List[Particle] = []
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
        self.particles.clear()
        self._emission_charge = {node_id: 0.0 for node_id in self.nodes}
        self.tick_count = 0
        self._update_total_units()

    def _update_total_units(self) -> None:
        self.total_units = sum(node.units for node in self.nodes.values()) + len(self.particles)

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

        for _ in range(int(round(node.units))):
            angle = random.uniform(0.0, 2.0 * math.pi)
            speed = self.EMISSION_SPEED * (0.5 + random.random())
            self.particles.append(Particle(
                x=node.x + math.cos(angle) * node.radius,
                y=node.y + math.sin(angle) * node.radius,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
            ))

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
        nodes = list(self.nodes.values())
        for particle in self.particles:
            fx = 0.0
            fy = 0.0
            for node in nodes:
                dx = particle.x - node.x
                dy = particle.y - node.y
                distance_sq = max(dx * dx + dy * dy, self.MIN_DISTANCE ** 2)
                factor = node.pressure * self.FORCE_CONSTANT / distance_sq
                fx += dx * factor
                fy += dy * factor

            particle.vx = (particle.vx + fx) * self.DAMPING
            particle.vy = (particle.vy + fy) * self.DAMPING
            particle.x += particle.vx
            particle.y += particle.vy

            if particle.x < 0.0:
                particle.x = 0.0
                particle.vx = -particle.vx * 0.5
            elif particle.x > self.width:
                particle.x = self.width
                particle.vx = -particle.vx * 0.5

            if particle.y < 0.0:
                particle.y = 0.0
                particle.vy = -particle.vy * 0.5
            elif particle.y > self.height:
                particle.y = self.height
                particle.vy = -particle.vy * 0.5

    def _absorb_particles(self) -> None:
        remaining: List[Particle] = []
        for particle in self.particles:
            absorbed = False
            for node in self.nodes.values():
                if node.units >= node.capacity:
                    continue
                dx = particle.x - node.x
                dy = particle.y - node.y
                if dx * dx + dy * dy <= node.radius ** 2:
                    node.units = min(node.capacity, node.units + 1.0)
                    absorbed = True
                    break
            if not absorbed:
                remaining.append(particle)
        self.particles = remaining

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
        for node in self.nodes.values():
            if node.pressure <= 0.0 or node.units < 1.0:
                self._emission_charge[node.id] = 0.0
                continue

            charge = self._emission_charge.get(node.id, 0.0) + node.pressure * self.EMISSION_CHARGE_RATE
            while charge >= 1.0 and node.units >= 1.0:
                node.units -= 1.0
                px, py, dx, dy = self._emission_launch(node)
                speed = self.EMISSION_SPEED * (0.5 + random.random())
                self.particles.append(Particle(x=px, y=py, vx=dx * speed, vy=dy * speed))
                charge -= 1.0

            self._emission_charge[node.id] = charge

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

    def get_particles(self) -> List[Particle]:
        return self.particles[:]

    def create_default_graph(self) -> None:
        self.nodes.clear()
        self.particles.clear()
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
            f"total={simulator.total_units:.1f} particles={len(simulator.particles)}"
        )
