"""
    This file is part of StrainNode2D.
    Copyright (C) 2026 Nikita Kondrakhin

    StrainNode2D is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    StrainNode2D is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import pygame
from typing import Optional
from strainnode2d.physics.serializer import (
    get_default_prefabs_dir,
    load_prefab_file,
    spawn_prefab as spawn_prefab_into_sim,
)


class PrefabMenu:
    WIDTH = 190
    HEADER_HEIGHT = 36
    PADDING = 10
    BTN_HEIGHT = 28
    BTN_GAP = 6

    def __init__(self, prefabs_dir: Optional[str] = None):
        self.font = pygame.font.SysFont("Consolas", 13)
        self.title_font = pygame.font.SysFont("Consolas", 14, bold=True)
        self.visible = False
        self.prefabs_dir = prefabs_dir or get_default_prefabs_dir()
        self.prefabs: list = []
        self.btn_rects: dict = {}
        self.panel_rect: Optional[pygame.Rect] = None
        self.toggle_btn_rect: Optional[pygame.Rect] = None
        self.refresh()

    def refresh(self):
        self.prefabs.clear()
        if not os.path.isdir(self.prefabs_dir):
            return
        for name in sorted(os.listdir(self.prefabs_dir)):
            if name.lower().endswith(".json"):
                path = os.path.join(self.prefabs_dir, name)
                self.prefabs.append((self._pretty_name(name), path))

    @staticmethod
    def _pretty_name(filename: str) -> str:
        base = os.path.splitext(filename)[0]
        return base.replace("_", " ").title()

    def toggle_visible(self):
        self.visible = not self.visible

    def spawn_prefab(self, app, filepath: str):
        try:
            data = load_prefab_file(filepath)
        except OSError:
            return

        app._clear_scene_editor_state()
        new_nodes, new_springs = spawn_prefab_into_sim(app.sim, data)
        if not new_nodes:
            return

        app.selected_nodes = new_nodes
        app.selected_springs = new_springs

    def handle_mouse_down(self, mx: int, my: int, app) -> bool:
        if not self.visible:
            return False

        if self.toggle_btn_rect and self.toggle_btn_rect.collidepoint(mx, my):
            self.toggle_visible()
            return True

        if self.panel_rect is None:
            return False

        if not self.panel_rect.collidepoint(mx, my):
            return False

        for path, rect in self.btn_rects.items():
            if rect.collidepoint(mx, my):
                self.spawn_prefab(app, path)
                return True
        return True

    def _draw_button(self, screen, rect: pygame.Rect, text: str, color: tuple, hover: bool):
        bg = tuple(min(255, c + 25) for c in color) if hover else color
        pygame.draw.rect(screen, bg, rect, border_radius=5)
        pygame.draw.rect(screen, (90, 100, 130), rect, width=1, border_radius=5)
        label = self.font.render(text, True, (240, 240, 240))
        if label.get_width() > rect.width - 8:
            while label.get_width() > rect.width - 8 and len(text) > 3:
                text = text[:-1]
            label = self.font.render(text + "…", True, (240, 240, 240))
        screen.blit(label, (rect.x + 8, rect.centery - label.get_height() // 2))

    def draw(self, screen: pygame.Surface, screen_height: int):
        if not self.visible:
            return

        mx, my = pygame.mouse.get_pos()
        self.btn_rects = {}

        panel_h = screen_height
        panel = pygame.Rect(0, 0, self.WIDTH, panel_h)
        self.panel_rect = panel

        bg = pygame.Surface((self.WIDTH, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (22, 24, 32, 235), bg.get_rect())
        screen.blit(bg, (0, 0))
        pygame.draw.line(screen, (70, 90, 130), (self.WIDTH - 1, 0), (self.WIDTH - 1, panel_h), 2)

        header_rect = pygame.Rect(0, 0, self.WIDTH, self.HEADER_HEIGHT)
        pygame.draw.rect(screen, (32, 36, 48), header_rect)
        title = self.title_font.render("Префабы", True, (190, 210, 255))
        screen.blit(title, (self.PADDING, (self.HEADER_HEIGHT - title.get_height()) // 2))

        collapse_rect = pygame.Rect(self.WIDTH - 28, 8, 20, 20)
        self.toggle_btn_rect = collapse_rect
        pygame.draw.rect(screen, (50, 55, 70), collapse_rect, border_radius=3)
        collapse_label = self.font.render("<", True, (200, 210, 230))
        screen.blit(collapse_label, (collapse_rect.centerx - collapse_label.get_width() // 2,
                                       collapse_rect.centery - collapse_label.get_height() // 2))

        curr_y = self.HEADER_HEIGHT + self.PADDING
        btn_width = self.WIDTH - self.PADDING * 2

        if not self.prefabs:
            empty = self.font.render("Нет .json", True, (160, 160, 170))
            screen.blit(empty, (self.PADDING, curr_y))
            return

        for label, path in self.prefabs:
            btn_rect = pygame.Rect(self.PADDING, curr_y, btn_width, self.BTN_HEIGHT)
            hover = btn_rect.collidepoint(mx, my)
            self._draw_button(screen, btn_rect, label, (45, 70, 110), hover)
            self.btn_rects[path] = btn_rect
            curr_y += self.BTN_HEIGHT + self.BTN_GAP
