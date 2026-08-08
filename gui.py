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
        self.root.geometry("600x510")
        self.root.resizable(False, False)

        self.core = KeyRebinderCore(status_callback=self.update_status_label)
        self.recording_target = None
        self.tray_icon = None

        self.create_widgets()
        self.update_table()
        self.setup_tray()

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
        is_checked = self.autostart_var.get()
        success = self.core.set_windows_autostart(is_checked)
        if not success:
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
            key_name = self.get_recorded_key_name(event)
            keyboard.unhook(self.on_key_pressed)
            self.root.after(0, lambda: self.finish_recording(key_name))

    def get_recorded_key_name(self, event):
        key_name = event.name.lower()
        scan_code = getattr(event, "scan_code", None)
        is_keypad = getattr(event, "is_keypad", False)

        # GetKeyNameText может вернуть локализованное имя (например,
        # "Стрелка вверх"), поэтому стрелки надёжнее определять по скан-коду.
        arrow_scan_codes = {
            0x48: "up",
            0x50: "down",
            0x4B: "left",
            0x4D: "right",
        }
        if not is_keypad and scan_code in arrow_scan_codes:
            return arrow_scan_codes[scan_code]
        if not is_keypad:
            # Буквы зависят от активной раскладки в event.name. Скан-код же
            # всегда указывает на одну и ту же физическую клавишу.
            physical_key = self.core.rev_key_map.get((scan_code, False))
            return physical_key or self.core.normalize_key_name(key_name)

        keypad_names = {
            **{str(digit): f"numeric {digit}" for digit in range(10)},
            "insert": "numeric 0",
            "end": "numeric 1",
            "down": "numeric 2",
            "page down": "numeric 3",
            "left": "numeric 4",
            "clear": "numeric 5",
            "right": "numeric 6",
            "home": "numeric 7",
            "up": "numeric 8",
            "page up": "numeric 9",
            "delete": "decimal",
            "*": "multiply",
            "+": "add",
            "-": "subtract",
            "/": "divide",
        }
        return keypad_names.get(key_name, self.core.normalize_key_name(key_name))

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
            self.tree.insert("", tk.END, iid=str(idx), values=(rule["process"], rule["from"].upper(), rule["to"].upper()))

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

        # Проверка на дубликат (опционально)
        for rule in self.core.rebind_rules:
            if rule["process"] == proc_name and rule["from"] == self.key_from_value:
                messagebox.showwarning("Внимание", "Правило для данного процесса и клавиши уже существует.")
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
        # Исправлено: берём первый элемент кортежа
        idx = int(selected[0])
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
            
            try:
                self.core.start()
                self.btn_toggle.config(text="СТОП")
                self.update_status_label("Работает (Поиск окна...)", "green")
            except Exception as e:
                self.update_status_label(f"Ошибка: {str(e)}", "red")
                messagebox.showerror("Ошибка", f"Не удалось запустить службу:\n{e}")
                self.btn_toggle.config(text="СТАРТ")
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
