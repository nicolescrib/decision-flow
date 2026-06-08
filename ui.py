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


class UI:
    WINDOW_SIZE = (760, 520)
    MENU_HEIGHT = 28
    MENU_BG = (14, 16, 26)
    MENU_BORDER = (70, 76, 100)
    MENU_TEXT = (240, 242, 248)
    MENU_HIGHLIGHT = (70, 95, 150)
    STATUS_TEXT = (205, 212, 230)
    PRESSURE_STEP = 0.5
    MAX_PRESSURE = 10.0
    SCALE_STEP = 0.25

    def __init__(self, simulator: Simulator, renderers: Sequence[Renderer]) -> None:
        pygame.init()
        self.simulator = simulator
        self.renderers = list(renderers)
        self.active_renderer_index = 0
        self.active_renderer = self.renderers[self.active_renderer_index]
        self.auto_run = False
        self.running = True
        self.open_menu: Optional[str] = None
        self.selected_node: Optional[str] = None

        self.screen = pygame.display.set_mode(self.WINDOW_SIZE)
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
        self.renderer_menu_items = [
            MenuItem(renderer.name, self._make_renderer_select_action(index))
            for index, renderer in enumerate(self.renderers)
        ]

        self.file_button_rect: Optional[Rect] = None
        self.renderer_button_rect: Optional[Rect] = None
        self.start_button_rect: Optional[Rect] = None
        self.stop_button_rect: Optional[Rect] = None
        self.step_button_rect: Optional[Rect] = None
        self.mouse_pos: Tuple[int, int] = (0, 0)
        self.pressed_button: Optional[str] = None
        self.node_rects: Dict[str, Rect] = {}

    def _make_renderer_select_action(self, index: int) -> Callable[[], None]:
        def select_renderer() -> None:
            self.active_renderer_index = index
            self.active_renderer = self.renderers[index]
            self.open_menu = None

        return select_renderer

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
                self.mouse_pos = event.pos
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
                elif event.key == pygame.K_LEFTBRACKET:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        node = self.simulator.nodes[self.selected_node]
                        node.pressure = max(-self.MAX_PRESSURE, node.pressure - self.PRESSURE_STEP)
                elif event.key == pygame.K_n:
                    self.simulator.add_random_node()
                elif event.key == pygame.K_k:
                    removed_id = self.simulator.remove_random_node()
                    if removed_id is not None and removed_id == self.selected_node:
                        self.selected_node = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse_press(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.pressed_button = None

    def _handle_mouse_press(self, position: Tuple[int, int]) -> None:
        if self.file_button_rect and self.file_button_rect.collidepoint(position):
            self.pressed_button = "file"
            self.open_menu = "file" if self.open_menu != "file" else None
            return

        if self.renderer_button_rect and self.renderer_button_rect.collidepoint(position):
            self.pressed_button = "renderer"
            self.open_menu = "renderer" if self.open_menu != "renderer" else None
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
        elif self.open_menu == "renderer":
            for item in self.renderer_menu_items:
                if item.rect and item.rect.collidepoint(position):
                    item.action()
                    return

        for node_id, node_rect in self.node_rects.items():
            if node_rect.collidepoint(position):
                self.selected_node = node_id
                self.open_menu = None
                return

        self.open_menu = None

    def _draw(self) -> None:
        self.screen.fill((10, 12, 18))
        self._draw_menu_bar()
        content_rect = Rect(0, self.MENU_HEIGHT, self.WINDOW_SIZE[0], self.WINDOW_SIZE[1] - self.MENU_HEIGHT)
        self.node_rects.clear()
        self.active_renderer.render(self.screen, self.simulator, content_rect, self.selected_node, self.node_rects)
        self._draw_hints()

        if self.open_menu == "file":
            self._draw_dropdown(self.file_menu_items, 10, self.MENU_HEIGHT)
        elif self.open_menu == "renderer":
            self._draw_dropdown(self.renderer_menu_items, 90, self.MENU_HEIGHT)

        pygame.display.flip()

    def _draw_menu_bar(self) -> None:
        bar_rect = Rect(0, 0, self.WINDOW_SIZE[0], self.MENU_HEIGHT)
        pygame.draw.rect(self.screen, self.MENU_BG, bar_rect)
        pygame.draw.line(self.screen, self.MENU_BORDER, (0, self.MENU_HEIGHT - 1), (self.WINDOW_SIZE[0], self.MENU_HEIGHT - 1))

        file_label = self.menu_font.render("File", True, self.MENU_TEXT)
        file_rect = file_label.get_rect(topleft=(10, 6))
        self.file_button_rect = Rect(file_rect.left - 4, 0, file_rect.width + 12, self.MENU_HEIGHT)
        file_hover = self.file_button_rect.collidepoint(self.mouse_pos)
        file_color = self.MENU_HIGHLIGHT if (self.open_menu == "file" or file_hover or self.pressed_button == "file") else self.MENU_BG
        pygame.draw.rect(self.screen, file_color, self.file_button_rect)
        if self.open_menu == "file" or file_hover:
            pygame.draw.rect(self.screen, self.MENU_BORDER, self.file_button_rect, width=1)
        self.screen.blit(file_label, file_rect)

        renderer_label = self.menu_font.render("Renderer", True, self.MENU_TEXT)
        renderer_rect = renderer_label.get_rect(topleft=(90, 6))
        self.renderer_button_rect = Rect(renderer_rect.left - 4, 0, renderer_rect.width + 12, self.MENU_HEIGHT)
        renderer_hover = self.renderer_button_rect.collidepoint(self.mouse_pos)
        renderer_color = self.MENU_HIGHLIGHT if (self.open_menu == "renderer" or renderer_hover or self.pressed_button == "renderer") else self.MENU_BG
        pygame.draw.rect(self.screen, renderer_color, self.renderer_button_rect)
        if self.open_menu == "renderer" or renderer_hover:
            pygame.draw.rect(self.screen, self.MENU_BORDER, self.renderer_button_rect, width=1)
        self.screen.blit(renderer_label, renderer_rect)

        start_label = self.menu_font.render("Start", True, self.MENU_TEXT)
        start_rect = start_label.get_rect(topleft=(190, 6))
        self.start_button_rect = Rect(start_rect.left - 6, 0, start_rect.width + 12, self.MENU_HEIGHT)
        start_hover = self.start_button_rect.collidepoint(self.mouse_pos)
        start_color = (90, 180, 115) if (start_hover or self.pressed_button == "start") else (55, 130, 80)
        pygame.draw.rect(self.screen, start_color, self.start_button_rect, border_radius=3)
        pygame.draw.rect(self.screen, (140, 220, 165), self.start_button_rect, width=1, border_radius=3)
        self.screen.blit(start_label, start_rect)

        stop_label = self.menu_font.render("Stop", True, self.MENU_TEXT)
        stop_rect = stop_label.get_rect(topleft=(250, 6))
        self.stop_button_rect = Rect(stop_rect.left - 6, 0, stop_rect.width + 12, self.MENU_HEIGHT)
        stop_hover = self.stop_button_rect.collidepoint(self.mouse_pos)
        stop_color = (185, 90, 110) if (stop_hover or self.pressed_button == "stop") else (130, 55, 65)
        pygame.draw.rect(self.screen, stop_color, self.stop_button_rect, border_radius=3)
        pygame.draw.rect(self.screen, (230, 150, 165), self.stop_button_rect, width=1, border_radius=3)
        self.screen.blit(stop_label, stop_rect)

        step_label = self.menu_font.render("Step", True, self.MENU_TEXT)
        step_rect = step_label.get_rect(topleft=(310, 6))
        self.step_button_rect = Rect(step_rect.left - 6, 0, step_rect.width + 12, self.MENU_HEIGHT)
        step_hover = self.step_button_rect.collidepoint(self.mouse_pos)
        step_color = (135, 135, 180) if (step_hover or self.pressed_button == "step") else (85, 85, 130)
        pygame.draw.rect(self.screen, step_color, self.step_button_rect, border_radius=3)
        pygame.draw.rect(self.screen, (190, 190, 235), self.step_button_rect, width=1, border_radius=3)
        self.screen.blit(step_label, step_rect)

        status = "Running" if self.auto_run else "Stopped"
        total_units = int(self.simulator.total_units)
        if self.selected_node and self.selected_node in self.simulator.nodes:
            node = self.simulator.nodes[self.selected_node]
            status_line = (
                f"Status: {status}  |  {node.id}: {node.units:.1f}u  pressure {node.pressure:+.1f}"
                f"  |  Total units: {total_units}"
            )
        else:
            status_line = f"Status: {status}  |  Renderer: {self.active_renderer.name}  |  Total units: {total_units}"
        status_text = self.menu_font.render(status_line, True, self.STATUS_TEXT)
        self.screen.blit(status_text, (380, 6))

    def _draw_dropdown(self, items: List[MenuItem], x: int, y: int) -> None:
        item_height = 24
        width = 160
        background = Rect(x, y, width, item_height * len(items))
        pygame.draw.rect(self.screen, self.MENU_BG, background)
        pygame.draw.rect(self.screen, self.MENU_BORDER, background, width=1)

        for index, item in enumerate(items):
            item_rect = Rect(x, y + index * item_height, width, item_height)
            item.rect = item_rect
            item_hover = item_rect.collidepoint(self.mouse_pos)
            if item_hover:
                pygame.draw.rect(self.screen, self.MENU_HIGHLIGHT, item_rect)
            text_surface = self.menu_font.render(item.label, True, self.MENU_TEXT)
            self.screen.blit(text_surface, (x + 8, y + index * item_height + 5))
            if index > 0:
                pygame.draw.line(self.screen, self.MENU_BORDER, (x + 1, item_rect.top), (x + width - 1, item_rect.top))

    def _draw_hints(self) -> None:
        hint_text = (
            "Space: toggle | Tab: renderer | Click node: Up/Down units, [ ]: pressure | "
            "+/-: scale | n: new node | k: kill random node"
        )
        text_surface = self.menu_font.render(hint_text, True, self.STATUS_TEXT)
        self.screen.blit(text_surface, (12, self.WINDOW_SIZE[1] - 24))
