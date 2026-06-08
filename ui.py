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
    MENU_BG = (20, 22, 36)
    MENU_TEXT = (220, 220, 220)
    MENU_HIGHLIGHT = (60, 80, 130)
    STATUS_TEXT = (200, 200, 220)

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
        self.simulator.particles.clear()
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
                    elif hasattr(self.active_renderer, 'set_resolution'):
                        self.active_renderer.set_resolution(self.active_renderer.resolution + 1)
                elif event.key == pygame.K_MINUS:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        self.simulator.nodes[self.selected_node].units = max(0.0, self.simulator.nodes[self.selected_node].units - 5.0)
                    elif hasattr(self.active_renderer, 'set_resolution'):
                        self.active_renderer.set_resolution(self.active_renderer.resolution - 1)
                elif event.key == pygame.K_UP:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        self.simulator.nodes[self.selected_node].units = min(
                            self.simulator.nodes[self.selected_node].capacity,
                            self.simulator.nodes[self.selected_node].units + 1.0
                        )
                elif event.key == pygame.K_DOWN:
                    if self.selected_node and self.selected_node in self.simulator.nodes:
                        self.simulator.nodes[self.selected_node].units = max(0.0, self.simulator.nodes[self.selected_node].units - 1.0)
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

        file_label = self.menu_font.render("File", True, self.MENU_TEXT)
        file_rect = file_label.get_rect(topleft=(10, 6))
        self.file_button_rect = Rect(file_rect.left - 4, 0, file_rect.width + 12, self.MENU_HEIGHT)
        file_hover = self.file_button_rect.collidepoint(self.mouse_pos)
        file_color = self.MENU_HIGHLIGHT if (self.open_menu == "file" or file_hover or self.pressed_button == "file") else self.MENU_BG
        pygame.draw.rect(self.screen, file_color, self.file_button_rect)
        self.screen.blit(file_label, file_rect)

        renderer_label = self.menu_font.render("Renderer", True, self.MENU_TEXT)
        renderer_rect = renderer_label.get_rect(topleft=(90, 6))
        self.renderer_button_rect = Rect(renderer_rect.left - 4, 0, renderer_rect.width + 12, self.MENU_HEIGHT)
        renderer_hover = self.renderer_button_rect.collidepoint(self.mouse_pos)
        renderer_color = self.MENU_HIGHLIGHT if (self.open_menu == "renderer" or renderer_hover or self.pressed_button == "renderer") else self.MENU_BG
        pygame.draw.rect(self.screen, renderer_color, self.renderer_button_rect)
        self.screen.blit(renderer_label, renderer_rect)

        start_label = self.menu_font.render("Start", True, self.MENU_TEXT)
        start_rect = start_label.get_rect(topleft=(190, 6))
        self.start_button_rect = Rect(start_rect.left - 6, 0, start_rect.width + 12, self.MENU_HEIGHT)
        start_hover = self.start_button_rect.collidepoint(self.mouse_pos)
        start_color = (80, 160, 100) if (start_hover or self.pressed_button == "start") else (50, 120, 70)
        pygame.draw.rect(self.screen, start_color, self.start_button_rect, border_radius=4)
        self.screen.blit(start_label, start_rect)

        stop_label = self.menu_font.render("Stop", True, self.MENU_TEXT)
        stop_rect = stop_label.get_rect(topleft=(250, 6))
        self.stop_button_rect = Rect(stop_rect.left - 6, 0, stop_rect.width + 12, self.MENU_HEIGHT)
        stop_hover = self.stop_button_rect.collidepoint(self.mouse_pos)
        stop_color = (160, 80, 100) if (stop_hover or self.pressed_button == "stop") else (120, 50, 60)
        pygame.draw.rect(self.screen, stop_color, self.stop_button_rect, border_radius=4)
        self.screen.blit(stop_label, stop_rect)

        step_label = self.menu_font.render("Step", True, self.MENU_TEXT)
        step_rect = step_label.get_rect(topleft=(310, 6))
        self.step_button_rect = Rect(step_rect.left - 6, 0, step_rect.width + 12, self.MENU_HEIGHT)
        step_hover = self.step_button_rect.collidepoint(self.mouse_pos)
        step_color = (120, 120, 160) if (step_hover or self.pressed_button == "step") else (80, 80, 120)
        pygame.draw.rect(self.screen, step_color, self.step_button_rect, border_radius=4)
        self.screen.blit(step_label, step_rect)

        status = "Running" if self.auto_run else "Stopped"
        status_text = self.menu_font.render(f"Status: {status}  |  Renderer: {self.active_renderer.name}", True, self.STATUS_TEXT)
        self.screen.blit(status_text, (380, 6))

    def _draw_dropdown(self, items: List[MenuItem], x: int, y: int) -> None:
        item_height = 24
        width = 160
        background = Rect(x, y, width, item_height * len(items))
        pygame.draw.rect(self.screen, (30, 35, 60), background)
        pygame.draw.rect(self.screen, (180, 180, 210), background, width=1)

        for index, item in enumerate(items):
            item_rect = Rect(x, y + index * item_height, width, item_height)
            item.rect = item_rect
            pygame.draw.rect(self.screen, self.MENU_BG if index % 2 == 0 else (28, 32, 50), item_rect)
            text_surface = self.menu_font.render(item.label, True, self.MENU_TEXT)
            self.screen.blit(text_surface, (x + 8, y + index * item_height + 5))

    def _draw_hints(self) -> None:
        hint_text = "Space: toggle  |  Tab: renderer  |  +/-: resolution  |  Click menus"
        text_surface = self.menu_font.render(hint_text, True, self.STATUS_TEXT)
        self.screen.blit(text_surface, (12, self.WINDOW_SIZE[1] - 24))
