import pygame
import random
import sys
import math
import tkinter as tk
from tkinter import messagebox
from physics.area import Area
from physics.objects import Object, MotorWheel
from physics.springs import Spring
from physics.simulation import PhysicSimulation

FPS = 120
SCALE = 20.0
WIDTH, HEIGHT = 1200, 800


class SimulationApp:
    def __init__(self, fps: int = 120, width: int = 1200, height: int = 800, scale: float = 20.0):
        pygame.init()
        pygame.font.init()
        self.fps = fps
        self.width = width
        self.height = height
        self.scale = scale

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("StrainNode2D")

        self.clock = pygame.time.Clock()
        self.running = True
        self.selected_obj = None
        self.dragged_obj = None

        self.font = pygame.font.SysFont("Consolas", 18)

        phys_width = self.width / self.scale
        phys_height = self.height / self.scale
        self.area = Area(0, 0, phys_width, phys_height)
        self.sim = PhysicSimulation(self.area)

    @staticmethod
    def get_ball_surface(obj: Object, scale: float = 20):
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

    @staticmethod
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

    @staticmethod
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

    def handle_events(self, dt: float):
        """Метод сбора и обработки всех нажатий и системных событий."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # Обработка изменения размера окна
            elif event.type == pygame.VIDEORESIZE:
                self.width, self.height = event.w, event.h
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                phys_width = self.width / self.scale
                phys_height = self.height / self.scale
                self.sim.Area = Area(0, 0, phys_width, phys_height)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                phys_mx = mx / self.scale
                phys_my = (self.height - my) / self.scale

                if event.button == 1:
                    clicked_obj = None
                    for obj in self.sim.objects:
                        ox, oy = obj.get_location()
                        dist = math.sqrt((ox - phys_mx) ** 2 + (oy - phys_my) ** 2)
                        if dist <= obj.radius:
                            clicked_obj = obj
                            break

                    if clicked_obj is not None:
                        self.dragged_obj = clicked_obj
                        if self.selected_obj is None:
                            # Выделяем первый шар
                            self.selected_obj = clicked_obj
                        elif self.selected_obj == clicked_obj:
                            # Кликнули на тот же шар повторно — снимаем выделение
                            self.selected_obj = None
                        else:
                            # Кликнули на другой шар — связываем их балкой!
                            # Жесткость k = 25000, демпфирование d = 200
                            new_spring = Spring(self.selected_obj, clicked_obj, k=2500000.0, d=20000.0)
                            self.sim.add_spring(new_spring)
                            self.selected_obj = None  # Сбрасываем выделение
                    else:
                        # Кликнули на пустое место. Спавн объекта со случайными характеристиками
                        if self.selected_obj is not None:
                            # Если что-то было выделено — просто отменяем выбор
                            self.selected_obj = None
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
                            self.sim.add_object(new_obj)

                elif event.button == 2:
                    clicked_obj = None
                    for obj in self.sim.objects:
                        ox, oy = obj.get_location()
                        dist = math.sqrt((ox - phys_mx) ** 2 + (oy - phys_my) ** 2)
                        if dist <= obj.radius:
                            clicked_obj = obj
                            break

                    if clicked_obj is not None:
                        # Переключаем состояние (Заморозить/Разморозить)
                        clicked_obj.is_static = not clicked_obj.is_static

                        # Если заморозили — сразу гасим скорость, чтобы он замер
                        if clicked_obj.is_static:
                            clicked_obj.velocity = [0.0, 0.0]
                            clicked_obj.angular_velocity = 0.0
                        break

                elif event.button == 3:
                    # Сбрасываем выделение, чтобы не мешало
                    self.selected_obj = None
                    data = self.show_spawn_dialog()

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
                        self.sim.add_object(custom_obj)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    if self.dragged_obj and self.dragged_obj.is_static:
                        self.dragged_obj.velocity = [0.0, 0.0]
                        self.dragged_obj.angular_velocity = 0.0
                    self.dragged_obj = None

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_a:
                    for obj in self.sim.objects:
                        if isinstance(obj, MotorWheel):
                            obj.direction = 1
                elif event.key == pygame.K_d:
                    for obj in self.sim.objects:
                        if isinstance(obj, MotorWheel):
                            obj.direction = -1

            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_a, pygame.K_d):
                    for obj in self.sim.objects:
                        if isinstance(obj, MotorWheel):
                            obj.direction = 0

    def update_physics(self, dt: float):
        """Логика перемещения зажатого объекта мышкой и расчет кадра физики."""
        for obj in self.sim.objects:
            if isinstance(obj, MotorWheel):
                obj.apply_motor(dt)

        # Корректируем положение ДО расчета шага физики
        if self.dragged_obj:
            mx, my = pygame.mouse.get_pos()
            phys_mx = mx / SCALE
            phys_my = (self.height - my) / SCALE

            if dt > 0:
                self.dragged_obj.velocity[0] = (phys_mx - self.dragged_obj.location[0]) / dt
                self.dragged_obj.velocity[1] = (phys_my - self.dragged_obj.location[1]) / dt

            self.dragged_obj.location = [phys_mx, phys_my]

        # Шаг физической симуляции
        self.sim.step(dt)

        # Дублируем прижатие ПОСЛЕ расчета шага физики, чтобы убрать дрожание
        if self.dragged_obj:
            mx, my = pygame.mouse.get_pos()
            phys_mx = mx / SCALE
            phys_my = (self.height - my) / SCALE
            self.dragged_obj.location = [phys_mx, phys_my]

    def draw_scene(self):
        """Отрисовывает все графические элементы на экране."""
        self.screen.fill((30, 30, 30))

        # 1. Отрисовка деформируемых пружин-балок
        for spring in self.sim.springs:
            if spring.is_broken:
                continue

            p1_x, p1_y = spring.obj1.get_location()
            p2_x, p2_y = spring.obj2.get_location()

            start_pos = (int(p1_x * SCALE), int(self.height - (p1_y * SCALE)))
            end_pos = (int(p2_x * SCALE), int(self.height - (p2_y * SCALE)))

            strain = spring.current_strain
            factor = min(1.0, abs(strain) / spring.yield_limit)

            if strain > 0:  # Растяжение (Тенденция к красному)
                color = (int(255 * factor), int(255 * (1 - factor)), 0)
            else:  # Сжатие (Тенденция к синему)
                color = (0, int(255 * (1 - factor)), int(255 * factor))

            thickness = max(1, min(8, int(spring.k / 3000)))
            pygame.draw.line(self.screen, color, start_pos, end_pos, thickness)

        # 2. Отрисовка тяжелых узлов
        for obj in self.sim.objects:
            x, y = obj.get_location()
            screen_x = int(x * SCALE)
            screen_y = int(self.height - (y * SCALE))

            surf = self.get_ball_surface(obj)
            draw_radius = surf.get_width() // 2
            self.screen.blit(surf, (screen_x - draw_radius, screen_y - draw_radius))

            surf = self.get_ball_surface(obj)

            angle_degrees = math.degrees(obj.angle)
            rotated_surf = pygame.transform.rotate(surf, angle_degrees)

            rect = rotated_surf.get_rect(center=(screen_x, screen_y))
            self.screen.blit(rotated_surf, rect.topleft)

            if obj.is_static:
                pygame.draw.circle(self.screen, (255, 50, 50), (screen_x, screen_y), 6)
                pygame.draw.circle(self.screen, (0, 0, 0), (screen_x, screen_y), 6, 2)

            if obj == self.selected_obj:
                pygame.draw.circle(self.screen, (255, 215, 0), (screen_x, screen_y), int(obj.radius * SCALE) + 4, 3)

        telemetry = [
            f"Time:    {self.sim.time:.2f}s",
            f"FPS:     {self.clock.get_fps():.0f}",
            f"Nodes:   {len(self.sim.objects)}",
            f"Beams:   {len(self.sim.springs)}",
            "Controls:",
            " - LKM on Node: Select / Link nodes",
            " - LKM on Space: Spawn Random Node",
            " - PKM on Space: Custom Node Dialog"
        ]

        for i, text_line in enumerate(telemetry):
            text_surface = self.font.render(text_line, True, (240, 240, 240))
            self.screen.blit(text_surface, (20, 20 + i * 22))

        pygame.display.flip()

    def run(self):
        """Главный игровой цикл приложения."""
        while self.running:
            dt = self.clock.tick(self.fps) / 1000.0
            dt = min(dt, 0.1)

            self.handle_events(dt)
            self.update_physics(dt)
            self.draw_scene()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    # Запуск приложения
    app = SimulationApp(fps=FPS, width=WIDTH, height=HEIGHT, scale=SCALE)
    app.run()
