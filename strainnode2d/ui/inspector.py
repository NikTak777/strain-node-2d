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
from typing import Union
from strainnode2d.physics.objects import Object, MotorWheel
from strainnode2d.physics.springs import Spring
from strainnode2d.core.camera import Camera


class InspectorHUD:
    def __init__(self):
        self.font = pygame.font.SysFont("Consolas", 14)
        self.bg_color = (25, 25, 30, 210)
        self.border_color = (100, 150, 255, 255)

    def draw(self, screen: pygame.Surface, target: Union[Object, Spring], scale: float,
             camera: Camera, screen_width: int, screen_height: int)-> None:
        """
        Отрисовка информационного окна (HUD) с характеристиками выбранного физического объекта.

        Выполняет расчет экранных координат через камеру, формирует текстовые строки
        на основе типа объекта и отрисовывает подложку с обводкой.

        :param screen: Основная поверхность Pygame для отрисовки интерфейса.
        :param target: Физический объект (узел Object или балка Spring) для инспекции.
        :param scale: Базовый физический масштаб (пикселей на метр).
        :param camera: Экземпляр виртуальной камеры для учета смещения и зума.
        :param screen_width: Текущая ширина окна приложения в пикселях.
        :param screen_height: Текущая высота окна приложения в пикселях.
        :return: None
        """
        lines = []
        anchor_x, anchor_y = 0.0, 0.0  # Физические координаты, куда привяжется окно

        # Если выбрана балка
        if isinstance(target, Object):
            speed = math.sqrt(target.velocity[0] ** 2 + target.velocity[1] ** 2)
            anchor_x, anchor_y = target.get_location()

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

        # Если выбрана балка
        elif isinstance(target, Spring):
            x1, y1 = target.obj1.get_location()
            x2, y2 = target.obj2.get_location()
            # Привязывает окно к центру балки
            anchor_x, anchor_y = (x1 + x2) / 2, (y1 + y2) / 2

            strain_pct = (target.current_strain / target.yield_limit) * 100 if target.yield_limit else 0

            lines.extend([
                "----- Пружина / Балка -----",
                f"Жесткость: {target.k:.0f}",
                f"Демпфер:   {target.d:.0f}",
                f"Натяжение: {target.current_strain:.2f} м",
                f"Нагрузка:  {abs(strain_pct):.1f}%",
                f"Предел:    {target.yield_limit:.2f} м"
            ])

        # Отрисовка интерфейса (общая логика)
        rendered_lines = [self.font.render(line, True, (240, 240, 240)) for line in lines]
        max_width = max(surf.get_width() for surf in rendered_lines)
        total_height = sum(surf.get_height() for surf in rendered_lines) + (len(lines) - 1) * 2

        padding = 12
        bg_width, bg_height = max_width + padding * 2, total_height + padding * 2

        # Перевод физических координат в экранные
        screen_x, screen_y = camera.phys_to_screen(anchor_x, anchor_y, scale)

        margin_px = 20  # Внешний отступ от желтой обводки (в пикселях)
        eff_scale = scale * camera.zoom  # Эффективный масштаб для учета зума

        if isinstance(target, Object):
            offset_x = int(target.radius * eff_scale) + margin_px
        else:
            offset_x = 25

        hud_x, hud_y = screen_x + offset_x, screen_y - bg_height // 2

        # Защита от выхода за экран
        if hud_x + bg_width > screen_width:
            hud_x = screen_x - offset_x - bg_width
        if hud_y < 10:
            hud_y = 10
        elif hud_y + bg_height > screen_height - 10:
            hud_y = screen_height - bg_height - 10

        # Фон и обводка
        bg_surf = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, self.bg_color, bg_surf.get_rect(), border_radius=10)
        pygame.draw.rect(bg_surf, self.border_color, bg_surf.get_rect(), width=2, border_radius=10)
        screen.blit(bg_surf, (hud_x, hud_y))

        # Текст
        curr_y = hud_y + padding
        for surf in rendered_lines:
            screen.blit(surf, (hud_x + padding, curr_y))
            curr_y += surf.get_height() + 2