from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, NamedTuple, Tuple


class NodeType(Enum):
    NORMAL = "normal"
    SOURCE = "source"
    SINK = "sink"


@dataclass
class Node:
    id: str
    units: float = 0.0
    node_type: NodeType = NodeType.NORMAL
    capacity: float = 100.0
    source_rate: float = 0.0
    sink_rate: float = 0.0

    def clamp(self) -> None:
        self.units = max(0.0, min(self.units, self.capacity))


@dataclass
class Edge:
    from_id: str
    to_id: str
    transfer_rate: float = 0.25
    max_transfer: float = 10.0


@dataclass
class Particle:
    from_id: str
    to_id: str
    progress: float = 0.0


class Transfer(NamedTuple):
    from_id: str
    to_id: str
    amount: float


class Simulator:
    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.particles: List[Particle] = []
        self.tick_count: int = 0
        self.total_units: float = 0.0

    def add_node(
        self,
        node_id: str,
        units: float = 0.0,
        node_type: NodeType = NodeType.NORMAL,
        capacity: float = 100.0,
        source_rate: float = 0.0,
        sink_rate: float = 0.0,
    ) -> None:
        self.nodes[node_id] = Node(
            id=node_id,
            units=units,
            node_type=node_type,
            capacity=capacity,
            source_rate=source_rate,
            sink_rate=sink_rate,
        )
        self._update_total_units()

    def add_edge(self, from_id: str, to_id: str, transfer_rate: float = 0.25, max_transfer: float = 10.0) -> None:
        if from_id not in self.nodes or to_id not in self.nodes:
            raise ValueError("Both nodes must exist before adding an edge.")
        self.edges.append(Edge(from_id=from_id, to_id=to_id, transfer_rate=transfer_rate, max_transfer=max_transfer))

    def reset(self) -> None:
        for node in self.nodes.values():
            node.units = 0.0
            node.clamp()
        self.particles.clear()
        self.tick_count = 0
        self._update_total_units()

    def _update_total_units(self) -> None:
        self.total_units = sum(node.units for node in self.nodes.values()) + len(self.particles)

    def tick(self) -> None:
        if not self.nodes:
            return

        transfers: List[Transfer] = []

        for edge in self.edges:
            source = self.nodes[edge.from_id]
            target = self.nodes[edge.to_id]

            high, low = (source, target) if source.units >= target.units else (target, source)
            delta = high.units - low.units
            amount = max(0.0, min(delta * edge.transfer_rate, edge.max_transfer))

            if amount > 0.0:
                if high is target:
                    transfers.append(Transfer(from_id=target.id, to_id=source.id, amount=amount))
                else:
                    transfers.append(Transfer(from_id=source.id, to_id=target.id, amount=amount))

        net_changes: Dict[str, float] = {node_id: 0.0 for node_id in self.nodes}

        for transfer in transfers:
            net_changes[transfer.from_id] -= transfer.amount
            net_changes[transfer.to_id] += transfer.amount
            for _ in range(int(transfer.amount)):
                self.particles.append(Particle(from_id=transfer.from_id, to_id=transfer.to_id, progress=0.0))

        for node in self.nodes.values():
            node.units += net_changes[node.id]

        for node in self.nodes.values():
            if node.node_type == NodeType.SOURCE:
                emission = min(node.source_rate, node.capacity - node.units)
                node.units += emission
            elif node.node_type == NodeType.SINK:
                absorption = min(node.sink_rate, node.units)
                node.units -= absorption
            node.clamp()

        for particle in self.particles:
            particle.progress += 0.15

        self.particles = [p for p in self.particles if p.progress < 1.0]

        for particle in self.particles:
            if particle.progress >= 1.0:
                target_node = self.nodes[particle.to_id]
                target_node.units += 1.0

        self.tick_count += 1
        self._update_total_units()

    def get_snapshot(self) -> Dict[str, float]:
        return {node_id: node.units for node_id, node in self.nodes.items()}

    def get_particles(self) -> List[Particle]:
        return self.particles[:]

    def create_default_graph(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self.particles.clear()
        self.add_node("A", units=30.0, node_type=NodeType.SOURCE, capacity=120.0, source_rate=3.0)
        self.add_node("B", units=20.0)
        self.add_node("C", units=10.0, node_type=NodeType.SINK, capacity=120.0, sink_rate=2.0)
        self.add_edge("A", "B", transfer_rate=0.3, max_transfer=8.0)
        self.add_edge("B", "C", transfer_rate=0.2, max_transfer=6.0)


if __name__ == "__main__":
    simulator = Simulator()
    simulator.create_default_graph()
    for _ in range(10):
        simulator.tick()
        print(f"Tick {simulator.tick_count}: {simulator.get_snapshot()}")
