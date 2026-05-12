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
    def __init__(self, x, y, radius: float = 10.0, velocity=[0,0], density=7800, restitution=0.75, friction=0.9, color=(0, 200, 255)):
        self.location = [x, y]
        self.velocity = velocity
        self.radius = radius  # Радиус объекта
        self.color = color  # Цвет объекта
        self.density = density  # Плотность объекта
        self.Cd = 0.47  # Коэффициент сопротивления (для шара)
        self.restitution = restitution  # Коэффициент восстановления энергии (прыгучесть, от 0 до 1)
        self.friction = friction  # Трение о стены (сохранение скорости вдоль стены, от 0 до 1)
        self.angle = 0.0  # Угол поворота в радианах
        self.angular_velocity = 0.0  # Угловая скорость (рад/с)

        # Расчет реальной массы и момента инерции сплошного шара
        volume = (4.0 / 3.0) * math.pi * (self.radius ** 3)
        self.mass = self.density * volume
        self.I = 0.4 * self.mass * (self.radius ** 2)  # I = 2/5 * m * r^2

        self.surface = None  # Текстура шара
        self.on_ground = False  # Флаг контакта с землей
        self.rolling_resistance = 0.01  # Коэффициент сопротивления качению (0.01 - 0.05)
        self.is_static = False  # Флаг статичного объекта

    def get_location(self):
        return self.location


class MotorWheel(Object):
    def __init__(self, x: float, y: float, radius: float = 15.0, power: float = 25.0, **kwargs):
        super().__init__(x, y, radius=radius, **kwargs)

        self.power = power  # Ускорение вращения (рад/с^2)
        self.direction = 0  # 0 - стоп, 1 - влево (A), -1 - вправо (D)

        self.friction = 0.95

    def apply_motor(self, dt):
        """Раскручивает колесо, если включен мотор"""
        if self.direction != 0:
            self.angular_velocity += self.direction * self.power * dt