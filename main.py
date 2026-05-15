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
import sys
import math
from physics.area import Area
from physics.objects import Object, MotorWheel
from physics.simulation import PhysicSimulation
from ui.inspector import InspectorHUD
from input_handler import InputHandler
from camera import Camera

FPS = 1000
SCALE = 80.0
WIDTH, HEIGHT = 1200, 800


class SimulationApp:
    def __init__(self, fps: int = 120, width: int = 1200, height: int = 800, scale: float = 20.0):
        """
        Инициализация главного приложения симулятора.

        :param fps: Целевая частота кадров в секунду (Frames Per Second).
        :param width: Ширина окна приложения в пикселях.
        :param height: Высота окна приложения в пикселях.
        :param scale: Масштаб отображения (количество пикселей в одном физическом метре).
        """
        pygame.init()
        pygame.font.init()
        self.fps = fps
        self.width = width
        self.height = height
        self.scale = scale

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("StrainNode2D")

        self.clock = pygame.time.Clock()
        self.running = True
        self.dragged_obj = None
        self.drag_offset = [0.0, 0.0]
        self.clipboard = None  # Буфер обмена

        self.selected_nodes = []  # Список выделенных узлов
        self.selected_springs = []  # Список выделенных балок

        # Переменные для выделения рамкой
        self.is_selecting = False
        self.selection_start = (0, 0)
        self.selection_current = (0, 0)

        self.is_panning = False
        self.pan_start_mouse = (0, 0)
        self.pan_start_camera = (0.0, 0.0)

        self.is_paused = False
        self.time_scale = 1.0  # От 0.1 до 1.0

        self.font = pygame.font.SysFont("Consolas", 18)
        self.hud_font = pygame.font.SysFont("Consolas", 14)

        phys_width = self.width / self.scale
        phys_height = self.height / self.scale
        self.area = Area(0, 0, phys_width, phys_height)
        self.sim = PhysicSimulation(self.area)
        self.inspector = InspectorHUD()
        self.input_handler = InputHandler(self)

        self.camera = Camera(self.width, self.height)
        self.camera.x = phys_width / 2
        self.camera.y = phys_height / 2

    @staticmethod
    def get_ball_surface(obj: Object, scale: float = 20):
        """
        Генерация и кэширование графической текстуры (поверхности) для физического узла.
        Создает радиальный градиент и наносит маркеры для визуализации вращения.

        :param obj: Экземпляр физического объекта (узла), для которого создается текстура.
        :param scale: Масштаб для корректного перевода физического радиуса в пиксели.
        :return: Сгенерированная текстура с поддержкой прозрачности (Alpha-канал).
        :rtype: pygame.surface
        """
        if obj.surface is not None and obj.surface_scale == scale:
            return obj.surface

        draw_radius = max(3, int(obj.radius * scale))
        surf_size = draw_radius * 2
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)

        color = obj.color
        for r_offset in range(draw_radius, 0, -1):
            factor = r_offset / draw_radius
            r_c = max(0, min(255, int(color[0] * (1 - factor * 0.5))))
            g_c = max(0, min(255, int(color[1] * (1 - factor * 0.5))))
            b_c = max(0, min(255, int(color[2] * (1 - factor * 0.5))))
            pygame.draw.circle(surf, (r_c, g_c, b_c), (draw_radius, draw_radius), r_offset)

        # Текстурные точки, чтобы видеть вращение
        dark_spot = (max(0, color[0] - 100), max(0, color[1] - 100), max(0, color[2] - 100))
        pygame.draw.circle(surf, dark_spot, (int(draw_radius * 1.4), int(draw_radius * 1.3)), max(2, draw_radius // 6))
        # Блик света (для эффекта глянца)
        pygame.draw.circle(surf, (255, 255, 255), (int(draw_radius * 0.6), int(draw_radius * 0.6)),
                           max(1, draw_radius // 8))

        obj.surface = surf
        obj.surface_scale = scale
        return surf

    @staticmethod
    def draw_springs(screen, springs, scale, height):
        """
        Отрисовка массива упругих связей (балок) на экране.
        Примечание: В текущей архитектуре логика также дублируется в draw_scene.

        :param screen: Основная поверхность окна Pygame для отрисовки.
        :param springs: Список объектов связей (балок).
        :param scale: Масштаб отображения (пикселей на метр).
        :param height: Высота окна (для инверсии оси Y из физической в экранную).
        """
        for spring in springs:
            if spring.is_broken:
                continue

            p1_x, p1_y = spring.obj1.get_location()
            p2_x, p2_y = spring.obj2.get_location()

            # Перевод в экранные координаты
            start_pos = (int(p1_x * scale), int(height - (p1_y * scale)))
            end_pos = (int(p2_x * scale), int(height - (p2_y * scale)))

            # Цветовая индикация деформации (плавно перетекает из зеленого в красный/синий)
            strain = spring.current_strain
            # Нормализуем деформацию относительно предела пластичности
            factor = min(1.0, abs(strain) / spring.yield_limit)

            if strain > 0:  # Растяжение (Тенденция к красному)
                color = (int(255 * factor), int(255 * (1 - factor)), 0)
            else:  # Сжатие (Тенденция к синему)
                color = (0, int(255 * (1 - factor)), int(255 * factor))

            # Толщина линии зависит от упругости (чем жестче балка, тем она толще визуально)
            thickness = max(1, min(8, int(spring.k / 3000)))

            pygame.draw.line(screen, color, start_pos, end_pos, thickness)

    def update_physics(self, dt: float):
        """
        Обработка перемещения объектов мышью и выполнение шагов физической симуляции.

        :param dt: Базовый шаг времени, прошедший с прошлого кадра (в секундах).
        """
        self.camera.update(dt)

        # Шаг времени умножается на множитель (или обнуляется, если пауза)
        scaled_dt = 0.0 if self.is_paused else dt * self.time_scale

        if scaled_dt == 0.0:
            if self.dragged_obj:
                mx, my = pygame.mouse.get_pos()
                phys_mx, phys_my = self.camera.screen_to_phys(mx, my, self.scale)
                self.dragged_obj.location = [phys_mx + self.drag_offset[0], phys_my + self.drag_offset[1]]
                self.dragged_obj.velocity = [0.0, 0.0]
            return

        for obj in self.sim.objects:
            if isinstance(obj, MotorWheel):
                obj.apply_motor(scaled_dt)

        # Корректируется положение ДО расчета шага физики
        if self.dragged_obj:
            mx, my = pygame.mouse.get_pos()
            phys_mx, phys_my = self.camera.screen_to_phys(mx, my, self.scale)
            target_x = phys_mx + self.drag_offset[0]
            target_y = phys_my + self.drag_offset[1]
            if scaled_dt > 0:
                # Умножается на 15.0 (мягкая привязка)
                self.dragged_obj.velocity[0] = (target_x - self.dragged_obj.location[0]) * 15.0
                self.dragged_obj.velocity[1] = (target_y - self.dragged_obj.location[1]) * 15.0

        # Шаг физической симуляции
        substeps = 10  # Дробится шаг на 10 частей
        sub_dt = scaled_dt / substeps
        for _ in range(substeps):
            for obj in self.sim.objects:
                if isinstance(obj, MotorWheel):
                    obj.apply_motor(sub_dt)
            self.sim.step(sub_dt)

    def draw_scene(self):
        """
        Очистка окна и полная отрисовка всех графических элементов сцены.
        Включает в себя отрисовку связей (с цветовой индикацией нагрузки),
        отрисовку узлов, инспектора свойств (HUD) выделенного объекта и вывод телеметрии.
        """
        self.screen.fill((30, 30, 30))
        eff_scale = self.scale * self.camera.zoom

        borders = self.sim.Area.get_border()
        max_x, max_y = borders[0]
        min_x, min_y = borders[1]

        # Переводим углы физического мира в экранные пиксели (через камеру)
        screen_min_x, screen_min_y = self.camera.phys_to_screen(min_x, max_y, self.scale)
        screen_max_x, screen_max_y = self.camera.phys_to_screen(max_x, min_y, self.scale)

        rect_width = screen_max_x - screen_min_x
        rect_height = screen_max_y - screen_min_y

        border_rect = pygame.Rect(screen_min_x, screen_min_y, rect_width, rect_height)

        # Рисуем темно-зеленую рамку (шириной 3 пикселя)
        pygame.draw.rect(self.screen, (50, 100, 50), border_rect, 3)

        # Отрисовка балок
        for spring in self.sim.springs:
            if spring.is_broken:
                continue

            p1_x, p1_y = spring.obj1.get_location()
            p2_x, p2_y = spring.obj2.get_location()
            start_pos = self.camera.phys_to_screen(p1_x, p1_y, self.scale)
            end_pos = self.camera.phys_to_screen(p2_x, p2_y, self.scale)

            strain = spring.current_strain
            factor = min(1.0, abs(strain) / spring.yield_limit)
            if strain > 0:  # Растяжение (Тенденция к красному)
                color = (int(255 * factor), int(255 * (1 - factor)), 0)
            else:  # Сжатие (Тенденция к синему)
                color = (0, int(255 * (1 - factor)), int(255 * factor))

            thickness = max(1, min(8, int(spring.k / 3000 * self.camera.zoom)))
            pygame.draw.line(self.screen, color, start_pos, end_pos, thickness)

            if spring in self.selected_springs:
                pygame.draw.line(self.screen, (255, 215, 0), start_pos, end_pos, thickness + 4)

        # Отрисовка узлов
        for obj in self.sim.objects:
            x, y = obj.get_location()
            screen_x, screen_y = self.camera.phys_to_screen(x, y, self.scale)

            surf = self.get_ball_surface(obj, scale=eff_scale)

            angle_degrees = math.degrees(obj.angle)
            rotated_surf = pygame.transform.rotate(surf, angle_degrees)
            rect = rotated_surf.get_rect(center=(screen_x, screen_y))
            self.screen.blit(rotated_surf, rect.topleft)

            if obj.is_static:
                frozen_radius = max(2, int(6 * self.camera.zoom))
                pygame.draw.circle(self.screen, (255, 50, 50), (screen_x, screen_y), frozen_radius)
                pygame.draw.circle(self.screen, (0, 0, 0), (screen_x, screen_y), frozen_radius,
                                   max(1, int(2 * self.camera.zoom)))

            if obj in self.selected_nodes:
                pygame.draw.circle(self.screen, (255, 215, 0), (screen_x, screen_y), int(obj.radius * eff_scale) + 4, 3)

        # Отрисовка рамки выделения
        if self.is_selecting:
            x1, y1 = self.selection_start
            x2, y2 = self.selection_current
            rect = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

            s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            s.fill((50, 150, 255, 40))
            self.screen.blit(s, rect.topleft)
            pygame.draw.rect(self.screen, (100, 200, 255), rect, 1)

        telemetry = [
            f"Time:    {self.sim.time:.2f}s",
            f"Speed:   {'[PAUSED]' if self.is_paused else f'{self.time_scale:.1f}x'}",
            f"FPS:     {self.clock.get_fps():.0f}",
            f"Zoom:    {self.camera.zoom:.2f}x",
            f"Nodes:   {len(self.sim.objects)}",
            f"Beams:   {len(self.sim.springs)}"
        ]

        for i, text_line in enumerate(telemetry):
            color = (255, 200, 50) if i == 1 and self.is_paused else (240, 240, 240)
            text_surface = self.font.render(text_line, True, color)
            self.screen.blit(text_surface, (20, 20 + i * 22))

        if len(self.selected_nodes) == 1 and len(self.selected_springs) == 0:
            self.inspector.draw(self.screen, self.selected_nodes[0], self.scale, self.camera, self.width, self.height)
        elif len(self.selected_springs) == 1 and len(self.selected_nodes) == 0:
            self.inspector.draw(self.screen, self.selected_springs[0], self.scale, self.camera, self.width, self.height)

        pygame.display.flip()

    def run(self):
        """
        Запуск основного игрового цикла (Game Loop).
        Управляет генерацией дельты времени (dt), собирает события ввода,
        обновляет физическую модель и инициирует перерисовку сцены.
        """
        while self.running:
            dt = self.clock.tick(self.fps) / 1000.0
            dt = min(dt, 0.1)

            self.input_handler.handle_events(dt)
            self.update_physics(dt)
            self.draw_scene()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    # Запуск приложения
    app = SimulationApp(fps=FPS, width=WIDTH, height=HEIGHT, scale=SCALE)
    app.run()
