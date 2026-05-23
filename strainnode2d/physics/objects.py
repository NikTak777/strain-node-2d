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


class Object:
    def __init__(self, x: float, y: float, radius: float = 10.0, velocity: list = None, density: float = 7800,
                 restitution: float = 0.75, friction: float = 0.9, color: tuple = (0, 200, 255)):
        """
        Инициализация базового физического объекта (узла).

        :param x: Начальная позиция по оси X (м)
        :param y: Начальная позиция по оси Y (м)
        :param radius: Радиус объекта (м)
        :param velocity: Вектор начальной линейной скорости [vx, vy]
        :param density: Плотность материала (кг/м³)
        :param restitution: Коэффициент восстановления энергии при ударе (прыгучесть, от 0.0 до 1.0).
        :param friction: Коэффициент трения о другие поверхности (от 0.0 до 1.0).
        :param color: Цвет объекта для отрисовки в формате кортежа RGB (R, G, B).
        """
        self.location = [x, y]
        self.velocity = velocity if velocity is not None else [0, 0]
        self.radius = radius
        self.color = color
        self.density = density
        self.Cd = 0.47  # Коэффициент сопротивления (для шара)
        self.restitution = restitution
        self.friction = friction
        self.angle = 0.0  # Угол поворота в радианах
        self.angular_velocity = 0.0  # Угловая скорость (рад/с)

        # Расчет реальной массы и момента инерции сплошного шара
        volume = (4.0 / 3.0) * math.pi * (self.radius ** 3)
        self.mass = self.density * volume
        self.I = 0.4 * self.mass * (self.radius ** 2)  # I = 2/5 * m * r^2

        self.surface = None  # Текстура шара
        self.surface_scale = None
        self.on_ground = False  # Флаг контакта с землей
        self.rolling_resistance = 0.01  # Коэффициент сопротивления качению (0.01 - 0.05)
        self.is_static = False  # Флаг статичного объекта

    def get_location(self):
        """
        Возвращает текущие координаты физического объекта (узла).

        :return: Список из двух чисел [x, y], представляющий положение объекта.
        :rtype: list[float]
        """
        return self.location


class MotorWheel(Object):
    def __init__(self, x: float, y: float, radius: float = 15.0, power: float = 25.0, **kwargs):
        """
        Инициализация моторного колеса (узла с возможностью вращения).

        :param x: Начальная позиция по оси X
        :param y: Начальная позиция по оси Y
        :param radius: Радиус колеса (м)
        :param power: Мощность мотора (ускорение вращения в рад/с²)
        :param kwargs: Дополнительные параметры для базового класса Object
        """
        super().__init__(x, y, radius=radius, **kwargs)

        self.power = power  # Ускорение вращения (рад/с^2)
        self.direction = 0  # Текущее направление: 0 - стоп, 1 - влево (A), -1 - вправо (D)

    def apply_motor(self, dt):
        """
        Прикладывает крутящий момент к колесу, изменяя его угловую скорость.

        :param dt: Шаг времени симуляции (с)
        """
        if self.direction != 0:
            self.angular_velocity += self.direction * self.power * dt


class StructuralNode(Object):
    def __init__(self, x: float, y: float, radius: float = 10.0, **kwargs):
        """
        Структурный узел, обладает бесконечным моментом инерции из-за чего физически не может вращаться.
        """
        # По умолчанию делаем каркас менее прыгучим, чем обычные мячи
        kwargs.setdefault('restitution', 0.1)
        # Трение металла об асфальт (будет скользить)
        kwargs.setdefault('friction', 0.5)

        super().__init__(x, y, radius=radius, **kwargs)
        self.I = float('inf')
        self.angular_velocity = 0.0