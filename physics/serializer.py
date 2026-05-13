import json
from physics.objects import Object, MotorWheel
from physics.springs import Spring


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

        data["springs"].append({
            "obj1_id": obj_to_id[spring.obj1],
            "obj2_id": obj_to_id[spring.obj2],
            "k": spring.k,
            "d": spring.d,
            "yield_limit": spring.yield_limit
        })

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

    # 1. Загружаем объекты
    for obj_data in data["objects"]:
        obj_type = obj_data["type"]

        # Извлекаем общие параметры
        kwargs = {
            "x": obj_data["x"],
            "y": obj_data["y"],
            "radius": obj_data["radius"],
            "velocity": obj_data["velocity"],
            "density": obj_data["density"],
            "restitution": obj_data["restitution"],
            "friction": obj_data["friction"],
            "color": tuple(obj_data["color"])  # Возвращаем кортеж для Pygame
        }

        # Создаем нужный класс
        if obj_type == "MotorWheel":
            kwargs["power"] = obj_data.get("power", 500.0)
            obj = MotorWheel(**kwargs)
        else:
            obj = Object(**kwargs)

        # Восстанавливаем состояние
        obj.is_static = obj_data.get("is_static", False)
        obj.angle = obj_data.get("angle", 0.0)
        obj.angular_velocity = obj_data.get("angular_velocity", 0.0)

        id_to_obj[obj_data["id"]] = obj
        sim.add_object(obj)

    # 2. Восстанавливаем пружины
    for spring_data in data["springs"]:
        obj1 = id_to_obj[spring_data["obj1_id"]]
        obj2 = id_to_obj[spring_data["obj2_id"]]

        spring = Spring(obj1, obj2, k=spring_data["k"], d=spring_data["d"])
        spring.yield_limit = spring_data.get("yield_limit", float('inf'))
        sim.add_spring(spring)