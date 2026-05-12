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
from physics.objects import Object


class Spring:
    def __init__(self, obj1: Object, obj2: Object, k: float = 15000.0, d: float = 150.0,
                 rest_length: float = None, yield_limit: float = 0.15, break_limit: float = 0.35):
        """
        obj1, obj2: Связанные объекты (узлы)
        k: Жесткость пружины
        d: Коэффициент демпфирования (амортизатор)
        rest_length: Исходная длина (если None, вычисляется автоматически при создании)
        yield_limit: Предел пластичности (какой % деформации согнет балку навсегда, например 0.15 = 15%)
        break_limit: Предел разрыва (при каком % деформации балка лопнет)
        """
        self.obj1 = obj1
        self.obj2 = obj2
        self.k = k
        self.d = d

        # Автоматический расчет длины покоя, если она не задана явно
        if rest_length is None:
            dx = obj2.location[0] - obj1.location[0]
            dy = obj2.location[1] - obj1.location[1]
            self.rest_length = math.sqrt(dx ** 2 + dy ** 2)
        else:
            self.rest_length = rest_length

        self.yield_limit = yield_limit
        self.break_limit = break_limit
        self.is_broken = False
        self.current_strain = 0.0  # Относительная деформация для визуализации

    def update(self, dt: float):
        if self.is_broken:
            return

        # Вектор между узлами
        dx = self.obj2.location[0] - self.obj1.location[0]
        dy = self.obj2.location[1] - self.obj1.location[1]
        L = math.sqrt(dx ** 2 + dy ** 2)

        if L == 0.0:
            return

        # Единичный вектор направления балки
        nx = dx / L
        ny = dy / L

        # Текущая относительная деформация (положительная - растяжение, отрицательная - сжатие)
        self.current_strain = (L - self.rest_length) / self.rest_length

        # 1. ПРОВЕРКА НА РАЗРЫВ (Разрушение конструкции)
        if abs(self.current_strain) > self.break_limit:
            self.is_broken = True
            return

        # 2. ПЛАСТИЧЕСКАЯ ДЕФОРМАЦИЯ (Эффект "мятого металла")
        # Если балка сжата или растянута сильнее предела пластичности, она меняет свою базовую длину
        if abs(self.current_strain) > self.yield_limit:
            # Вычисляем целевую длину, к которой балка деформируется
            target_rest = L - math.copysign(self.yield_limit * self.rest_length, self.current_strain)
            # Металл мнется постепенно (скорость пластического сдвига)
            self.rest_length += (target_rest - self.rest_length) * 0.2

        # 3. РАСЧЕТ СИЛЫ УПРУГОСТИ (Закон Гука)
        fs = self.k * (L - self.rest_length)

        # 4. РАСЧЕТ СИЛЫ ДЕМПФИРОВАНИЯ (Гашение колебаний)
        # Нам нужна проекция относительной скорости на ось балки
        rvx = self.obj2.velocity[0] - self.obj1.velocity[0]
        rvy = self.obj2.velocity[1] - self.obj1.velocity[1]
        v_damp = rvx * nx + rvy * ny
        fd = self.d * v_damp

        # Полное скалярное усилие
        f_total = fs + fd

        # Вектор силы
        fx = f_total * nx
        fy = f_total * ny

        # Применяем силы к узлам (Ускорение a = F / m, изменение скорости dv = a * dt)
        # Мы можем закрепить некоторые узлы намертво, добавив им флаг `static = True`
        if not getattr(self.obj1, 'static', False):
            self.obj1.velocity[0] += (fx / self.obj1.mass) * dt
            self.obj1.velocity[1] += (fy / self.obj1.mass) * dt

        if not getattr(self.obj2, 'static', False):
            self.obj2.velocity[0] -= (fx / self.obj2.mass) * dt
            self.obj2.velocity[1] -= (fy / self.obj2.mass) * dt


class Hydraulic(Spring):

    def change_length(self, new_length):
        self.rest_length = new_length
