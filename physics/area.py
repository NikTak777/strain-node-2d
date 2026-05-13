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


class Area:
    def __init__(self, max_x: float, max_y: float, min_x: float, min_y: float):
        """
        Инициализация области работы физического движка.

        Создает прямоугольную зону, ограничивающую перемещение объектов.
        Автоматически корректирует значения, если перепутаны max и min.

        :param max_x: Верхняя граница по оси X (м)
        :param max_y: Верхняя граница по оси Y (м)
        :param min_x: Нижняя граница по оси X (м)
        :param min_y: Нижняя граница по оси Y (м)
        """
        self.borders = [[max(max_x, min_x), max(max_y, min_y)],
                        [min(max_x, min_x), min(max_y, min_y)]]

    def get_border(self):
        """
        Возвращает список координат границ области.

        :return: Список вида [[max_x, max_y], [min_x, min_y]]
        :rtype: list[list[float]]
        """
        return self.borders

    def is_in_border(self, x: float, y: float, radius: float):
        """
        Проверяет, находится ли объект полностью внутри границ области.

        Учитывает радиус объекта, чтобы он не пересекал границы даже краем.

        :param x: Координата центра объекта по оси X
        :param y: Координата центра объекта по оси Y
        :param radius: Физический радиус объекта
        :return: True, если объект внутри границ, иначе False
        :rtype: bool
        """
        return self.borders[1][0] + radius < x < self.borders[0][0] - radius \
                and self.borders[1][1] + radius < y < self.borders[0][1] - radius
