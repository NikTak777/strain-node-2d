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
        self.target = None    # Объект для слежения
        self.width = width    # Ширина окна
        self.height = height  # Высота окна

    def update(self, dt: float):
        """Плавное следование за целью, если она задана."""
        if self.target is not None:
            try:
                tx, ty = self.target.get_location()
                # Плавная интерполяция движения (Lerp)
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