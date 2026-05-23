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

import json
from strainnode2d.physics.objects import Object, MotorWheel, StructuralNode
from strainnode2d.physics.springs import Spring, Rope, Hydraulic, Beam, AeroBeam


def save_scene(sim, filename):
    """Сохраняет текущее состояние симуляции в JSON файл."""
    data = {"objects": [], "springs": []}

    # Словарь для быстрого поиска ID объекта по его ссылке в памяти
    obj_to_id = {}

    # 1. Сохраняем объекты
    for i, obj in enumerate(sim.objects):
        obj_to_id[obj] = i  # Запоминаем ID

        obj_data = {
            "id": i,
            "type": obj.__class__.__name__,
            "x": obj.location[0],
            "y": obj.location[1],
            "radius": obj.radius,
            "velocity": obj.velocity.copy(),
            "density": obj.density,
            "restitution": obj.restitution,
            "friction": obj.friction,
            "color": list(obj.color),
            "is_static": getattr(obj, 'is_static', False),
            "angle": obj.angle,
            "angular_velocity": obj.angular_velocity
        }

        # Если это мотор, сохраняем его специфичные свойства
        if isinstance(obj, MotorWheel):
            obj_data["power"] = obj.power

        data["objects"].append(obj_data)

    # 2. Сохраняем пружины
    for spring in sim.springs:
        if spring.is_broken:
            continue

        # Базовые параметры, которые есть у всех балок
        spring_data = {
            "type": spring.__class__.__name__,  # <--- Теперь мы сохраняем тип!
            "obj1_id": obj_to_id[spring.obj1],
            "obj2_id": obj_to_id[spring.obj2],
            "k": spring.k,
            "d": spring.d,
            "yield_limit": spring.yield_limit,
            "break_limit": getattr(spring, 'break_limit', 0.35),
            "rest_length": spring.rest_length
        }

        # Специфичные параметры для гидравлики
        if isinstance(spring, Hydraulic):
            spring_data["speed"] = spring.speed
            spring_data["min_length"] = spring.min_length
            spring_data["max_length"] = spring.max_length

        # Специфичные параметры для аэро-балок
        elif isinstance(spring, AeroBeam):
            spring_data["chord"] = spring.chord
            spring_data["lift_coef"] = spring.lift_coef
            spring_data["base_drag"] = spring.base_drag
            spring_data["induced_drag"] = spring.induced_drag
            spring_data["normal_flip"] = getattr(spring, 'normal_flip', 1)

        data["springs"].append(spring_data)

    # Записываем в файл с красивыми отступами
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_scene(sim, filename):
    """Загружает сцену из JSON файла, полностью заменяя текущую."""
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Очищаем текущую сцену
    sim.objects.clear()
    sim.springs.clear()

    # Словарь для связывания ID из файла с созданными объектами
    id_to_obj = {}

    # 1. Загружаем объекты (без изменений)
    for obj_data in data["objects"]:
        obj_type = obj_data["type"]

        kwargs = {
            "x": obj_data["x"],
            "y": obj_data["y"],
            "radius": obj_data["radius"],
            "velocity": obj_data["velocity"],
            "density": obj_data["density"],
            "restitution": obj_data["restitution"],
            "friction": obj_data["friction"],
            "color": tuple(obj_data["color"])
        }

        if obj_type == "MotorWheel":
            kwargs["power"] = obj_data.get("power", 500.0)
            obj = MotorWheel(**kwargs)
        elif obj_type == "StructuralNode":
            obj = StructuralNode(**kwargs)
        else:
            obj = Object(**kwargs)

        obj.is_static = obj_data.get("is_static", False)
        obj.angle = obj_data.get("angle", 0.0)
        obj.angular_velocity = obj_data.get("angular_velocity", 0.0)

        id_to_obj[obj_data["id"]] = obj
        sim.add_object(obj)

    # 2. Восстанавливаем пружины с учетом их типа
    for spring_data in data["springs"]:
        obj1 = id_to_obj[spring_data["obj1_id"]]
        obj2 = id_to_obj[spring_data["obj2_id"]]

        # Получаем тип. Если это старое сохранение, по умолчанию будет "Spring"
        s_type = spring_data.get("type", "Spring")

        # Собираем общие аргументы
        kwargs = {
            "k": spring_data.get("k", 15000.0),
            "d": spring_data.get("d", 150.0),
            "yield_limit": spring_data.get("yield_limit", float('inf')),
            "break_limit": spring_data.get("break_limit", 0.35)
        }

        # Восстанавливаем сохраненную длину, если она есть
        if "rest_length" in spring_data:
            kwargs["rest_length"] = spring_data["rest_length"]

        # Создаем нужный класс балки
        if s_type == "Rope":
            spring = Rope(obj1, obj2, **kwargs)
        elif s_type == "Beam":
            spring = Beam(obj1, obj2, **kwargs)
        elif s_type == "Hydraulic":
            kwargs["speed"] = spring_data.get("speed", 2.0)
            kwargs["min_length"] = spring_data.get("min_length", 0.5)
            kwargs["max_length"] = spring_data.get("max_length", 5.0)
            spring = Hydraulic(obj1, obj2, **kwargs)
        elif s_type == "AeroBeam":
            kwargs["chord"] = spring_data.get("chord", 1.0)
            kwargs["lift_coef"] = spring_data.get("lift_coef", 1.5)
            kwargs["base_drag"] = spring_data.get("base_drag", 0.1)
            kwargs["induced_drag"] = spring_data.get("induced_drag", 1.0)
            kwargs["normal_flip"] = spring_data.get("normal_flip", 1)
            spring = AeroBeam(obj1, obj2, **kwargs)
        else:
            # Фолбэк на обычную пружину
            spring = Spring(obj1, obj2, **kwargs)

        sim.add_spring(spring)