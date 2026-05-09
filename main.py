import pygame
import random
import sys
import math
import tkinter as tk
from tkinter import messagebox
from physics import VirtualArea, Object, PhysicSimulation

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
        # Делаем края темнее для придания объема
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

    # Первый летящий шар
    obj1 = Object(x=10.0, y=60.0, radius=2.5, velocity=[40.0, 5.0], density=8700.0, restitution=0.5, friction=0.5,
                  color=(0, 180, 255))
    sim.add_object(obj1)

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
                    rand_radius = random.uniform(1.0, 2.5)
                    rand_velocity = [random.uniform(-50, 50), random.uniform(-10, 50)]
                    rand_density = random.uniform(1000, 20000)  # Легкие шары круче подвержены эффекту Магнуса!
                    rand_restitution = random.uniform(0.4, 0.7)
                    rand_friction = random.uniform(0.3, 0.5)  # Разное сцепление
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

                    # Придаем сильную начальную угловую скорость при спавне (от -30 до 30 рад/сек)
                    new_obj.angular_velocity = random.uniform(-30.0, 30.0)

                    sim.add_object(new_obj)

                elif event.button == 3:
                    # Вызываем наше диалоговое окно
                    data = show_spawn_dialog()

                    # Если пользователь заполнил поля и нажал "Создать"
                    if data is not None:
                        # Генерируем красивый цвет для нашего осознанно созданного шара
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

        sim.step(dt)

        # Отрисовка
        screen.fill((25, 25, 30))

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

        # Телеметрия
        font = pygame.font.SysFont("Consolas", 18)
        telemetry = [
            f"Time:  {sim.time:.2f}s",
            f"FPS:   {clock.get_fps():.0f}",
            f"Balls: {len(sim.objects)}",
            f"Main Ball Spin: {obj1.angular_velocity:.1f} rad/s",
            "Click anywhere to spawn spinning balls!"
        ]

        for i, text_line in enumerate(telemetry):
            text_surface = font.render(text_line, True, (240, 240, 240))
            screen.blit(text_surface, (20, 20 + i * 22))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()