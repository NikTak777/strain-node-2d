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


class Camera:
    """
        Модуль управления виртуальной камерой.
    """
    def __init__(self, width: int, height: int):
        self.x = 0.0          # Физическая координата X центра экрана
        self.y = 0.0          # Физическая координата Y центра экрана
        self.zoom = 1.0       # Множитель масштаба (1.0 = нормальный)
        self.target = None         # Узел для слежения
        self.spring_target = None  # Балка для слежения (центр между узлами)
        self.width = width    # Ширина окна
        self.height = height  # Высота окна
        self.focus_x = None   # Точка для разового плавного перелёта
        self.focus_y = None

    def clear_follow(self):
        self.target = None
        self.spring_target = None

    def pan_to(self, x: float, y: float):
        """Запускает быстрый плавный перелёт камеры к точке в мире."""
        self.focus_x = x
        self.focus_y = y
        self.clear_follow()

    def update(self, dt: float):
        """Плавное следование за целью или перелёт к заданной точке."""
        if self.focus_x is not None:
            dx = self.focus_x - self.x
            dy = self.focus_y - self.y
            if dx * dx + dy * dy < 0.04:
                self.x = self.focus_x
                self.y = self.focus_y
                self.focus_x = None
                self.focus_y = None
            else:
                t = min(1.0, 10.0 * dt)
                self.x += dx * t
                self.y += dy * t
            return

        if self.spring_target is not None:
            spring = self.spring_target
            if getattr(spring, 'is_broken', False):
                self.spring_target = None
            else:
                try:
                    x1, y1 = spring.obj1.get_location()
                    x2, y2 = spring.obj2.get_location()
                    tx, ty = (x1 + x2) * 0.5, (y1 + y2) * 0.5
                    self.x += (tx - self.x) * 5.0 * dt
                    self.y += (ty - self.y) * 5.0 * dt
                except AttributeError:
                    self.spring_target = None
            return

        if self.target is not None:
            try:
                tx, ty = self.target.get_location()
                self.x += (tx - self.x) * 5.0 * dt
                self.y += (ty - self.y) * 5.0 * dt
            except AttributeError:
                self.target = None

    def phys_to_screen(self, px: float, py: float, base_scale: float):
        """Перевод физических координат в пиксели на экране с учетом положения камеры и зума."""
        eff_scale = base_scale * self.zoom
        sx = (px - self.x) * eff_scale + self.width / 2
        sy = self.height / 2 - (py - self.y) * eff_scale
        return int(sx), int(sy)

    def screen_to_phys(self, sx: int, sy: int, base_scale: float):
        """Перевод пикселей экрана (клика мыши) обратно в физические координаты мира."""
        eff_scale = base_scale * self.zoom
        px = (sx - self.width / 2) / eff_scale + self.x
        py = self.y - (sy - self.height / 2) / eff_scale
        return px, py