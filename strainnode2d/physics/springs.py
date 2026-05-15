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
from strainnode2d.physics.objects import Object


class Spring:
    def __init__(self, obj1: Object, obj2: Object, k: float = 15000.0, d: float = 150.0,
                 rest_length: float = None, yield_limit: float = 0.15, break_limit: float = 0.35):
        """
        Инициализация стандартной упругой балки (пружины) между двумя физическими узлами.

        :param obj1: Первый привязанный объект (узел)
        :param obj2: Второй привязанный объект (узел)
        :param k: Жесткость пружины (Закон Гука). Чем больше, тем сильнее сопротивляется растяжению/сжатию
        :param d: Коэффициент демпфирования (амортизатор). Гасит колебания системы
        :param rest_length: Длина покоя (м). Если None, вычисляется автоматически по текущему расстоянию между узлами
        :param yield_limit: Предел текучести/пластичности (в долях деформации, например 0.15 = 15%). При превышении балка деформируется навсегда
        :param break_limit: Предел прочности (в долях деформации). При превышении балка лопается и удаляется
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
        self.current_strain = 0.0

    def update(self, dt: float):
        """
        Вычисляет и применяет физические силы упругости и демпфирования к связанным узлам.
        Также обрабатывает пластическую деформацию и разрыв балки.

        :param dt: Шаг времени симуляции (с).
        """
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

        # Проверка на разрыв, разрушение конструкции
        if abs(self.current_strain) > self.break_limit:
            self.is_broken = True
            return

        # Проверка на пластическую деформацию
        if abs(self.current_strain) > self.yield_limit:
            # Целевая длина, к которой балка деформируется
            target_rest = L - math.copysign(self.yield_limit * self.rest_length, self.current_strain)
            self.rest_length += (target_rest - self.rest_length) * 0.2

        # Расчёт силы упругости (Закон Гука)
        fs = self.k * (L - self.rest_length)

        # Расчёт силы демпфирования (Гашение колебаний)
        rvx = self.obj2.velocity[0] - self.obj1.velocity[0]
        rvy = self.obj2.velocity[1] - self.obj1.velocity[1]
        v_damp = rvx * nx + rvy * ny
        fd = self.d * v_damp

        # Полное скалярное усилие
        f_total = fs + fd

        # Вектор силы
        fx = f_total * nx
        fy = f_total * ny

        # Применение силы к узлам (Ускорение a = F / m, изменение скорости dv = a * dt)
        if not getattr(self.obj1, 'static', False):
            self.obj1.velocity[0] += (fx / self.obj1.mass) * dt
            self.obj1.velocity[1] += (fy / self.obj1.mass) * dt

        if not getattr(self.obj2, 'static', False):
            self.obj2.velocity[0] -= (fx / self.obj2.mass) * dt
            self.obj2.velocity[1] -= (fy / self.obj2.mass) * dt


class Rope(Spring):
    def __init__(self, obj1: Object, obj2: Object, k: float = 150000.0, d: float = 500.0, **kwargs):
        """
        Инициализация троса (верёвки).
        Трос работает только на растяжение. При сближении узлов он провисает и не создает сил.

        :param obj1: Первый привязанный объект
        :param obj2: Второй привязанный объект
        :param k: Жесткость натяжения троса
        :param d: Коэффициент демпфирования
        :param kwargs: Дополнительные параметры базового класса
        """
        kwargs.setdefault('yield_limit', float('inf'))
        super().__init__(obj1, obj2, k=k, d=d, **kwargs)

    def update(self, dt: float):
        """
        Вычисляет силы для троса. Отключает расчет, если расстояние меньше длины покоя (провисание).

        :param dt: Шаг времени симуляции (с)
        """
        if self.is_broken:
            return

        dx = self.obj2.location[0] - self.obj1.location[0]
        dy = self.obj2.location[1] - self.obj1.location[1]
        L = math.sqrt(dx ** 2 + dy ** 2)

        if L == 0.0:
            return

        self.current_strain = (L - self.rest_length) / self.rest_length

        # Проверка на разрыв (трос рвётся, если перетянуть)
        if abs(self.current_strain) > self.break_limit:
            self.is_broken = True
            return

        # Если расстояние меньше длины покоя, веревка провисает, силы равны нулю
        if L <= self.rest_length:
            return

        nx = dx / L
        ny = dy / L

        # Закон Гука работает только на растяжение
        fs = self.k * (L - self.rest_length)

        # Демпфирование
        rvx = self.obj2.velocity[0] - self.obj1.velocity[0]
        rvy = self.obj2.velocity[1] - self.obj1.velocity[1]
        v_damp = rvx * nx + rvy * ny
        fd = self.d * v_damp

        f_total = fs + fd

        # Веревка не может толкать узлы друг от друга
        if f_total < 0:
            f_total = 0

        fx = f_total * nx
        fy = f_total * ny

        if not getattr(self.obj1, 'is_static', False):
            self.obj1.velocity[0] += (fx / self.obj1.mass) * dt
            self.obj1.velocity[1] += (fy / self.obj1.mass) * dt

        if not getattr(self.obj2, 'is_static', False):
            self.obj2.velocity[0] -= (fx / self.obj2.mass) * dt
            self.obj2.velocity[1] -= (fy / self.obj2.mass) * dt


class Hydraulic(Spring):
    def __init__(self, obj1, obj2, speed: float = 2.0, min_length: float = 0.5, max_length: float = 5.0, **kwargs):
        """
        Инициализация гидравлического цилиндра.
        Это жесткая балка, способная активно изменять свою базовую длину при подаче сигнала.

        :param obj1: Первый привязанный объект
        :param obj2: Второй привязанный объект
        :param speed: Скорость выдвижения/втягивания штока (м/с)
        :param min_length: Минимально возможная длина цилиндра (м)
        :param max_length: Максимально возможная длина выдвинутого штока (м)
        :param kwargs: Дополнительные параметры базового класса
        """
        kwargs.setdefault('k', 500000.0)
        kwargs.setdefault('d', 10000.0)
        kwargs.setdefault('yield_limit', float('inf'))
        super().__init__(obj1, obj2, **kwargs)

        self.speed = speed  # Скорость выдвижения штока (м/с)
        self.min_length = min_length
        self.max_length = max_length
        self.activation = 0  # Текущее состояние: -1 (сжатие), 0 (стоп), 1 (выдвижение)

    def update(self, dt: float):
        """
        Обновляет длину штока гидравлики и вызывает расчет сил родительского класса Spring.

        :param dt: Шаг времени симуляции (с)
        """
        # Изменение базовой длины, если гидравлика активна
        if self.activation != 0:
            self.rest_length += self.activation * self.speed * dt
            # Ограничение хода штока цилиндра
            self.rest_length = max(self.min_length, min(self.max_length, self.rest_length))

        # Передается управление стандартной физике пружины
        super().update(dt)


class Beam(Spring):
    def __init__(self, obj1: Object, obj2: Object, **kwargs):
        """
        Инициализация максимально жесткой балки.
        Использует экстремальные коэффициенты жесткости для минимизации деформации.
        Рекомендуется для создания несущих рам, где эластичность не требуется.

        :param obj1: Первый физический узел (Object), к которому привязана балка.
        :param obj2: Второй физический узел (Object), к которому привязана балка.
        :param kwargs: Дополнительные параметры, передаваемые в родительский класс Spring.
                       Позволяет переопределить rest_length, k, d и другие свойства.
        """
        kwargs.setdefault('k', 100000000.0)
        kwargs.setdefault('d', 500000.0)

        kwargs.setdefault('yield_limit', float('inf'))
        kwargs.setdefault('break_limit', 0.99)

        super().__init__(obj1, obj2, **kwargs)

    def update(self, dt: float):
        """
        Обновление состояния балки.

        :param dt: Шаг времени симуляции (в секундах).
        """
        super().update(dt)
