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
from strainnode2d.physics.objects import Object, MotorWheel
from strainnode2d.physics.springs import Spring, Rope, Hydraulic, Beam, AeroBeam
from strainnode2d.physics.serializer import save_scene, load_scene
from strainnode2d.ui.dialogs import show_edit_dialog, show_type_dialog


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
                app.camera.width = app.width
                app.camera.height = app.height

            # Колёсико мыши (зум камеры)
            elif event.type == pygame.MOUSEWHEEL:
                zoom_factor = 1.1 if event.y > 0 else 0.9
                app.camera.zoom *= zoom_factor
                # Ограничивает приближение/отдаление (от 10% до 1000%)
                app.camera.zoom = max(0.1, min(app.camera.zoom, 10.0))

            # Обработка событий мыши
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                phys_mx, phys_my = app.camera.screen_to_phys(mx, my, app.scale)

                mods = pygame.key.get_mods()
                is_shift = bool(mods & pygame.KMOD_SHIFT)
                is_ctrl = bool(mods & pygame.KMOD_CTRL)

                if event.button == 1:  # ЛКМ (Выделение или перетаскивание)

                    # Перехват клика по кнопке инспектора
                    if len(app.selected_springs) == 1:
                        target_spring = app.selected_springs[0]

                        # Проверка клика по новой кнопке "Повернуть нормаль"
                        if getattr(app.inspector, 'flip_btn_rect',
                                   None) and app.inspector.flip_btn_rect.collidepoint(mx, my):
                            if target_spring.__class__.__name__ == "AeroBeam":
                                target_spring.normal_flip *= -1
                            continue

                        if getattr(app.inspector, 'change_btn_rect',
                                   None) and app.inspector.change_btn_rect.collidepoint(mx, my):

                            obj1, obj2 = target_spring.obj1, target_spring.obj2

                            # Вызов окна Tkinter
                            new_type = show_type_dialog(target_spring.__class__.__name__)

                            # Если пользователь выбрал другой тип и нажал "Применить"
                            if new_type and new_type != target_spring.__class__.__name__:
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
                                    app.selected_springs = [new_link]  # Инспектор останется открытым

                            continue  # Цикл прерывается, чтобы клик не "провалился" в физический движок

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
                        if isinstance(clicked_obj, Object):
                            # Построение балок
                            if is_ctrl:
                                # Если у нас уже выделен ровно один узел, и мы кликаем по другому
                                if len(app.selected_nodes) == 1 and clicked_obj != app.selected_nodes[0]:
                                    new_spring = Spring(app.selected_nodes[0], clicked_obj, k=20000.0, d=160.0)
                                    app.sim.add_spring(new_spring)
                                    app.selected_nodes = [clicked_obj]
                                    app.selected_springs.clear()
                            # Логика множественного выделения
                            if is_shift:
                                if clicked_obj in app.selected_nodes:
                                    app.selected_nodes.remove(clicked_obj)
                                else:
                                    app.selected_nodes.append(clicked_obj)
                            # Логика одиночного выделения
                            else:
                                if clicked_obj not in app.selected_nodes:
                                    app.selected_nodes = [clicked_obj]
                                    app.selected_springs.clear()

                        elif isinstance(clicked_obj, Spring):
                            if is_shift:
                                if clicked_obj in app.selected_springs:
                                    app.selected_springs.remove(clicked_obj)
                                else:
                                    app.selected_springs.append(clicked_obj)
                                    if clicked_obj.obj1 not in app.selected_nodes: app.selected_nodes.append(
                                        clicked_obj.obj1)
                                    if clicked_obj.obj2 not in app.selected_nodes: app.selected_nodes.append(
                                        clicked_obj.obj2)
                            else:
                                app.selected_springs = [clicked_obj]
                                app.selected_nodes = [clicked_obj.obj1, clicked_obj.obj2]
                    else:
                        if not is_shift and not is_ctrl:
                            app.selected_nodes.clear()
                            app.selected_springs.clear()
                            app.is_panning = True
                            app.pan_start_mouse = pygame.mouse.get_pos()
                            app.pan_start_camera = (app.camera.x, app.camera.y)
                            app.camera.target = None
                        elif is_shift:
                            rand_radius = random.uniform(0.15, 1.0)
                            rand_velocity = [random.uniform(-10, 10), random.uniform(-10, 10)]
                            rand_density = random.uniform(200, 20000)
                            rand_color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
                            new_obj = Object(x=phys_mx, y=phys_my, radius=rand_radius, velocity=rand_velocity,
                                             density=rand_density, color=rand_color)
                            app.sim.add_object(new_obj)

                elif event.button == 2:  # СКМ (Заморозка объекта)
                    for node in app.selected_nodes:
                        node.is_static = not node.is_static
                        if node.is_static:
                            node.velocity = [0.0, 0.0]
                            node.angular_velocity = 0.0


                elif event.button == 3:  # ПКМ (Начало выделения рамкой)
                    app.is_selecting = True
                    app.selection_start = pygame.mouse.get_pos()
                    app.selection_current = pygame.mouse.get_pos()
                    if not is_shift:
                        app.selected_nodes.clear()
                        app.selected_springs.clear()

            elif event.type == pygame.MOUSEMOTION:
                if app.is_selecting:
                    app.selection_current = event.pos

                # Движение камеры
                if getattr(app, 'is_panning', False):
                    mx, my = event.pos
                    smx, smy = app.pan_start_mouse
                    dx = mx - smx
                    dy = my - smy

                    eff_scale = app.scale * app.camera.zoom
                    # Сдвигаются физические координаты камеры пропорционально пикселям мыши
                    app.camera.x = app.pan_start_camera[0] - dx / eff_scale
                    app.camera.y = app.pan_start_camera[1] + dy / eff_scale

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    app.is_panning = False
                    if app.dragged_obj and app.dragged_obj.is_static:
                        app.dragged_obj.velocity = [0.0, 0.0]
                        app.dragged_obj.angular_velocity = 0.0
                    app.dragged_obj = None

                elif event.button == 3:  # ПКМ (Конец выделения рамкой)
                    app.is_selecting = False
                    x1, y1 = app.selection_start
                    x2, y2 = event.pos

                    # Защита от случайного клика (рамка должна быть хотя бы 5 пикселей)
                    if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
                        phys_x1, phys_y1 = app.camera.screen_to_phys(x1, y1, app.scale)
                        phys_x2, phys_y2 = app.camera.screen_to_phys(x2, y2, app.scale)
                        phys_min_x, phys_max_x = min(phys_x1, phys_x2), max(phys_x1, phys_x2)
                        phys_min_y, phys_max_y = min(phys_y1, phys_y2), max(phys_y1, phys_y2)

                        # Поиск всех узлов внутри рамки
                        for obj in app.sim.objects:
                            ox, oy = obj.get_location()
                            if phys_min_x <= ox <= phys_max_x and phys_min_y <= oy <= phys_max_y:
                                if obj not in app.selected_nodes:
                                    app.selected_nodes.append(obj)

                        # Поиск всех балок внутри рамки (упрощенно: если центр балки в рамке, выделяем её)
                        for spring in app.sim.springs:
                            ox = (spring.obj1.location[0] + spring.obj2.location[0]) / 2
                            oy = (spring.obj1.location[1] + spring.obj2.location[1]) / 2
                            if phys_min_x <= ox <= phys_max_x and phys_min_y <= oy <= phys_max_y:
                                if spring not in app.selected_springs:
                                    app.selected_springs.append(spring)
                                    if spring.obj1 not in app.selected_nodes: app.selected_nodes.append(spring.obj1)
                                    if spring.obj2 not in app.selected_nodes: app.selected_nodes.append(spring.obj2)

            # Обработка нажатий клавиш на клавиатуре
            elif event.type == pygame.KEYDOWN:

                # Управление временем
                if event.key == pygame.K_SPACE:
                    app.is_paused = not app.is_paused
                elif event.key == pygame.K_TAB:
                    # Включает/Выключает режим отладки
                    app.debug_mode = not getattr(app, 'debug_mode', False)
                elif event.key == pygame.K_UP:
                    # Ускоряет, но не больше 1.0 (начальная скорость)
                    app.time_scale = min(1.0, app.time_scale + 0.1)
                elif event.key == pygame.K_DOWN:
                    # Замедляет, но не меньше 0.1
                    app.time_scale = max(0.1, app.time_scale - 0.1)

                elif event.key == pygame.K_f:
                    if len(app.selected_nodes) == 1:
                        app.camera.target = app.selected_nodes[0]
                    else:
                        app.camera.target = None

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
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    if len(app.selected_springs) == 1:
                        target_spring = app.selected_springs[0]
                        obj1, obj2 = target_spring.obj1, target_spring.obj2
                        if target_spring in app.sim.springs:
                            app.sim.springs.remove(target_spring)

                        new_link = None
                        if event.key == pygame.K_1:
                            new_link = Spring(obj1, obj2, k=20000.0, d=160.0)
                        elif event.key == pygame.K_2:
                            new_link = Rope(obj1, obj2, k=150000.0, d=500.0)
                        elif event.key == pygame.K_3:
                            new_link = Hydraulic(obj1, obj2, speed=2.0, min_length=0.5, max_length=10.0)
                        elif event.key == pygame.K_4:
                            new_link = Beam(obj1, obj2)
                        elif event.key == pygame.K_5:
                            new_link = AeroBeam(obj1, obj2, lift_coef=2.5)

                        if new_link:
                            app.sim.add_spring(new_link)
                            app.selected_springs = [new_link]

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
                    target = None
                    if len(app.selected_nodes) == 1 and len(app.selected_springs) == 0:
                        target = app.selected_nodes[0]
                    elif len(app.selected_springs) == 1 and len(app.selected_nodes) <= 2:
                        target = app.selected_springs[0]

                    if target is not None:
                        new_data = show_edit_dialog(target)
                        if new_data:
                            if isinstance(target, Object):
                                target.radius = new_data["radius"]
                                target.density = new_data["density"]
                                target.restitution = new_data["restitution"]
                                target.friction = new_data["friction"]
                                if "power" in new_data: target.power = new_data["power"]
                                volume = (4.0 / 3.0) * math.pi * (target.radius ** 3)
                                target.mass = target.density * volume
                                target.I = 0.4 * target.mass * (target.radius ** 2)
                                target.surface = None
                            elif isinstance(target, Spring):
                                target.k = new_data["k"]
                                target.d = new_data["d"]
                                target.yield_limit = new_data["yield_limit"]
                                target.rest_length = new_data["rest_length"]

                elif event.key == pygame.K_DELETE:
                    for spring in app.selected_springs:
                        if spring in app.sim.springs:
                            app.sim.springs.remove(spring)
                    for node in app.selected_nodes:
                        app.sim.springs = [s for s in app.sim.springs if s.obj1 != node and s.obj2 != node]
                        if node in app.sim.objects:
                            app.sim.objects.remove(node)

                    app.selected_nodes.clear()
                    app.selected_springs.clear()


                mods = pygame.key.get_mods()
                is_ctrl = bool(mods & pygame.KMOD_CTRL)

                # Копирование объектов (Ctrl + C)
                if event.key == pygame.K_c and is_ctrl:
                    if len(app.selected_nodes) > 0:
                        # Находим "центр масс" выделенной геометрии
                        cx = sum(n.location[0] for n in app.selected_nodes) / len(app.selected_nodes)
                        cy = sum(n.location[1] for n in app.selected_nodes) / len(app.selected_nodes)

                        clipboard_nodes = []
                        node_to_id = {}  # Карта: Объект -> Временный ID

                        # Сохраняем узлы
                        for i, node in enumerate(app.selected_nodes):
                            node_to_id[node] = i  # Запоминаем ID этого узла
                            node_data = {
                                "class": node.__class__,
                                "rel_x": node.location[0] - cx,  # Сохраняем координату ОТНОСИТЕЛЬНО центра
                                "rel_y": node.location[1] - cy,
                                "radius": node.radius,
                                "density": node.density,
                                "restitution": node.restitution,
                                "friction": node.friction,
                                "color": node.color,
                                "is_static": getattr(node, 'is_static', False)
                            }
                            if isinstance(node, MotorWheel):
                                node_data["power"] = node.power
                            clipboard_nodes.append(node_data)

                        clipboard_springs = []
                        # Сохраняем балки (только те, чьи оба узла выделены)
                        for spring in app.sim.springs:
                            if spring.obj1 in node_to_id and spring.obj2 in node_to_id:
                                spring_data = {
                                    "class": spring.__class__,
                                    "id1": node_to_id[spring.obj1],  # Запоминаем, какие временные ID она соединяет
                                    "id2": node_to_id[spring.obj2],
                                    "k": spring.k,
                                    "d": spring.d,
                                    "yield_limit": spring.yield_limit,
                                    "break_limit": spring.break_limit,
                                    "rest_length": spring.rest_length
                                }
                                if isinstance(spring, Hydraulic):
                                    spring_data["speed"] = spring.speed
                                    spring_data["min_length"] = spring.min_length
                                    spring_data["max_length"] = spring.max_length
                                clipboard_springs.append(spring_data)

                        app.clipboard = {
                            "nodes": clipboard_nodes,
                            "springs": clipboard_springs
                        }
                        print(f"Скопировано узлов: {len(clipboard_nodes)}, балок: {len(clipboard_springs)}")

                    # --- НОВОЕ: СТРУКТУРНАЯ ВСТАВКА (Ctrl + V) ---
                elif event.key == pygame.K_v and is_ctrl:
                    if app.clipboard is not None and "nodes" in app.clipboard:
                        mx, my = pygame.mouse.get_pos()
                        phys_mx, phys_my = app.camera.screen_to_phys(mx, my, app.scale)

                        new_nodes = []

                        app.selected_nodes.clear()
                        app.selected_springs.clear()

                        # 1. Спавним все новые узлы
                        for node_data in app.clipboard["nodes"]:
                            target_class = node_data["class"]
                            new_obj = target_class(
                                x=phys_mx + node_data["rel_x"],
                                y=phys_my + node_data["rel_y"],
                                radius=node_data["radius"],
                                velocity=[0.0, 0.0],
                                density=node_data["density"],
                                restitution=node_data["restitution"],
                                friction=node_data["friction"],
                                color=node_data["color"]
                            )
                            new_obj.is_static = node_data["is_static"]
                            if issubclass(target_class, MotorWheel):
                                new_obj.power = node_data.get("power", 25.0)

                            app.sim.add_object(new_obj)
                            new_nodes.append(new_obj)
                            app.selected_nodes.append(new_obj)

                        # 2. Спавним балки и привязываем их к НОВЫМ узлам по сохраненным ID
                        for spring_data in app.clipboard["springs"]:
                            target_class = spring_data["class"]
                            obj1 = new_nodes[spring_data["id1"]]
                            obj2 = new_nodes[spring_data["id2"]]

                            new_spring = target_class(
                                obj1, obj2,
                                k=spring_data["k"],
                                d=spring_data["d"],
                                yield_limit=spring_data["yield_limit"],
                                break_limit=spring_data["break_limit"],
                                rest_length=spring_data["rest_length"]
                            )
                            if issubclass(target_class, Hydraulic):
                                new_spring.speed = spring_data.get("speed", 2.0)
                                new_spring.min_length = spring_data.get("min_length", 0.5)
                                new_spring.max_length = spring_data.get("max_length", 5.0)

                            app.sim.add_spring(new_spring)
                            app.selected_springs.append(new_spring)

            # Отпускание клавиш (остановка моторов и гидравлики)
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_a, pygame.K_d):
                    for obj in app.sim.objects:
                        if isinstance(obj, MotorWheel): obj.direction = 0
                if event.key in (pygame.K_w, pygame.K_s):
                    for spring in app.sim.springs:
                        if isinstance(spring, Hydraulic): spring.activation = 0