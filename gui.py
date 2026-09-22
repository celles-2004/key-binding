import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
import threading
from main import KeyRebinderCore, get_running_processes

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw


# --- ЦВЕТОВАЯ ПАЛИТРА ---
BG      = "#eef1f5"
CARD    = "#ffffff"
DARK    = "#2c3e50"
ACCENT  = "#3498db"
GREEN   = "#27ae60"
RED     = "#e74c3c"
BORDER  = "#d7dde4"
MUTED   = "#7f8c8d"

# Отображение клавиш-стрелок в таблице
ARROW_NAMES = {"up": "↑", "down": "↓", "left": "←", "right": "→"}


class RebinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Process Rebinder")
        self.root.geometry("880x740")
        self.root.minsize(640, 520)         # можно свободно тянуть
        self.root.configure(bg=BG)

        self.core = KeyRebinderCore(status_callback=self.update_status_label)
        self.recording_target = None
        self.tray_icon = None

        self._setup_styles()
        self._build_layout()

        self.update_table()
        self.setup_tray()

        if self.core.is_windows_autostart_enabled():
            self.autostart_var.set(True)
        self.admin_var.set(self.core.run_as_admin)

        if self.core.auto_start and self.core.rebind_rules:
            self.root.after(200, self.toggle_service)

    # ============================ СТИЛИ ============================
    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=CARD, foreground=DARK, font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground="white", font=("Segoe UI", 10))
        style.configure("TCheckbutton", background=BG, foreground=DARK, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", BG)])

        style.configure("Treeview",
                        background=CARD, fieldbackground=CARD,
                        foreground=DARK, rowheight=30,
                        font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading",
                        background="#f4f7fa", foreground=DARK,
                        font=("Segoe UI", 10, "bold"), padding=8,
                        borderwidth=0)
        style.map("Treeview.Heading", background=[("active", "#e6ebf1")])
        style.map("Treeview", background=[("selected", ACCENT)],
                              foreground=[("selected", "white")])

    # ============================ ОБЩИЙ КАРКАС ============================
    def _build_layout(self):
        # Корень: 6 строк — header | add_rule | quick | rules | options | footer
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)   # header — фикс.
        self.root.rowconfigure(1, weight=0)   # add_rule — фикс.
        self.root.rowconfigure(2, weight=0)   # quick — фикс.
        self.root.rowconfigure(3, weight=1)   # rules — растягивается
        self.root.rowconfigure(4, weight=0)   # options
        self.root.rowconfigure(5, weight=0)   # footer

        self._build_header()
        self._build_add_rule_card()
        self._build_quick_presets_card()
        self._build_rules_card()
        self._build_options_bar()
        self._build_footer()

    # ============================ ЗАГОЛОВОК ============================
    def _build_header(self):
        header = tk.Frame(self.root, bg=DARK)
        header.grid(row=0, column=0, sticky="nsew")
        header.columnconfigure(0, weight=1)

        tk.Label(header, text="⌨  Advanced Process Rebinder",
                 bg=DARK, fg="white",
                 font=("Segoe UI", 15, "bold"),
                 anchor="w").grid(row=0, column=0, sticky="w", padx=20, pady=14)

        tk.Label(header, text="Драйвер Interception",
                 bg=DARK, fg="#95a5a6",
                 font=("Segoe UI", 9),
                 anchor="e").grid(row=0, column=1, sticky="e", padx=20)

    # ============================ КАРТОЧКА «ДОБАВИТЬ ПРАВИЛО» ============================
    def _build_add_rule_card(self):
        card = tk.Frame(self.root, bg=CARD,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=1, column=0, sticky="ew", padx=15, pady=(15, 8))
        card.columnconfigure(0, weight=1)

        # Заголовок карточки
        head = tk.Frame(card, bg=CARD)
        head.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 0))
        head.columnconfigure(0, weight=1)

        tk.Label(head, text="Добавить правило",
                 bg=CARD, fg=DARK,
                 font=("Segoe UI", 11, "bold"), anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(head, text="Укажите .exe-процесс и клавиши для перепривязки",
                 bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").grid(row=1, column=0, sticky="w", pady=(2, 10))

        # Сетка полей: 4 колонки — процесс | источник | стрелка | цель
        grid = tk.Frame(card, bg=CARD)
        grid.grid(row=1, column=0, sticky="ew", padx=15)
        grid.columnconfigure(0, weight=3, minsize=140)   # процесс
        grid.columnconfigure(1, weight=4, minsize=160)   # источник
        grid.columnconfigure(2, weight=0, minsize=36)    # стрелка
        grid.columnconfigure(3, weight=4, minsize=160)   # цель

        # --- Заголовки колонок ---
        tk.Label(grid, text="Процесс (.exe)", bg=CARD, fg=DARK,
                 font=("Segoe UI", 9, "bold"), anchor="w")\
            .grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Label(grid, text="Нажимается", bg=CARD, fg=DARK,
                 font=("Segoe UI", 9, "bold"), anchor="w")\
            .grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=(0, 4))
        tk.Label(grid, text="Сработает как", bg=CARD, fg=DARK,
                 font=("Segoe UI", 9, "bold"), anchor="w")\
            .grid(row=0, column=3, sticky="ew", padx=(12, 0), pady=(0, 4))

        # --- Поля ---
        proc_cell = tk.Frame(grid, bg=CARD)
        proc_cell.grid(row=1, column=0, sticky="ew")
        proc_cell.columnconfigure(0, weight=1)

        self.process_var = tk.StringVar()
        self.entry_process = ttk.Combobox(proc_cell, textvariable=self.process_var)
        self.entry_process.grid(row=0, column=0, sticky="ew", ipady=4)
        self.process_var.set("notepad.exe")
        self._refresh_process_list()
        self.entry_process.configure(postcommand=self._refresh_process_list)

        self.btn_refresh_proc = tk.Button(
            proc_cell, text="↻", bg="#f4f7fa", fg=DARK,
            activebackground="#e6ebf1",
            relief="flat", bd=1, font=("Segoe UI", 11), cursor="hand2",
            width=3, command=self._refresh_process_list)
        self.btn_refresh_proc.grid(row=0, column=1, sticky="e", padx=(6, 0))

        self.btn_key_from = tk.Button(
            grid, text="● Кликни для записи",
            bg="#f4f7fa", fg=DARK, activebackground="#e6ebf1",
            relief="flat", bd=1, font=("Segoe UI", 10), cursor="hand2",
            command=lambda: self.start_recording("from"))
        self.btn_key_from.grid(row=1, column=1, sticky="ew", padx=(12, 0), ipady=4)
        self.key_from_value = ""

        tk.Label(grid, text="→", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 14, "bold"))\
            .grid(row=1, column=2, sticky="ew")

        self.btn_key_to = tk.Button(
            grid, text="● Кликни для записи",
            bg="#f4f7fa", fg=DARK, activebackground="#e6ebf1",
            relief="flat", bd=1, font=("Segoe UI", 10), cursor="hand2",
            command=lambda: self.start_recording("to"))
        self.btn_key_to.grid(row=1, column=3, sticky="ew", padx=(12, 0), ipady=4)
        self.key_to_value = ""

        # --- Кнопка «Добавить» ---
        btn_row = tk.Frame(card, bg=CARD)
        btn_row.grid(row=2, column=0, sticky="ew", padx=15, pady=(12, 14))
        btn_row.columnconfigure(0, weight=1)

        self.btn_add = tk.Button(
            btn_row, text="+ Добавить правило",
            bg=ACCENT, fg="white",
            activebackground="#2980b9", activeforeground="white",
            relief="flat", font=("Segoe UI", 10, "bold"),
            cursor="hand2", padx=20, pady=6,
            command=self.add_rule)
        self.btn_add.grid(row=0, column=1, sticky="e")

    # ============================ КАРТОЧКА «БЫСТРАЯ ЗАМЕНА» ============================
    def _build_quick_presets_card(self):
        card = tk.Frame(self.root, bg=CARD,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=2, column=0, sticky="ew", padx=15, pady=8)
        card.columnconfigure(0, weight=1)

        row = tk.Frame(card, bg=CARD)
        row.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        tk.Label(row, text="Быстрая замена", bg=CARD, fg=DARK,
                 font=("Segoe UI", 10, "bold"), anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=(0, 12))

        tk.Label(row, text="для процесса выше", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w")\
            .grid(row=0, column=1, sticky="w", padx=(0, 12))

        tk.Button(row, text="WASD → Стрелки", bg=ACCENT, fg="white",
                  activebackground="#2980b9", activeforeground="white",
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2", padx=12, pady=3,
                  command=self.on_quick_wasd_to_arrows)\
            .grid(row=0, column=2, sticky="e", padx=(8, 0))

        tk.Button(row, text="Стрелки → WASD", bg="#f4f7fa", fg=DARK,
                  activebackground="#e6ebf1",
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2", padx=12, pady=3,
                  command=self.on_quick_arrows_to_wasd)\
            .grid(row=0, column=3, sticky="e", padx=(6, 0))

    # ============================ КАРТОЧКА «ПРАВИЛА» ============================
    def _build_rules_card(self):
        card = tk.Frame(self.root, bg=CARD,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=3, column=0, sticky="nsew", padx=15, pady=8)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)   # строка таблицы растягивается

        # Верх: заголовок + счётчик
        top = tk.Frame(card, bg=CARD)
        top.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 6))
        top.columnconfigure(0, weight=1)

        tk.Label(top, text="Активные правила",
                 bg=CARD, fg=DARK,
                 font=("Segoe UI", 11, "bold"), anchor="w")\
            .grid(row=0, column=0, sticky="w")

        self.lbl_rules_count = tk.Label(top, text="0 правил",
                                        bg=CARD, fg=MUTED,
                                        font=("Segoe UI", 9), anchor="e")
        self.lbl_rules_count.grid(row=0, column=1, sticky="e")

        # Таблица + скроллбар
        table_wrap = tk.Frame(card, bg=CARD)
        table_wrap.grid(row=1, column=0, sticky="nsew", padx=15)
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)

        columns = ("key_from", "key_to")
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="tree headings")
        self.tree.heading("#0", text="Процесс (.exe)", anchor="w")
        self.tree.heading("key_from", text="Исходная клавиша", anchor="center")
        self.tree.heading("key_to", text="Новое действие", anchor="center")
        self.tree.column("#0", width=260, anchor="w", stretch=True)
        self.tree.column("key_from", width=180, anchor="center", stretch=True)
        self.tree.column("key_to", width=180, anchor="center", stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        # Низ карточки с кнопками
        bottom = tk.Frame(card, bg=CARD)
        bottom.grid(row=2, column=0, sticky="ew", padx=15, pady=(10, 14))
        bottom.columnconfigure(2, weight=1)

        tk.Button(bottom, text="Удалить выбранное",
                  bg="#f4f7fa", fg=RED,
                  activebackground="#fdecea", activeforeground=RED,
                  relief="flat", font=("Segoe UI", 10),
                  cursor="hand2", padx=14, pady=4,
                  command=self.delete_rule).grid(row=0, column=0, sticky="w")

        tk.Button(bottom, text="Очистить всё",
                  bg="#f4f7fa", fg=MUTED,
                  activebackground="#e6ebf1",
                  relief="flat", font=("Segoe UI", 10),
                  cursor="hand2", padx=14, pady=4,
                  command=self.clear_rules).grid(row=0, column=1, sticky="w", padx=8)

    # ============================ ОПЦИИ ============================
    def _build_options_bar(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.grid(row=4, column=0, sticky="ew", padx=15, pady=(4, 0))
        bar.columnconfigure(2, weight=1)

        self.autostart_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Автозапуск при входе (Планировщик задач)",
                       variable=self.autostart_var,
                       bg=BG, fg=DARK, activebackground=BG,
                       font=("Segoe UI", 10), cursor="hand2",
                       selectcolor="white",
                       command=self.on_autostart_toggle)\
            .grid(row=0, column=0, sticky="w")

        self.admin_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="Запускать от администратора",
                       variable=self.admin_var,
                       bg=BG, fg=DARK, activebackground=BG,
                       font=("Segoe UI", 10), cursor="hand2",
                       selectcolor="white",
                       command=self.on_admin_toggle)\
            .grid(row=0, column=1, sticky="w", padx=(20, 0))

    # ============================ НИЖНЯЯ ПАНЕЛЬ ============================
    def _build_footer(self):
        footer = tk.Frame(self.root, bg=BG)
        footer.grid(row=5, column=0, sticky="ew", padx=15, pady=(8, 15))
        footer.columnconfigure(0, weight=1)

        status_box = tk.Frame(footer, bg=BG)
        status_box.grid(row=0, column=0, sticky="w")

        self.lbl_dot = tk.Label(status_box, text="●", bg=BG, fg=RED,
                                font=("Segoe UI", 14))
        self.lbl_dot.grid(row=0, column=0)

        self.lbl_status = tk.Label(status_box, text="Остановлен",
                                   bg=BG, fg=DARK,
                                   font=("Segoe UI", 10, "bold"))
        self.lbl_status.grid(row=0, column=1, padx=(6, 0))

        self.btn_toggle = tk.Button(footer, text="▶  СТАРТ",
                                    bg=GREEN, fg="white",
                                    activebackground="#1e8449",
                                    activeforeground="white",
                                    relief="flat", font=("Segoe UI", 11, "bold"),
                                    cursor="hand2", padx=30, pady=8,
                                    command=self.toggle_service)
        self.btn_toggle.grid(row=0, column=1, sticky="e")

    # ============================ АВТОЗАПУСК ============================
    def on_autostart_toggle(self):
        enabled = self.autostart_var.get()
        ok, msg = self.core.set_windows_autostart(enabled)
        if not ok:
            self.autostart_var.set(not enabled)
            messagebox.showerror(
                "Ошибка автозапуска",
                "Не удалось изменить задачу в Планировщике задач.\n\n"
                f"{msg}")

    def on_admin_toggle(self):
        enabled = self.admin_var.get()
        ok, msg = self.core.set_run_as_admin(enabled)
        if not ok:
            messagebox.showerror("Ошибка", f"Не удалось обновить задачу:\n{msg}")

    # ============================ ПРОЦЕССЫ ============================
    def _refresh_process_list(self):
        procs = get_running_processes()
        self.entry_process["values"] = procs
        return procs

    # ============================ БЫСТРАЯ ЗАМЕНА ============================
    QUICK_WASD_TO_ARROWS = [
        ("w", "up"), ("a", "left"), ("s", "down"), ("d", "right"),
    ]
    QUICK_ARROWS_TO_WASD = [
        ("up", "w"), ("left", "a"), ("down", "s"), ("right", "d"),
    ]

    def _get_process_from_field(self):
        proc = self.process_var.get().strip().lower()
        if not proc:
            return None
        if not proc.endswith(".exe"):
            proc += ".exe"
        return proc

    def _apply_quick_preset(self, pairs):
        proc = self._get_process_from_field()
        if not proc:
            messagebox.showwarning(
                "Ошибка", "Сначала выберите или введите процесс (.exe).")
            return
        if self.core.is_running:
            messagebox.showwarning(
                "Внимание", "Остановите службу перед изменением правил.")
            return
        existing = {(r["process"], r["from"]) for r in self.core.rebind_rules}
        added = 0
        for src, dst in pairs:
            if (proc, src) in existing:
                continue
            self.core.rebind_rules.append({"process": proc, "from": src, "to": dst})
            added += 1
        if added:
            self.update_table()
            self.core.save_config()
        messagebox.showinfo(
            "Быстрая замена", f"Добавлено правил: {added} для {proc}.")

    def on_quick_wasd_to_arrows(self):
        self._apply_quick_preset(self.QUICK_WASD_TO_ARROWS)

    def on_quick_arrows_to_wasd(self):
        self._apply_quick_preset(self.QUICK_ARROWS_TO_WASD)

    # ============================ ЗАПИСЬ КЛАВИШ ============================
    def start_recording(self, target):
        if self.core.is_running:
            messagebox.showwarning("Внимание", "Остановите службу перед изменением клавиш.")
            return
        self.recording_target = target
        btn = self.btn_key_from if target == "from" else self.btn_key_to
        btn.config(text="● Нажмите клавишу…", bg="#fff3cd", fg="#856404")
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

        arrow_scan_codes = {0x48: "up", 0x50: "down", 0x4B: "left", 0x4D: "right"}
        if not is_keypad and scan_code in arrow_scan_codes:
            return arrow_scan_codes[scan_code]
        if not is_keypad:
            physical_key = self.core.rev_key_map.get((scan_code, False))
            return physical_key or self.core.normalize_key_name(key_name)

        keypad_names = {
            **{str(d): f"numeric {d}" for d in range(10)},
            "insert": "numeric 0", "end": "numeric 1",
            "down": "numeric 2", "page down": "numeric 3",
            "left": "numeric 4", "clear": "numeric 5",
            "right": "numeric 6", "home": "numeric 7",
            "up": "numeric 8", "page up": "numeric 9",
            "delete": "decimal", "*": "multiply",
            "+": "add", "-": "subtract", "/": "divide",
        }
        return keypad_names.get(key_name, self.core.normalize_key_name(key_name))

    def finish_recording(self, key_name):
        btn = None
        if self.recording_target == "from":
            self.key_from_value = key_name
            btn = self.btn_key_from
        elif self.recording_target == "to":
            self.key_to_value = key_name
            btn = self.btn_key_to
        if btn:
            btn.config(text=f"● {key_name.upper()}", bg="#e8f5e9", fg="#1b5e20")
        self.recording_target = None

    # ============================ ТАБЛИЦА ============================
    @staticmethod
    def _plural(n, one, few, many):
        n = abs(n) % 100
        if 11 <= n <= 14:
            return many
        n = n % 10
        if n == 1:
            return one
        if 2 <= n <= 4:
            return few
        return many

    def _fmt_key(self, key):
        key = key.lower()
        if key in ARROW_NAMES:
            return ARROW_NAMES[key]
        if key.startswith("numeric "):
            return "Num" + key[len("numeric "):]
        return key.upper()

    def update_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        groups = {}
        for idx, rule in enumerate(self.core.rebind_rules):
            groups.setdefault(rule["process"], []).append((idx, rule))
        for proc, items in groups.items():
            self.tree.insert("", tk.END, iid=proc, open=True,
                             text=f"{proc}  ({len(items)})",
                             values=("", ""))
            for idx, rule in items:
                self.tree.insert(
                    proc, tk.END, iid=f"{proc}::{idx}", text="",
                    values=(self._fmt_key(rule["from"]),
                            self._fmt_key(rule["to"])))
        n = len(self.core.rebind_rules)
        pc = len(groups)
        self.lbl_rules_count.config(text=(
            f"{pc} {self._plural(pc, 'процесс', 'процесса', 'процессов')} · "
            f"{n} {self._plural(n, 'правило', 'правила', 'правил')}"
        ))

    def add_rule(self):
        proc = self.entry_process.get().strip().lower()
        if not proc:
            messagebox.showwarning("Ошибка", "Введите имя процесса.")
            return
        if not proc.endswith(".exe"):
            proc += ".exe"

        if not self.key_from_value or not self.key_to_value:
            messagebox.showwarning("Ошибка", "Запишите обе клавиши.")
            return

        for rule in self.core.rebind_rules:
            if rule["process"] == proc and rule["from"] == self.key_from_value:
                messagebox.showwarning("Внимание",
                                       "Такое правило уже существует.")
                return

        self.core.rebind_rules.append({
            "process": proc,
            "from": self.key_from_value,
            "to": self.key_to_value,
        })
        self.update_table()
        self.core.save_config()

        self.key_from_value = ""
        self.key_to_value = ""
        self.btn_key_from.config(text="● Кликни для записи", bg="#f4f7fa", fg=DARK)
        self.btn_key_to.config(text="● Кликни для записи", bg="#f4f7fa", fg=DARK)

    def delete_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(
                "Внимание", "Выберите процесс или правило для удаления.")
            return
        iid = selected[0]
        if "::" in iid:
            idx = int(iid.split("::")[1])
            del self.core.rebind_rules[idx]
        else:
            proc = iid
            if not messagebox.askyesno(
                    "Подтверждение",
                    f"Удалить все правила для «{proc}»?"):
                return
            self.core.rebind_rules = [
                r for r in self.core.rebind_rules if r["process"] != proc]
        self.update_table()
        self.core.save_config()

    def clear_rules(self):
        if not self.core.rebind_rules:
            return
        if not messagebox.askyesno("Подтверждение", "Удалить все правила?"):
            return
        self.core.rebind_rules.clear()
        self.update_table()
        self.core.save_config()

    # ============================ СТАТУС И СЛУЖБА ============================
    def update_status_label(self, text, color):
        mapped = {"green": GREEN, "red": RED, "blue": ACCENT}.get(color, DARK)
        self.root.after(0, lambda: self._apply_status(text, mapped))

    def _apply_status(self, text, color):
        self.lbl_dot.config(fg=color)
        self.lbl_status.config(text=text, fg=DARK)

    def toggle_service(self):
        if not self.core.is_running:
            if not self.core.rebind_rules:
                messagebox.showwarning("Ошибка", "Список правил пуст!")
                return
            try:
                self.core.start()
                self.btn_toggle.config(text="■  СТОП", bg=RED,
                                       activebackground="#c0392b")
                self.update_status_label("Работает (ожидание окна)", "green")
            except Exception as e:
                self.update_status_label(f"Ошибка: {e}", "red")
                messagebox.showerror("Ошибка", f"Не удалось запустить службу:\n{e}")
                self.btn_toggle.config(text="▶  СТАРТ", bg=GREEN,
                                       activebackground="#1e8449")
        else:
            self.core.stop()
            self.btn_toggle.config(text="▶  СТАРТ", bg=GREEN,
                                   activebackground="#1e8449")
            self.update_status_label("Остановлен", "red")

    # ============================ ТРЕЙ ============================
    def create_tray_icon(self):
        img = Image.new("RGB", (64, 64), color=DARK)
        dc = ImageDraw.Draw(img)
        dc.rounded_rectangle((10, 18, 54, 46), radius=6, fill=ACCENT)
        dc.rectangle((16, 24, 20, 40), fill="white")
        dc.rectangle((24, 24, 28, 40), fill="white")
        dc.rectangle((32, 24, 36, 40), fill="white")
        dc.rectangle((40, 24, 44, 40), fill="white")
        return img

    def setup_tray(self):
        menu = (
            item("Развернуть", self.show_window, default=True),
            item("Выход", self.quit_app),
        )
        self.tray_icon = pystray.Icon(
            "rebinder", self.create_tray_icon(),
            "Advanced Process Rebinder", menu)
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