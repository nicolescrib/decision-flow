from __future__ import annotations

import math
from typing import List, Optional, Protocol, Tuple

import pygame
from pygame import Rect

from audio import Audio
from levels import BOARD_HEIGHT, BOARD_WIDTH, LEVELS
from progress import Progress
from puzzle import FAILED, RUNNING, WON, Puzzle
from puzzle_view import (
    BACKGROUND, PANEL_BG, PANEL_BORDER, STAR_OFF, STAR_ON, TEXT, TEXT_DIM, VOID_CORE, VOID_RIM,
    PuzzleView, draw_star, goal_color, scaled,
)
from renderer import CompactListRenderer, ParticleRenderer, SimpleNumberRenderer
from simulator import ROLE_SOURCE, Simulator, Void
from ui import UI

WINDOW_SIZE = (760, 520)
FPS = 60
PUZZLE_TICKS_PER_SECOND = 30
FAST_FORWARD = 3


class Screen(Protocol):
    def handle_event(self, event: pygame.event.Event, pos: Optional[Tuple[float, float]]) -> None: ...
    def update(self, dt_ms: float) -> None: ...
    def draw(self, canvas: pygame.Surface) -> None: ...


class App:
    """Owns the window and main loop, and switches between screens. Every
    screen draws onto a WINDOW_SIZE canvas that is scaled up to the window
    with nearest-neighbour filtering, for the chunky pixel look."""

    def __init__(self, ui_scale: float = 2.0) -> None:
        pygame.init()
        display_info = pygame.display.Info()
        # Cap the scale so the window fits the display (minus room for the
        # taskbar/title bar) without distorting the aspect ratio.
        max_width = display_info.current_w - 80
        max_height = display_info.current_h - 120
        fit_scale = min(max_width / WINDOW_SIZE[0], max_height / WINDOW_SIZE[1])
        self.ui_scale = max(1.0, min(ui_scale, fit_scale)) if fit_scale >= 1.0 else ui_scale
        self.window_size = (round(WINDOW_SIZE[0] * self.ui_scale), round(WINDOW_SIZE[1] * self.ui_scale))
        self.window = pygame.display.set_mode(self.window_size)
        pygame.display.set_caption("Decision Flow")
        self.canvas = pygame.Surface(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.mouse_pos: Tuple[float, float] = (0.0, 0.0)

        self.progress = Progress()
        self.audio = Audio()
        self.audio.muted = self.progress.muted
        self.screen: Screen = TitleScreen(self)

    def show_title(self, selected: int = 0) -> None:
        self.screen = TitleScreen(self, selected)

    def play_level(self, index: int) -> None:
        self.screen = PuzzleScreen(self, index)

    def open_sandbox(self) -> None:
        simulator = Simulator()
        simulator.create_default_graph()
        renderers = [ParticleRenderer(scale=1.0), SimpleNumberRenderer(), CompactListRenderer()]
        self.screen = UI(simulator, renderers, on_exit=lambda: self.show_title(len(LEVELS)))

    def toggle_mute(self) -> None:
        self.audio.toggle_mute()
        self.progress.muted = self.audio.muted
        self.progress.save()

    def quit(self) -> None:
        self.running = False

    def _logical(self, position: Tuple[int, int]) -> Tuple[float, float]:
        return position[0] / self.ui_scale, position[1] / self.ui_scale

    def run(self) -> None:
        while self.running:
            dt_ms = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    continue
                pos: Optional[Tuple[float, float]] = None
                if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    pos = self._logical(event.pos)
                    self.mouse_pos = pos
                elif event.type == pygame.MOUSEWHEEL:
                    pos = self.mouse_pos
                self.screen.handle_event(event, pos)
            self.screen.update(dt_ms)
            self.screen.draw(self.canvas)
            pygame.transform.scale(self.canvas, self.window_size, self.window)
            pygame.display.flip()
        pygame.quit()


# --------------------------------------------------------------------- title

class TitleScreen:
    COLUMNS = 5
    CARD_SIZE = (132, 82)
    GRID_TOP = 196

    def __init__(self, app: App, selected: int = 0) -> None:
        self.app = app
        self.selected = selected
        self.font = pygame.font.Font(None, 20)
        self.small_font = pygame.font.Font(None, 16)
        self.number_font = pygame.font.Font(None, 34)
        self.title_surface = self._pixel_title("DECISION FLOW")
        self.cards = self._layout_cards()
        self.sandbox_rect = Rect(0, 0, 200, 34)
        self.sandbox_rect.center = (WINDOW_SIZE[0] // 2, 440)
        self.ambient = self._build_ambient()
        self.trail = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
        self.frame = 0
        self.mouse_pos: Tuple[float, float] = (0.0, 0.0)

    def _layout_cards(self) -> List[Tuple[int, Rect]]:
        width, height = self.CARD_SIZE
        gap = 12
        grid_width = self.COLUMNS * width + (self.COLUMNS - 1) * gap
        left = (WINDOW_SIZE[0] - grid_width) // 2
        cards = []
        for index in range(len(LEVELS)):
            column, row = index % self.COLUMNS, index // self.COLUMNS
            cards.append((index, Rect(left + column * (width + gap), self.GRID_TOP + row * (height + gap), width, height)))
        return cards

    @staticmethod
    def _pixel_title(text: str) -> pygame.Surface:
        small = pygame.font.Font(None, 30).render(text, False, TEXT)
        return pygame.transform.scale(small, (small.get_width() * 2, small.get_height() * 2))

    @staticmethod
    def _build_ambient() -> Simulator:
        """A small endless simulation behind the menu: one fountain feeding
        two orbiting voids, so the title screen shows the game's own physics."""
        simulator = Simulator(width=WINDOW_SIZE[0], height=WINDOW_SIZE[1])
        simulator.damping = 0.975
        simulator.max_speed = 4.0
        simulator.emission_speed = 2.5
        simulator.emission_angle_jitter = math.pi
        simulator.emission_speed_jitter = 0.3
        simulator.particle_repulsion = 0.0
        simulator.emission_charge_rate = 0.12
        simulator.add_node("S", units=1e9, pressure=1.0, capacity=1e9, radius=6.0,
                           x=WINDOW_SIZE[0] / 2, y=118, role=ROLE_SOURCE)
        simulator.voids = [
            Void(WINDOW_SIZE[0] / 2, 118, radius=10.0, pressure=-1.6, orbit_radius=170, orbit_speed=0.012),
            Void(WINDOW_SIZE[0] / 2, 118, radius=10.0, pressure=-1.6, orbit_radius=170, orbit_speed=0.012, phase=math.pi),
        ]
        return simulator

    def _activate(self, index: int) -> None:
        if index == len(LEVELS):
            self.app.open_sandbox()
        elif self.app.progress.is_unlocked(index):
            self.app.play_level(index)

    def handle_event(self, event: pygame.event.Event, pos: Optional[Tuple[float, float]]) -> None:
        if event.type == pygame.MOUSEMOTION and pos is not None:
            self.mouse_pos = pos
            for index, rect in self.cards:
                if rect.collidepoint(pos):
                    self.selected = index
            if self.sandbox_rect.collidepoint(pos):
                self.selected = len(LEVELS)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and pos is not None:
            for index, rect in self.cards:
                if rect.collidepoint(pos):
                    self._activate(index)
                    return
            if self.sandbox_rect.collidepoint(pos):
                self._activate(len(LEVELS))
        elif event.type == pygame.KEYDOWN:
            count = len(LEVELS) + 1
            if event.key == pygame.K_ESCAPE:
                self.app.quit()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self._activate(self.selected)
            elif event.key == pygame.K_RIGHT:
                self.selected = (self.selected + 1) % count
            elif event.key == pygame.K_LEFT:
                self.selected = (self.selected - 1) % count
            elif event.key == pygame.K_DOWN:
                self.selected = min(count - 1, self.selected + self.COLUMNS)
            elif event.key == pygame.K_UP:
                self.selected = max(0, self.selected - self.COLUMNS) if self.selected < len(LEVELS) else len(LEVELS) - 1
            elif event.key == pygame.K_s:
                self.app.open_sandbox()
            elif event.key == pygame.K_m:
                self.app.toggle_mute()

    def update(self, dt_ms: float) -> None:
        self.ambient.tick()
        if len(self.ambient.particle_positions) > 220:
            self.ambient._keep_particles(slice(-220, None))

    def draw(self, canvas: pygame.Surface) -> None:
        self.frame += 1
        canvas.fill(BACKGROUND)
        self.trail.fill((255, 255, 255, 230), special_flags=pygame.BLEND_RGBA_MULT)
        for x, y in self.ambient.particle_positions:
            pygame.draw.circle(self.trail, (255, 196, 96, 110), (int(x), int(y)), 1)
        canvas.blit(self.trail, (0, 0))
        for void in self.ambient.voids:
            pygame.draw.circle(canvas, VOID_CORE, (int(void.x), int(void.y)), int(void.radius))
            pygame.draw.circle(canvas, scaled(VOID_RIM, 0.7), (int(void.x), int(void.y)), int(void.radius), width=2)

        canvas.blit(self.title_surface, self.title_surface.get_rect(center=(WINDOW_SIZE[0] // 2, 64)))
        subtitle = self.font.render("guide the flow  -  fill every ring  -  lose as little as you can", True, TEXT_DIM)
        canvas.blit(subtitle, subtitle.get_rect(center=(WINDOW_SIZE[0] // 2, 100)))

        progress = self.app.progress
        total = self.font.render(f"{progress.total_stars} / {len(LEVELS) * 3}", True, STAR_ON)
        total_rect = total.get_rect(midright=(WINDOW_SIZE[0] // 2 + 40, 166))
        canvas.blit(total, total_rect)
        draw_star(canvas, (total_rect.left - 14, 166), 7, STAR_ON)

        for index, rect in self.cards:
            self._draw_card(canvas, rect, index, LEVELS[index].name)

        selected = self.selected == len(LEVELS)
        pygame.draw.rect(canvas, (44, 50, 80) if selected else PANEL_BG, self.sandbox_rect, border_radius=6)
        pygame.draw.rect(canvas, TEXT if selected else PANEL_BORDER, self.sandbox_rect, width=2 if selected else 1, border_radius=6)
        label = self.font.render("Sandbox", True, TEXT)
        canvas.blit(label, label.get_rect(center=self.sandbox_rect.center))

        keys = self.small_font.render("click or ENTER to play   S sandbox   M mute   ESC quit", True, TEXT_DIM)
        canvas.blit(keys, keys.get_rect(center=(WINDOW_SIZE[0] // 2, 494)))
        if self.app.audio.muted:
            muted = self.small_font.render("muted", True, STAR_ON)
            canvas.blit(muted, (12, 10))

    def _draw_card(self, canvas: pygame.Surface, rect: Rect, index: int, name: str) -> None:
        progress = self.app.progress
        unlocked = progress.is_unlocked(index)
        selected = index == self.selected
        stars = progress.stars(index)
        background = (44, 50, 80) if selected and unlocked else PANEL_BG
        pygame.draw.rect(canvas, background, rect, border_radius=6)
        border = TEXT if selected and unlocked else (PANEL_BORDER if unlocked else (40, 44, 64))
        pygame.draw.rect(canvas, border, rect, width=2 if selected else 1, border_radius=6)

        number = self.number_font.render(str(index + 1), True, TEXT if unlocked else STAR_OFF)
        canvas.blit(number, number.get_rect(topleft=(rect.left + 10, rect.top + 8)))
        if unlocked:
            title = self.small_font.render(name, True, TEXT_DIM)
            canvas.blit(title, (rect.left + 10, rect.top + 38))
            for i in range(3):
                draw_star(canvas, (rect.left + 18 + i * 20, rect.bottom - 16), 7, STAR_ON if i < stars else STAR_OFF)
        else:
            # A small padlock.
            cx, cy = rect.right - 26, rect.top + 26
            pygame.draw.rect(canvas, STAR_OFF, Rect(cx - 7, cy - 2, 14, 11), border_radius=2)
            pygame.draw.arc(canvas, STAR_OFF, Rect(cx - 5, cy - 10, 10, 14), 0, math.pi, 2)
            locked = self.small_font.render("locked", True, STAR_OFF)
            canvas.blit(locked, (rect.left + 10, rect.top + 38))


# -------------------------------------------------------------------- puzzle

class PuzzleScreen:
    def __init__(self, app: App, index: int) -> None:
        self.app = app
        self.index = index
        self.puzzle = Puzzle(LEVELS[index])
        self.view = PuzzleView(WINDOW_SIZE, (int(BOARD_WIDTH), int(BOARD_HEIGHT)))
        self.mouse_pos: Tuple[float, float] = app.mouse_pos
        self.drag_kind: Optional[str] = None   # a new pin being dragged out of the tray
        self.drag_pin = None                   # a placed pin being moved
        self.fast_forward = False
        self._tick_time_ms = 0.0
        self._full_goals: set = set()
        self._new_best = False

    # --------------------------------------------------------------- input

    def _board_pos(self) -> Tuple[float, float]:
        return self.view.to_board(self.mouse_pos)

    def _hover_pin(self):
        if self.drag_pin is not None:
            return self.drag_pin
        bx, by = self._board_pos()
        return self.puzzle.pin_at(bx, by)

    def handle_event(self, event: pygame.event.Event, pos: Optional[Tuple[float, float]]) -> None:
        if pos is not None:
            self.mouse_pos = pos
        if event.type == pygame.MOUSEMOTION:
            if self.drag_pin is not None:
                bx, by = self._board_pos()
                self.puzzle.move_pin(self.drag_pin, bx, by)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._press()
            elif event.button == 3:
                pin = self._hover_pin()
                if pin is not None and not self.puzzle.is_over:
                    self.puzzle.remove_pin(pin)
                    self.drag_pin = None
                    self.app.audio.play("lift")
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.drag_kind is not None:
                bx, by = self._board_pos()
                if self.puzzle.place_pin(self.drag_kind, bx, by) is not None:
                    self.app.audio.play("place")
                self.drag_kind = None
            if self.drag_pin is not None:
                self.app.audio.play("place")
                self.drag_pin = None
        elif event.type == pygame.MOUSEWHEEL:
            pin = self._hover_pin()
            if pin is not None and event.y:
                self.puzzle.change_strength(pin, 1 if event.y > 0 else -1)
                self.app.audio.play("place")
        elif event.type == pygame.KEYDOWN:
            self._key(event)

    def _press(self) -> None:
        if self.puzzle.is_over:
            return
        for kind, rect in self.view.tray_buttons:
            if rect.collidepoint(self.mouse_pos) and self.puzzle.pins_left(kind) > 0:
                self.drag_kind = kind
                self.app.audio.play("lift")
                return
        pin = self._hover_pin()
        if pin is not None:
            self.drag_pin = pin
            self.app.audio.play("lift")

    def _key(self, event: pygame.event.Event) -> None:
        key = event.key
        if key == pygame.K_ESCAPE:
            self.app.show_title(self.index)
        elif key == pygame.K_SPACE:
            if not self.puzzle.is_over:
                self.puzzle.release()
        elif key == pygame.K_r:
            self._restart()
        elif key == pygame.K_c and not self.puzzle.is_over:
            self.puzzle.clear_pins()
            self.drag_pin = None
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.puzzle.state == WON:
            if self.index + 1 < len(LEVELS):
                self.app.play_level(self.index + 1)
            else:
                self.app.show_title(self.index)
        elif key == pygame.K_m:
            self.app.toggle_mute()
        elif key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
            pin = self._hover_pin()
            if pin is not None:
                self.puzzle.change_strength(pin, 1 if key == pygame.K_RIGHTBRACKET else -1)

    def _restart(self) -> None:
        self.puzzle.restart()
        self.view.reset_effects()
        self._full_goals = set()
        self._tick_time_ms = 0.0
        self._new_best = False
        self.drag_pin = None
        self.drag_kind = None

    # -------------------------------------------------------------- update

    def update(self, dt_ms: float) -> None:
        self.fast_forward = bool(pygame.key.get_pressed()[pygame.K_f])
        if self.puzzle.state != RUNNING:
            self._tick_time_ms = 0.0
            return
        self._tick_time_ms += dt_ms * (FAST_FORWARD if self.fast_forward else 1)
        interval = 1000.0 / PUZZLE_TICKS_PER_SECOND
        steps = 0
        while self._tick_time_ms >= interval and steps < 12:
            self._tick_time_ms -= interval
            steps += 1
            self.puzzle.step()
            self._react()
            if self.puzzle.state != RUNNING:
                self._finish()
                break

    def _react(self) -> None:
        """Turn the last tick's simulation events into sound and ripples."""
        goals = {goal.id: goal for goal in self.puzzle.goals}
        goal_order = list(goals)
        for event in self.puzzle.simulator.events:
            if event[0] == "absorb":
                goal = goals[event[1]]
                self.view.add_ripple(goal.x, goal.y, goal_color(goal), max_radius=goal.radius + 10, lifetime=18)
                index = goal_order.index(goal.id)
                self.app.audio.play(f"plink{(index * 2 + int(goal.units)) % 7}", throttle=goal.id)
            elif event[0] == "lost":
                self.view.add_ripple(event[1], event[2], VOID_RIM, max_radius=26, lifetime=30)
                self.app.audio.play("lost")
        for goal in goals.values():
            if goal.is_full and goal.id not in self._full_goals:
                self._full_goals.add(goal.id)
                self.view.add_ripple(goal.x, goal.y, goal_color(goal), max_radius=70, lifetime=40)
                self.view.add_ripple(goal.x, goal.y, goal_color(goal), max_radius=40, lifetime=30)
                if self.puzzle.state != WON:
                    self.app.audio.play("fill")

    def _finish(self) -> None:
        self.drag_pin = None
        self.drag_kind = None
        if self.puzzle.state == WON:
            self._new_best = self.app.progress.record(self.index, self.puzzle.stars)
            self.app.audio.play("win")
            for goal in self.puzzle.goals:
                self.view.add_ripple(goal.x, goal.y, STAR_ON, max_radius=120, lifetime=50)
        elif self.puzzle.state == FAILED:
            self.app.audio.play("fail")

    def draw(self, canvas: pygame.Surface) -> None:
        drag_valid = False
        if self.drag_kind is not None:
            bx, by = self._board_pos()
            drag_valid = self.puzzle.can_place(bx, by)
        self.view.draw(
            canvas, self.puzzle, self.index + 1, self.app.progress.stars(self.index), self.mouse_pos,
            self._hover_pin(), self.drag_kind, drag_valid, self.fast_forward, self.app.audio.muted,
            self._new_best,
        )
