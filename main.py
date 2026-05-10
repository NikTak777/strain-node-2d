import pygame
import random
import sys
import math
import tkinter as tk
from tkinter import messagebox
from physics import VirtualArea, Object, PhysicSimulation, Spring

FPS = 120
SCALE = 20.0


def get_ball_surface(obj, scale):
    """
    Генерирует и кэширует красивую градиентную текстуру шара
    с рисунком, чтобы было видно его вращение.
    """
    if obj.surface is not None:
        return obj.surface

    draw_radius = max(3, int(obj.radius * scale))
    surf_size = draw_radius * 2
    surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)

    color = obj.color
    # Отрисовка радиального 3D-градиента (concentric circles)
    for r_offset in range(draw_radius, 0, -1):
        factor = r_offset / draw_radius  # 1 на краю, 0 в центре
        r_c = max(0, min(255, int(color[0] * (1 - factor * 0.5))))
        g_c = max(0, min(255, int(color[1] * (1 - factor * 0.5))))
        b_c = max(0, min(255, int(color[2] * (1 - factor * 0.5))))

        pygame.draw.circle(surf, (r_c, g_c, b_c), (draw_radius, draw_radius), r_offset)

    # Текстурные линии и точки, чтобы видеть вращение
    # 2. Декоративное темное пятно
    dark_spot = (max(0, color[0] - 100), max(0, color[1] - 100), max(0, color[2] - 100))
    pygame.draw.circle(surf, dark_spot, (int(draw_radius * 1.4), int(draw_radius * 1.3)), max(2, draw_radius // 6))
    # 3. Блик света (для эффекта глянца)
    pygame.draw.circle(surf, (255, 255, 255), (int(draw_radius * 0.6), int(draw_radius * 0.6)),
                       max(1, draw_radius // 8))

    obj.surface = surf
    return surf


def show_spawn_dialog():
    """
    Открывает маленькое нативное диалоговое окно для ввода параметров шара.
    Возвращает словарь с параметрами, если нажали 'Создать', или None, если 'Отменить'.
    """
    result = {}

    # Создаем скрытое главное окно, чтобы не плодить лишние элементы
    root = tk.Tk()
    root.title("Параметры нового шара")
    root.geometry("320x350")
    root.resizable(False, False)

    # Помещаем окно поверх остальных
    root.attributes('-topmost', True)

    # Список полей: (Название для пользователя, ключ в словаре, значение по умолчанию)
    fields = [
        ("Радиус (м):", "radius", "2.0"),
        ("Плотность (кг/м³):", "density", "5000"),
        ("Упругость Restitution (0.0 - 1.0):", "restitution", "0.6"),
        ("Трение Friction (0.0 - 1.0):", "friction", "0.4"),
        ("Начальная скорость X (м/с):", "vx", "20.0"),
        ("Начальная скорость Y (м/с):", "vy", "10.0"),
        ("Вращение (рад/с):", "spin", "0.0")
    ]

    entries = {}

    # Сетка для размещения элементов
    for i, (label_text, key, default) in enumerate(fields):
        lbl = tk.Label(root, text=label_text, font=("Arial", 10))
        lbl.grid(row=i, column=0, padx=15, pady=6, sticky="e")

        entry = tk.Entry(root, font=("Arial", 10), width=12)
        entry.insert(0, default)
        entry.grid(row=i, column=1, padx=15, pady=6)
        entries[key] = entry

    def on_create():
        try:
            # Парсим введенные значения и проверяем на ошибки ввода
            result["radius"] = float(entries["radius"].get())
            result["density"] = float(entries["density"].get())
            result["restitution"] = float(entries["restitution"].get())
            result["friction"] = float(entries["friction"].get())
            result["vx"] = float(entries["vx"].get())
            result["vy"] = float(entries["vy"].get())
            result["spin"] = float(entries["spin"].get())
            result["create"] = True
            root.destroy()  # Закрываем окно
        except ValueError:
            messagebox.showerror("Ошибка", "Пожалуйста, введите корректные числа во все поля!")

    def on_cancel():
        result["create"] = False
        root.destroy()

    # Фрейм для кнопок внизу
    btn_frame = tk.Frame(root)
    btn_frame.grid(row=len(fields), columnspan=2, pady=15)

    btn_cancel = tk.Button(btn_frame, text="Отменить", command=on_cancel, width=10, bg="#ff6666")
    btn_cancel.pack(side="left", padx=10)

    btn_create = tk.Button(btn_frame, text="Создать", command=on_create, width=10, bg="#66ff66")
    btn_create.pack(side="left", padx=10)

    # Если пользователь закроет окно на крестик, сработает отмена
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    # Запуск цикла обработки событий окна (блокирует Pygame, пока не закроем)
    root.mainloop()

    return result if result.get("create") else None


def draw_springs(screen, springs, scale, height):
    for spring in springs:
        if spring.is_broken:
            continue

        p1_x, p1_y = spring.obj1.get_location()
        p2_x, p2_y = spring.obj2.get_location()

        # Перевод в экранные координаты
        start_pos = (int(p1_x * scale), int(height - (p1_y * scale)))
        end_pos = (int(p2_x * scale), int(height - (p2_y * scale)))

        # Цветовая индикация деформации (плавно перетекает из зеленого в красный/синий)
        strain = spring.current_strain
        # Нормализуем деформацию относительно предела пластичности
        factor = min(1.0, abs(strain) / spring.yield_limit)

        if strain > 0:  # Растяжение (Тенденция к красному)
            color = (int(255 * factor), int(255 * (1 - factor)), 0)
        else:  # Сжатие (Тенденция к синему)
            color = (0, int(255 * (1 - factor)), int(255 * factor))

        # Толщина линии зависит от упругости (чем жестче балка, тем она толще визуально)
        thickness = max(1, min(8, int(spring.k / 3000)))

        pygame.draw.line(screen, color, start_pos, end_pos, thickness)


def main():
    pygame.init()
    WIDTH, HEIGHT = 1200, 800
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("2D Spin & Magnus Physics Engine")
    clock = pygame.time.Clock()

    phys_width = WIDTH / SCALE
    phys_height = HEIGHT / SCALE

    box = VirtualArea(0, 0, phys_width, phys_height)
    sim = PhysicSimulation(box)

    selected_obj = None

    obj1 = Object(x=4.0, y=4.0, radius=2.0, velocity=[30.0, 0.0], density=200.0, restitution=0.5, friction=0.5,
                  color=(255, 50, 50))
    sim.add_object(obj1)
    obj2 = Object(x=20.0, y=4.0, radius=2.0, velocity=[30.0, 0.0], density=200.0, restitution=0.5, friction=0.5,
                  color=(255, 50, 50))
    sim.add_object(obj2)
    obj3 = Object(x=8.0, y=4.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj3)
    obj4 = Object(x=12.0, y=4.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj4)
    obj5 = Object(x=16.0, y=4.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj5)

    #spring1 = Spring(obj1, obj2, k=25000000.0, d=2000.0)
    #sim.add_spring(spring1)
    spring2 = Spring(obj1, obj3, k=2500000.0, d=20000.0)
    sim.add_spring(spring2)
    spring3 = Spring(obj3, obj4, k=2500000.0, d=20000.0)
    sim.add_spring(spring3)
    spring4 = Spring(obj4, obj5, k=2500000.0, d=20000.0)
    sim.add_spring(spring4)
    spring5 = Spring(obj5, obj2, k=2500000.0, d=20000.0)
    sim.add_spring(spring5)

    obj6 = Object(x=0.0, y=4.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj6)
    spring6 = Spring(obj6, obj1, k=2500000.0, d=20000.0)
    sim.add_spring(spring6)

    obj7 = Object(x=0.0, y=8.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj7)
    spring7 = Spring(obj7, obj6, k=2500000.0, d=20000.0)
    sim.add_spring(spring7)
    spring8 = Spring(obj7, obj1, k=2500000.0, d=20000.0)
    sim.add_spring(spring8)

    obj8 = Object(x=4.0, y=8.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj8)
    spring9 = Spring(obj8, obj1, k=2500000.0, d=20000.0)
    sim.add_spring(spring9)
    spring10 = Spring(obj8, obj6, k=2500000.0, d=20000.0)
    sim.add_spring(spring10)
    spring10 = Spring(obj8, obj7, k=2500000.0, d=20000.0)
    sim.add_spring(spring10)

    obj9 = Object(x=8.0, y=8.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj9)
    spring11 = Spring(obj9, obj1, k=2500000.0, d=20000.0)
    sim.add_spring(spring11)
    spring12 = Spring(obj8, obj9, k=2500000.0, d=20000.0)
    sim.add_spring(spring12)
    spring13 = Spring(obj9, obj3, k=2500000.0, d=20000.0)
    sim.add_spring(spring13)
    spring14 = Spring(obj8, obj3, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)

    obj10 = Object(x=12.0, y=8.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj10)
    spring11 = Spring(obj10, obj3, k=2500000.0, d=20000.0)
    sim.add_spring(spring11)
    spring12 = Spring(obj10, obj9, k=2500000.0, d=20000.0)
    sim.add_spring(spring12)
    spring13 = Spring(obj10, obj4, k=2500000.0, d=20000.0)
    sim.add_spring(spring13)
    spring14 = Spring(obj9, obj4, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)

    obj11 = Object(x=16.0, y=8.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj11)
    spring11 = Spring(obj11, obj4, k=2500000.0, d=20000.0)
    sim.add_spring(spring11)
    spring12 = Spring(obj11, obj10, k=2500000.0, d=20000.0)
    sim.add_spring(spring12)
    spring13 = Spring(obj11, obj5, k=2500000.0, d=20000.0)
    sim.add_spring(spring13)
    spring14 = Spring(obj10, obj5, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)

    obj12 = Object(x=20.0, y=8.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj12)
    spring11 = Spring(obj12, obj5, k=2500000.0, d=20000.0)
    sim.add_spring(spring11)
    spring12 = Spring(obj12, obj11, k=2500000.0, d=20000.0)
    sim.add_spring(spring12)
    spring13 = Spring(obj12, obj2, k=2500000.0, d=20000.0)
    sim.add_spring(spring13)
    spring14 = Spring(obj11, obj2, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)

    obj13 = Object(x=24.0, y=8.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj13)
    obj14 = Object(x=24.0, y=4.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj14)
    spring11 = Spring(obj13, obj12, k=2500000.0, d=20000.0)
    sim.add_spring(spring11)
    spring12 = Spring(obj13, obj14, k=2500000.0, d=20000.0)
    sim.add_spring(spring12)
    spring13 = Spring(obj13, obj2, k=2500000.0, d=20000.0)
    sim.add_spring(spring13)
    spring14 = Spring(obj14, obj2, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)
    spring14 = Spring(obj12, obj14, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)

    obj15 = Object(x=16.0, y=12.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj15)
    spring14 = Spring(obj15, obj12, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)
    spring14 = Spring(obj15, obj11, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)
    #spring14 = Spring(obj15, obj10, k=2500000.0, d=20000.0)
    #sim.add_spring(spring14)

    obj16 = Object(x=12.0, y=12.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj16)
    spring14 = Spring(obj16, obj15, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)
    spring14 = Spring(obj16, obj10, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)
    #spring14 = Spring(obj16, obj11, k=2500000.0, d=20000.0)
    #sim.add_spring(spring14)
    #spring14 = Spring(obj16, obj9, k=2500000.0, d=20000.0)
    #sim.add_spring(spring14)

    obj17 = Object(x=8.0, y=12.0, radius=0.5, velocity=[30.0, 0.0], density=1000.0, restitution=0.5, friction=0.5,
                  color=(50, 50, 255))
    sim.add_object(obj17)
    spring14 = Spring(obj17, obj16, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)
    spring14 = Spring(obj17, obj9, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)
    #spring14 = Spring(obj17, obj10, k=2500000.0, d=20000.0)
    #sim.add_spring(spring14)
    spring14 = Spring(obj17, obj8, k=2500000.0, d=20000.0)
    sim.add_spring(spring14)


    # Первый летящий шар
    #obj1 = Object(x=10.0, y=60.0, radius=2.5, velocity=[40.0, 5.0], density=8700.0, restitution=0.5, friction=0.5,
    #              color=(0, 180, 255))
    #sim.add_object(obj1)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.1)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Обработка изменения размера окна
            elif event.type == pygame.VIDEORESIZE:
                # Обновляем глобальные переменные ширины и высоты
                WIDTH, HEIGHT = event.w, event.h
                # Пересоздаем поверхность окна (Pygame это требует для корректной работы)
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

                # Обновляем границы физического мира (VirtualArea), чтобы шары не улетали за новый экран
                phys_width = WIDTH / SCALE
                phys_height = HEIGHT / SCALE
                sim.Area = VirtualArea(0, 0, phys_width, phys_height)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                phys_mx = mx / SCALE
                phys_my = (HEIGHT - my) / SCALE

                # Спавним легкие упругие шары с сильным случайным закручиванием и скоростью
                if event.button == 1:
                    # Проверяем, кликнули ли мы по существующему объекту
                    clicked_obj = None
                    for obj in sim.objects:
                        ox, oy = obj.get_location()
                        dist = math.sqrt((ox - phys_mx) ** 2 + (oy - phys_my) ** 2)
                        if dist <= obj.radius:
                            clicked_obj = obj
                            break

                    if clicked_obj is not None:
                        # Если кликнули на шар
                        if selected_obj is None:
                            # Выделяем первый шар
                            selected_obj = clicked_obj
                        elif selected_obj == clicked_obj:
                            # Кликнули на тот же шар повторно — снимаем выделение
                            selected_obj = None
                        else:
                            # Кликнули на другой шар — связываем их балкой!
                            # Жесткость k = 25000, демпфирование d = 200 (можно настроить)
                            new_spring = Spring(selected_obj, clicked_obj, k=2500000.0, d=20000.0)
                            sim.add_spring(new_spring)
                            selected_obj = None  # Сбрасываем выделение
                    else:
                        # Кликнули на пустое место
                        if selected_obj is not None:
                            # Если что-то было выделено — просто отменяем выбор
                            selected_obj = None
                        else:
                            # Спавним новый случайный шар
                            rand_radius = random.uniform(1.0, 2.5)
                            rand_velocity = [random.uniform(-50, 50), random.uniform(-10, 50)]
                            rand_density = random.uniform(1000, 20000)
                            rand_restitution = random.uniform(0.4, 0.7)
                            rand_friction = random.uniform(0.3, 0.5)
                            rand_color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))

                            new_obj = Object(
                                x=phys_mx,
                                y=phys_my,
                                radius=rand_radius,
                                velocity=rand_velocity,
                                density=rand_density,
                                restitution=rand_restitution,
                                friction=rand_friction,
                                color=rand_color
                            )
                            new_obj.angular_velocity = random.uniform(-30.0, 30.0)
                            sim.add_object(new_obj)

                    # --- ПРАВАЯ КНОПКА МЫШИ (ПКМ) ---
                elif event.button == 3:
                    # Сбрасываем выделение, чтобы не мешало
                    selected_obj = None
                    data = show_spawn_dialog()

                    if data is not None:
                        custom_color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
                        custom_obj = Object(
                            x=phys_mx,
                            y=phys_my,
                            radius=data["radius"],
                            velocity=[data["vx"], data["vy"]],
                            density=data["density"],
                            restitution=data["restitution"],
                            friction=data["friction"],
                            color=custom_color
                        )
                        custom_obj.angular_velocity = data["spin"]
                        sim.add_object(custom_obj)

        substeps = 10  # Дробим шаг на 10 частей
        sub_dt = dt / substeps
        for _ in range(substeps):
            sim.step(sub_dt)

        # Отрисовка
        screen.fill((25, 25, 30))

        # 1. Сначала рисуем балки (чтобы они визуально находились ПОД шарами)
        draw_springs(screen, sim.springs, SCALE, HEIGHT)

        for obj in sim.objects:
            phys_x, phys_y = obj.get_location()
            screen_x = int(phys_x * SCALE)
            screen_y = int(HEIGHT - (phys_y * SCALE))

            # Получаем базовую текстуру
            ball_surf = get_ball_surface(obj, SCALE)

            # Поворачиваем текстуру на текущий угол (в Pygame углы в градусах и идут против часовой стрелки)
            angle_degrees = math.degrees(obj.angle)
            rotated_surf = pygame.transform.rotate(ball_surf, angle_degrees)

            # Находим новый центр после поворота (так как размеры повёрнутой картинки немного увеличиваются)
            rect = rotated_surf.get_rect(center=(screen_x, screen_y))
            screen.blit(rotated_surf, rect.topleft)

            # Отрисовка подсветки выделенного шара
            if obj == selected_obj:
                # Рисуем красивую толстую желтую ауру вокруг выделенного объекта
                pygame.draw.circle(screen, (255, 215, 0), (screen_x, screen_y), int(obj.radius * SCALE) + 4, 3)

        # Телеметрия
        font = pygame.font.SysFont("Consolas", 18)
        telemetry = [
            f"Time:    {sim.time:.2f}s",
            f"FPS:     {clock.get_fps():.0f}",
            f"Balls:   {len(sim.objects)}",
            f"Springs: {len(sim.springs)}",
            "Controls:",
            " - LKM on Ball: Select/Connect",
            " - LKM on Empty Space: Spawn Random",
            " - PKM on Screen: Custom Spawn Dialog"
        ]

        for i, text_line in enumerate(telemetry):
            text_surface = font.render(text_line, True, (240, 240, 240))
            screen.blit(text_surface, (20, 20 + i * 22))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()