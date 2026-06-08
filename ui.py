from __future__ import annotations

import pygame
from pygame import Rect
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from renderer import Renderer
from simulator import Simulator


class MenuItem:
    def __init__(self, label: str, action: Callable[[], None]) -> None:
        self.label = label
        self.action = action
        self.rect: Optional[Rect] = None


class SettingControl:
    """A single clickable button (e.g. "-", "+", "Toggle") within a settings row."""

    def __init__(self, caption: str, action: Callable[[], None]) -> None:
        self.caption = caption
        self.action = action
        self.rect: Optional[Rect] = None


class SettingRow:
    """One editable setting: a label, a live value display, and its controls.

    New settings should be appended in `UI._build_setting_rows` so they show
    up here automatically.
    """

    def __init__(self, label: str, value: Callable[[], str], controls: List[SettingControl]) -> None:
        self.label = label
        self.value = value
        self.controls = controls


class UI:
    WINDOW_SIZE = (760, 520)
    UI_SCALE = 2.0
    MENU_HEIGHT = 28
    MENU_BG = (14, 16, 26)
    MENU_BORDER = (70, 76, 100)
    MENU_TEXT = (240, 242, 248)
    MENU_HIGHLIGHT = (70, 95, 150)
    STATUS_TEXT = (205, 212, 230)
    PRESSURE_STEP = 0.5
    MAX_PRESSURE = 10.0
    SCALE_STEP = 0.25

    def __init__(self, simulator: Simulator, renderers: Sequence[Renderer], ui_scale: Optional[float] = None) -> None:
        pygame.init()
        self.simulator = simulator
        self.renderers = list(renderers)
        self.active_renderer_index = 0
        self.active_renderer = self.renderers[self.active_renderer_index]
        self.auto_run = False
        self.running = True
        self.open_menu: Optional[str] = None
        self.selected_node: Optional[str] = None

        # UI_SCALE renders the interface at WINDOW_SIZE and upscales it to the
        # window, so every layout/font value below stays in logical pixels.
        # The scale is capped so the window fits the display (minus room for
        # taskbar/title bar) without distorting WINDOW_SIZE's aspect ratio.
        requested_scale = self.UI_SCALE if ui_scale is None else ui_scale
        display_info = pygame.display.Info()
        max_width = display_info.current_w - 80
        max_height = display_info.current_h - 120
        fit_scale = min(max_width / self.WINDOW_SIZE[0], max_height / self.WINDOW_SIZE[1])
        self.ui_scale = min(requested_scale, fit_scale)
        self.window_size = (round(self.WINDOW_SIZE[0] * self.ui_scale), round(self.WINDOW_SIZE[1] * self.ui_scale))
        self.screen = pygame.display.set_mode(self.window_size)
        self.canvas = pygame.Surface(self.WINDOW_SIZE)
        pygame.display.set_caption("Decision Flow")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 20)
        self.menu_font = pygame.font.Font(None, 18)

        self.file_menu_items = [
            MenuItem("Start", self.start_animation),
            MenuItem("Stop", self.stop_animation),
            MenuItem("Step", self.step_animation),
            MenuItem("Reset", self.reset_simulation),
            MenuItem("Clear All", self.clear_all),
            MenuItem("Exit", self.quit),
        ]
        self.settings_rows: List[SettingRow] = []

        self.file_button_rect: Optional[Rect] = None
        self.settings_button_rect: Optional[Rect] = None
        self.start_button_rect: Optional[Rect] = None
        self.stop_button_rect: Optional[Rect] = None
        self.step_button_rect: Optional[Rect] = None
        self.mouse_pos: Tuple[int, int] = (0, 0)
        self.pressed_button: Optional[str] = None
        self.node_rects: Dict[str, Rect] = {}

    def _select_previous_renderer(self) -> None:
        self.active_renderer_index = (self.active_renderer_index - 1) % len(self.renderers)
        self.active_renderer = self.renderers[self.active_renderer_index]

    def _select_next_renderer(self) -> None:
        self.active_renderer_index = (self.active_renderer_index + 1) % len(self.renderers)
        self.active_renderer = self.renderers[self.active_renderer_index]

    def _build_setting_rows(self) -> List[SettingRow]:
        """All editable settings, shown in the Settings menu.

        Add a new `SettingRow` here whenever a new editable setting is added
        so it appears in the menu automatically.
        """
        rows: List[SettingRow] = [
            SettingRow(
                "Renderer",
                lambda: self.active_renderer.name,
                [
                    SettingControl("<", self._select_previous_renderer),
                    SettingControl(">", self._select_next_renderer),
                ],
            ),
            SettingRow(
                "Pressure gain",
                lambda: f"{self.simulator.pressure_gain:.1f}x",
                [
                    SettingControl("-", lambda: self.simulator.adjust_pressure_gain(-self.simulator.GAIN_STEP)),
                    SettingControl("+", lambda: self.simulator.adjust_pressure_gain(self.simulator.GAIN_STEP)),
                ],
            ),
            SettingRow(
                "Invert pressure",
                lambda: "On" if self.simulator.pressure_inverted else "Off",
                [SettingControl("Toggle", self.simulator.toggle_pressure_inverted)],
            ),
        ]

        renderer = self.active_renderer
        if hasattr(renderer, "set_scale"):
            rows.append(
                SettingRow(
                    "Particle scale",
                    lambda: f"{renderer.scale:.2f}x",
                    [
                        SettingControl("-", lambda: renderer.set_scale(renderer.scale - self.SCALE_STEP)),
                        SettingControl("+", lambda: renderer.set_scale(renderer.scale + self.SCALE_STEP)),
                    ],
                )
            )

        return rows

    def start_animation(self) -> None:
        self.auto_run = True
        self.open_menu = None

    def stop_animation(self) -> None:
        self.auto_run = False
        self.open_menu = None

    def step_animation(self) -> None:
        self.simulator.tick()
        self.open_menu = None

    def reset_simulation(self) -> None:
        self.simulator.reset()
        self.selected_node = None
        self.open_menu = None

    def clear_all(self) -> None:
        for node in self.simulator.nodes.values():
            node.units = 0.0
            node.clamp()
        self.simulator.clear_particles()
        self.selected_node = None
        self.open_menu = None

    def quit(self) -> None:
        self.running = False

    def run(self) -> None:
        while self.running:
            self._handle_events()
            if self.auto_run:
                self.simulator.tick()
            self._draw()
            self.clock.tick(10)

        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = self._to_logical(event.pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    self.selected_node = None
                elif event.key == pygame.K_SPACE:
                    self.auto_run = not self.auto_run
                elif event.key == pygame.K_TAB:
                    self.active_renderer_index = (self.active_renderer_index + 1) % len(self.renderers)
                    self.active_renderer = self.renderers[self.active_renderer_index]
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        self.simulator.nodes[self.selected_node].units = min(
                            self.simulator.nodes[self.selected_node].capacity,
                            self.simulator.nodes[self.selected_node].units + 5.0
                        )
                    elif hasattr(self.active_renderer, 'set_scale'):
                        self.active_renderer.set_scale(self.active_renderer.scale + self.SCALE_STEP)
                elif event.key == pygame.K_MINUS:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        self.simulator.nodes[self.selected_node].units = max(0.0, self.simulator.nodes[self.selected_node].units - 5.0)
                    elif hasattr(self.active_renderer, 'set_scale'):
                        self.active_renderer.set_scale(self.active_renderer.scale - self.SCALE_STEP)
                elif event.key == pygame.K_UP:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        self.simulator.nodes[self.selected_node].units = min(
                            self.simulator.nodes[self.selected_node].capacity,
                            self.simulator.nodes[self.selected_node].units + 1.0
                        )
                elif event.key == pygame.K_DOWN:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        self.simulator.nodes[self.selected_node].units = max(0.0, self.simulator.nodes[self.selected_node].units - 1.0)
                elif event.key == pygame.K_RIGHTBRACKET:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        node = self.simulator.nodes[self.selected_node]
                        node.pressure = min(self.MAX_PRESSURE, node.pressure + self.PRESSURE_STEP)
                    else:
                        self.simulator.adjust_pressure_gain(self.simulator.GAIN_STEP)
                elif event.key == pygame.K_LEFTBRACKET:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        node = self.simulator.nodes[self.selected_node]
                        node.pressure = max(-self.MAX_PRESSURE, node.pressure - self.PRESSURE_STEP)
                    else:
                        self.simulator.adjust_pressure_gain(-self.simulator.GAIN_STEP)
                elif event.unicode == ")":
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        node = self.simulator.nodes[self.selected_node]
                        node.pressure = min(self.MAX_PRESSURE, node.pressure + self.PRESSURE_STEP)
                elif event.unicode == "(":
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        node = self.simulator.nodes[self.selected_node]
                        node.pressure = max(-self.MAX_PRESSURE, node.pressure - self.PRESSURE_STEP)
                elif event.key == pygame.K_i:
                    self.simulator.toggle_pressure_inverted()
                elif event.key == pygame.K_n:
                    self.simulator.add_random_node()
                elif event.key == pygame.K_k:
                    removed_id = self.simulator.remove_random_node()
                    if removed_id is not None and removed_id == self.selected_node:
                        self.selected_node = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse_press(self._to_logical(event.pos))
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.pressed_button = None

    def _to_logical(self, position: Tuple[int, int]) -> Tuple[float, float]:
        return (position[0] / self.ui_scale, position[1] / self.ui_scale)

    def _handle_mouse_press(self, position: Tuple[float, float]) -> None:
        if self.file_button_rect and self.file_button_rect.collidepoint(position):
            self.pressed_button = "file"
            self.open_menu = "file" if self.open_menu != "file" else None
            return

        if self.settings_button_rect and self.settings_button_rect.collidepoint(position):
            self.pressed_button = "settings"
            self.open_menu = "settings" if self.open_menu != "settings" else None
            return

        if self.start_button_rect and self.start_button_rect.collidepoint(position):
            self.pressed_button = "start"
            self.start_animation()
            return

        if self.stop_button_rect and self.stop_button_rect.collidepoint(position):
            self.pressed_button = "stop"
            self.stop_animation()
            return

        if self.step_button_rect and self.step_button_rect.collidepoint(position):
            self.pressed_button = "step"
            self.step_animation()
            return

        if self.open_menu == "file":
            for item in self.file_menu_items:
                if item.rect and item.rect.collidepoint(position):
                    item.action()
                    return
        elif self.open_menu == "settings":
            for row in self.settings_rows:
                for control in row.controls:
                    if control.rect and control.rect.collidepoint(position):
                        control.action()
                        return

        for node_id, node_rect in self.node_rects.items():
            if node_rect.collidepoint(position):
                self.selected_node = node_id
                self.open_menu = None
                return

        self.open_menu = None
        self.selected_node = None

    def _draw(self) -> None:
        self.canvas.fill((10, 12, 18))
        self._draw_menu_bar()
        content_rect = Rect(0, self.MENU_HEIGHT, self.WINDOW_SIZE[0], self.WINDOW_SIZE[1] - self.MENU_HEIGHT)
        self.node_rects.clear()
        self.active_renderer.render(self.canvas, self.simulator, content_rect, self.selected_node, self.node_rects)
        self._draw_hints()

        if self.open_menu == "file":
            self._draw_dropdown(self.file_menu_items, 10, self.MENU_HEIGHT)
        elif self.open_menu == "settings":
            self._draw_settings_panel(90, self.MENU_HEIGHT)

        if self.ui_scale == 1.0:
            self.screen.blit(self.canvas, (0, 0))
        else:
            pygame.transform.scale(self.canvas, self.window_size, self.screen)
        pygame.display.flip()

    def _draw_menu_bar(self) -> None:
        bar_rect = Rect(0, 0, self.WINDOW_SIZE[0], self.MENU_HEIGHT)
        pygame.draw.rect(self.canvas, self.MENU_BG, bar_rect)
        pygame.draw.line(self.canvas, self.MENU_BORDER, (0, self.MENU_HEIGHT - 1), (self.WINDOW_SIZE[0], self.MENU_HEIGHT - 1))

        file_label = self.menu_font.render("File", True, self.MENU_TEXT)
        file_rect = file_label.get_rect(topleft=(10, 6))
        self.file_button_rect = Rect(file_rect.left - 4, 0, file_rect.width + 12, self.MENU_HEIGHT)
        file_hover = self.file_button_rect.collidepoint(self.mouse_pos)
        file_color = self.MENU_HIGHLIGHT if (self.open_menu == "file" or file_hover or self.pressed_button == "file") else self.MENU_BG
        pygame.draw.rect(self.canvas, file_color, self.file_button_rect)
        if self.open_menu == "file" or file_hover:
            pygame.draw.rect(self.canvas, self.MENU_BORDER, self.file_button_rect, width=1)
        self.canvas.blit(file_label, file_rect)

        settings_label = self.menu_font.render("Settings", True, self.MENU_TEXT)
        settings_rect = settings_label.get_rect(topleft=(90, 6))
        self.settings_button_rect = Rect(settings_rect.left - 4, 0, settings_rect.width + 12, self.MENU_HEIGHT)
        settings_hover = self.settings_button_rect.collidepoint(self.mouse_pos)
        settings_color = self.MENU_HIGHLIGHT if (self.open_menu == "settings" or settings_hover or self.pressed_button == "settings") else self.MENU_BG
        pygame.draw.rect(self.canvas, settings_color, self.settings_button_rect)
        if self.open_menu == "settings" or settings_hover:
            pygame.draw.rect(self.canvas, self.MENU_BORDER, self.settings_button_rect, width=1)
        self.canvas.blit(settings_label, settings_rect)

        start_label = self.menu_font.render("Start", True, self.MENU_TEXT)
        start_rect = start_label.get_rect(topleft=(190, 6))
        self.start_button_rect = Rect(start_rect.left - 6, 0, start_rect.width + 12, self.MENU_HEIGHT)
        start_hover = self.start_button_rect.collidepoint(self.mouse_pos)
        start_color = (90, 180, 115) if (start_hover or self.pressed_button == "start") else (55, 130, 80)
        pygame.draw.rect(self.canvas, start_color, self.start_button_rect, border_radius=3)
        pygame.draw.rect(self.canvas, (140, 220, 165), self.start_button_rect, width=1, border_radius=3)
        self.canvas.blit(start_label, start_rect)

        stop_label = self.menu_font.render("Stop", True, self.MENU_TEXT)
        stop_rect = stop_label.get_rect(topleft=(250, 6))
        self.stop_button_rect = Rect(stop_rect.left - 6, 0, stop_rect.width + 12, self.MENU_HEIGHT)
        stop_hover = self.stop_button_rect.collidepoint(self.mouse_pos)
        stop_color = (185, 90, 110) if (stop_hover or self.pressed_button == "stop") else (130, 55, 65)
        pygame.draw.rect(self.canvas, stop_color, self.stop_button_rect, border_radius=3)
        pygame.draw.rect(self.canvas, (230, 150, 165), self.stop_button_rect, width=1, border_radius=3)
        self.canvas.blit(stop_label, stop_rect)

        step_label = self.menu_font.render("Step", True, self.MENU_TEXT)
        step_rect = step_label.get_rect(topleft=(310, 6))
        self.step_button_rect = Rect(step_rect.left - 6, 0, step_rect.width + 12, self.MENU_HEIGHT)
        step_hover = self.step_button_rect.collidepoint(self.mouse_pos)
        step_color = (135, 135, 180) if (step_hover or self.pressed_button == "step") else (85, 85, 130)
        pygame.draw.rect(self.canvas, step_color, self.step_button_rect, border_radius=3)
        pygame.draw.rect(self.canvas, (190, 190, 235), self.step_button_rect, width=1, border_radius=3)
        self.canvas.blit(step_label, step_rect)

        status = "Running" if self.auto_run else "Stopped"
        total_units = int(self.simulator.total_units)
        field = f"Gain {self.simulator.pressure_gain:.1f}x"
        if self.simulator.pressure_inverted:
            field += " INV"
        if self.selected_node and self.selected_node in self.simulator.nodes:
            node = self.simulator.nodes[self.selected_node]
            status_line = (
                f"Status: {status}  |  {node.id}: {node.units:.1f}u  pressure {node.pressure:+.1f}"
                f"  |  {field}  |  Total units: {total_units}"
            )
        else:
            status_line = f"Status: {status}  |  Renderer: {self.active_renderer.name}  |  {field}  |  Total units: {total_units}"
        status_text = self.menu_font.render(status_line, True, self.STATUS_TEXT)
        self.canvas.blit(status_text, (380, 6))

    def _draw_dropdown(self, items: List[MenuItem], x: int, y: int) -> None:
        item_height = 24
        width = 160
        background = Rect(x, y, width, item_height * len(items))
        pygame.draw.rect(self.canvas, self.MENU_BG, background)
        pygame.draw.rect(self.canvas, self.MENU_BORDER, background, width=1)

        for index, item in enumerate(items):
            item_rect = Rect(x, y + index * item_height, width, item_height)
            item.rect = item_rect
            item_hover = item_rect.collidepoint(self.mouse_pos)
            if item_hover:
                pygame.draw.rect(self.canvas, self.MENU_HIGHLIGHT, item_rect)
            text_surface = self.menu_font.render(item.label, True, self.MENU_TEXT)
            self.canvas.blit(text_surface, (x + 8, y + index * item_height + 5))
            if index > 0:
                pygame.draw.line(self.canvas, self.MENU_BORDER, (x + 1, item_rect.top), (x + width - 1, item_rect.top))

    def _draw_settings_panel(self, x: int, y: int) -> None:
        self.settings_rows = self._build_setting_rows()
        row_height = 28
        width = 280
        button_size = 24

        background = Rect(x, y, width, row_height * len(self.settings_rows))
        pygame.draw.rect(self.canvas, self.MENU_BG, background)
        pygame.draw.rect(self.canvas, self.MENU_BORDER, background, width=1)

        for index, row in enumerate(self.settings_rows):
            row_top = y + index * row_height
            if index > 0:
                pygame.draw.line(self.canvas, self.MENU_BORDER, (x + 1, row_top), (x + width - 1, row_top))

            label_text = f"{row.label}: {row.value()}"
            text_surface = self.menu_font.render(label_text, True, self.MENU_TEXT)
            self.canvas.blit(text_surface, (x + 8, row_top + (row_height - text_surface.get_height()) // 2))

            control_right = x + width - 8
            for control in reversed(row.controls):
                control_width = button_size if len(control.caption) <= 1 else button_size * 2
                control_rect = Rect(control_right - control_width, row_top + 3, control_width, row_height - 6)
                control.rect = control_rect
                control_hover = control_rect.collidepoint(self.mouse_pos)
                control_color = self.MENU_HIGHLIGHT if control_hover else (40, 44, 64)
                pygame.draw.rect(self.canvas, control_color, control_rect, border_radius=3)
                pygame.draw.rect(self.canvas, self.MENU_BORDER, control_rect, width=1, border_radius=3)
                caption_surface = self.menu_font.render(control.caption, True, self.MENU_TEXT)
                self.canvas.blit(caption_surface, caption_surface.get_rect(center=control_rect.center))
                control_right -= control_width + 6

    def _draw_hints(self) -> None:
        hint_text = (
            "Space: toggle | Tab: renderer | +/-/↑↓: units | ( ): node pressure | "
            "[ ]: node pressure or global gain | i: invert | n: new node | k: kill node"
        )
        text_surface = self.menu_font.render(hint_text, True, self.STATUS_TEXT)
        self.canvas.blit(text_surface, (12, self.WINDOW_SIZE[1] - 24))
