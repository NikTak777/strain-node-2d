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

import math
from collections import defaultdict
from strainnode2d.physics.area import Area
from strainnode2d.physics.objects import Object
from strainnode2d.physics.springs import Spring


class PhysicSimulation:
    def __init__(self, area: Area):
        """
        Инициализация главного движка физической симуляции.

        :param area: Экземпляр класса Area, задающий физические границы мира.
        """
        self.Area = area
        self.objects = []       # Список всех объектов симуляции
        self.springs = []       # Список всех баллок симуляции
        self.time = 0           # Общее время симуляции (с)
        self.g = 9.80665        # Ускорение свободного падения (м/c2)
        self.dt = 0.1           # Шаг времени симуляции (с)
        self.density = 1.29     # Плотность воздуха (кг/м3)

    def add_object(self, obj: Object):
        """
        Добавление нового физического тела (узла) в симуляцию.

        :param obj: Экземпляр класса Object
        """
        self.objects.append(obj)

    def add_spring(self, spring: Spring):
        """
        Добавление новой упругой связи (балки) в симуляцию.

        :param spring: Экземпляр класса Spring
        """
        self.springs.append(spring)

    def resolve_ball_collisions(self):
        """
        Вычисление и разрешение соударений (Spatial Hashing).
        Снижает сложность алгоритма с O(N^2) до почти O(N).
        """
        if not self.objects:
            return

        # Создание множество соединенных пар, поиск мгновенный за O(1)
        connected_pairs = set()
        for s in self.springs:
            id1, id2 = id(s.obj1), id(s.obj2)
            if id1 > id2: id1, id2 = id2, id1
            connected_pairs.add((id1, id2))

        # Настройка сетки пространства, ячейки равны диаметру самого большого объекта
        max_radius = max((obj.radius for obj in self.objects), default=1.0)
        cell_size = max_radius * 2.1  # Чуть больше диаметра для запаса

        if cell_size <= 0:
            return

        # Распределение объектов по ячейкам
        # Ключ словаря - координаты ячейки (x, y), значение - список объектов в ней
        grid = defaultdict(list)
        for obj in self.objects:
            grid_x = int(obj.location[0] / cell_size)
            grid_y = int(obj.location[1] / cell_size)
            grid[(grid_x, grid_y)].append(obj)

        checked_pairs = set()

        # Проверка самой ячейки и 4 соседние (вправо и вниз). Остальные 4 проверятся сами с другой стороны.
        neighbor_offsets = [
            (0, 0),  # Сама ячейка
            (1, 0),  # Вправо
            (0, 1),  # Вниз
            (1, 1),  # Вправо-вниз
            (-1, 1)  # Влево-вниз
        ]

        # Проверка столкновений
        for (gx, gy), cell_objects in grid.items():
            for obj1 in cell_objects:
                for dx, dy in neighbor_offsets:
                    nx, ny = gx + dx, gy + dy

                    # Если соседней ячейки нет в сетке - пропуск
                    if (nx, ny) not in grid:
                        continue

                    for obj2 in grid[(nx, ny)]:
                        if obj1 == obj2:
                            continue

                        # Гарантирует уникальный ID пары (меньший ID всегда первый)
                        id1, id2 = id(obj1), id(obj2)
                        if id1 > id2:
                            id1, id2 = id2, id1
                        pair_id = (id1, id2)

                        # Если эта пара объектов проверена - пропуск
                        if pair_id in checked_pairs:
                            continue
                        checked_pairs.add(pair_id)

                        # Проверяет, не соединены ли они балкой (Мгновенный поиск в Set)
                        if pair_id in connected_pairs:
                            continue

                        # Вектор расстояния между центрами шаров
                        dx = obj2.location[0] - obj1.location[0]
                        dy = obj2.location[1] - obj1.location[1]
                        distance = math.sqrt(dx ** 2 + dy ** 2)
                        min_dist = obj1.radius + obj2.radius

                        if distance < min_dist:  # Фиксация факта пересечения (столкновения)
                            if distance == 0:  # Защита от деления на ноль при идеальном совпадении центров
                                dx = 1.0
                                dy = 0.0
                                distance = 1.0

                            # Единичный вектор нормали (от obj1 к obj2)
                            nx = dx / distance
                            ny = dy / distance

                            # Устранение взаимного проникновения
                            overlap = min_dist - distance

                            # Получение обратных масс (0.0, если объект заморожен)
                            inv_m1 = 0.0 if getattr(obj1, 'is_static', False) else 1.0 / obj1.mass
                            inv_m2 = 0.0 if getattr(obj2, 'is_static', False) else 1.0 / obj2.mass

                            sum_inv_m = inv_m1 + inv_m2

                            if sum_inv_m == 0.0:
                                continue

                            ratio1 = inv_m1 / sum_inv_m
                            ratio2 = inv_m2 / sum_inv_m

                            obj1.location[0] -= nx * overlap * ratio1
                            obj1.location[1] -= ny * overlap * ratio1
                            obj2.location[0] += nx * overlap * ratio2
                            obj2.location[1] += ny * overlap * ratio2

                            # Расчёт импульсов отскока и вращения
                            # Единичный вектор тангенциали
                            tx = -ny
                            ty = nx

                            # Проекции линейных скоростей на нормаль и тангенциаль
                            v1n = obj1.velocity[0] * nx + obj1.velocity[1] * ny
                            v1t = obj1.velocity[0] * tx + obj1.velocity[1] * ty
                            v2n = obj2.velocity[0] * nx + obj2.velocity[1] * ny
                            v2t = obj2.velocity[0] * tx + obj2.velocity[1] * ty

                            # Относительная нормальная скорость
                            rel_vn = v2n - v1n

                            # Отмена импульса, если шары уже движутся в разные стороны
                            if rel_vn >= 0:
                                continue

                            # Усредненный коэффициент восстановления (отскока)
                            re = (obj1.restitution + obj2.restitution) / 2.0

                            # Величина нормального импульса с учетом обратных масс
                            Jn = -(1.0 + re) * rel_vn / sum_inv_m

                            # Обновление нормальных скоростей
                            v1n_new = v1n - Jn * inv_m1
                            v2n_new = v2n + Jn * inv_m2

                            # Расчёт трения и передачи вращения
                            # Относительная скорость в точке контакта вдоль касательной с учетом вращения обоих шаров
                            v_rel_t = (v2t - obj2.angular_velocity * obj2.radius) - (v1t + obj1.angular_velocity * obj1.radius)

                            # Эффективная тангенциальная масса для твердых шаров (множитель 3.5 из-за момента инерции)
                            inv_eff_mt = sum_inv_m * 3.5
                            Jt = -v_rel_t / inv_eff_mt

                            # Ограничение трения силой реакции опоры (Закон Кулона: F_тр <= mu * N)
                            fr = (obj1.friction + obj2.friction) / 2.0
                            max_friction = fr * Jn
                            if abs(Jt) > max_friction:
                                Jt = math.copysign(max_friction, Jt)

                            # Изменение тангенциальных скоростей
                            v1t_new = v1t - Jt * inv_m1
                            v2t_new = v2t + Jt * inv_m2

                            # Получение обратных моментов инерции (0.0, если объект заморожен)
                            inv_I1 = 0.0 if getattr(obj1, 'is_static', False) else 1.0 / obj1.I
                            inv_I2 = 0.0 if getattr(obj2, 'is_static', False) else 1.0 / obj2.I

                            # Изменение угловых скоростей шаров
                            obj1.angular_velocity -= (Jt * obj1.radius) * inv_I1
                            obj2.angular_velocity -= (Jt * obj2.radius) * inv_I2

                            # Применение новых скоростей
                            # Сборка векторов конечных скоростей обратно из нормальных и тангенциальных составляющих
                            obj1.velocity[0] = v1n_new * nx + v1t_new * tx
                            obj1.velocity[1] = v1n_new * ny + v1t_new * ty
                            obj2.velocity[0] = v2n_new * nx + v2t_new * tx
                            obj2.velocity[1] = v2n_new * ny + v2t_new * ty

    def resolve_node_beam_collisions(self):
        """
        Столкновения узлов с балками, у которых включена коллизия.
        Импульс передаётся на оба конца балки пропорционально положению контакта.
        """
        collision_springs = [
            s for s in self.springs
            if not s.is_broken and getattr(s, 'collision_enabled', False)
        ]
        if not collision_springs:
            return

        for spring in collision_springs:
            ep1, ep2 = spring.obj1, spring.obj2
            x1, y1 = ep1.get_location()
            x2, y2 = ep2.get_location()
            beam_r = spring.collision_radius

            seg_dx = x2 - x1
            seg_dy = y2 - y1
            l2 = seg_dx ** 2 + seg_dy ** 2
            if l2 == 0:
                continue
            seg_len = math.sqrt(l2)

            for node in self.objects:
                if node is ep1 or node is ep2:
                    continue
                if getattr(node, 'is_static', False):
                    continue

                px = node.location[0] - x1
                py = node.location[1] - y1
                t = max(0.0, min(1.0, (px * seg_dx + py * seg_dy) / l2))

                cx = x1 + t * seg_dx
                cy = y1 + t * seg_dy
                dx = node.location[0] - cx
                dy = node.location[1] - cy
                dist = math.sqrt(dx * dx + dy * dy)
                min_dist = node.radius + beam_r

                if dist >= min_dist:
                    continue

                if dist < 1e-8:
                    nx = -seg_dy / seg_len
                    ny = seg_dx / seg_len
                    if nx * px + ny * py < 0:
                        nx, ny = -nx, -ny
                    dist = 1e-8
                else:
                    nx = dx / dist
                    ny = dy / dist

                overlap = min_dist - dist
                inv_m_n = 1.0 / node.mass
                inv_m1 = 0.0 if getattr(ep1, 'is_static', False) else 1.0 / ep1.mass
                inv_m2 = 0.0 if getattr(ep2, 'is_static', False) else 1.0 / ep2.mass
                lever1 = (1.0 - t) * inv_m1
                lever2 = t * inv_m2
                sum_inv_pos = inv_m_n + lever1 + lever2
                sum_inv_imp = inv_m_n + (1.0 - t) ** 2 * inv_m1 + t ** 2 * inv_m2
                if sum_inv_pos == 0.0:
                    continue

                node.location[0] += nx * overlap * inv_m_n / sum_inv_pos
                node.location[1] += ny * overlap * inv_m_n / sum_inv_pos
                if inv_m1 > 0.0:
                    ep1.location[0] -= nx * overlap * lever1 / sum_inv_pos
                    ep1.location[1] -= ny * overlap * lever1 / sum_inv_pos
                if inv_m2 > 0.0:
                    ep2.location[0] -= nx * overlap * lever2 / sum_inv_pos
                    ep2.location[1] -= ny * overlap * lever2 / sum_inv_pos

                tx = -ny
                ty = nx

                v_node_n = node.velocity[0] * nx + node.velocity[1] * ny
                v_node_t = node.velocity[0] * tx + node.velocity[1] * ty
                v1n = ep1.velocity[0] * nx + ep1.velocity[1] * ny
                v1t = ep1.velocity[0] * tx + ep1.velocity[1] * ty
                v2n = ep2.velocity[0] * nx + ep2.velocity[1] * ny
                v2t = ep2.velocity[0] * tx + ep2.velocity[1] * ty
                v_beam_n = (1.0 - t) * v1n + t * v2n
                v_beam_t = (1.0 - t) * v1t + t * v2t

                rel_vn = v_node_n - v_beam_n
                if rel_vn >= 0:
                    continue

                re = (node.restitution + ep1.restitution + ep2.restitution) / 3.0
                Jn = -(1.0 + re) * rel_vn / sum_inv_imp

                v_node_n_new = v_node_n + Jn * inv_m_n
                v1n_new = v1n - Jn * (1.0 - t) * inv_m1 if inv_m1 > 0 else v1n
                v2n_new = v2n - Jn * t * inv_m2 if inv_m2 > 0 else v2n

                v_rel_t = v_node_t - v_beam_t
                inv_eff_mt = sum_inv_imp * 3.5
                Jt = -v_rel_t / inv_eff_mt

                fr = (node.friction + ep1.friction + ep2.friction) / 3.0
                max_friction = fr * Jn
                if abs(Jt) > max_friction:
                    Jt = math.copysign(max_friction, Jt)

                v_node_t_new = v_node_t + Jt * inv_m_n
                v1t_new = v1t - Jt * (1.0 - t) * inv_m1 if inv_m1 > 0 else v1t
                v2t_new = v2t - Jt * t * inv_m2 if inv_m2 > 0 else v2t

                node.velocity[0] = v_node_n_new * nx + v_node_t_new * tx
                node.velocity[1] = v_node_n_new * ny + v_node_t_new * ty
                if inv_m1 > 0:
                    ep1.velocity[0] = v1n_new * nx + v1t_new * tx
                    ep1.velocity[1] = v1n_new * ny + v1t_new * ty
                if inv_m2 > 0:
                    ep2.velocity[0] = v2n_new * nx + v2t_new * tx
                    ep2.velocity[1] = v2n_new * ny + v2t_new * ty

    def resolve_collisions(self, obj: Object):
        """
        Обработка столкновений конкретного объекта с внешними границами симуляции (Area).
        Включает модель сухого трения Кулона (Статика и Кинетика).

        :param obj: Физический объект для проверки
        """
        if obj.is_static:
            return

        borders = self.Area.get_border()
        max_x, max_y = borders[0]
        min_x, min_y = borders[1]

        ra = obj.radius
        re = obj.restitution
        m = obj.mass
        I = obj.I

        # Коэффициенты трения (кинетическое по умолчанию составляет 75% от статического)
        mu_s = obj.friction
        mu_k = getattr(obj, 'friction_kinetic', mu_s * 0.75)

        def apply_contact_physics(normal_axis: int, normal_dir: int):
            """
            Применение физики удара и трения Кулона для конкретной стены.

            :param normal_axis: 0 для вертикальных стен (X), 1 для горизонтальных (Y)
            :param normal_dir: Направление нормали от стены к центру шара (+1 или -1)
            """
            n_axis = normal_axis
            t_axis = 1 - normal_axis

            v_n = obj.velocity[n_axis] * normal_dir
            v_t = obj.velocity[t_axis]

            # Изменение нормальной скорости (отскок)
            obj.velocity[n_axis] = -v_n * re * normal_dir

            # Расчет относительной тангенциальной скорости точки контакта
            if n_axis == 1:  # Пол / Потолок
                v_rel_t = v_t + normal_dir * obj.angular_velocity * ra
            else:  # Левая / Правая стены
                v_rel_t = v_t - normal_dir * obj.angular_velocity * ra

            # Нормальный импульс удара
            P_n = m * abs(v_n) * (1 + re)

            # Идеальный тангенциальный импульс, необходимый для полной остановки скольжения
            J_t = -m * v_rel_t / 3.5

            # Трение кулона
            max_static_impulse = mu_s * P_n

            if abs(J_t) <= max_static_impulse:
                # Импульс меньше предела статического трения.
                # Сцепления хватает, объект "цепляется" за поверхность и переходит в чистое качение.
                pass
            else:
                # Предел превышен, колесо срывается в скольжение (букс).
                # Применяется меньший импульс кинетического (динамического) трения.
                max_kinetic_impulse = mu_k * P_n
                J_t = math.copysign(max_kinetic_impulse, J_t)

            # Изменяем линейную скорость вдоль стены
            obj.velocity[t_axis] += J_t / m

            # Изменение угловой скорости вращения
            if n_axis == 1:
                obj.angular_velocity += (J_t * ra * normal_dir) / I
            else:
                obj.angular_velocity -= (J_t * ra * normal_dir) / I

        # Левая стена (нормаль вправо: +1)
        if obj.location[0] - ra < min_x:
            obj.location[0] = min_x + ra
            apply_contact_physics(0, 1)

        # Правая стена (нормаль влево: -1)
        elif obj.location[0] + ra > max_x:
            obj.location[0] = max_x - ra
            apply_contact_physics(0, -1)

        # Пол (нормаль вверх: +1)
        if obj.location[1] - ra < min_y:
            obj.location[1] = min_y + ra
            apply_contact_physics(1, 1)
            obj.on_ground = True

        # Потолок (нормаль вниз: -1)
        elif obj.location[1] + ra > max_y:
            obj.location[1] = max_y - ra
            apply_contact_physics(1, -1)

    def apply_ground_effect(self, spring: Spring):
        """
        Симулирует аэродинамический граунд-эффект.
        Работает только для внешних аэро-балок (AeroBeam), нормаль которых направлена в землю.
        """
        # Проверяет, что это аэро-балка (только обшивка взаимодействует с воздухом)
        if spring.__class__.__name__ != "AeroBeam":
            return

        obj1 = spring.obj1
        obj2 = spring.obj2

        # Вычисляет геометрию нормали (куда "смотрит" поверхность)
        dx = obj2.location[0] - obj1.location[0]
        dy = obj2.location[1] - obj1.location[1]
        L = math.sqrt(dx ** 2 + dy ** 2)

        if L == 0:
            return

        # Вычисляет Y-компоненту вектора нормали точно так же, как внутри AeroBeam
        ny = (dx / L) * spring.normal_flip

        # 3. Фильтр днища: Нормаль должна смотреть ВНИЗ.
        # Если ny > 0 (смотрит вверх, как крыша) или ny == 0 (вертикальный бампер) - игнорируем!
        # Берем небольшой допуск (-0.1), чтобы исключить почти вертикальные детали.
        if ny > -0.1:
            return

        # 4. Вычисляем реальную высоту над землей
        borders = self.Area.get_border()
        ground_y = borders[1][1]  # Координата пола (min_y)

        h1 = obj1.location[1] - ground_y
        h2 = obj2.location[1] - ground_y

        # Если балка слишком высоко (например, больше 1 метра над землей), вакуум рассеивается
        if h1 > 0.5 or h2 > 0.5:
            return

        avg_height = (h1 + h2) / 2.0
        avg_height = max(0.05, avg_height)  # Защита от деления на ноль при ударе днищем

        # 5. Вычисляем горизонтальную скорость
        vx = (obj1.velocity[0] + obj2.velocity[0]) / 2.0
        v_sq = vx ** 2

        # Граунд-эффект начинает работать только на высоких скоростях (напр. > 10 м/с = 36 км/ч)
        if v_sq < 100:
            spring.current_ge_force = 0.0
            return

        # 6. Формула Бернулли с учетом ширины (chord) машины
        # Сила вакуума = Константа * Скорость^2 * (Площадь днища) / Расстояние до земли
        GE_Multiplier = 0.2  # Коэффициент мощности граунд-эффекта
        downforce = GE_Multiplier * self.density * v_sq * (L * spring.chord) / avg_height

        # max_downforce = (obj1.mass + obj2.mass) * self.g * 3.0
        # downforce = min(downforce, max_downforce)

        spring.current_ge_force = downforce

        # Применяем силу направленную строго вниз (по оси Y с минусом)
        half_force = downforce / 2.0

        if not getattr(obj1, 'is_static', False):
            obj1.velocity[1] -= (half_force / obj1.mass) * self.dt
        if not getattr(obj2, 'is_static', False):
            obj2.velocity[1] -= (half_force / obj2.mass) * self.dt

    def step(self, dt: float):
        """
        Выполнение одного шага физической симуляции для всех объектов и связей.

        :param dt: Дельта времени (размер шага интеграции в секундах)
        """
        # Вычисление сил во всех балках и обновление скоростей узлов
        for spring in self.springs:
            if hasattr(spring, 'air_density'):
                spring.update(dt, air_density=self.density)
            else:
                spring.update(dt)
            # self.apply_ground_effect(spring) # Вычисление граунд-эффекта

        # Очистка физического мира от разорванных связей
        self.springs = [s for s in self.springs if not s.is_broken]

        for obj in self.objects:
            if obj.is_static:  # Пропуск замороженных объектов
                obj.velocity = [0.0, 0.0]
                obj.angular_velocity = 0.0
                continue

            vx = obj.velocity[0]
            vy = obj.velocity[1]

            speed = math.sqrt(vx ** 2 + vy ** 2)

            if speed > 0.0001:
                drag_const = (3 * obj.Cd * self.density) / (8 * obj.density * obj.radius)
                # Ускорение свободного падения с квадратичным сопротивлением
                acc_drag_x = -drag_const * speed * vx
                acc_drag_y = -drag_const * speed * vy
            else:
                acc_drag_x = 0.0
                acc_drag_y = 0.0

            # Эффект Магнуса (аэродинамическая подъемная сила от вращения)
            C_M = 1.0  # Сила закрутки
            acc_magnus_x = -C_M * self.density * (obj.radius ** 3) * obj.angular_velocity * vy / obj.mass
            acc_magnus_y = C_M * self.density * (obj.radius ** 3) * obj.angular_velocity * vx / obj.mass

            # Сопротивление воздуха вращению (постепенное затухание спина)
            C_rot = 0.05
            obj.angular_velocity *= math.exp(-C_rot * (self.density / obj.density) * dt)

            # Эффективная гравитация (с учетом силы Архимеда)
            effective_g = self.g * (1 - self.density / obj.density)

            # Сопротивление качению
            # Применение силы сопротивления качению только при контакте с поверхностью
            if getattr(obj, 'on_ground', False):
                crr = getattr(obj, 'rolling_resistance', 0.03)

                # Линейное замедление по горизонтали (деселерация a = crr * g)
                dec_v = crr * abs(effective_g) * dt
                if abs(obj.velocity[0]) > dec_v:
                    obj.velocity[0] -= math.copysign(dec_v, obj.velocity[0])
                else:
                    obj.velocity[0] = 0.0

                # Угловое замедление (тормозящий момент сопротивления качению)
                # Из уравнения моментов: dec_omega = 2.5 * crr * g / R * dt
                dec_omega = 2.5 * crr * abs(effective_g) / obj.radius * dt
                if abs(obj.angular_velocity) > dec_omega:
                    obj.angular_velocity -= math.copysign(dec_omega, obj.angular_velocity)
                else:
                    obj.angular_velocity = 0.0

            # Обновление скоростей
            obj.velocity[0] += (acc_drag_x + acc_magnus_x) * dt
            obj.velocity[1] += (-effective_g + acc_drag_y + acc_magnus_y) * dt

            # Обновление координат
            obj.location[0] += obj.velocity[0] * dt
            obj.location[1] += obj.velocity[1] * dt

            # Обновление угла вращения
            obj.angle += obj.angular_velocity * dt
            obj.angle = obj.angle % (2 * math.pi)  # Удержание угла в пределах [0; 2pi]

            # Сброс флага контакта перед проверкой коллизий на текущем шаге
            obj.on_ground = False

        # Структурированная обработка столкновений
        # Приоритетное вычисление столкновений шаров между собой
        self.resolve_ball_collisions()
        self.resolve_node_beam_collisions()

        # Обработка столкновений со стенами
        # Это гарантирует, что если один шар вытолкнет другой наружу, стена вернет его обратно на экран
        for obj in self.objects:
            self.resolve_collisions(obj)

        self.time += dt