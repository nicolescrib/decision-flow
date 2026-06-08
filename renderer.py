from __future__ import annotations

import pygame
from pygame import Rect
from typing import Dict, Optional

from simulator import NodeType, Simulator, Particle


class Renderer:
    name = "base"

    def render(
        self,
        screen: pygame.Surface,
        simulator: Simulator,
        content_rect: Rect,
        selected_node: Optional[str] = None,
        node_rects: Optional[Dict[str, Rect]] = None,
    ) -> None:
        raise NotImplementedError


class SimpleNumberRenderer(Renderer):
    name = "Simple Number Renderer"

    def __init__(self) -> None:
        self.font = pygame.font.Font(None, 20)
        self.large_font = pygame.font.Font(None, 30)

    def render(
        self,
        screen: pygame.Surface,
        simulator: Simulator,
        content_rect: Rect,
        selected_node: Optional[str] = None,
        node_rects: Optional[Dict[str, Rect]] = None,
    ) -> None:
        screen.fill((20, 24, 44), content_rect)

        nodes = list(simulator.nodes.values())
        if not nodes:
            text = self.font.render("No nodes available", True, (200, 200, 200))
            screen.blit(text, text.get_rect(center=content_rect.center))
            return

        count = len(nodes)
        spacing = max(180, content_rect.width // max(1, count + 1))
        center_y = content_rect.centery

        for index, node in enumerate(nodes):
            x = content_rect.left + spacing * (index + 1)
            rect = Rect(x - 50, center_y - 40, 100, 80)

            if node_rects is not None:
                node_rects[node.id] = rect

            if node.node_type == NodeType.SOURCE:
                fill_color = (110, 140, 220)
            elif node.node_type == NodeType.SINK:
                fill_color = (190, 120, 100)
            else:
                fill_color = (100, 150, 120)

            intensity = min(180, max(80, int((node.units / node.capacity) * 160)))
            fill_color = (min(255, fill_color[0] + intensity // 3), min(255, fill_color[1] + intensity // 4), min(255, fill_color[2] + intensity // 4))

            pygame.draw.rect(screen, fill_color, rect, border_radius=10)
            border_color = (255, 255, 0) if selected_node == node.id else (240, 240, 240)
            border_width = 4 if selected_node == node.id else 2
            pygame.draw.rect(screen, border_color, rect, width=border_width, border_radius=10)

            units_text = f"{node.units:.1f}"
            text_surface = self.large_font.render(units_text, True, (245, 245, 245))
            screen.blit(text_surface, text_surface.get_rect(center=rect.center))

            label_surface = self.font.render(node.id, True, (220, 220, 200))
            label_rect = label_surface.get_rect(midtop=(rect.centerx, rect.bottom + 8))
            screen.blit(label_surface, label_rect)


class CompactListRenderer(Renderer):
    name = "Compact List Renderer"

    def __init__(self) -> None:
        self.font = pygame.font.Font(None, 24)

    def render(
        self,
        screen: pygame.Surface,
        simulator: Simulator,
        content_rect: Rect,
        selected_node: Optional[str] = None,
        node_rects: Optional[Dict[str, Rect]] = None,
    ) -> None:
        screen.fill((18, 20, 30), content_rect)

        x = content_rect.left + 20
        y = content_rect.top + 20
        line_height = 28

        heading = self.font.render("Node pressure values (Click in other renderers)", True, (210, 210, 210))
        screen.blit(heading, (x, y))
        y += line_height * 1.5

        for node in simulator.nodes.values():
            is_selected = selected_node == node.id
            color = (255, 255, 100) if is_selected else ((180, 180, 220) if node.node_type == NodeType.NORMAL else (220, 200, 150))
            label = f"{node.id}: {node.units:.1f} units"
            line = self.font.render(label, True, color)
            screen.blit(line, (x, y))
            y += line_height

        if not simulator.nodes:
            hint = self.font.render("No nodes in simulation.", True, (210, 210, 210))
            screen.blit(hint, (x, y))


class ParticleRenderer(Renderer):
    name = "Particle Flow Renderer"

    def __init__(self, resolution: int = 1) -> None:
        self.font = pygame.font.Font(None, 18)
        self.small_font = pygame.font.Font(None, 14)
        self.resolution = max(1, min(4, resolution))

    def set_resolution(self, resolution: int) -> None:
        self.resolution = max(1, min(4, resolution))

    def render(
        self,
        screen: pygame.Surface,
        simulator: Simulator,
        content_rect: Rect,
        selected_node: Optional[str] = None,
        node_rects: Optional[Dict[str, Rect]] = None,
    ) -> None:
        screen.fill((15, 18, 30), content_rect)

        nodes = list(simulator.nodes.values())
        if not nodes:
            text = self.font.render("No nodes available", True, (200, 200, 200))
            screen.blit(text, text.get_rect(center=content_rect.center))
            return

        count = len(nodes)
        spacing = max(140, content_rect.width // max(1, count + 1))
        center_y = content_rect.centery
        node_positions = {}

        for index, node in enumerate(nodes):
            x = content_rect.left + spacing * (index + 1)
            node_positions[node.id] = (x, center_y)
        if node_rects is not None:
            node_rects[node.id] = Rect(x - 35, y - 35, 70, 70)

        for particle in simulator.particles:
            from_node = simulator.nodes[particle.from_id]
            to_node = simulator.nodes[particle.to_id]
            from_x, from_y = node_positions[from_node.id]
            to_x, to_y = node_positions[to_node.id]

            px = from_x + (to_x - from_x) * particle.progress
            py = from_y + (to_y - from_y) * particle.progress

            particle_size = 3 * self.resolution
            pygame.draw.circle(screen, (255, 200, 100), (int(px), int(py)), particle_size)

        for index, node in enumerate(nodes):
            x, y = node_positions[node.id]
            rect = Rect(x - 35, y - 35, 70, 70)

            if node.node_type == NodeType.SOURCE:
                fill_color = (100, 140, 200)
            elif node.node_type == NodeType.SINK:
                fill_color = (200, 100, 80)
            else:
                fill_color = (80, 140, 100)

            intensity = min(200, max(60, int((node.units / node.capacity) * 180)))
            fill_color = (
                min(255, fill_color[0] + intensity // 4),
                min(255, fill_color[1] + intensity // 4),
                min(255, fill_color[2] + intensity // 4),
            )

            pygame.draw.rect(screen, fill_color, rect, border_radius=8)
            border_color = (255, 255, 0) if selected_node == node.id else (200, 200, 220)
            border_width = 4 if selected_node == node.id else 2
            pygame.draw.rect(screen, border_color, rect, width=border_width, border_radius=8)

            units_text = f"{int(node.units)}"
            text_surface = self.font.render(units_text, True, (245, 245, 245))
            screen.blit(text_surface, text_surface.get_rect(center=rect.center))

            label_surface = self.small_font.render(node.id, True, (210, 210, 190))
            label_rect = label_surface.get_rect(midtop=(rect.centerx, rect.bottom + 4))
            screen.blit(label_surface, label_rect)

        total_text = self.small_font.render(f"Total units: {int(simulator.total_units)}", True, (180, 200, 220))
        screen.blit(total_text, (content_rect.left + 8, content_rect.top + 8))

        resolution_text = self.small_font.render(f"Resolution: {self.resolution}x", True, (160, 180, 200))
        screen.blit(resolution_text, (content_rect.left + 8, content_rect.top + 24))
