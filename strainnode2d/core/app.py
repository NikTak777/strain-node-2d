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
import os
import time
import threading
from pypresence import Presence
from strainnode2d.physics.area import Area
from strainnode2d.physics.objects import Object, MotorWheel
from strainnode2d.physics.simulation import PhysicSimulation
from strainnode2d.ui.inspector import InspectorHUD
from strainnode2d.core.input_handler import InputHandler
from strainnode2d.core.camera import Camera
from strainnode2d.physics.serializer import snapshot_scene, restore_scene, load_scene

FPS = 1000
WORLD_WIDTH, WORLD_HEIGHT = 500.0, 80.0
SCALE = 10.0
WIDTH, HEIGHT = 1920, 1080
SELECTION_COLOR = (255, 215, 0)
SELECTION_ANCHOR_COLOR = (255, 130, 40)


class SimulationApp:
    def __init__(self, fps: int = 120, width: int = WIDTH, height: int = HEIGHT, scale: float = SCALE,
                 world_width: float = WORLD_WIDTH, world_height: float = WORLD_HEIGHT):
        """
        Инициализация главного приложения симулятора.

        :param fps: Целевая частота кадров в секунду (Frames Per Second).
        :param width: Ширина окна приложения в пикселях.
        :param height: Высота окна приложения в пикселях.
        :param scale: Масштаб отображения (пикселей на физический метр). Влияет только на рендер.
        :param world_width: Ширина физического мира в метрах.
        :param world_height: Высота физического мира в метрах.
        """
        pygame.init()
        pygame.font.init()
        self.fps = fps
        self.width = width
        self.height = height
        self.scale = scale
        self.world_width = world_width
        self.world_height = world_height

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("StrainNode2D")

        self.clock = pygame.time.Clock()
        self.running = True
        self.dragged_obj = None
        self.drag_offset = [0.0, 0.0]
        self.clipboard = None  # Буфер обмена
        self.last_scene = None
        self.quick_save_snapshot = None

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
        self.debug_mode = 0  # 0 — выкл, 1 — нормали AeroBeam, 2 — сопротивление

        self.font = pygame.font.SysFont("Consolas", 18)
        self.hud_font = pygame.font.SysFont("Consolas", 14)

        self.area = Area(world_width, world_height, 0, 0)
        self.sim = PhysicSimulation(self.area)
        self.inspector = InspectorHUD()
        self.input_handler = InputHandler(self)

        self.camera = Camera(self.width, self.height)
        self.camera.x = world_width / 2
        self.camera.y = world_height / 2
        self.fit_camera_to_world()

        # Инициализация Discord RPC
        self.client_id = 1504956012195479572
        self.rpc = None
        self.last_rpc_update = 0
        self.session_start_time = int(time.time())

        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            print("Discord RPC подключен успешно!")
        except Exception as e:
            self.rpc = None
            print(f"Discord не запущен или ошибка подключения: {e}")

    def fit_camera_to_world(self):
        """Настраивает зум камеры, чтобы весь мир был виден в текущем окне."""
        if self.world_width <= 0 or self.world_height <= 0 or self.scale <= 0:
            return
        zoom_x = self.width / (self.world_width * self.scale)
        zoom_y = self.height / (self.world_height * self.scale)
        self.camera.zoom = min(zoom_x, zoom_y) * 0.95

    def focus_on_loaded_scene(self):
        """Плавно перемещает камеру к центру загруженной сцены."""
        objects = self.sim.objects
        if not objects:
            return
        inv_n = 1.0 / len(objects)
        cx = sum(obj.location[0] for obj in objects) * inv_n
        cy = sum(obj.location[1] for obj in objects) * inv_n
        self.camera.pan_to(cx, cy)

    def _clear_scene_editor_state(self):
        self.dragged_obj = None
        self.selected_nodes.clear()
        self.selected_springs.clear()
        self.camera.clear_follow()

    def reload_last_scene(self):
        """Перезагружает последнюю сцену, открытую через F9."""
        if not self.last_scene:
            print("Нет сцены для перезагрузки — сначала загрузите файл через F9")
            return
        self._clear_scene_editor_state()
        load_scene(self.sim, self.last_scene)
        self.focus_on_loaded_scene()
        print(f"Сцена перезагружена: {self.last_scene}")

    def save_quick_checkpoint(self):
        """Быстрая точка в памяти (позиции, скорости, состояние конструкции)."""
        self.quick_save_snapshot = snapshot_scene(self.sim)
        print("Быстрая точка сохранена (Home — восстановить)")

    def restore_quick_checkpoint(self):
        """Восстанавливает последнюю быструю точку (Insert)."""
        if self.quick_save_snapshot is None:
            print("Нет быстрой точки — нажмите Insert перед восстановлением")
            return
        self._clear_scene_editor_state()
        restore_scene(self.sim, self.quick_save_snapshot)
        print("Быстрая точка восстановлена")

    def _draw_aero_debug(self):
        """Отрисовка отладочных данных по аэродинамике."""
        debug_mode = getattr(self, 'debug_mode', 0)
        if debug_mode == 0:
            return

        show_normals = debug_mode == 1
        show_drag = debug_mode == 2

        for spring in self.sim.springs:
            if spring.__class__.__name__ != "AeroBeam":
                continue

            x1, y1 = spring.obj1.get_location()
            x2, y2 = spring.obj2.get_location()
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            L = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if L == 0:
                continue

            nx = (-(y2 - y1) / L) * spring.normal_flip
            ny = ((x2 - x1) / L) * spring.normal_flip
            sc_cx, sc_cy = self.camera.phys_to_screen(cx, cy, self.scale)

            if show_normals:
                arrow_len = 1.5
                end_x, end_y = cx + nx * arrow_len, cy + ny * arrow_len
                sc_ex, sc_ey = self.camera.phys_to_screen(end_x, end_y, self.scale)
                pygame.draw.line(self.screen, (255, 255, 0), (sc_cx, sc_cy), (sc_ex, sc_ey), 2)
                pygame.draw.circle(self.screen, (255, 50, 50), (int(sc_ex), int(sc_ey)), 4)

            if show_drag:
                drag = getattr(spring, 'current_drag', 0.0)
                if drag < 0.5:
                    continue

                stripe_len = min(5.0, math.sqrt(drag) * 0.07)
                sin_alpha = abs(getattr(spring, 'current_sin_alpha', 0.0))
                stripe_len *= max(0.15, sin_alpha)

                back_x = cx - nx * stripe_len
                back_y = cy - ny * stripe_len
                sc_bx, sc_by = self.camera.phys_to_screen(back_x, back_y, self.scale)

                intensity = min(1.0, drag / 800.0)
                color = (
                    int(40 + 60 * intensity),
                    int(120 + 100 * intensity),
                    int(220 + 35 * intensity),
                )
                thickness = max(3, min(12, int(3 + stripe_len * self.scale * self.camera.zoom * 0.15)))

                pygame.draw.line(self.screen, color, (sc_cx, sc_cy), (sc_bx, sc_by), thickness)

                tx, ty = -(sc_by - sc_cy), (sc_bx - sc_cx)
                t_len = math.sqrt(tx * tx + ty * ty)
                if t_len > 0:
                    tx, ty = tx / t_len, ty / t_len
                    wing = max(4, int(spring.chord * self.scale * self.camera.zoom * sin_alpha * 0.25))
                    tip_x, tip_y = sc_bx, sc_by
                    p1 = (int(tip_x + tx * wing), int(tip_y + ty * wing))
                    p2 = (int(tip_x - tx * wing), int(tip_y - ty * wing))
                    pygame.draw.polygon(self.screen, color, [(sc_cx, sc_cy), p1, p2])

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
    def _selection_highlight_color(entity, selected: list) -> tuple[int, int, int]:
        if len(selected) <= 1:
            return SELECTION_COLOR
        if entity is selected[-1]:
            return SELECTION_ANCHOR_COLOR
        return SELECTION_COLOR

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
                for spring in self.sim.springs:
                    if spring.obj1 == self.dragged_obj or spring.obj2 == self.dragged_obj:
                        dx = spring.obj2.location[0] - spring.obj1.location[0]
                        dy = spring.obj2.location[1] - spring.obj1.location[1]
                        spring.rest_length = math.sqrt(dx ** 2 + dy ** 2)
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
        substeps = 10  # Дробится шаг на 25 частей
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
                highlight = self._selection_highlight_color(spring, self.selected_springs)
                pygame.draw.line(self.screen, highlight, start_pos, end_pos, thickness + 4)

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
                obj_screen_radius = max(3, int(obj.radius * eff_scale))
                frozen_radius = max(2, int(obj_screen_radius * 0.55))
                pygame.draw.circle(self.screen, (255, 50, 50), (screen_x, screen_y), frozen_radius)
                pygame.draw.circle(self.screen, (0, 0, 0), (screen_x, screen_y), frozen_radius,
                                   max(1, int(frozen_radius * 0.45)))

            if obj in self.selected_nodes:
                highlight = self._selection_highlight_color(obj, self.selected_nodes)
                pygame.draw.circle(
                    self.screen, highlight, (screen_x, screen_y),
                    int(obj.radius * eff_scale) + 4, 3,
                )

        # Отрисовка рамки выделения
        if self.is_selecting:
            x1, y1 = self.selection_start
            x2, y2 = self.selection_current
            rect = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

            s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            s.fill((50, 150, 255, 40))
            self.screen.blit(s, rect.topleft)
            pygame.draw.rect(self.screen, (100, 200, 255), rect, 1)

        # Расчёт телеметрии по аэродинамике
        total_drag = 0.0
        total_downforce = 0.0
        total_frontal_area = 0.0
        total_ge_force = 0.0

        for spring in self.sim.springs:
            if spring.__class__.__name__ == "AeroBeam":
                total_drag += getattr(spring, 'current_drag', 0.0)
                total_downforce += getattr(spring, 'current_downforce', 0.0)
                total_frontal_area += getattr(spring, 'current_frontal_area', 0.0)
                total_ge_force += getattr(spring, 'current_ge_force', 0.0)

        total_grip_force = total_downforce + total_ge_force
        ld_ratio = total_grip_force / total_drag if total_drag > 0.1 else 0.0

        telemetry = [
            f"Time:    {self.sim.time:.2f}s",
            f"Speed:   {'[PAUSED]' if self.is_paused else f'{self.time_scale:.1f}x'}",
            f"FPS:     {self.clock.get_fps():.0f}",
            f"Zoom:    {self.camera.zoom:.2f}x",
            f"Nodes:   {len(self.sim.objects)}",
            f"Beams:   {len(self.sim.springs)}",
            f"Area:    {total_frontal_area:.2f} m2",
            f"Drag:    {total_drag:.1f} N",
            f"DownFrc: {total_downforce:.1f} N",
            f"GroundE: {total_ge_force:.1f} N",
            f"L/D:     {ld_ratio:.2f}",
            f"Debug:   {['off', 'normals', 'drag'][getattr(self, 'debug_mode', 0)]}",
        ]

        for i, text_line in enumerate(telemetry):
            color = (255, 200, 50) if i == 1 and self.is_paused else (240, 240, 240)
            text_surface = self.font.render(text_line, True, color)
            self.screen.blit(text_surface, (20, 20 + i * 22))

        self._draw_aero_debug()

        if self.inspector.is_visible(self):
            ctx = self.inspector.get_selection_context(self)
            self.inspector.draw(self.screen, ctx, self.scale, self.camera, self.width, self.height)
        else:
            self.inspector.close_edit_mode()
            self.inspector.close_type_picker()

        pygame.display.flip()

    def update_discord_status(self):
        """Обновление активности в Discord (лимит: 1 раз в 15 секунд)."""
        if self.rpc and (time.time() - self.last_rpc_update > 15):
            state_str = "Симуляция на паузе" if getattr(self, 'is_paused', False) else "В движении"
            details_str = f"Nodes: {len(self.sim.objects)} | Beams: {len(self.sim.springs)}"
            session_start_time = getattr(self, 'session_start_time', int(time.time()))

            def send_rpc():
                try:
                    self.rpc.update(
                        state=state_str,
                        details=details_str,
                        large_image="StrainNode2D Logo",
                        large_text="StrainNode2D Engine",
                        start=session_start_time
                    )
                    self.last_rpc_update = time.time()
                except Exception as e:
                    self.rpc = None
                    print(f"Ошибка обновления Discord RPC: {e}")

            # Запускает отправку в параллельном потоке
            threading.Thread(target=send_rpc, daemon=True).start()
            self.last_rpc_update = time.time()

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
            self.update_discord_status()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    app = SimulationApp(
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
        scale=SCALE,
        world_width=WORLD_WIDTH,
        world_height=WORLD_HEIGHT,
    )
    app.run()
