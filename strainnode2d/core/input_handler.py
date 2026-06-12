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
from strainnode2d.physics.springs import Spring, Hydraulic
from strainnode2d.core.entity_conversion import SPRING_TYPE_NAMES
from strainnode2d.core.clipboard import snapshot_selection, paste_clipboard
from strainnode2d.physics.serializer import save_scene, load_scene


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

                    if app.inspector.handle_mouse_down(mx, my, app):
                        continue

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
                        click_radius = 0.1
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
                            else:
                                app.selected_springs = [clicked_obj]
                                app.selected_nodes.clear()
                    else:
                        if not is_shift and not is_ctrl:
                            app.selected_nodes.clear()
                            app.selected_springs.clear()
                            app.is_panning = True
                            app.pan_start_mouse = pygame.mouse.get_pos()
                            app.pan_start_camera = (app.camera.x, app.camera.y)
                            app.camera.clear_follow()
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
                mx, my = event.pos
                app.inspector.handle_mouse_motion(mx, my, app)

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
                    app.inspector.handle_mouse_up()
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

            elif event.type == pygame.TEXTINPUT:
                if app.inspector.handle_textinput(event.text, app):
                    continue

            # Обработка нажатий клавиш на клавиатуре
            elif event.type == pygame.KEYDOWN:
                if app.inspector.blocks_input and app.inspector.handle_keydown(event, app):
                    continue

                # Управление временем
                if event.key == pygame.K_SPACE:
                    app.is_paused = not app.is_paused
                elif event.key == pygame.K_TAB:
                    # 0 — выкл, 1 — нормали, 2 — визуализация сопротивления
                    app.debug_mode = (getattr(app, 'debug_mode', 0) + 1) % 3
                elif event.key == pygame.K_UP:
                    # Ускоряет, но не больше 1.0 (начальная скорость)
                    app.time_scale = min(1.0, app.time_scale + 0.1)
                elif event.key == pygame.K_DOWN:
                    # Замедляет, но не меньше 0.1
                    app.time_scale = max(0.1, app.time_scale - 0.1)

                elif event.key == pygame.K_f:
                    if len(app.selected_springs) == 1:
                        app.camera.clear_follow()
                        app.camera.spring_target = app.selected_springs[0]
                    elif len(app.selected_nodes) == 1:
                        app.camera.clear_follow()
                        app.camera.target = app.selected_nodes[0]
                    else:
                        app.camera.clear_follow()

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

                # Смена типов балок (с сохранением параметров)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    if len(app.selected_springs) == 1:
                        idx = event.key - pygame.K_1
                        if idx < len(SPRING_TYPE_NAMES):
                            app.inspector.apply_spring_type_change(
                                app, app.selected_springs[0], SPRING_TYPE_NAMES[idx]
                            )

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
                        app.last_scene = filepath
                        app._clear_scene_editor_state()
                        load_scene(app.sim, filepath)
                        app.focus_on_loaded_scene()

                elif event.key == pygame.K_r:
                    app.reload_last_scene()

                elif event.key == pygame.K_INSERT:
                    app.save_quick_checkpoint()

                elif event.key == pygame.K_HOME:
                    app.restore_quick_checkpoint()

                elif event.key == pygame.K_q:
                    app.inspector.toggle_enabled()

                elif event.key == pygame.K_e:
                    target = app.inspector.get_inspection_target(app)
                    if target is not None and app.inspector.enabled:
                        app.inspector.open_edit_mode(target)

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

                if event.key == pygame.K_c and is_ctrl:
                    if len(app.selected_nodes) > 0:
                        app.clipboard = snapshot_selection(app.selected_nodes, app.sim.springs)
                        print(
                            f"Скопировано узлов: {len(app.clipboard['nodes'])}, "
                            f"балок: {len(app.clipboard['springs'])}"
                        )

                elif event.key == pygame.K_v and is_ctrl:
                    if app.clipboard is not None and app.clipboard.get("nodes"):
                        mx, my = pygame.mouse.get_pos()
                        phys_mx, phys_my = app.camera.screen_to_phys(mx, my, app.scale)

                        app.selected_nodes.clear()
                        app.selected_springs.clear()

                        new_nodes, new_springs = paste_clipboard(app.clipboard, phys_mx, phys_my)
                        for new_obj in new_nodes:
                            app.sim.add_object(new_obj)
                            app.selected_nodes.append(new_obj)
                        for new_spring in new_springs:
                            app.sim.add_spring(new_spring)
                            app.selected_springs.append(new_spring)

            elif event.type == pygame.KEYUP:
                if app.inspector.blocks_input:
                    continue
                if event.key in (pygame.K_a, pygame.K_d):
                    for obj in app.sim.objects:
                        if isinstance(obj, MotorWheel): obj.direction = 0
                if event.key in (pygame.K_w, pygame.K_s):
                    for spring in app.sim.springs:
                        if isinstance(spring, Hydraulic): spring.activation = 0