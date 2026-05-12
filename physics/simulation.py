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
from physics.area import Area
from physics.objects import Object
from physics.springs import Spring


class PhysicSimulation:
    def __init__(self, area: Area):
        self.Area = area
        self.objects = []
        self.springs = []
        self.time = 0  # Общее время симуляции
        self.g = 9.80665  # Ускорение свободного падения
        self.dt = 0.1  # Шаг интеграции времени в секундах
        self.density = 1.29  # Плотность воздуха

    def add_object(self, obj: Object):
        """Метод для добавления новых тел в симуляцию"""
        self.objects.append(obj)

    def add_spring(self, spring: Spring):
        """Регистрация новой балки в симуляции"""
        self.springs.append(spring)

    def resolve_ball_collisions(self):
        """Просчет соударений между всеми парами шаров"""
        n = len(self.objects)
        for i in range(n):
            for j in range(i + 1, n):
                obj1 = self.objects[i]
                obj2 = self.objects[j]

                connected = False
                for s in self.springs:
                    if (s.obj1 == obj1 and s.obj2 == obj2) or (s.obj1 == obj2 and s.obj2 == obj1):
                        connected = True
                        break
                if connected:
                    continue

                # Вектор расстояния между центрами шаров
                dx = obj2.location[0] - obj1.location[0]
                dy = obj2.location[1] - obj1.location[1]
                distance = math.sqrt(dx ** 2 + dy ** 2)
                min_dist = obj1.radius + obj2.radius

                if distance < min_dist:  # Если шары пересекаются (произошло столкновение)
                    if distance == 0:  # Защита от деления на ноль, если центры совпали идеально
                        dx = 1.0
                        dy = 0.0
                        distance = 1.0

                    # Единичный вектор нормали (от obj1 к obj2)
                    nx = dx / distance
                    ny = dy / distance

                    # 1. РАСТАЛКИВАНИЕ (Устранение взаимного проникновения)
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

                    # 2. РАСЧЕТ ИМПУЛЬСОВ ОТСКОКА И ВРАЩЕНИЯ
                    # Единичный вектор тангенциали (касательной, повернутой на 90 градусов против часовой)
                    tx = -ny
                    ty = nx

                    # Проекции линейных скоростей на нормаль и тангенциаль
                    v1n = obj1.velocity[0] * nx + obj1.velocity[1] * ny
                    v1t = obj1.velocity[0] * tx + obj1.velocity[1] * ty
                    v2n = obj2.velocity[0] * nx + obj2.velocity[1] * ny
                    v2t = obj2.velocity[0] * tx + obj2.velocity[1] * ty

                    # Относительная нормальная скорость
                    rel_vn = v2n - v1n

                    # Если шары уже движутся в разные стороны, импульс не нужен
                    if rel_vn >= 0:
                        continue

                    # Усредненный коэффициент восстановления (отскока)
                    re = (obj1.restitution + obj2.restitution) / 2.0

                    # Величина нормального импульса с учетом обратных масс
                    Jn = -(1.0 + re) * rel_vn / sum_inv_m

                    # Обновляем нормальные скорости
                    v1n_new = v1n - Jn * inv_m1
                    v2n_new = v2n + Jn * inv_m2

                    # --- 3. РАСЧЕТ ТРЕНИЯ И ПЕРЕДАЧИ ВРАЩЕНИЯ ---
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

                    # Получаем обратные моменты инерции (0.0, если объект заморожен)
                    inv_I1 = 0.0 if getattr(obj1, 'is_static', False) else 1.0 / obj1.I
                    inv_I2 = 0.0 if getattr(obj2, 'is_static', False) else 1.0 / obj2.I

                    # Изменение угловых скоростей шаров
                    obj1.angular_velocity -= (Jt * obj1.radius) * inv_I1
                    obj2.angular_velocity -= (Jt * obj2.radius) * inv_I2

                    # --- 4. ПРИМЕНЕНИЕ НОВЫХ СКОРОСТЕЙ ---
                    # Собираем векторы конечных скоростей обратно из нормальных и тангенциальных составляющих
                    obj1.velocity[0] = v1n_new * nx + v1t_new * tx
                    obj1.velocity[1] = v1n_new * ny + v1t_new * ty
                    obj2.velocity[0] = v2n_new * nx + v2t_new * tx
                    obj2.velocity[1] = v2n_new * ny + v2t_new * ty

    def resolve_collisions(self, obj: Object):
        """Проверка столкновений для конкретного объекта"""
        if obj.is_static:
            return

        borders = self.Area.get_border()
        max_x, max_y = borders[0]
        min_x, min_y = borders[1]

        ra = obj.radius
        re = obj.restitution
        fr = obj.friction
        m = obj.mass
        I = obj.I

        def apply_contact_physics(normal_axis, normal_dir):
            """
            Применяет физику удара и трения для конкретной стены.
            normal_axis: 0 для вертикальных стен (X), 1 для пола/потолка (Y)
            normal_dir: направление нормали от стены к центру шара (+1 или -1)
            """
            n_axis = normal_axis
            t_axis = 1 - normal_axis

            v_n = obj.velocity[n_axis] * normal_dir
            v_t = obj.velocity[t_axis]

            # 1. Изменение нормальной скорости (отскок)
            obj.velocity[n_axis] = -v_n * re * normal_dir

            # 2. Расчет относительной тангенциальной скорости точки контакта
            if n_axis == 1:  # Пол / Потолок
                v_rel_t = v_t + normal_dir * obj.angular_velocity * ra
            else:  # Левая / Правая стены
                v_rel_t = v_t - normal_dir * obj.angular_velocity * ra

            # Нормальный импульс удара
            P_n = m * abs(v_n) * (1 + re)

            # Тангенциальный импульс, необходимый для полной остановки скольжения (качение)
            J_t = - m * v_rel_t / 3.5

            # Ограничение трения силой реакции опоры (закон Кулона: F_тр <= mu * N)
            max_friction_impulse = fr * P_n
            if abs(J_t) > max_friction_impulse:
                J_t = math.copysign(max_friction_impulse, J_t)

            # Изменяем линейную скорость вдоль стены
            obj.velocity[t_axis] += J_t / m

            # Изменяем угловую скорость вращения
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

    def step(self, dt):
        """Просчитывает физику для всех объектов"""
        # Рассчитываем силы во всех балках и обновляем скорости узлов
        for spring in self.springs:
            spring.update(dt)

        # Очищаем физический мир от разорванных балок
        self.springs = [s for s in self.springs if not s.is_broken]

        for obj in self.objects:
            # Пропускаем замороженные объекты
            if obj.is_static:
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

            # 2. Эффект Магнуса (аэродинамическая подъемная сила от вращения)
            C_M = 1.0  # Сила закрутки
            acc_magnus_x = -C_M * self.density * (obj.radius ** 3) * obj.angular_velocity * vy / obj.mass
            acc_magnus_y = C_M * self.density * (obj.radius ** 3) * obj.angular_velocity * vx / obj.mass

            # 3. Сопротивление воздуха вращению (постепенное затухание спина)
            C_rot = 0.05
            obj.angular_velocity *= math.exp(-C_rot * (self.density / obj.density) * dt)

            # 4. Эффективная гравитация (с учетом силы Архимеда)
            effective_g = self.g * (1 - self.density / obj.density)

            # --- НОВОЕ: СОПРОТИВЛЕНИЕ КАЧЕНИЮ ---
            # Применяем силу только если шар касался земли на предыдущем шаге
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
            obj.angle = obj.angle % (2 * math.pi)  # Держим угол в пределах [0; 2pi]

            # --- НОВОЕ: ПОРОГ ПОЛНОЙ ОСТАНОВКИ (SLEEP THRESHOLD) ---
            # Избавляемся от микроскопического "дрожания" на одном месте
            if getattr(obj, 'on_ground', False):
                if abs(obj.velocity[0]) < 0.05:
                    obj.velocity[0] = 0.0
                if abs(obj.angular_velocity) < 0.05:
                    obj.angular_velocity = 0.0

            # Сбрасываем флаг контакта перед проверкой коллизий на текущем шаге
            obj.on_ground = False

        # --- СТРУКТУРИРОВАННАЯ ОБРАБОТКА СТОЛКНОВЕНИЙ ---
        # 1. Сначала рассчитываем столкновения шаров между собой
        self.resolve_ball_collisions()

        # 2. Только после этого проверяем столкновения со стенами.
        # Это гарантирует, что если один шар вытолкнет другой наружу, стена вернет его обратно на экран.
        for obj in self.objects:
            self.resolve_collisions(obj)

        self.time += dt