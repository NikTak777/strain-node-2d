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

import tkinter as tk
from tkinter import ttk, messagebox
from physics.objects import Object, MotorWheel
from physics.springs import Spring


def show_spawn_dialog():
    """
    Открывает окно для ввода параметров объекта.
    Возвращает словарь с параметрами и типом объекта.
    """
    result = {}

    root = tk.Tk()
    root.title("Спавн объекта")
    root.geometry("340x400")
    root.resizable(False, False)
    root.attributes('-topmost', True)

    # Выпадающий список для выбора типа
    tk.Label(root, text="Тип объекта:", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=15, pady=10, sticky="e")

    type_var = tk.StringVar(value="Обычный узел")
    type_cb = ttk.Combobox(root, textvariable=type_var, state="readonly", width=15)
    type_cb['values'] = ("Обычный узел", "Моторное колесо")
    type_cb.grid(row=0, column=1, padx=15, pady=10)

    # Список полей
    fields = [
        ("Радиус (м):", "radius", "2.0"),
        ("Плотность (кг/м³):", "density", "5000"),
        ("Упругость (0-1):", "restitution", "0.6"),
        ("Трение (0-1):", "friction", "0.4"),
        ("Нач. скорость X:", "vx", "0.0"),
        ("Нач. скорость Y:", "vy", "0.0"),
        ("Вращение (рад/с):", "spin", "0.0"),
        ("Мощность мотора:", "power", "50.0")
    ]

    entries = {}
    for i, (label_text, key, default) in enumerate(fields, start=1):
        lbl = tk.Label(root, text=label_text, font=("Arial", 10))
        lbl.grid(row=i, column=0, padx=15, pady=4, sticky="e")

        entry = tk.Entry(root, font=("Arial", 10), width=18)
        entry.insert(0, default)
        entry.grid(row=i, column=1, padx=15, pady=4)
        entries[key] = entry

    def on_create():
        try:
            result["type"] = type_var.get()  # Сохраняем выбранный тип
            result["radius"] = float(entries["radius"].get())
            result["density"] = float(entries["density"].get())
            result["restitution"] = float(entries["restitution"].get())
            result["friction"] = float(entries["friction"].get())
            result["vx"] = float(entries["vx"].get())
            result["vy"] = float(entries["vy"].get())
            result["spin"] = float(entries["spin"].get())
            result["power"] = float(entries["power"].get())
            result["create"] = True
            root.destroy()
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректные числа!")

    def on_cancel():
        result["create"] = False
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.grid(row=len(fields) + 1, columnspan=2, pady=15)

    tk.Button(btn_frame, text="Отмена", command=on_cancel, width=10, bg="#ff6666").pack(side="left", padx=10)
    tk.Button(btn_frame, text="Создать", command=on_create, width=10, bg="#66ff66").pack(side="left", padx=10)

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()

    return result if result.get("create") else None


def show_edit_dialog(target):
    """
    Открывает окно для редактирования параметров существующего объекта или балки.
    Предзаполняет поля текущими значениями.
    """
    result = {}

    root = tk.Tk()
    if isinstance(target, Object):
        root.title("Редактирование Узла")
    else:
        root.title("Редактирование Балки")

    root.geometry("320x350")
    root.resizable(False, False)
    root.attributes('-topmost', True)

    # Определяет, какие поля показывать в зависимости от типа цели
    fields = []
    if isinstance(target, Object):
        fields = [
            ("Радиус (м):", "radius", str(target.radius)),
            ("Плотность (кг/м³):", "density", str(target.density)),
            ("Упругость (0-1):", "restitution", str(target.restitution)),
            ("Трение (0-1):", "friction", str(target.friction)),
        ]
        # Если это мотор, добавляем мощность
        if isinstance(target, MotorWheel):
            fields.append(("Мощность мотора:", "power", str(target.power)))

    elif isinstance(target, Spring):
        fields = [
            ("Жесткость (k):", "k", str(target.k)),
            ("Демпфирование (d):", "d", str(target.d)),
            ("Предел текучести:", "yield_limit", str(target.yield_limit)),
            ("Длина покоя (м):", "rest_length", str(target.rest_length)),
        ]

    entries = {}
    for i, (label_text, key, default) in enumerate(fields):
        lbl = tk.Label(root, text=label_text, font=("Arial", 10))
        lbl.grid(row=i, column=0, padx=15, pady=6, sticky="e")

        entry = tk.Entry(root, font=("Arial", 10), width=12)
        entry.insert(0, default)
        entry.grid(row=i, column=1, padx=15, pady=6)
        entries[key] = entry

    def on_apply():
        try:
            for _, key, _ in fields:
                result[key] = float(entries[key].get())
            result["apply"] = True
            root.destroy()
        except ValueError:
            messagebox.showerror("Ошибка", "Пожалуйста, введите корректные числа!")

    def on_cancel():
        result["apply"] = False
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.grid(row=len(fields), columnspan=2, pady=15)

    tk.Button(btn_frame, text="Отменить", command=on_cancel, width=10, bg="#ff6666").pack(side="left", padx=10)
    tk.Button(btn_frame, text="Применить", command=on_apply, width=10, bg="#66ff66").pack(side="left", padx=10)

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()

    return result if result.get("apply") else None