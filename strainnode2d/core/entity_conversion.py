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
from strainnode2d.physics.objects import Object, MotorWheel, StructuralNode
from strainnode2d.physics.springs import Spring, Rope, Hydraulic, Beam, AeroBeam


OBJECT_TYPE_NAMES = ("Object", "MotorWheel", "StructuralNode")
SPRING_TYPE_NAMES = ("Spring", "Rope", "Hydraulic", "Beam", "AeroBeam")

BEAM_DEFAULT_K = 100000000.0
BEAM_DEFAULT_D = 500000.0

_SPRING_TYPE_DEFAULTS = {
    "Spring": {"k": 15000.0, "d": 150.0, "yield_limit": 0.15},
    "Rope": {"k": 150000.0, "d": 500.0, "yield_limit": float("inf")},
    "Hydraulic": {"k": 500000.0, "d": 10000.0, "yield_limit": float("inf")},
    "AeroBeam": {"k": 50000.0, "d": 500.0, "yield_limit": 0.15},
}


def _object_common_kwargs(source: Object) -> dict:
    return {
        "x": source.location[0],
        "y": source.location[1],
        "radius": source.radius,
        "velocity": source.velocity.copy(),
        "density": source.density,
        "restitution": source.restitution,
        "friction": source.friction,
        "color": source.color,
    }


def convert_object_type(source: Object, new_type: str):
    """
    Создаёт узел нового типа с сохранением общих физических параметров.
    Параметры мотора сохраняются при переключении на/с MotorWheel.
    """
    if new_type not in OBJECT_TYPE_NAMES:
        return None
    if new_type == source.__class__.__name__:
        return None

    kwargs = _object_common_kwargs(source)
    power, max_speed, direction = 25.0, 50.0, 0
    if isinstance(source, MotorWheel):
        power = source.power
        max_speed = source.max_speed
        direction = source.direction

    if new_type == "MotorWheel":
        new_obj = MotorWheel(**kwargs, power=power, max_speed=max_speed)
        new_obj.direction = direction
    elif new_type == "StructuralNode":
        new_obj = StructuralNode(**kwargs)
    else:
        new_obj = Object(**kwargs)

    new_obj.is_static = source.is_static
    new_obj.angle = source.angle
    new_obj.surface = None

    if new_type == "StructuralNode":
        new_obj.angular_velocity = 0.0
        new_obj.I = float("inf")
    else:
        new_obj.angular_velocity = source.angular_velocity
        if isinstance(source, StructuralNode):
            volume = (4.0 / 3.0) * math.pi * (new_obj.radius ** 3)
            new_obj.mass = new_obj.density * volume
        new_obj.I = 0.4 * new_obj.mass * (new_obj.radius ** 2)

    return new_obj


def replace_object_in_simulation(sim, old_obj: Object, new_obj: Object):
    """Заменяет узел в симуляции и обновляет ссылки в балках."""
    if old_obj in sim.objects:
        idx = sim.objects.index(old_obj)
        sim.objects[idx] = new_obj
    else:
        sim.objects.remove(old_obj)
        sim.add_object(new_obj)

    for spring in sim.springs:
        if spring.obj1 is old_obj:
            spring.obj1 = new_obj
        if spring.obj2 is old_obj:
            spring.obj2 = new_obj


def convert_spring_type(source: Spring, new_type: str):
    """
    Создаёт балку нового типа, сохраняя общие параметры (k, d, rest_length и т.д.).
    Исключение: Beam при создании всегда получает сверхжёсткие параметры;
    при уходе с Beam механика берётся из дефолтов целевого типа, а не 100M k.
    """
    if new_type not in SPRING_TYPE_NAMES:
        return None
    if new_type == source.__class__.__name__:
        return None

    obj1, obj2 = source.obj1, source.obj2
    rest_length = source.rest_length
    break_limit = source.break_limit
    k, d, yield_limit = source.k, source.d, source.yield_limit

    if new_type == "Beam":
        k = BEAM_DEFAULT_K
        d = BEAM_DEFAULT_D
        yield_limit = float("inf")
        break_limit = 0.99
    elif isinstance(source, Beam):
        defaults = _SPRING_TYPE_DEFAULTS[new_type]
        k = defaults["k"]
        d = defaults["d"]
        yield_limit = defaults["yield_limit"]

    spring_kwargs = {
        "k": k,
        "d": d,
        "rest_length": rest_length,
        "yield_limit": yield_limit,
        "break_limit": break_limit,
    }

    if new_type == "Spring":
        return Spring(obj1, obj2, **spring_kwargs)
    if new_type == "Rope":
        return Rope(obj1, obj2, **spring_kwargs)
    if new_type == "Hydraulic":
        if isinstance(source, Hydraulic):
            speed = source.speed
            min_length = source.min_length
            max_length = source.max_length
        else:
            speed = 2.0
            min_length = min(0.5, rest_length * 0.5)
            max_length = max(rest_length * 2.0, rest_length + 1.0)
        return Hydraulic(obj1, obj2, speed=speed, min_length=min_length, max_length=max_length, **spring_kwargs)
    if new_type == "Beam":
        return Beam(obj1, obj2, **spring_kwargs)
    if new_type == "AeroBeam":
        if isinstance(source, AeroBeam):
            return AeroBeam(
                obj1, obj2,
                chord=source.chord,
                lift_coef=source.lift_coef,
                base_drag=source.base_drag,
                induced_drag=source.induced_drag,
                normal_flip=source.normal_flip,
                **spring_kwargs,
            )
        return AeroBeam(
            obj1, obj2,
            chord=1.0,
            lift_coef=1.0,
            base_drag=0.03,
            induced_drag=0.35,
            **spring_kwargs,
        )
    return None
