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

from strainnode2d.core.app import SimulationApp, FPS, WIDTH, HEIGHT, SCALE, WORLD_WIDTH, WORLD_HEIGHT

if __name__ == "__main__": # Запуск приложения
    app = SimulationApp(
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
        scale=SCALE,
        world_width=WORLD_WIDTH,
        world_height=WORLD_HEIGHT,
    )
    app.run() # Запускаем главный цикл