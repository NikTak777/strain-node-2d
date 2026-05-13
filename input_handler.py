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
import random
import math
import tkinter as tk
from tkinter import filedialog
from physics.objects import Object, MotorWheel
from physics.springs import Spring, Rope, Hydraulic
from physics.serializer import save_scene, load_scene
from ui.dialogs import show_spawn_dialog, show_edit_dialog


class InputHandler:
    def __init__(self, app):
        """
        Класс для обработки всего пользовательского ввода.
        :param app: Ссылка на главный объект SimulationApp
        """
        self.app = app

    def handle_events(self, dt: float):
        app = self.app

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app.running = False

            # Обработка изменения размера окна
            elif event.type == pygame.VIDEORESIZE:
                app.width, app.height = event.w, event.h
                app.screen = pygame.display.set_mode((app.width, app.height), pygame.RESIZABLE)
                phys_width = app.width / app.scale
                phys_height = app.height / app.scale
                # Обновляем границы физического мира
                app.sim.Area.borders = [[max(phys_width, 0), max(phys_height, 0)],
                                        [min(phys_width, 0), min(phys_height, 0)]]

            # --- НАЖАТИЯ МЫШИ ---
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                phys_mx = mx / app.scale
                phys_my = (app.height - my) / app.scale

                if event.button == 1:  # ЛКМ
                    clicked_obj = None
                    for obj in app.sim.objects:
                        ox, oy = obj.get_location()
                        dist = math.sqrt((ox - phys_mx) ** 2 + (oy - phys_my) ** 2)
                        if dist <= obj.radius:
                            clicked_obj = obj
                            app.dragged_obj = obj
                            app.drag_offset = [ox - phys_mx, oy - phys_my]
                            break

                    if clicked_obj is None:
                        click_radius = 0.3
                        for spring in app.sim.springs:
                            x1, y1 = spring.obj1.get_location()
                            x2, y2 = spring.obj2.get_location()
                            l2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
                            if l2 == 0: continue
                            t = max(0, min(1, ((phys_mx - x1) * (x2 - x1) + (phys_my - y1) * (y2 - y1)) / l2))
                            proj_x = x1 + t * (x2 - x1)
                            proj_y = y1 + t * (y2 - y1)
                            dist_to_spring = math.sqrt((phys_mx - proj_x) ** 2 + (phys_my - proj_y) ** 2)
                            if dist_to_spring <= click_radius:
                                clicked_obj = spring
                                break

                    if clicked_obj is not None:
                        if isinstance(app.selected_obj, Object) and isinstance(clicked_obj,
                                                                               Object) and app.selected_obj != clicked_obj:
                            new_spring = Spring(app.selected_obj, clicked_obj, k=20000.0, d=160.0)
                            app.sim.add_spring(new_spring)
                            app.selected_obj = None
                        else:
                            if app.selected_obj == clicked_obj:
                                app.selected_obj = None
                            else:
                                app.selected_obj = clicked_obj
                    else:
                        if app.selected_obj is not None:
                            app.selected_obj = None
                        else:
                            rand_radius = random.uniform(0.15, 1.0)
                            rand_velocity = [random.uniform(-10, 10), random.uniform(-10, 10)]
                            rand_density = random.uniform(200, 20000)
                            rand_color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
                            new_obj = Object(x=phys_mx, y=phys_my, radius=rand_radius, velocity=rand_velocity,
                                             density=rand_density, color=rand_color)
                            app.sim.add_object(new_obj)

                elif event.button == 2:  # СКМ
                    clicked_obj = None
                    for obj in app.sim.objects:
                        ox, oy = obj.get_location()
                        dist = math.sqrt((ox - phys_mx) ** 2 + (oy - phys_my) ** 2)
                        if dist <= obj.radius:
                            clicked_obj = obj
                            break
                    if clicked_obj is not None:
                        clicked_obj.is_static = not clicked_obj.is_static
                        if clicked_obj.is_static:
                            clicked_obj.velocity = [0.0, 0.0]
                            clicked_obj.angular_velocity = 0.0

                elif event.button == 3:  # ПКМ
                    app.selected_obj = None
                    data = show_spawn_dialog()
                    if data is not None:
                        target_class = MotorWheel if data["type"] == "Моторное колесо" else Object
                        custom_obj = target_class(x=phys_mx, y=phys_my, radius=data["radius"],
                                                  velocity=[data["vx"], data["vy"]], density=data["density"],
                                                  restitution=data["restitution"], friction=data["friction"],
                                                  color=(200, 200, 200))
                        custom_obj.angular_velocity = data["spin"]
                        if isinstance(custom_obj, MotorWheel):
                            custom_obj.power = data["power"]
                        app.sim.add_object(custom_obj)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    if app.dragged_obj and app.dragged_obj.is_static:
                        app.dragged_obj.velocity = [0.0, 0.0]
                        app.dragged_obj.angular_velocity = 0.0
                    app.dragged_obj = None

            # --- НАЖАТИЯ КЛАВИАТУРЫ ---
            elif event.type == pygame.KEYDOWN:

                # Управление временем (НОВОЕ)
                if event.key == pygame.K_SPACE:
                    app.is_paused = not app.is_paused
                elif event.key == pygame.K_UP:
                    # Ускоряем, но не больше 1.0 (начальная скорость)
                    app.time_scale = min(1.0, app.time_scale + 0.1)
                elif event.key == pygame.K_DOWN:
                    # Замедляем, но не меньше 0.1
                    app.time_scale = max(0.1, app.time_scale - 0.1)

                # Управление моторами
                elif event.key == pygame.K_a:
                    for obj in app.sim.objects:
                        if isinstance(obj, MotorWheel): obj.direction = 1
                elif event.key == pygame.K_d:
                    for obj in app.sim.objects:
                        if isinstance(obj, MotorWheel): obj.direction = -1

                # Управление гидравликой
                elif event.key == pygame.K_w:
                    for spring in app.sim.springs:
                        if isinstance(spring, Hydraulic): spring.activation = 1
                elif event.key == pygame.K_s:
                    for spring in app.sim.springs:
                        if isinstance(spring, Hydraulic): spring.activation = -1

                # Смена типов балок
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    if isinstance(app.selected_obj, Spring):
                        obj1, obj2 = app.selected_obj.obj1, app.selected_obj.obj2
                        if app.selected_obj in app.sim.springs:
                            app.sim.springs.remove(app.selected_obj)

                        new_link = None
                        if event.key == pygame.K_1:
                            new_link = Spring(obj1, obj2, k=20000.0, d=160.0)
                        elif event.key == pygame.K_2:
                            new_link = Rope(obj1, obj2, k=150000.0, d=500.0)
                        elif event.key == pygame.K_3:
                            new_link = Hydraulic(obj1, obj2, speed=2.0, min_length=0.5, max_length=10.0)

                        if new_link:
                            app.sim.add_spring(new_link)
                            app.selected_obj = new_link

                # Сохранение / Загрузка
                elif event.key == pygame.K_F5:
                    root = tk.Tk()
                    root.withdraw()
                    filepath = filedialog.asksaveasfilename(defaultextension=".json",
                                                            filetypes=[("JSON Files", "*.json")])
                    root.destroy()
                    if filepath: save_scene(app.sim, filepath)

                elif event.key == pygame.K_F9:
                    root = tk.Tk()
                    root.withdraw()
                    filepath = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
                    root.destroy()
                    if filepath:
                        app.selected_obj = None
                        app.dragged_obj = None
                        load_scene(app.sim, filepath)

                # Редактирование (E)
                elif event.key == pygame.K_e:
                    if app.selected_obj is not None:
                        new_data = show_edit_dialog(app.selected_obj)
                        if new_data:
                            if isinstance(app.selected_obj, Object):
                                app.selected_obj.radius = new_data["radius"]
                                app.selected_obj.density = new_data["density"]
                                app.selected_obj.restitution = new_data["restitution"]
                                app.selected_obj.friction = new_data["friction"]
                                if "power" in new_data: app.selected_obj.power = new_data["power"]
                                volume = (4.0 / 3.0) * math.pi * (app.selected_obj.radius ** 3)
                                app.selected_obj.mass = app.selected_obj.density * volume
                                app.selected_obj.I = 0.4 * app.selected_obj.mass * (app.selected_obj.radius ** 2)
                                app.selected_obj.surface = None
                            elif isinstance(app.selected_obj, Spring):
                                app.selected_obj.k = new_data["k"]
                                app.selected_obj.d = new_data["d"]
                                app.selected_obj.yield_limit = new_data["yield_limit"]
                                app.selected_obj.rest_length = new_data["rest_length"]

                elif event.key == pygame.K_DELETE:
                    if app.selected_obj is not None:
                        if isinstance(app.selected_obj, Spring):
                            if app.selected_obj in app.sim.springs:
                                app.sim.springs.remove(app.selected_obj)
                        elif isinstance(app.selected_obj, Object):
                            app.sim.springs = [
                                s for s in app.sim.springs
                                if s.obj1 != app.selected_obj and s.obj2 != app.selected_obj
                            ]
                            if app.selected_obj in app.sim.objects:
                                app.sim.objects.remove(app.selected_obj)
                        app.selected_obj = None

                mods = pygame.key.get_mods()
                is_ctrl = bool(mods & pygame.KMOD_CTRL)

                # --- КОПИРОВАНИЕ (Ctrl + C) ---
                if event.key == pygame.K_c and is_ctrl:
                    if isinstance(app.selected_obj, Object):
                        app.clipboard = {
                            "class": app.selected_obj.__class__,
                            "radius": app.selected_obj.radius,
                            "density": app.selected_obj.density,
                            "restitution": app.selected_obj.restitution,
                            "friction": app.selected_obj.friction,
                            "color": app.selected_obj.color,
                            "is_static": getattr(app.selected_obj, 'is_static', False)
                        }
                        if isinstance(app.selected_obj, MotorWheel):
                            app.clipboard["power"] = app.selected_obj.power

                        print(f"Скопирован объект: {app.clipboard['class'].__name__}")

                # --- ВСТАВКА (Ctrl + V) ---
                elif event.key == pygame.K_v and is_ctrl:
                    if app.clipboard is not None:
                        mx, my = pygame.mouse.get_pos()
                        phys_mx = mx / app.scale
                        phys_my = (app.height - my) / app.scale

                        target_class = app.clipboard["class"]
                        new_obj = target_class(
                            x=phys_mx,
                            y=phys_my,
                            radius=app.clipboard["radius"],
                            velocity=[0.0, 0.0],
                            density=app.clipboard["density"],
                            restitution=app.clipboard["restitution"],
                            friction=app.clipboard["friction"],
                            color=app.clipboard["color"]
                        )
                        new_obj.is_static = app.clipboard["is_static"]
                        if issubclass(target_class, MotorWheel):
                            new_obj.power = app.clipboard["power"]

                        app.sim.add_object(new_obj)
                        app.selected_obj = new_obj

            # Отпускание клавиш (остановка моторов и гидравлики)
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_a, pygame.K_d):
                    for obj in app.sim.objects:
                        if isinstance(obj, MotorWheel): obj.direction = 0
                if event.key in (pygame.K_w, pygame.K_s):
                    for spring in app.sim.springs:
                        if isinstance(spring, Hydraulic): spring.activation = 0