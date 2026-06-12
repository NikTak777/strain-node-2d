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

from strainnode2d.physics.objects import Object, MotorWheel, StructuralNode
from strainnode2d.physics.springs import Spring, Rope, Hydraulic, Beam, AeroBeam


def snapshot_node(node: Object, cx: float, cy: float) -> dict:
    data = {
        "class": node.__class__,
        "rel_x": node.location[0] - cx,
        "rel_y": node.location[1] - cy,
        "radius": node.radius,
        "density": node.density,
        "restitution": node.restitution,
        "friction": node.friction,
        "color": node.color,
        "is_static": getattr(node, "is_static", False),
        "angle": node.angle,
    }
    if isinstance(node, MotorWheel):
        data["power"] = node.power
        data["max_speed"] = node.max_speed
    return data


def snapshot_spring(spring: Spring, id1: int, id2: int) -> dict:
    data = {
        "class": spring.__class__,
        "id1": id1,
        "id2": id2,
        "k": spring.k,
        "d": spring.d,
        "yield_limit": spring.yield_limit,
        "break_limit": spring.break_limit,
        "rest_length": spring.rest_length,
    }
    if isinstance(spring, Hydraulic):
        data["speed"] = spring.speed
        data["min_length"] = spring.min_length
        data["max_length"] = spring.max_length
    elif isinstance(spring, AeroBeam):
        data["chord"] = spring.chord
        data["lift_coef"] = spring.lift_coef
        data["base_drag"] = spring.base_drag
        data["induced_drag"] = spring.induced_drag
        data["normal_flip"] = getattr(spring, "normal_flip", 1)
    return data


def snapshot_selection(nodes: list, springs: list) -> dict:
    if not nodes:
        return {"nodes": [], "springs": []}

    cx = sum(n.location[0] for n in nodes) / len(nodes)
    cy = sum(n.location[1] for n in nodes) / len(nodes)
    node_to_id = {node: i for i, node in enumerate(nodes)}

    clipboard_nodes = [snapshot_node(node, cx, cy) for node in nodes]
    clipboard_springs = []
    for spring in springs:
        if spring.is_broken:
            continue
        if spring.obj1 in node_to_id and spring.obj2 in node_to_id:
            clipboard_springs.append(
                snapshot_spring(spring, node_to_id[spring.obj1], node_to_id[spring.obj2])
            )

    return {"nodes": clipboard_nodes, "springs": clipboard_springs}


def instantiate_node(node_data: dict, anchor_x: float, anchor_y: float) -> Object:
    target_class = node_data["class"]
    kwargs = {
        "x": anchor_x + node_data["rel_x"],
        "y": anchor_y + node_data["rel_y"],
        "radius": node_data["radius"],
        "velocity": [0.0, 0.0],
        "density": node_data["density"],
        "restitution": node_data["restitution"],
        "friction": node_data["friction"],
        "color": node_data["color"],
    }
    if issubclass(target_class, MotorWheel):
        kwargs["power"] = node_data.get("power", 25.0)
        kwargs["max_speed"] = node_data.get("max_speed", 50.0)
        new_obj = MotorWheel(**kwargs)
    elif issubclass(target_class, StructuralNode):
        new_obj = StructuralNode(**kwargs)
    else:
        new_obj = Object(**kwargs)

    new_obj.is_static = node_data.get("is_static", False)
    new_obj.angle = node_data.get("angle", 0.0)
    new_obj.angular_velocity = 0.0
    return new_obj


def instantiate_spring(spring_data: dict, obj1: Object, obj2: Object) -> Spring:
    target_class = spring_data["class"]
    kwargs = {
        "k": spring_data["k"],
        "d": spring_data["d"],
        "yield_limit": spring_data["yield_limit"],
        "break_limit": spring_data["break_limit"],
        "rest_length": spring_data["rest_length"],
    }

    if issubclass(target_class, Hydraulic):
        kwargs["speed"] = spring_data.get("speed", 2.0)
        kwargs["min_length"] = spring_data.get("min_length", 0.5)
        kwargs["max_length"] = spring_data.get("max_length", 5.0)
        return Hydraulic(obj1, obj2, **kwargs)

    if issubclass(target_class, AeroBeam):
        kwargs["chord"] = spring_data.get("chord", 1.0)
        kwargs["lift_coef"] = spring_data.get("lift_coef", 1.0)
        kwargs["base_drag"] = spring_data.get("base_drag", 0.03)
        kwargs["induced_drag"] = spring_data.get("induced_drag", 0.35)
        kwargs["normal_flip"] = spring_data.get("normal_flip", 1)
        return AeroBeam(obj1, obj2, **kwargs)

    if issubclass(target_class, Rope):
        return Rope(obj1, obj2, **kwargs)
    if issubclass(target_class, Beam):
        return Beam(obj1, obj2, **kwargs)
    return Spring(obj1, obj2, **kwargs)


def paste_clipboard(clipboard: dict, anchor_x: float, anchor_y: float) -> tuple[list, list]:
    new_nodes = [
        instantiate_node(node_data, anchor_x, anchor_y)
        for node_data in clipboard.get("nodes", [])
    ]
    new_springs = []
    for spring_data in clipboard.get("springs", []):
        obj1 = new_nodes[spring_data["id1"]]
        obj2 = new_nodes[spring_data["id2"]]
        new_springs.append(instantiate_spring(spring_data, obj1, obj2))
    return new_nodes, new_springs
