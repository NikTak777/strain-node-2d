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

import pygame
import math
from typing import Union, Optional
from strainnode2d.physics.objects import Object, MotorWheel
from strainnode2d.physics.springs import Spring, Rope, Hydraulic, Beam, AeroBeam
from strainnode2d.core.camera import Camera


class InspectorHUD:
    def __init__(self):
        self.font = pygame.font.SysFont("Consolas", 14)
        self.bg_color = (25, 25, 30, 210)
        self.border_color = (100, 150, 255, 255)
        self.header_color = (35, 35, 45, 230)

        self.pinned = True
        self.screen_x = 20
        self.screen_y = 20
        self.is_dragging = False
        self.drag_offset = (0, 0)
        self.last_hud_x = 20
        self.last_hud_y = 20

        self.panel_rect = None
        self.title_rect = None
        self.pin_btn_rect = None
        self.change_btn_rect = None
        self.flip_btn_rect = None

        self.header_height = 35
        self.padding = 12

    @staticmethod
    def get_inspection_target(app) -> Optional[Union[Object, Spring]]:
        if len(app.selected_springs) == 1:
            return app.selected_springs[0]
        if len(app.selected_nodes) == 1:
            return app.selected_nodes[0]
        return None

    def is_visible(self, app) -> bool:
        return self.get_inspection_target(app) is not None

    def toggle_pin(self):
        if self.pinned:
            self.screen_x = self.last_hud_x
            self.screen_y = self.last_hud_y
        self.pinned = not self.pinned
        self.is_dragging = False

    def handle_mouse_down(self, mx: int, my: int, app) -> bool:
        if not self.is_visible(app) or self.panel_rect is None:
            return False

        if self.pin_btn_rect and self.pin_btn_rect.collidepoint(mx, my):
            self.toggle_pin()
            return True

        target = self.get_inspection_target(app)

        if isinstance(target, Spring):
            if self.flip_btn_rect and self.flip_btn_rect.collidepoint(mx, my):
                if target.__class__.__name__ == "AeroBeam":
                    target.normal_flip *= -1
                return True

            if self.change_btn_rect and self.change_btn_rect.collidepoint(mx, my):
                self._change_spring_type(app, target)
                return True

        if self.panel_rect.collidepoint(mx, my):
            if not self.pinned and self.title_rect and self.title_rect.collidepoint(mx, my):
                self.is_dragging = True
                self.drag_offset = (mx - self.screen_x, my - self.screen_y)
            return True

        return False

    def handle_mouse_motion(self, mx: int, my: int, app):
        if not self.is_dragging or self.pinned or self.panel_rect is None:
            return

        bg_width = self.panel_rect.width
        bg_height = self.panel_rect.height
        self.screen_x, self.screen_y = self._clamp_position(
            mx - self.drag_offset[0],
            my - self.drag_offset[1],
            bg_width,
            bg_height,
            app.width,
            app.height,
        )

    def handle_mouse_up(self):
        self.is_dragging = False

    def _change_spring_type(self, app, target_spring: Spring):
        from strainnode2d.ui.dialogs import show_type_dialog

        obj1, obj2 = target_spring.obj1, target_spring.obj2
        new_type = show_type_dialog(target_spring.__class__.__name__)

        if not new_type or new_type == target_spring.__class__.__name__:
            return

        if target_spring in app.sim.springs:
            app.sim.springs.remove(target_spring)

        new_link = None
        if new_type == "Spring":
            new_link = Spring(obj1, obj2, k=20000.0, d=160.0)
        elif new_type == "Rope":
            new_link = Rope(obj1, obj2, k=150000.0, d=500.0)
        elif new_type == "Hydraulic":
            new_link = Hydraulic(obj1, obj2, speed=2.0, min_length=0.5, max_length=10.0)
        elif new_type == "Beam":
            new_link = Beam(obj1, obj2)
        elif new_type == "AeroBeam":
            new_link = AeroBeam(obj1, obj2, lift_coef=2.5, chord=2.0)

        if new_link:
            app.sim.add_spring(new_link)
            app.selected_springs = [new_link]

    @staticmethod
    def _clamp_position(hud_x: float, hud_y: float, bg_width: int, bg_height: int,
                        screen_width: int, screen_height: int) -> tuple[int, int]:
        margin = 10
        hud_x = max(margin, min(hud_x, screen_width - bg_width - margin))
        hud_y = max(margin, min(hud_y, screen_height - bg_height - margin))
        return int(hud_x), int(hud_y)

    def _compute_anchored_position(self, target: Union[Object, Spring], scale: float,
                                   camera: Camera, bg_width: int, bg_height: int,
                                   screen_width: int, screen_height: int) -> tuple[int, int]:
        if isinstance(target, Object):
            anchor_x, anchor_y = target.get_location()
        else:
            x1, y1 = target.obj1.get_location()
            x2, y2 = target.obj2.get_location()
            anchor_x, anchor_y = (x1 + x2) / 2, (y1 + y2) / 2

        screen_x, screen_y = camera.phys_to_screen(anchor_x, anchor_y, scale)
        margin_px = 20
        eff_scale = scale * camera.zoom
        offset_x = int(target.radius * eff_scale) + margin_px if isinstance(target, Object) else 25

        hud_x = screen_x + offset_x
        hud_y = screen_y - bg_height // 2

        if hud_x + bg_width > screen_width:
            hud_x = screen_x - offset_x - bg_width

        return self._clamp_position(hud_x, hud_y, bg_width, bg_height, screen_width, screen_height)

    @staticmethod
    def _get_header_label(target: Union[Object, Spring], pinned: bool) -> str:
        kind = "узла" if isinstance(target, Object) else "балки"
        status = "закреплён" if pinned else "свободен"
        return f"Инспектор {kind}: {status}"

    def _draw_header(self, screen: pygame.Surface, hud_x: int, hud_y: int, bg_width: int,
                     target: Union[Object, Spring]):
        header_rect = pygame.Rect(hud_x, hud_y, bg_width, self.header_height)
        self.title_rect = header_rect

        pin_size = 16
        pin_x = hud_x + bg_width - self.padding - pin_size
        pin_y = hud_y + (self.header_height - pin_size) // 2
        self.pin_btn_rect = pygame.Rect(pin_x, pin_y, pin_size, pin_size)

        label = self._get_header_label(target, self.pinned)
        label_color = (190, 210, 255) if self.pinned else (255, 215, 140)
        label_surf = self.font.render(label, True, label_color)
        screen.blit(label_surf, (hud_x + self.padding, hud_y + (self.header_height - label_surf.get_height()) // 2))

        pygame.draw.rect(screen, (50, 50, 60), self.pin_btn_rect, border_radius=3)
        pygame.draw.rect(screen, (140, 160, 200), self.pin_btn_rect, width=1, border_radius=3)
        if self.pinned:
            pygame.draw.line(screen, (100, 220, 120),
                             (pin_x + 3, pin_y + 8), (pin_x + 6, pin_y + 12), 2)
            pygame.draw.line(screen, (100, 220, 120),
                             (pin_x + 6, pin_y + 12), (pin_x + 13, pin_y + 4), 2)

    def draw(self, screen: pygame.Surface, target: Union[Object, Spring], scale: float,
             camera: Camera, screen_width: int, screen_height: int) -> None:
        """
        Отрисовка информационного окна (HUD) с характеристиками выбранного физического объекта.
        """
        self.change_btn_rect = None
        self.flip_btn_rect = None

        lines = []

        if isinstance(target, Object):
            speed = math.sqrt(target.velocity[0] ** 2 + target.velocity[1] ** 2)

            lines.extend([
                f"----- {target.__class__.__name__} -----",
                f"ID/Метка:         #{id(target) % 1000}",
                f"Масса:            {target.mass:.2f} кг",
                f"Радиус:           {target.radius:.2f} м",
                f"Плотность:        {target.density:.2f} кг/м3",
                f"Коэф. прыгучести: {target.restitution:.2f}",
                f"Коэф. трения:     {target.friction:.2f}",
                f"Статичный:        {'Да' if getattr(target, 'is_static', False) else 'Нет'}",
                f"Скор. общ:        {speed:.2f} м/с",
                f"Вращение:         {target.angular_velocity:.2f} рад/с"
            ])

            if isinstance(target, MotorWheel):
                lines.append(f"Мотор:           {'Вкл' if target.direction != 0 else 'Выкл'}")
                lines.append(f"Мощность:        {target.power:.2f}")

        elif isinstance(target, Spring):
            strain_pct = (target.current_strain / target.yield_limit) * 100 if target.yield_limit else 0

            lines.extend([
                f"--- {target.__class__.__name__} ---",
                f"Жесткость: {target.k:.0f}",
                f"Демпфер:   {target.d:.0f}",
                f"Натяжение: {target.current_strain:.2f} м",
                f"Нагрузка:  {abs(strain_pct):.1f}%",
                f"Предел:    {target.yield_limit:.2f} м"
            ])

        rendered_lines = [self.font.render(line, True, (240, 240, 240)) for line in lines]
        max_width = max(surf.get_width() for surf in rendered_lines)
        total_height = sum(surf.get_height() for surf in rendered_lines) + (len(lines) - 1) * 2

        btn_height = 25
        content_height = total_height + self.padding * 2
        if isinstance(target, Spring):
            content_height += btn_height + 10
            if target.__class__.__name__ == "AeroBeam":
                content_height += btn_height + 5

        pin_size = 16
        header_label_surf = self.font.render(self._get_header_label(target, self.pinned), True, (255, 255, 255))
        min_header_width = header_label_surf.get_width() + self.padding * 2 + pin_size + 8
        bg_width = max(max_width + self.padding * 2, min_header_width)
        bg_height = self.header_height + content_height

        if self.pinned:
            hud_x, hud_y = self._compute_anchored_position(
                target, scale, camera, bg_width, bg_height, screen_width, screen_height
            )
        else:
            hud_x, hud_y = self._clamp_position(
                self.screen_x, self.screen_y, bg_width, bg_height, screen_width, screen_height
            )
            self.screen_x, self.screen_y = hud_x, hud_y

        self.last_hud_x, self.last_hud_y = hud_x, hud_y
        self.panel_rect = pygame.Rect(hud_x, hud_y, bg_width, bg_height)

        bg_surf = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, self.bg_color, bg_surf.get_rect(), border_radius=10)
        pygame.draw.rect(bg_surf, self.header_color,
                         pygame.Rect(0, 0, bg_width, self.header_height),
                         border_top_left_radius=10, border_top_right_radius=10)
        screen.blit(bg_surf, (hud_x, hud_y))

        self._draw_header(screen, hud_x, hud_y, bg_width, target)

        curr_y = hud_y + self.header_height + self.padding
        for surf in rendered_lines:
            screen.blit(surf, (hud_x + self.padding, curr_y))
            curr_y += surf.get_height() + 2

        if isinstance(target, Spring):
            curr_y += 5
            btn_rect = pygame.Rect(hud_x + self.padding, curr_y, bg_width - self.padding * 2, btn_height)
            pygame.draw.rect(screen, (70, 100, 200), btn_rect, border_radius=5)

            btn_text = self.font.render("Изменить тип", True, (255, 255, 255))
            screen.blit(btn_text, (btn_rect.centerx - btn_text.get_width() // 2,
                                    btn_rect.centery - btn_text.get_height() // 2))
            self.change_btn_rect = btn_rect

            if target.__class__.__name__ == "AeroBeam":
                curr_y += btn_height + 5
                flip_rect = pygame.Rect(hud_x + self.padding, curr_y, bg_width - self.padding * 2, btn_height)
                pygame.draw.rect(screen, (200, 100, 70), flip_rect, border_radius=5)
                flip_text = self.font.render("Повернуть нормаль", True, (255, 255, 255))
                screen.blit(flip_text, (flip_rect.centerx - flip_text.get_width() // 2,
                                        flip_rect.centery - flip_text.get_height() // 2))
                self.flip_btn_rect = flip_rect

        pygame.draw.rect(screen, self.border_color, self.panel_rect, width=2, border_radius=10)
