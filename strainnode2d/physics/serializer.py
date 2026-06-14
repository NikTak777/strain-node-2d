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
import math
import os
from strainnode2d.physics.objects import Object, MotorWheel, StructuralNode
from strainnode2d.physics.springs import Spring, Rope, Hydraulic, Beam, AeroBeam


def _sync_spring_rest_length(spring: Spring):
    """Выставляет длину покоя по текущей геометрии (сбрасывает начальное натяжение)."""
    dx = spring.obj2.location[0] - spring.obj1.location[0]
    dy = spring.obj2.location[1] - spring.obj1.location[1]
    spring.rest_length = math.sqrt(dx * dx + dy * dy)
    spring.current_strain = 0.0


def _create_object_from_data(
    obj_data: dict,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    zero_velocity: bool = False,
) -> Object:
    obj_type = obj_data["type"]
    velocity = [0.0, 0.0] if zero_velocity else obj_data["velocity"]

    kwargs = {
        "x": obj_data["x"] + offset_x,
        "y": obj_data["y"] + offset_y,
        "radius": obj_data["radius"],
        "velocity": velocity,
        "density": obj_data["density"],
        "restitution": obj_data["restitution"],
        "friction": obj_data["friction"],
        "color": tuple(obj_data["color"]),
    }

    if obj_type == "MotorWheel":
        kwargs["power"] = obj_data.get("power", 500.0)
        kwargs["max_speed"] = obj_data.get("max_speed", 50.0)
        obj = MotorWheel(**kwargs)
    elif obj_type == "StructuralNode":
        obj = StructuralNode(**kwargs)
    else:
        obj = Object(**kwargs)

    obj.is_static = obj_data.get("is_static", False)
    obj.node_collision_enabled = obj_data.get("node_collision_enabled", True)
    obj.angle = obj_data.get("angle", 0.0)
    obj.angular_velocity = 0.0 if zero_velocity else obj_data.get("angular_velocity", 0.0)
    return obj


def _create_spring_from_data(spring_data: dict, obj1: Object, obj2: Object) -> Spring:
    s_type = spring_data.get("type", "Spring")
    kwargs = {
        "k": spring_data.get("k", 15000.0),
        "d": spring_data.get("d", 150.0),
        "yield_limit": spring_data.get("yield_limit", float("inf")),
        "break_limit": spring_data.get("break_limit", 0.35),
    }
    if "rest_length" in spring_data:
        kwargs["rest_length"] = spring_data["rest_length"]

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
        spring = Spring(obj1, obj2, **kwargs)

    spring.collision_enabled = spring_data.get("collision_enabled", False)
    spring.collision_radius = spring_data.get("collision_radius", 0.08)
    return spring


def snapshot_scene(sim) -> dict:
    """Снимок текущей сцены в память (для быстрого сохранения / восстановления)."""
    data = {"objects": [], "springs": []}
    obj_to_id = {}

    for i, obj in enumerate(sim.objects):
        obj_to_id[obj] = i
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
            "angular_velocity": obj.angular_velocity,
        }
        if not getattr(obj, 'node_collision_enabled', True):
            obj_data["node_collision_enabled"] = False
        if isinstance(obj, MotorWheel):
            obj_data["power"] = obj.power
            obj_data["max_speed"] = obj.max_speed
        data["objects"].append(obj_data)

    for spring in sim.springs:
        if spring.is_broken:
            continue
        spring_data = {
            "type": spring.__class__.__name__,
            "obj1_id": obj_to_id[spring.obj1],
            "obj2_id": obj_to_id[spring.obj2],
            "k": spring.k,
            "d": spring.d,
            "yield_limit": spring.yield_limit,
            "break_limit": getattr(spring, 'break_limit', 0.35),
            "rest_length": spring.rest_length,
        }
        if isinstance(spring, Hydraulic):
            spring_data["speed"] = spring.speed
            spring_data["min_length"] = spring.min_length
            spring_data["max_length"] = spring.max_length
        elif isinstance(spring, AeroBeam):
            spring_data["chord"] = spring.chord
            spring_data["lift_coef"] = spring.lift_coef
            spring_data["base_drag"] = spring.base_drag
            spring_data["induced_drag"] = spring.induced_drag
            spring_data["normal_flip"] = getattr(spring, 'normal_flip', 1)
        if getattr(spring, 'collision_enabled', False):
            spring_data["collision_enabled"] = True
            spring_data["collision_radius"] = spring.collision_radius
        data["springs"].append(spring_data)

    return data


def restore_scene(sim, data: dict):
    """Восстанавливает сцену из снимка, полностью заменяя текущую."""
    sim.objects.clear()
    sim.springs.clear()
    sim.invalidate_collision_springs_cache()
    id_to_obj = {}

    for obj_data in data["objects"]:
        obj = _create_object_from_data(obj_data)
        id_to_obj[obj_data["id"]] = obj
        sim.add_object(obj)

    for spring_data in data["springs"]:
        obj1 = id_to_obj[spring_data["obj1_id"]]
        obj2 = id_to_obj[spring_data["obj2_id"]]
        spring = _create_spring_from_data(spring_data, obj1, obj2)
        sim.add_spring(spring)


def load_prefab_file(filename: str) -> dict:
    """Читает JSON префаба с диска."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def spawn_prefab(sim, data: dict) -> tuple[list, list]:
    """
    Добавляет префаб в текущую сцену на координатах из файла.
    Скорости обнуляются, длины покоя балок синхронизируются с геометрией.
    """
    objects_data = data.get("objects", [])
    if not objects_data:
        return [], []

    id_to_obj = {}
    new_objects = []
    for obj_data in objects_data:
        obj = _create_object_from_data(obj_data, zero_velocity=True)
        id_to_obj[obj_data["id"]] = obj
        sim.add_object(obj)
        new_objects.append(obj)

    new_springs = []
    for spring_data in data.get("springs", []):
        obj1 = id_to_obj[spring_data["obj1_id"]]
        obj2 = id_to_obj[spring_data["obj2_id"]]
        spring = _create_spring_from_data(spring_data, obj1, obj2)
        _sync_spring_rest_length(spring)
        sim.add_spring(spring)
        new_springs.append(spring)

    return new_objects, new_springs


def get_default_prefabs_dir() -> str:
    """Путь к data/prefabs относительно корня проекта."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "data", "prefabs")


def save_scene(sim, filename):
    """Сохраняет текущее состояние симуляции в JSON файл."""
    data = snapshot_scene(sim)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_scene(sim, filename):
    """Загружает сцену из JSON файла, полностью заменяя текущую."""
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    restore_scene(sim, data)