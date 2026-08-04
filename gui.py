import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
from main import KeyRebinderCore

class RebinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Process Rebinder")
        self.root.geometry("600x480")
        self.root.resizable(False, False)

        # Инициализируем логику и передаем метод обновления статуса
        self.core = KeyRebinderCore(status_callback=self.update_status_label)
        self.recording_target = None

        self.create_widgets()
        
        # Дефолтный пример
        self.core.rebind_rules.append({"process": "notepad.exe", "from": "caps lock", "to": "left ctrl"})
        self.update_table()

    def create_widgets(self):
        # --- Блок добавления правила ---
        rule_frame = ttk.LabelFrame(self.root, text=" Добавить новое правило ребинда ", padding=10)
        rule_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(rule_frame, text="Процесс (.exe):").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.entry_process = ttk.Entry(rule_frame, width=15)
        self.entry_process.grid(row=0, column=1, padx=5, pady=2)
        self.entry_process.insert(0, "notepad.exe")

        ttk.Label(rule_frame, text="Нажать клавишу:").grid(row=0, column=2, sticky="w", padx=2, pady=2)
        self.btn_key_from = ttk.Button(rule_frame, text="Кликни для записи", width=18, command=lambda: self.start_recording("from"))
        self.btn_key_from.grid(row=0, column=3, padx=5, pady=2)
        self.key_from_value = ""

        ttk.Label(rule_frame, text="Сработает как:").grid(row=1, column=2, sticky="w", padx=2, pady=2)
        self.btn_key_to = ttk.Button(rule_frame, text="Кликни для записи", width=18, command=lambda: self.start_recording("to"))
        self.btn_key_to.grid(row=1, column=3, padx=5, pady=2)
        self.key_to_value = ""

        # ИСПРАВЛЕНО: заменили fill="x" на sticky="ew"
        btn_add = ttk.Button(rule_frame, text="Добавить правило", command=self.add_rule)
        btn_add.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        # --- Таблица правил ---
        table_frame = ttk.LabelFrame(self.root, text=" Активные правила ", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Конфигурируем сетку, чтобы таблица растягивалась, а колонка с кнопкой — нет
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("process", "key_from", "key_to")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("process", text="Процесс (.exe)")
        self.tree.heading("key_from", text="Исходная клавиша")
        self.tree.heading("key_to", text="Новое действие")
        self.tree.column("process", width=180)
        self.tree.column("key_from", width=180)
        self.tree.column("key_to", width=180)
        self.tree.pack(side="left", fill="both", expand=True)

        # Размещаем таблицу через grid
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Размещаем кнопку по центру правой стороны таблицы
        btn_delete = ttk.Button(table_frame, text="Удалить\nправило", command=self.delete_rule)
        btn_delete.grid(row=0, column=1, sticky="ns", padx=(5, 0))

        # --- Панель управления ---
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_status = ttk.Label(control_frame, text="Статус: Остановлен", font=("Arial", 10, "bold"), foreground="red")
        self.lbl_status.pack(side="left")

        self.btn_toggle = ttk.Button(control_frame, text="СТАРТ", command=self.toggle_service, width=15)
        self.btn_toggle.pack(side="right")

    def start_recording(self, target):
        if self.core.is_running:
            messagebox.showwarning("Внимание", "Остановите службу перед изменением кнопок.")
            return
        
        self.recording_target = target
        if target == "from":
            self.btn_key_from.config(text="[Нажмите клавишу...]")
        else:
            self.btn_key_to.config(text="[Нажмите клавишу...]")
        
        keyboard.hook(self.on_key_pressed)

    def on_key_pressed(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            key_name = event.name
            keyboard.unhook(self.on_key_pressed)
            self.root.after(0, lambda: self.finish_recording(key_name))

    def finish_recording(self, key_name):
        if self.recording_target == "from":
            self.key_from_value = key_name
            self.btn_key_from.config(text=key_name.upper())
        elif self.recording_target == "to":
            self.key_to_value = key_name
            self.btn_key_to.config(text=key_name.upper())
        self.recording_target = None

    def update_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, rule in enumerate(self.core.rebind_rules):
            self.tree.insert("", tk.END, iid=idx, values=(rule["process"], rule["from"].upper(), rule["to"].upper()))

    def add_rule(self):
        proc_name = self.entry_process.get().strip().lower()
        if not proc_name:
            messagebox.showwarning("Ошибка", "Введите имя процесса.")
            return
        if not proc_name.endswith(".exe"):
            proc_name += ".exe"

        if not self.key_from_value or not self.key_to_value:
            messagebox.showwarning("Ошибка", "Запишите обе клавиши для ребинда.")
            return

        self.core.rebind_rules.append({
            "process": proc_name,
            "from": self.key_from_value,
            "to": self.key_to_value
        })
        self.update_table()
        
        self.key_from_value = ""
        self.key_to_value = ""
        self.btn_key_from.config(text="Кликни для записи")
        self.btn_key_to.config(text="Кликни для записи")

    def delete_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите правило из таблицы для удаления.")
            return
        idx = int(selected[0])
        del self.core.rebind_rules[idx]
        self.update_table()

    def update_status_label(self, text, color):
        # Метод для безопасного изменения текста из фонового потока
        self.root.after(0, lambda: self.lbl_status.config(text=f"Статус: {text}", foreground=color))

    def toggle_service(self):
        if not self.core.is_running:
            if not self.core.rebind_rules:
                messagebox.showwarning("Ошибка", "Список правил пуст!")
                return
            
            self.btn_toggle.config(text="СТОП")
            self.update_status_label("Работает (Поиск окна...)", "green")
            self.core.start()
        else:
            self.core.stop()
            self.btn_toggle.config(text="СТАРТ")
            self.update_status_label("Остановлен", "red")

if __name__ == "__main__":
    root = tk.Tk()
    app = RebinderApp(root)
    
    def on_closing():
        app.core.stop()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
