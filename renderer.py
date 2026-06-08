from __future__ import annotations

import pygame
from pygame import Rect
from typing import Dict, Optional, Tuple

from simulator import Simulator

PRESSURE_COLOR_THRESHOLD = 0.5


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

            display = simulator.display_pressure(node)
            if display > PRESSURE_COLOR_THRESHOLD:
                fill_color = (110, 140, 220)
            elif display < -PRESSURE_COLOR_THRESHOLD:
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
            display = simulator.display_pressure(node)
            if is_selected:
                color = (255, 255, 100)
            elif display > PRESSURE_COLOR_THRESHOLD:
                color = (220, 200, 150)
            elif display < -PRESSURE_COLOR_THRESHOLD:
                color = (160, 190, 230)
            else:
                color = (180, 180, 220)
            label = f"{node.id}: {node.units:.1f} units  (pressure {node.pressure:+.1f})"
            line = self.font.render(label, True, color)
            screen.blit(line, (x, y))
            y += line_height

        if not simulator.nodes:
            hint = self.font.render("No nodes in simulation.", True, (210, 210, 210))
            screen.blit(hint, (x, y))


class ParticleRenderer(Renderer):
    name = "Particle Flow Renderer"
    MIN_SCALE = 0.25
    MAX_SCALE = 4.0

    def __init__(self, scale: float = 1.0) -> None:
        self.font = pygame.font.Font(None, 18)
        self.small_font = pygame.font.Font(None, 14)
        self.scale = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))

    def set_scale(self, scale: float) -> None:
        self.scale = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))

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

        map_px_width = simulator.width / self.scale
        map_px_height = simulator.height / self.scale
        offset_x = content_rect.left + (content_rect.width - map_px_width) / 2.0
        offset_y = content_rect.top + (content_rect.height - map_px_height) / 2.0

        def to_screen(ux: float, uy: float) -> Tuple[int, int]:
            return int(offset_x + ux / self.scale), int(offset_y + uy / self.scale)

        previous_clip = screen.get_clip()
        screen.set_clip(content_rect)

        particle_radius_px = max(1, round(simulator.PARTICLE_RADIUS / self.scale))
        for x, y in simulator.particle_positions:
            px, py = to_screen(x, y)
            pygame.draw.circle(screen, (255, 200, 100), (px, py), particle_radius_px)

        for node in nodes:
            cx, cy = to_screen(node.x, node.y)
            radius_px = max(2, round(node.radius / self.scale))

            if node_rects is not None:
                click_radius = max(radius_px, 12)
                node_rects[node.id] = Rect(cx - click_radius, cy - click_radius, click_radius * 2, click_radius * 2)

            display = simulator.display_pressure(node)
            if display > PRESSURE_COLOR_THRESHOLD:
                fill_color = (100, 140, 200)
            elif display < -PRESSURE_COLOR_THRESHOLD:
                fill_color = (200, 100, 80)
            else:
                fill_color = (80, 140, 100)

            intensity = min(200, max(60, int((node.units / node.capacity) * 180)))
            fill_color = (
                min(255, fill_color[0] + intensity // 4),
                min(255, fill_color[1] + intensity // 4),
                min(255, fill_color[2] + intensity // 4),
            )

            pygame.draw.circle(screen, fill_color, (cx, cy), radius_px)
            border_color = (255, 255, 80) if selected_node == node.id else (235, 238, 245)
            border_width = 3 if selected_node == node.id else 2
            pygame.draw.circle(screen, border_color, (cx, cy), radius_px, width=border_width)

            label_surface = self.small_font.render(
                f"{node.id}  {int(node.units)}u  P {node.pressure:+.1f}", True, (228, 230, 235)
            )
            label_rect = label_surface.get_rect(midtop=(cx, cy + radius_px + 4))
            screen.blit(label_surface, label_rect)

        screen.set_clip(previous_clip)

        total_text = self.small_font.render(f"Total units: {int(simulator.total_units)}", True, (210, 220, 235))
        screen.blit(total_text, (content_rect.left + 8, content_rect.top + 8))

        scale_text = self.small_font.render(
            f"Scale: {self.scale:.2f} units/px  |  Map: {int(simulator.width)}x{int(simulator.height)}"
            f"  |  Particles: {len(simulator.particle_positions)}",
            True, (185, 195, 215),
        )
        screen.blit(scale_text, (content_rect.left + 8, content_rect.top + 24))
