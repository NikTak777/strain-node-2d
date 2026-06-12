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
from strainnode2d.physics.objects import Object, MotorWheel, StructuralNode
from strainnode2d.physics.springs import Spring
from strainnode2d.core.entity_conversion import (
    convert_object_type, convert_spring_type, replace_object_in_simulation,
)
from strainnode2d.core.camera import Camera


class InspectorHUD:
    SPRING_TYPE_OPTIONS = [
        ("1  Spring — пружина", "Spring"),
        ("2  Rope — трос", "Rope"),
        ("3  Hydraulic — гидравлика", "Hydraulic"),
        ("4  Beam — жёсткая балка", "Beam"),
        ("5  AeroBeam — аэробалка", "AeroBeam"),
    ]
    NODE_TYPE_OPTIONS = [
        ("1  Object — узел", "Object"),
        ("2  MotorWheel — колесо", "MotorWheel"),
        ("3  StructuralNode — каркас", "StructuralNode"),
    ]

    SPRING_COMMON_FIELDS = [
        ("Жесткость (k):", "k"),
        ("Демпфер (d):", "d"),
        ("Предел текучести:", "yield_limit"),
        ("Предел разрыва:", "break_limit"),
        ("Длина покоя (м):", "rest_length"),
        ("Радиус коллизии (м):", "collision_radius"),
    ]
    HYDRAULIC_FIELDS = [
        ("Скорость (м/с):", "speed"),
        ("Мин. длина:", "min_length"),
        ("Макс. длина:", "max_length"),
    ]
    AERO_FIELDS = [
        ("Хорда (м):", "chord"),
        ("Подъём (Cl):", "lift_coef"),
        ("Баз. сопр.:", "base_drag"),
        ("Инд. сопр.:", "induced_drag"),
    ]
    OBJECT_FIELDS = [
        ("Радиус (м):", "radius"),
        ("Плотность:", "density"),
        ("Упругость:", "restitution"),
        ("Трение:", "friction"),
    ]
    MOTOR_FIELDS = [
        ("Мощность:", "power"),
        ("Макс. скорость:", "max_speed"),
    ]

    def __init__(self):
        self.font = pygame.font.SysFont("Consolas", 14)
        self.bg_color = (25, 25, 30, 210)
        self.border_color = (100, 150, 255, 255)
        self.header_color = (35, 35, 45, 230)

        self.enabled = False
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
        self.collision_btn_rect = None
        self.edit_btn_rect = None
        self.save_btn_rect = None
        self.cancel_btn_rect = None
        self.field_rects = {}

        self.edit_mode = False
        self.type_picker_mode = False
        self._edit_target = None
        self.draft = {}
        self.active_field = None
        self.error_message = None
        self.picked_type = "Spring"
        self.type_option_rects = {}
        self._picker_kind = None
        self._type_picker_target = None

        self.header_height = 35
        self.padding = 12
        self.field_height = 22
        self.btn_height = 25

    @property
    def is_editing(self) -> bool:
        return self.edit_mode

    @property
    def blocks_input(self) -> bool:
        return self.edit_mode or self.type_picker_mode

    @staticmethod
    def get_inspection_target(app) -> Optional[Union[Object, Spring]]:
        if len(app.selected_springs) == 1:
            return app.selected_springs[0]
        if len(app.selected_nodes) == 1:
            return app.selected_nodes[0]
        return None

    def is_visible(self, app) -> bool:
        return self.enabled and self.get_inspection_target(app) is not None

    def toggle_enabled(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self.close_edit_mode()
            self.close_type_picker()

    def _get_active_type_options(self) -> list[tuple[str, str]]:
        if self._picker_kind == "node":
            return self.NODE_TYPE_OPTIONS
        return self.SPRING_TYPE_OPTIONS

    def _get_spring_fields(self, target: Spring) -> list[tuple[str, str]]:
        fields = list(self.SPRING_COMMON_FIELDS)
        type_name = target.__class__.__name__
        if type_name == "Hydraulic":
            fields.extend(self.HYDRAULIC_FIELDS)
        elif type_name == "AeroBeam":
            fields.extend(self.AERO_FIELDS)
        return fields

    def _get_object_fields(self, target: Object) -> list[tuple[str, str]]:
        fields = list(self.OBJECT_FIELDS)
        if isinstance(target, MotorWheel):
            fields.extend(self.MOTOR_FIELDS)
        return fields

    def _get_fields(self, target: Union[Object, Spring]) -> list[tuple[str, str]]:
        if isinstance(target, Spring):
            return self._get_spring_fields(target)
        return self._get_object_fields(target)

    def open_edit_mode(self, target: Union[Object, Spring]):
        self.close_type_picker()
        self.edit_mode = True
        self._edit_target = target
        self.active_field = None
        self.error_message = None
        self.draft = {key: str(getattr(target, key)) for _, key in self._get_fields(target)}

    def close_edit_mode(self):
        self.edit_mode = False
        self._edit_target = None
        self.draft = {}
        self.active_field = None
        self.error_message = None
        self.field_rects = {}

    def open_type_picker(self, target: Union[Object, Spring]):
        self.close_edit_mode()
        self.type_picker_mode = True
        self.picked_type = target.__class__.__name__
        self.type_option_rects = {}
        self._picker_kind = "spring" if isinstance(target, Spring) else "node"
        self._type_picker_target = target

    def close_type_picker(self):
        self.type_picker_mode = False
        self.type_option_rects = {}
        self._picker_kind = None
        self._type_picker_target = None

    def apply_spring_type_change(self, app, source: Spring, new_type: str) -> bool:
        new_link = convert_spring_type(source, new_type)
        if new_link is None:
            return False
        if source in app.sim.springs:
            app.sim.springs.remove(source)
        app.sim.add_spring(new_link)
        app.selected_springs = [new_link]
        self.close_type_picker()
        return True

    def apply_object_type_change(self, app, source: Object, new_type: str) -> bool:
        new_obj = convert_object_type(source, new_type)
        if new_obj is None:
            return False
        replace_object_in_simulation(app.sim, source, new_obj)
        if app.camera.target is source:
            app.camera.target = new_obj
        app.selected_nodes = [new_obj]
        self.close_type_picker()
        return True

    def _apply_type_change(self, app, target: Union[Object, Spring]) -> bool:
        if isinstance(target, Spring):
            return self.apply_spring_type_change(app, target, self.picked_type)
        return self.apply_object_type_change(app, target, self.picked_type)

    def toggle_pin(self):
        if self.pinned:
            self.screen_x = self.last_hud_x
            self.screen_y = self.last_hud_y
        self.pinned = not self.pinned
        self.is_dragging = False

    def handle_keydown(self, event: pygame.event.Event, app) -> bool:
        if not self.is_visible(app):
            return False

        if self.type_picker_mode:
            return self._handle_type_picker_keydown(event, app)

        if not self.edit_mode:
            return False

        if event.key == pygame.K_ESCAPE:
            self.close_edit_mode()
            return True

        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            target = self.get_inspection_target(app)
            if target is not None:
                self._try_save(target)
            return True

        if event.key == pygame.K_BACKSPACE and self.active_field:
            value = self.draft.get(self.active_field, "")
            self.draft[self.active_field] = value[:-1]
            self.error_message = None
            return True

        if event.key == pygame.K_TAB:
            fields = [key for _, key in self._get_fields(self.get_inspection_target(app))]
            if not fields:
                return True
            if self.active_field not in fields:
                self.active_field = fields[0]
            else:
                idx = fields.index(self.active_field)
                self.active_field = fields[(idx + 1) % len(fields)]
            return True

        return True

    def _handle_type_picker_keydown(self, event: pygame.event.Event, app) -> bool:
        if event.key == pygame.K_ESCAPE:
            self.close_type_picker()
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            target = self.get_inspection_target(app)
            if target is not None:
                self._apply_type_change(app, target)
            return True
        key_index = {
            pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2,
            pygame.K_4: 3, pygame.K_5: 4,
        }
        options = self._get_active_type_options()
        if event.key in key_index and key_index[event.key] < len(options):
            self.picked_type = options[key_index[event.key]][1]
            return True
        return True

    def handle_textinput(self, text: str, app) -> bool:
        if not self.edit_mode or not self.is_visible(app) or not self.active_field:
            return False

        for ch in text:
            if not (ch.isdigit() or ch in ".-"):
                continue
            current = self.draft.get(self.active_field, "")
            if ch == "-" and current:
                continue
            if ch == "." and "." in current:
                continue
            self.draft[self.active_field] = current + ch
        self.error_message = None
        return True

    def handle_mouse_down(self, mx: int, my: int, app) -> bool:
        if not self.is_visible(app) or self.panel_rect is None:
            return False

        if self.pin_btn_rect and self.pin_btn_rect.collidepoint(mx, my):
            self.toggle_pin()
            return True

        target = self.get_inspection_target(app)

        if self.type_picker_mode:
            for type_name, rect in self.type_option_rects.items():
                if rect.collidepoint(mx, my):
                    self.picked_type = type_name
                    return True
            if self.save_btn_rect and self.save_btn_rect.collidepoint(mx, my):
                self._apply_type_change(app, target)
                return True
            if self.cancel_btn_rect and self.cancel_btn_rect.collidepoint(mx, my):
                self.close_type_picker()
                return True
            if self.panel_rect.collidepoint(mx, my):
                if not self.pinned and self.title_rect and self.title_rect.collidepoint(mx, my):
                    self.is_dragging = True
                    self.drag_offset = (mx - self.screen_x, my - self.screen_y)
                return True
            return False

        if self.edit_mode:
            if self.save_btn_rect and self.save_btn_rect.collidepoint(mx, my):
                self._try_save(target)
                return True
            if self.cancel_btn_rect and self.cancel_btn_rect.collidepoint(mx, my):
                self.close_edit_mode()
                return True
            for key, rect in self.field_rects.items():
                if rect.collidepoint(mx, my):
                    self.active_field = key
                    self.error_message = None
                    return True
            if self.panel_rect.collidepoint(mx, my):
                if not self.pinned and self.title_rect and self.title_rect.collidepoint(mx, my):
                    self.is_dragging = True
                    self.drag_offset = (mx - self.screen_x, my - self.screen_y)
                return True
            return False

        if self.edit_btn_rect and self.edit_btn_rect.collidepoint(mx, my):
            self.open_edit_mode(target)
            return True

        if isinstance(target, Spring):
            if self.collision_btn_rect and self.collision_btn_rect.collidepoint(mx, my):
                target.collision_enabled = not target.collision_enabled
                return True
            if self.flip_btn_rect and self.flip_btn_rect.collidepoint(mx, my):
                if target.__class__.__name__ == "AeroBeam":
                    target.normal_flip *= -1
                return True

        if self.change_btn_rect and self.change_btn_rect.collidepoint(mx, my):
            self.open_type_picker(target)
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

    def _try_save(self, target: Union[Object, Spring]):
        try:
            values = {key: float(self.draft[key]) for _, key in self._get_fields(target)}
        except (ValueError, KeyError):
            self.error_message = "Некорректные числа"
            return

        if isinstance(target, Object):
            target.radius = values["radius"]
            target.density = values["density"]
            target.restitution = values["restitution"]
            target.friction = values["friction"]
            if isinstance(target, MotorWheel):
                target.power = values["power"]
                target.max_speed = values["max_speed"]
            volume = (4.0 / 3.0) * math.pi * (target.radius ** 3)
            target.mass = target.density * volume
            if isinstance(target, StructuralNode):
                target.I = float("inf")
                target.angular_velocity = 0.0
            else:
                target.I = 0.4 * target.mass * (target.radius ** 2)
            target.surface = None
        elif isinstance(target, Spring):
            target.k = values["k"]
            target.d = values["d"]
            target.yield_limit = values["yield_limit"]
            target.break_limit = values["break_limit"]
            target.rest_length = values["rest_length"]
            target.collision_radius = values["collision_radius"]
            type_name = target.__class__.__name__
            if type_name == "Hydraulic":
                target.speed = values["speed"]
                target.min_length = values["min_length"]
                target.max_length = values["max_length"]
            elif type_name == "AeroBeam":
                target.chord = values["chord"]
                target.lift_coef = values["lift_coef"]
                target.base_drag = values["base_drag"]
                target.induced_drag = values["induced_drag"]

        self.close_edit_mode()

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
    def _get_header_label(target: Union[Object, Spring], pinned: bool,
                          editing: bool, type_picking: bool) -> str:
        if type_picking:
            kind = "узла" if isinstance(target, Object) else "балки"
            return f"Тип {kind}"
        kind = "узла" if isinstance(target, Object) else "балки"
        if editing:
            return f"Редактирование {kind}"
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

        label = self._get_header_label(target, self.pinned, self.edit_mode, self.type_picker_mode)
        if self.type_picker_mode:
            label_color = (255, 200, 120)
        elif self.edit_mode:
            label_color = (255, 200, 120)
        else:
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

    def _draw_button(self, screen, rect: pygame.Rect, text: str, color: tuple):
        pygame.draw.rect(screen, color, rect, border_radius=5)
        label = self.font.render(text, True, (255, 255, 255))
        screen.blit(label, (rect.centerx - label.get_width() // 2,
                            rect.centery - label.get_height() // 2))

    def _measure_content(self, target: Union[Object, Spring]) -> tuple[int, int]:
        if self.type_picker_mode:
            options = self._get_active_type_options()
            option_width = max(self.font.size(label)[0] for label, _ in options)
            content_width = option_width + self.padding * 2 + 24
            row_h = self.field_height + 4
            content_height = self.padding * 2 + len(options) * row_h + self.btn_height + 14
            return content_width, content_height

        if self.edit_mode:
            fields = self._get_fields(target)
            label_width = max(self.font.size(label)[0] for label, _ in fields)
            input_width = 110
            row_width = label_width + 8 + input_width
            rows = len(fields) + (1 if self.error_message else 0)
            content_height = (
                self.padding * 2
                + rows * (self.field_height + 4)
                + self.btn_height + 10
            )
            return row_width + self.padding * 2, content_height

        lines = self._build_view_lines(target)
        rendered = [self.font.render(line, True, (240, 240, 240)) for line in lines]
        max_width = max(surf.get_width() for surf in rendered)
        total_height = sum(surf.get_height() for surf in rendered) + (len(lines) - 1) * 2
        content_height = total_height + self.padding * 2 + self.btn_height + 10
        content_height += self.btn_height + 5
        if isinstance(target, Spring):
            content_height += self.btn_height + 5
            if target.__class__.__name__ == "AeroBeam":
                content_height += self.btn_height + 5
        return max_width + self.padding * 2, content_height

    def _build_view_lines(self, target: Union[Object, Spring]) -> list[str]:
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
                f"Вращение:         {target.angular_velocity:.2f} рад/с",
            ])
            if isinstance(target, MotorWheel):
                lines.append(f"Мотор:           {'Вкл' if target.direction != 0 else 'Выкл'}")
                lines.append(f"Мощность:        {target.power:.2f}")
                lines.append(f"Макс. скорость:  {target.max_speed:.2f} рад/с")
            if isinstance(target, StructuralNode):
                lines.append("Инерция:         бесконечная")
        elif isinstance(target, Spring):
            strain_pct = (target.current_strain / target.yield_limit) * 100 if target.yield_limit else 0
            type_name = target.__class__.__name__
            lines.extend([
                f"--- {type_name} ---",
                f"Жесткость: {target.k:.0f}",
                f"Демпфер:   {target.d:.0f}",
                f"Натяжение: {target.current_strain:.2f} м",
                f"Нагрузка:  {abs(strain_pct):.1f}%",
                f"Текучесть: {target.yield_limit:.2f}",
                f"Разрыв:    {target.break_limit:.2f}",
                f"Коллизия:  {'Вкл' if target.collision_enabled else 'Выкл'}",
                f"Рад. колл: {target.collision_radius:.2f} м",
            ])
            if type_name == "Hydraulic":
                lines.extend([
                    f"Скорость:  {target.speed:.2f} м/с",
                    f"Ход:       {target.min_length:.2f} — {target.max_length:.2f} м",
                ])
            elif type_name == "AeroBeam":
                flip = getattr(target, "normal_flip", 1)
                lines.extend([
                    f"Хорда:     {target.chord:.2f} м",
                    f"Подъём Cl: {target.lift_coef:.2f}",
                    f"Сопр. баз: {target.base_drag:.3f}",
                    f"Сопр. инд:{target.induced_drag:.2f}",
                    f"Нормаль:   {'вверх' if flip > 0 else 'вниз'}",
                ])
        return lines

    def _draw_edit_form(self, screen, hud_x: int, hud_y: int, bg_width: int,
                        target: Union[Object, Spring]) -> int:
        self.field_rects = {}
        self.save_btn_rect = None
        self.cancel_btn_rect = None

        fields = self._get_fields(target)
        label_width = max(self.font.size(label)[0] for label, _ in fields)
        input_x = hud_x + self.padding + label_width + 8
        input_width = bg_width - (input_x - hud_x) - self.padding

        curr_y = hud_y + self.header_height + self.padding
        for label_text, key in fields:
            label_surf = self.font.render(label_text, True, (200, 200, 210))
            screen.blit(label_surf, (hud_x + self.padding, curr_y + 3))

            field_rect = pygame.Rect(input_x, curr_y, input_width, self.field_height)
            is_active = self.active_field == key
            bg = (45, 50, 70) if is_active else (35, 38, 50)
            border = (255, 215, 80) if is_active else (90, 100, 130)
            pygame.draw.rect(screen, bg, field_rect, border_radius=4)
            pygame.draw.rect(screen, border, field_rect, width=1, border_radius=4)

            value = self.draft.get(key, "")
            value_surf = self.font.render(value, True, (240, 240, 240))
            screen.blit(value_surf, (field_rect.x + 6, field_rect.centery - value_surf.get_height() // 2))
            self.field_rects[key] = field_rect
            curr_y += self.field_height + 4

        if self.error_message:
            err_surf = self.font.render(self.error_message, True, (255, 100, 100))
            screen.blit(err_surf, (hud_x + self.padding, curr_y + 2))
            curr_y += self.field_height

        curr_y += 6
        btn_gap = 8
        btn_width = (bg_width - self.padding * 2 - btn_gap) // 2
        self.save_btn_rect = pygame.Rect(hud_x + self.padding, curr_y, btn_width, self.btn_height)
        self.cancel_btn_rect = pygame.Rect(
            hud_x + self.padding + btn_width + btn_gap, curr_y, btn_width, self.btn_height
        )
        self._draw_button(screen, self.save_btn_rect, "Сохранить", (60, 140, 80))
        self._draw_button(screen, self.cancel_btn_rect, "Отмена", (140, 70, 70))
        return curr_y + self.btn_height

    def _draw_type_picker(self, screen, hud_x: int, hud_y: int, bg_width: int,
                          target: Union[Object, Spring]) -> int:
        self.type_option_rects = {}
        self.save_btn_rect = None
        self.cancel_btn_rect = None

        curr_y = hud_y + self.header_height + self.padding
        row_h = self.field_height + 4
        current_type = target.__class__.__name__

        for label_text, type_name in self._get_active_type_options():
            row_rect = pygame.Rect(hud_x + self.padding, curr_y, bg_width - self.padding * 2, self.field_height)
            is_selected = self.picked_type == type_name
            is_current = current_type == type_name

            bg = (55, 75, 110) if is_selected else (35, 38, 50)
            border = (255, 215, 80) if is_selected else (70, 80, 100)
            pygame.draw.rect(screen, bg, row_rect, border_radius=4)
            pygame.draw.rect(screen, border, row_rect, width=1, border_radius=4)

            marker = "● " if is_selected else "○ "
            suffix = " (текущий)" if is_current else ""
            text_surf = self.font.render(marker + label_text + suffix, True, (235, 235, 245))
            screen.blit(text_surf, (row_rect.x + 6, row_rect.centery - text_surf.get_height() // 2))
            self.type_option_rects[type_name] = row_rect
            curr_y += row_h

        curr_y += 6
        btn_gap = 8
        btn_width = (bg_width - self.padding * 2 - btn_gap) // 2
        self.save_btn_rect = pygame.Rect(hud_x + self.padding, curr_y, btn_width, self.btn_height)
        self.cancel_btn_rect = pygame.Rect(
            hud_x + self.padding + btn_width + btn_gap, curr_y, btn_width, self.btn_height
        )
        self._draw_button(screen, self.save_btn_rect, "Применить", (60, 140, 80))
        self._draw_button(screen, self.cancel_btn_rect, "Отмена", (140, 70, 70))
        return curr_y + self.btn_height

    def _draw_view_content(self, screen, hud_x: int, hud_y: int, bg_width: int,
                           target: Union[Object, Spring]) -> int:
        self.edit_btn_rect = None
        self.change_btn_rect = None
        self.flip_btn_rect = None
        self.collision_btn_rect = None

        lines = self._build_view_lines(target)
        rendered_lines = [self.font.render(line, True, (240, 240, 240)) for line in lines]

        curr_y = hud_y + self.header_height + self.padding
        for surf in rendered_lines:
            screen.blit(surf, (hud_x + self.padding, curr_y))
            curr_y += surf.get_height() + 2

        curr_y += 5
        btn_rect = pygame.Rect(hud_x + self.padding, curr_y, bg_width - self.padding * 2, self.btn_height)
        self._draw_button(screen, btn_rect, "Редактировать", (80, 120, 180))
        self.edit_btn_rect = btn_rect
        curr_y += self.btn_height + 5

        btn_rect = pygame.Rect(hud_x + self.padding, curr_y, bg_width - self.padding * 2, self.btn_height)
        self._draw_button(screen, btn_rect, "Изменить тип", (70, 100, 200))
        self.change_btn_rect = btn_rect
        curr_y += self.btn_height + 5

        if isinstance(target, Spring):
            collision_label = "Коллизия: выкл" if not target.collision_enabled else "Коллизия: вкл"
            collision_color = (90, 90, 100) if not target.collision_enabled else (60, 160, 90)
            collision_rect = pygame.Rect(hud_x + self.padding, curr_y, bg_width - self.padding * 2, self.btn_height)
            self._draw_button(screen, collision_rect, collision_label, collision_color)
            self.collision_btn_rect = collision_rect
            curr_y += self.btn_height + 5

        if isinstance(target, Spring) and target.__class__.__name__ == "AeroBeam":
            flip_rect = pygame.Rect(hud_x + self.padding, curr_y, bg_width - self.padding * 2, self.btn_height)
            self._draw_button(screen, flip_rect, "Повернуть нормаль", (200, 100, 70))
            self.flip_btn_rect = flip_rect
            curr_y += self.btn_height + 5

        return curr_y

    def draw(self, screen: pygame.Surface, target: Union[Object, Spring], scale: float,
             camera: Camera, screen_width: int, screen_height: int) -> None:
        if self.edit_mode and self._edit_target is not target:
            self.close_edit_mode()
        if self.type_picker_mode and target is not self._type_picker_target:
            self.close_type_picker()

        pin_size = 16
        header_label_surf = self.font.render(
            self._get_header_label(target, self.pinned, self.edit_mode, self.type_picker_mode),
            True, (255, 255, 255),
        )
        min_header_width = header_label_surf.get_width() + self.padding * 2 + pin_size + 8
        content_width, content_height = self._measure_content(target)
        bg_width = max(content_width, min_header_width)
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

        if self.type_picker_mode:
            self._draw_type_picker(screen, hud_x, hud_y, bg_width, target)
        elif self.edit_mode:
            self._draw_edit_form(screen, hud_x, hud_y, bg_width, target)
        else:
            self._draw_view_content(screen, hud_x, hud_y, bg_width, target)

        pygame.draw.rect(screen, self.border_color, self.panel_rect, width=2, border_radius=10)
