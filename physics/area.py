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
    def __init__(self, max_x, max_y, min_x, min_y):
        self.borders = [[max(max_x, min_x), max(max_y, min_y)],
                          [min(max_x, min_x), min(max_y, min_y)]]

    def get_border(self):
        return self.borders

    def is_in_border(self, x, y, radius):
        return self.borders[1][0] + radius < x < self.borders[0][0] - radius \
                and self.borders[1][1] + radius < y < self.borders[0][1] - radius
