import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
import threading
from main import KeyRebinderCore

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

class RebinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Process Rebinder")
        self.root.geometry("600x510")  # Слегка увеличили высоту под галочку
        self.root.resizable(False, False)

        self.core = KeyRebinderCore(status_callback=self.update_status_label)
        self.recording_target = None
        self.tray_icon = None

        self.create_widgets()
        self.update_table()
        self.setup_tray()

        # Восстанавливаем состояние галочки автозапуска Windows из реестра
        if self.core.is_windows_autostart_enabled():
            self.autostart_var.set(True)

        # Автостарт службы мониторинга, если она была активна
        if self.core.auto_start and self.core.rebind_rules:
            self.root.after(100, self.toggle_service)

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

        btn_add = ttk.Button(rule_frame, text="Добавить правило", command=self.add_rule)
        btn_add.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        # --- Таблица правил ---
        table_frame = ttk.LabelFrame(self.root, text=" Активные правила ", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("process", "key_from", "key_to")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("process", text="Процесс (.exe)")
        self.tree.heading("key_from", text="Исходная клавиша")
        self.tree.heading("key_to", text="Новое действие")
        self.tree.column("process", width=160)
        self.tree.column("key_from", width=160)
        self.tree.column("key_to", width=160)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        btn_delete = ttk.Button(table_frame, text="Удалить\nправило", command=self.delete_rule)
        btn_delete.grid(row=0, column=1, sticky="ns", padx=(5, 0))

        # --- Блок системных опций ---
        options_frame = ttk.Frame(self.root, padding=(10, 0, 10, 0))
        options_frame.pack(fill="x")
        
        self.autostart_var = tk.BooleanVar(value=False)
        chk_autostart = ttk.Checkbutton(
            options_frame, 
            text="Автозапуск вместе с Windows", 
            variable=self.autostart_var, 
            command=self.on_autostart_toggle
        )
        chk_autostart.pack(side="left")

        # --- Панель управления ---
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_status = ttk.Label(control_frame, text="Статус: Остановлен", font=("Arial", 10, "bold"), foreground="red")
        self.lbl_status.pack(side="left")

        self.btn_toggle = ttk.Button(control_frame, text="СТАРТ", command=self.toggle_service, width=15)
        self.btn_toggle.pack(side="right")

    def on_autostart_toggle(self):
        """Срабатывает при клике на чекбокс автозапуска Windows."""
        is_checked = self.autostart_var.get()
        success = self.core.set_windows_autostart(is_checked)
        if not success:
            # На случай сбоя доступа к реестру возвращаем галочку обратно
            self.autostart_var.set(not is_checked)
            messagebox.showerror("Ошибка", "Не удалось изменить настройки автозапуска в реестре.")

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
        self.core.save_config()
        
        self.key_from_value = ""
        self.key_to_value = ""
        self.btn_key_from.config(text="Кликни для записи")
        self.btn_key_to.config(text="Кликни для записи")

    def delete_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите правило из таблицы для удаления.")
            return
        idx = int(selected)
        del self.core.rebind_rules[idx]
        self.update_table()
        self.core.save_config()

    def update_status_label(self, text, color):
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

    def create_tray_icon(self):
        image = Image.new('RGB', (64, 64), color='white')
        dc = ImageDraw.Draw(image)
        dc.rectangle((10, 10, 54, 54), fill='blue')
        dc.ellipse((20, 20, 44, 44), fill='lightblue')
        return image

    def setup_tray(self):
        menu = (
            item('Развернуть', self.show_window, default=True),
            item('Выход', self.quit_app)
        )
        self.tray_icon = pystray.Icon("binder_icon", self.create_tray_icon(), "Key Rebinder", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def withdraw_window(self):
        self.root.withdraw()

    def show_window(self):
        self.root.after(0, self.root.deiconify)

    def quit_app(self):
        self.core.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

if __name__ == "__main__":
    root = tk.Tk()
    app = RebinderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.withdraw_window)
    root.mainloop()
