from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame
from pygame import Rect

from levels import AMBER, CYAN
from puzzle import DESIGN, FAILED, MAX_PIN_STRENGTH, PAUSED, PIN_KINDS, PIN_RADIUS, RUNNING, WON, Puzzle
from simulator import Node, Pin

BACKGROUND = (10, 12, 20)
BOARD_BG = (14, 17, 30)
GRID_DOT = (28, 33, 54)
TEXT = (232, 236, 246)
TEXT_DIM = (150, 160, 190)
PANEL_BG = (16, 19, 32)
PANEL_BORDER = (70, 76, 110)
WALL_FILL = (64, 68, 98)
WALL_LIGHT = (108, 114, 156)
WALL_DARK = (36, 38, 58)
VOID_RIM = (170, 70, 210)
VOID_CORE = (4, 2, 10)
SOURCE_COLOR = (250, 160, 80)
PULL_COLOR = (90, 150, 255)
PUSH_COLOR = (255, 120, 70)
STAR_ON = (255, 214, 90)
STAR_OFF = (60, 64, 90)
INVALID = (230, 70, 80)

PARTICLE_COLORS = {AMBER: (255, 196, 96), CYAN: (100, 225, 255)}
ANY_GOAL_COLOR = (200, 230, 210)


def particle_color(color: Optional[int]) -> Tuple[int, int, int]:
    return PARTICLE_COLORS.get(color if color is not None else AMBER, PARTICLE_COLORS[AMBER])


def goal_color(node: Node) -> Tuple[int, int, int]:
    return ANY_GOAL_COLOR if node.color is None else particle_color(node.color)


def scaled(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in color)  # type: ignore[return-value]


def draw_star(surface: pygame.Surface, center: Tuple[float, float], size: float, color: Tuple[int, int, int]) -> None:
    cx, cy = center
    points = []
    for i in range(10):
        radius = size if i % 2 == 0 else size * 0.45
        angle = -math.pi / 2 + i * math.pi / 5
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    pygame.draw.polygon(surface, color, points)


def draw_pin_shape(surface: pygame.Surface, kind: str, strength: int, center: Tuple[float, float],
                   outline: Optional[Tuple[int, int, int]] = None, alpha_dim: bool = False) -> None:
    cx, cy = center
    base = PULL_COLOR if kind == "pull" else PUSH_COLOR
    if alpha_dim:
        base = scaled(base, 0.55)
    r = PIN_RADIUS
    diamond = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    pygame.draw.polygon(surface, scaled(base, 0.45), diamond)
    inner = [(cx, cy - r + 3), (cx + r - 3, cy), (cx, cy + r - 3), (cx - r + 3, cy)]
    pygame.draw.polygon(surface, base, inner)
    pygame.draw.polygon(surface, outline or scaled(base, 1.3), diamond, width=1)
    # Arrow glyph: inward for pull, outward for push.
    glyph = (20, 22, 34)
    if kind == "pull":
        pygame.draw.line(surface, glyph, (cx - 3, cy - 3), (cx, cy), 2)
        pygame.draw.line(surface, glyph, (cx + 3, cy + 3), (cx, cy), 2)
    else:
        pygame.draw.line(surface, glyph, (cx - 3, cy), (cx + 3, cy), 2)
        pygame.draw.line(surface, glyph, (cx, cy - 3), (cx, cy + 3), 2)
    for pip in range(strength):
        px = cx - (MAX_PIN_STRENGTH - 1) * 3 + pip * 6
        pygame.draw.rect(surface, scaled(base, 1.25), Rect(int(px) - 1, int(cy + r + 3), 3, 3))


@dataclass
class Ripple:
    x: float
    y: float
    color: Tuple[int, int, int]
    max_radius: float
    age: int = 0
    lifetime: int = 24


class PuzzleView:
    """Draws a Puzzle onto the canvas: board, particles with fading trails,
    the flow preview, HUD and end-of-level overlays."""

    BOARD_ORIGIN = (10, 44)
    TRAY_TOP = 488

    def __init__(self, canvas_size: Tuple[int, int], board_size: Tuple[int, int]) -> None:
        self.canvas_size = canvas_size
        self.board_rect = Rect(self.BOARD_ORIGIN, board_size)
        self.font = pygame.font.Font(None, 20)
        self.small_font = pygame.font.Font(None, 16)
        self.big_font = pygame.font.Font(None, 44)
        self.title_font = pygame.font.Font(None, 26)
        self.trail = pygame.Surface(board_size)
        self.background = self._build_background(board_size)
        self.ripples: List[Ripple] = []
        self.frame = 0
        self.tray_buttons: List[Tuple[str, Rect]] = []

    # ------------------------------------------------------------ utilities

    def to_board(self, pos: Tuple[float, float]) -> Tuple[float, float]:
        return pos[0] - self.board_rect.left, pos[1] - self.board_rect.top

    def to_canvas(self, x: float, y: float) -> Tuple[int, int]:
        return int(self.board_rect.left + x), int(self.board_rect.top + y)

    def reset_effects(self) -> None:
        self.trail.fill((0, 0, 0))
        self.ripples.clear()

    def add_ripple(self, x: float, y: float, color: Tuple[int, int, int], max_radius: float = 22.0, lifetime: int = 24) -> None:
        if len(self.ripples) < 80:
            self.ripples.append(Ripple(x, y, color, max_radius, lifetime=lifetime))

    @staticmethod
    def _build_background(size: Tuple[int, int]) -> pygame.Surface:
        surface = pygame.Surface(size)
        surface.fill(BOARD_BG)
        for x in range(10, size[0], 20):
            for y in range(10, size[1], 20):
                surface.set_at((x, y), GRID_DOT)
        return surface

    # ----------------------------------------------------------------- draw

    def draw(
        self,
        canvas: pygame.Surface,
        puzzle: Puzzle,
        level_number: int,
        best_stars: int,
        mouse_pos: Tuple[float, float],
        hover_pin: Optional[Pin],
        drag_kind: Optional[str],
        drag_valid: bool,
        fast_forward: bool,
        muted: bool,
        new_best: bool = False,
    ) -> None:
        self.frame += 1
        canvas.fill(BACKGROUND)
        board = canvas.subsurface(self.board_rect)
        board.blit(self.background, (0, 0))

        simulator = puzzle.simulator
        for wall in simulator.walls:
            self._draw_wall(board, Rect(int(wall.x), int(wall.y), int(wall.w), int(wall.h)))
        for void in simulator.voids:
            self._draw_void(board, void.x, void.y, void.radius, void.orbit_radius, void.cx, void.cy)

        # Trails: fade what was drawn before, then add this frame's particles.
        self.trail.fill((214, 214, 214), special_flags=pygame.BLEND_RGB_MULT)
        for (x, y), color in zip(simulator.particle_positions, simulator.particle_colors):
            pygame.draw.circle(self.trail, scaled(particle_color(int(color)), 0.35), (int(x), int(y)), 2)
        board.blit(self.trail, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        if puzzle.state in (DESIGN, PAUSED):
            for source in puzzle.sources:
                if source.units >= 1.0:
                    self._draw_preview(board, simulator.predict_path(source), particle_color(source.color))

        for source in puzzle.sources:
            self._draw_source(board, source)
        for goal in puzzle.goals:
            self._draw_goal(board, goal)

        for pin in puzzle.pins:
            outline = (255, 255, 255) if pin is hover_pin else None
            if pin is hover_pin:
                reach = 26 + pin.strength * 10
                pygame.draw.circle(board, scaled(PULL_COLOR if pin.kind == "pull" else PUSH_COLOR, 0.5),
                                   (int(pin.x), int(pin.y)), reach, width=1)
            draw_pin_shape(board, pin.kind, pin.strength, (pin.x, pin.y), outline)

        for (x, y), color in zip(simulator.particle_positions, simulator.particle_colors):
            core = scaled(particle_color(int(color)), 1.25)
            board.fill(core, Rect(int(x) - 1, int(y) - 1, 2, 2))

        self._draw_ripples(board)

        if drag_kind is not None:
            bx, by = self.to_board(mouse_pos)
            draw_pin_shape(board, drag_kind, 2, (bx, by), outline=None if drag_valid else INVALID, alpha_dim=not drag_valid)

        pygame.draw.rect(canvas, PANEL_BORDER, self.board_rect.inflate(2, 2), width=1)

        self._draw_hud(canvas, puzzle, level_number, best_stars, fast_forward, muted)
        self._draw_tray(canvas, puzzle, mouse_pos)

        if puzzle.state == WON:
            self._draw_result(canvas, puzzle, won=True, new_best=new_best)
        elif puzzle.state == FAILED:
            self._draw_result(canvas, puzzle, won=False)
        elif puzzle.settled:
            self._draw_banner(canvas, "The flow has settled. Move a pin to stir it, or press R to restart.")

    def _draw_wall(self, board: pygame.Surface, rect: Rect) -> None:
        pygame.draw.rect(board, WALL_FILL, rect)
        pygame.draw.line(board, WALL_LIGHT, rect.topleft, (rect.right - 1, rect.top))
        pygame.draw.line(board, WALL_LIGHT, rect.topleft, (rect.left, rect.bottom - 1))
        pygame.draw.line(board, WALL_DARK, (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
        pygame.draw.line(board, WALL_DARK, (rect.right - 1, rect.top), (rect.right - 1, rect.bottom - 1))
        for y in range(rect.top + 6, rect.bottom - 3, 8):
            for x in range(rect.left + 4 + (y // 8) % 2 * 4, rect.right - 3, 8):
                board.set_at((x, y), WALL_DARK)

    def _draw_void(self, board: pygame.Surface, x: float, y: float, radius: float,
                   orbit_radius: float, cx: float, cy: float) -> None:
        if orbit_radius > 0:
            for i in range(0, 72, 2):
                angle = i * math.pi / 36
                board.set_at((int(cx + math.cos(angle) * orbit_radius), int(cy + math.sin(angle) * orbit_radius)),
                             scaled(VOID_RIM, 0.35))
        center = (int(x), int(y))
        pygame.draw.circle(board, scaled(VOID_RIM, 0.18), center, int(radius) + 6)
        pygame.draw.circle(board, VOID_CORE, center, int(radius))
        spin = self.frame * 0.06
        for arm in range(3):
            angle = spin + arm * 2 * math.pi / 3
            start = (x + math.cos(angle) * radius * 0.95, y + math.sin(angle) * radius * 0.95)
            end = (x + math.cos(angle + 1.4) * radius * 0.25, y + math.sin(angle + 1.4) * radius * 0.25)
            pygame.draw.line(board, scaled(VOID_RIM, 0.6), start, end, 1)
        pygame.draw.circle(board, VOID_RIM, center, int(radius), width=2)

    def _draw_source(self, board: pygame.Surface, node: Node) -> None:
        center = (int(node.x), int(node.y))
        color = particle_color(node.color)
        fraction = node.units / max(node.capacity, 1.0)
        pygame.draw.circle(board, scaled(color, 0.25), center, int(node.radius) + 4)
        pygame.draw.circle(board, scaled(color, 0.4), center, int(node.radius))
        if fraction > 0:
            pygame.draw.circle(board, color, center, max(2, int(node.radius * math.sqrt(fraction))))
        pygame.draw.circle(board, scaled(color, 1.2), center, int(node.radius), width=2)
        label = self.small_font.render(str(int(node.units)), True, TEXT)
        board.blit(label, label.get_rect(midtop=(center[0], center[1] + node.radius + 5)))

    def _draw_goal(self, board: pygame.Surface, node: Node) -> None:
        center = (int(node.x), int(node.y))
        color = goal_color(node)
        fraction = node.units / max(node.capacity, 1.0)
        radius = int(node.radius)
        if node.is_full:
            glow = 0.6 + 0.4 * math.sin(self.frame * 0.12)
            pygame.draw.circle(board, scaled(color, 0.25 + 0.15 * glow), center, radius + 8)
            pygame.draw.circle(board, color, center, radius)
            pygame.draw.lines(board, (20, 30, 30), False,
                              [(center[0] - 6, center[1]), (center[0] - 2, center[1] + 5), (center[0] + 7, center[1] - 5)], 3)
        else:
            pygame.draw.circle(board, scaled(color, 0.12), center, radius)
            if fraction > 0:
                pygame.draw.circle(board, scaled(color, 0.55), center, max(2, int(radius * math.sqrt(fraction))))
            pygame.draw.circle(board, scaled(color, 0.4), center, radius + 5, width=4)
            if fraction > 0:
                arc_rect = Rect(center[0] - radius - 5, center[1] - radius - 5, (radius + 5) * 2, (radius + 5) * 2)
                pygame.draw.arc(board, color, arc_rect, math.pi / 2 - 2 * math.pi * fraction, math.pi / 2, 4)
        label = self.small_font.render(f"{int(node.units)}/{int(node.capacity)}", True, TEXT if not node.is_full else color)
        board.blit(label, label.get_rect(midtop=(center[0], center[1] + radius + 9)))

    def _draw_preview(self, board: pygame.Surface, path: List[Tuple[float, float]], color: Tuple[int, int, int]) -> None:
        offset = (self.frame // 3) % 6
        count = len(path)
        for index in range(offset, count, 6):
            x, y = path[index]
            fade = 1.0 - index / max(count, 1) * 0.7
            board.fill(scaled(color, 0.8 * fade), Rect(int(x) - 1, int(y) - 1, 2, 2))

    def _draw_ripples(self, board: pygame.Surface) -> None:
        alive: List[Ripple] = []
        for ripple in self.ripples:
            t = ripple.age / ripple.lifetime
            radius = int(4 + ripple.max_radius * t)
            pygame.draw.circle(board, scaled(ripple.color, 1.0 - t), (int(ripple.x), int(ripple.y)), radius, width=1)
            ripple.age += 1
            if ripple.age < ripple.lifetime:
                alive.append(ripple)
        self.ripples = alive

    def _draw_hud(self, canvas: pygame.Surface, puzzle: Puzzle, level_number: int, best_stars: int,
                  fast_forward: bool, muted: bool) -> None:
        title = self.title_font.render(f"{level_number}. {puzzle.level.name}", True, TEXT)
        canvas.blit(title, (12, 5))
        flags = [text for text, on in ((">> fast", fast_forward), ("muted", muted)) if on]
        if flags:
            flag_surface = self.small_font.render("   ".join(flags), True, STAR_ON)
            canvas.blit(flag_surface, (title.get_width() + 24, 10))
        hint =self.small_font.render(puzzle.level.hint, True, TEXT_DIM)
        canvas.blit(hint, (12, 26))

        # Live star forecast: stars dim as particles are lost.
        level = puzzle.level
        if puzzle.state == WON:
            earned = puzzle.stars
        elif puzzle.lost <= level.three_star_lost:
            earned = 3
        elif puzzle.lost <= level.two_star_lost:
            earned = 2
        else:
            earned = 1
        right = self.canvas_size[0] - 14
        for i in range(3):
            draw_star(canvas, (right - (2 - i) * 20, 14), 8, STAR_ON if i < earned else STAR_OFF)
        lost = self.small_font.render(
            f"lost {puzzle.lost}   (3 stars: {level.three_star_lost}  2 stars: {level.two_star_lost})", True,
            INVALID if puzzle.lost > level.three_star_lost else TEXT_DIM,
        )
        canvas.blit(lost, lost.get_rect(topright=(right + 8, 27)))
        if best_stars:
            best = self.small_font.render("best", True, TEXT_DIM)
            best_rect = best.get_rect(topright=(right - 112, 8))
            canvas.blit(best, best_rect)
            for i in range(3):
                draw_star(canvas, (best_rect.right + 10 + i * 11, 14), 4, STAR_ON if i < best_stars else STAR_OFF)

    def _draw_tray(self, canvas: pygame.Surface, puzzle: Puzzle, mouse_pos: Tuple[float, float]) -> None:
        self.tray_buttons = []
        x = 12
        for kind in PIN_KINDS:
            total = puzzle.level.pins.get(kind, 0)
            if total == 0:
                continue
            left = puzzle.pins_left(kind)
            rect = Rect(x, self.TRAY_TOP + 2, 92, 26)
            hover = rect.collidepoint(mouse_pos) and left > 0
            pygame.draw.rect(canvas, (40, 46, 72) if hover else PANEL_BG, rect, border_radius=4)
            pygame.draw.rect(canvas, PANEL_BORDER, rect, width=1, border_radius=4)
            draw_pin_shape(canvas, kind, 2, (rect.left + 16, rect.top + 11), alpha_dim=left == 0)
            label = self.font.render(f"{kind.upper()} x{left}", True, TEXT if left else TEXT_DIM)
            canvas.blit(label, (rect.left + 32, rect.top + 6))
            self.tray_buttons.append((kind, rect))
            x += rect.width + 8

        if puzzle.state == DESIGN:
            status = "Place pins, then SPACE" if puzzle.level.pins else "SPACE to release the flow"
        elif puzzle.state == RUNNING:
            status = "Drag pins to steer the flow" if puzzle.pins or puzzle.level.pins else "Flowing"
        elif puzzle.state == PAUSED:
            status = "Paused. SPACE to resume"
        else:
            status = ""
        status_surface = self.font.render(status, True, TEXT)
        canvas.blit(status_surface, (max(x + 12, 140), self.TRAY_TOP + 8))

        keys =self.small_font.render("R restart   C clear pins   F fast   M mute   ESC levels", True, TEXT_DIM)
        canvas.blit(keys, keys.get_rect(topright=(self.canvas_size[0] - 12, self.TRAY_TOP + 10)))

    def _draw_banner(self, canvas: pygame.Surface, text: str) -> None:
        surface = self.font.render(text, True, TEXT)
        rect = surface.get_rect(midtop=(self.board_rect.centerx, self.board_rect.top + 10)).inflate(20, 10)
        pygame.draw.rect(canvas, PANEL_BG, rect, border_radius=4)
        pygame.draw.rect(canvas, PANEL_BORDER, rect, width=1, border_radius=4)
        canvas.blit(surface, surface.get_rect(center=rect.center))

    def _draw_result(self, canvas: pygame.Surface, puzzle: Puzzle, won: bool, new_best: bool = False) -> None:
        shade = pygame.Surface(self.board_rect.size, pygame.SRCALPHA)
        shade.fill((5, 6, 12, 150))
        canvas.blit(shade, self.board_rect.topleft)

        panel = Rect(0, 0, 340, 180)
        panel.center = self.board_rect.center
        pygame.draw.rect(canvas, PANEL_BG, panel, border_radius=8)
        pygame.draw.rect(canvas, PANEL_BORDER, panel, width=2, border_radius=8)

        heading = "Flow complete" if won else "Out of flow"
        title = self.big_font.render(heading, True, TEXT)
        canvas.blit(title, title.get_rect(midtop=(panel.centerx, panel.top + 16)))

        if won:
            for i in range(3):
                draw_star(canvas, (panel.centerx + (i - 1) * 44, panel.top + 84), 17, STAR_ON if i < puzzle.stars else STAR_OFF)
            detail = f"{puzzle.lost} lost" + ("   -   new best!" if new_best else "")
            actions = "ENTER next level    R replay    ESC levels"
            detail_top = 114
        else:
            detail = "Not enough flow is left to fill every ring."
            actions = "R retry (your pins stay)    ESC levels"
            detail_top = 82
        detail_surface = self.font.render(detail, True, STAR_ON if new_best else TEXT_DIM)
        canvas.blit(detail_surface, detail_surface.get_rect(midtop=(panel.centerx, panel.top + detail_top)))
        action_surface = self.font.render(actions, True, TEXT)
        canvas.blit(action_surface, action_surface.get_rect(midtop=(panel.centerx, panel.top + 146)))
