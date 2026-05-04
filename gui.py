import json
import threading
import time
import os
import sys
from tkinter import *
from tkinter import messagebox, ttk
from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Controller as KeyboardController
import ctypes

# ------------------------------------------------------------
#  Права администратора
# ------------------------------------------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def run_as_admin():
    python_exe = sys.executable
    script_path = os.path.abspath(sys.argv[0])
    args = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    command = f'"{script_path}" {args}'.strip()
    ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, command, None, 1)

if not is_admin() and sys.platform == "win32":
    run_as_admin()
    sys.exit(0)

print("Есть права администратора:", is_admin())

try:
    import win32gui
    import win32con
    WINDOWS = True
except ImportError:
    WINDOWS = False
    print("Установите pywin32: pip install pywin32")

# ------------------------------------------------------------
#  Словарь клавиш
# ------------------------------------------------------------
KEY_NAMES = {
    "Пробел": "Key.space", "Enter": "Key.enter", "Tab": "Key.tab",
    "Backspace": "Key.backspace", "Esc": "Key.esc", "Delete": "Key.delete",
    "Insert": "Key.insert", "Home": "Key.home", "End": "Key.end",
    "Page Up": "Key.page_up", "Page Down": "Key.page_down",
    "Стрелка вверх": "Key.up", "Стрелка вниз": "Key.down",
    "Стрелка влево": "Key.left", "Стрелка вправо": "Key.right",
    "Ctrl (левый)": "Key.ctrl_l", "Ctrl (правый)": "Key.ctrl_r",
    "Alt (левый)": "Key.alt_l", "Alt (правый)": "Key.alt_r",
    "Shift (левый)": "Key.shift_l", "Shift (правый)": "Key.shift_r",
    "Caps Lock": "Key.caps_lock", "Print Screen": "Key.print_screen",
    "Scroll Lock": "Key.scroll_lock", "Pause": "Key.pause",
    "Num Lock": "Key.num_lock", "Menu": "Key.menu",
    "F1": "Key.f1", "F2": "Key.f2", "F3": "Key.f3", "F4": "Key.f4",
    "F5": "Key.f5", "F6": "Key.f6", "F7": "Key.f7", "F8": "Key.f8",
    "F9": "Key.f9", "F10": "Key.f10", "F11": "Key.f11", "F12": "Key.f12",
}
REVERSE_NAMES = {v: k for k, v in KEY_NAMES.items()}

def key_to_display(key_str):
    if key_str in REVERSE_NAMES:
        return REVERSE_NAMES[key_str]
    if len(key_str) == 1:
        return key_str.upper()
    return key_str

def display_to_key(display_str):
    if display_str in KEY_NAMES:
        return KEY_NAMES[display_str]
    if len(display_str) == 1:
        return display_str.lower()
    return display_str

def get_visible_windows():
    windows = []
    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append(title)
        return True
    win32gui.EnumWindows(enum_callback, None)
    return windows

# ------------------------------------------------------------
#  Ядро ремаппера
# ------------------------------------------------------------
class KeyRemapperCore:
    def __init__(self, config, global_mode=False):
        self.config = config
        self.global_mode = global_mode
        self.controller = KeyboardController()
        self.listener = None
        self.running = False
        self.capture_mode = False
        self.capture_callback = None
        self.log_callback = None

    def set_log_callback(self, cb):
        self.log_callback = cb

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    def parse_key(self, key_str):
        if key_str.startswith("Key."):
            attr = key_str.split(".")[1].lower()
            if hasattr(Key, attr):
                return getattr(Key, attr)
        if len(key_str) == 1:
            return KeyCode.from_char(key_str)
        raise ValueError(f"Неизвестная клавиша: {key_str}")

    def get_active_window(self):
        if not WINDOWS:
            return ""
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd)
        except:
            return ""

    def on_press(self, key):
        # Режим захвата клавиши
        if self.capture_mode and self.capture_callback:
            try:
                if isinstance(key, Key):
                    key_repr = f"Key.{key.name}"
                elif isinstance(key, KeyCode) and key.char is not None:
                    key_repr = key.char
                else:
                    return False
                cb = self.capture_callback
                self.stop_capture()   # сброс флага ДО вызова
                cb(key_repr)
            except Exception as e:
                self.log(f"Ошибка захвата: {e}")
            return False

        # Нормальная работа ремаппера
        active = self.get_active_window()
        if not active:
            return True

        mapping = None
        if self.global_mode:
            mapping = self.config.get("global", {})
        else:
            for game_name, keymap in self.config.get("games", {}).items():
                if game_name and game_name.lower() in active.lower():
                    mapping = keymap
                    break

        if not mapping:
            return True

        try:
            if isinstance(key, Key):
                key_repr = f"Key.{key.name}"
            elif isinstance(key, KeyCode):
                if key.char is None:
                    return True
                key_repr = key.char
            else:
                return True
        except:
            return True

        if key_repr in mapping:
            target_repr = mapping[key_repr]
            try:
                target_key = self.parse_key(target_repr)
                self.controller.press(target_key)
                time.sleep(0.01)
                self.controller.release(target_key)
                self.log(f"✓ {key_repr} -> {target_repr} в окне '{active}'")
            except Exception as e:
                self.log(f"Ошибка: {e}")
            return False
        return True

    def on_release(self, key):
        return True

    def start(self):
        if self.running:
            return
        self.running = True
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
        mode = "глобальный" if self.global_mode else "по окнам"
        self.log(f"Ремаппер запущен в режиме {mode}")

    def stop(self):
        if not self.running:
            return
        if self.listener:
            self.listener.stop()
        self.running = False
        self.log("Ремаппер остановлен")

    def update_config(self, new_config):
        self.config = new_config

    def set_global_mode(self, enabled):
        self.global_mode = enabled

    def capture_key(self, callback):
        self.capture_mode = True
        self.capture_callback = callback

    def stop_capture(self):
        self.capture_mode = False
        self.capture_callback = None
        
# ------------------------------------------------------------
#  GUI
# ------------------------------------------------------------
class RemapperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Переназначение клавиш для игр")
        self.root.geometry("750x650")
        self.config_file = "keymap_config.json"
        self.config = self.load_config()
        self.global_mode = BooleanVar(value=False)   # галочка глобального режима
        self.remapper = KeyRemapperCore(self.config, global_mode=self.global_mode.get())
        self.remapper.set_log_callback(self.log)

        self.current_game = StringVar()
        self.source_key = StringVar()
        self.target_key = StringVar()

        self.key_choices = list(KEY_NAMES.keys()) + [chr(i) for i in range(ord('a'), ord('z')+1)] + [str(i) for i in range(10)]
        self.key_choices.sort()

        self.create_widgets()
        self.refresh_game_list()
        self.update_active_window_info()
        self.update_status()

    def load_config(self):
        default = {"games": {}, "global": {}}   # добавили глобальный раздел
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "games" not in data:
                    data["games"] = {}
                if "global" not in data:
                    data["global"] = {}
                return data
        except FileNotFoundError:
            self.save_config(default)
            return default
        except json.JSONDecodeError:
            messagebox.showerror("Ошибка", "Конфиг повреждён, создан новый.")
            self.save_config(default)
            return default

    def save_config(self, config=None):
        if config is None:
            config = self.config
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return False

    def log(self, msg):
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, msg + "\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def update_active_window_info(self):
        if WINDOWS:
            try:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                self.active_window_label.config(text=f"Активное окно: {title}")
            except:
                pass
        self.root.after(2000, self.update_active_window_info)

    def create_widgets(self):
        control_frame = Frame(self.root)
        control_frame.pack(fill=X, padx=5, pady=5)

        self.start_btn = Button(control_frame, text="Запустить ремаппер", command=self.start_remapper)
        self.start_btn.pack(side=LEFT, padx=5)
        self.stop_btn = Button(control_frame, text="Остановить ремаппер", command=self.stop_remapper, state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=5)
        self.status_label = Label(control_frame, text="Статус: не запущен", fg="red")
        self.status_label.pack(side=LEFT, padx=20)

        # Галочка глобального режима
        self.global_check = Checkbutton(control_frame, text=" Глобальный режим (для всех окон)", variable=self.global_mode, command=self.toggle_global_mode)
        self.global_check.pack(side=LEFT, padx=10)

        self.active_window_label = Label(control_frame, text="Активное окно: ", fg="blue")
        self.active_window_label.pack(side=RIGHT, padx=10)

        log_frame = LabelFrame(self.root, text="Лог")
        log_frame.pack(fill=X, padx=5, pady=5)
        self.log_text = Text(log_frame, height=8, state=DISABLED)
        self.log_text.pack(fill=BOTH, expand=True, padx=5, pady=5)

        main_pane = PanedWindow(self.root, orient=HORIZONTAL)
        main_pane.pack(fill=BOTH, expand=True, padx=5, pady=5)

        left_frame = Frame(main_pane)
        main_pane.add(left_frame, width=250)
        Label(left_frame, text="Игры (для режима по окнам):").pack(anchor=W)
        self.game_listbox = Listbox(left_frame, height=12)
        self.game_listbox.pack(fill=BOTH, expand=True)
        self.game_listbox.bind("<<ListboxSelect>>", self.on_game_select)
        btn_frame = Frame(left_frame)
        btn_frame.pack(fill=X, pady=5)
        Button(btn_frame, text="Добавить игру", command=self.add_game_dialog).pack(side=LEFT, padx=2)
        Button(btn_frame, text="Удалить", command=self.delete_game).pack(side=LEFT, padx=2)
        Button(btn_frame, text="📋 Окна", command=self.show_windows_list).pack(side=LEFT, padx=2)

        # Добавим отображение глобальных маппингов
        right_frame = Frame(main_pane)
        main_pane.add(right_frame, width=450)
        self.game_title = Label(right_frame, text="Выберите игру или глобальные настройки", font=("Arial", 10, "bold"))
        self.game_title.pack(anchor=W)

        columns = ("Исходная", "Целевая")
        self.tree = ttk.Treeview(right_frame, columns=columns, show="headings", height=10)
        self.tree.heading("Исходная", text="Исходная")
        self.tree.heading("Целевая", text="Целевая")
        self.tree.pack(fill=BOTH, expand=True, pady=5)

        edit_frame = LabelFrame(right_frame, text="Добавить/изменить переназначение")
        edit_frame.pack(fill=X, pady=5)
        row1 = Frame(edit_frame)
        row1.pack(fill=X, padx=5, pady=2)
        Label(row1, text="Исходная:").pack(side=LEFT)
        self.source_combo = ttk.Combobox(row1, textvariable=self.source_key, values=self.key_choices, width=12)
        self.source_combo.pack(side=LEFT, padx=5)
        Button(row1, text="Захватить", command=lambda: self.capture_key("source")).pack(side=LEFT, padx=2)
        Label(row1, text=" -> ").pack(side=LEFT, padx=5)
        Label(row1, text="Целевая:").pack(side=LEFT)
        self.target_combo = ttk.Combobox(row1, textvariable=self.target_key, values=self.key_choices, width=12)
        self.target_combo.pack(side=LEFT, padx=5)
        Button(row1, text="Захватить", command=lambda: self.capture_key("target")).pack(side=LEFT, padx=2)
        Button(row1, text="Добавить", command=self.add_mapping).pack(side=LEFT, padx=5)

        row2 = Frame(edit_frame)
        row2.pack(fill=X, padx=5, pady=2)
        Button(row2, text="Удалить выделенное", command=self.delete_mapping).pack(side=LEFT)
        Button(row2, text="Очистить", command=self.clear_mapping_fields).pack(side=LEFT, padx=5)

        info = "При глобальном режиме переназначения применяются ко всем окнам."
        Label(right_frame, text=info, font=("Arial", 8), fg="gray").pack(anchor=W)
        Button(right_frame, text="Сохранить конфиг", command=self.save_current_config, bg="lightgreen").pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def toggle_global_mode(self):
        enabled = self.global_mode.get()
        self.remapper.set_global_mode(enabled)
        if enabled:
            self.log("Включён глобальный режим (переназначение для всех окон)")
            # Показываем глобальные маппинги в таблице
            self.current_game.set("")
            self.game_title.config(text="Глобальные переназначения (для всех окон)")
            self.refresh_global_mappings()
        else:
            self.log("Выключен глобальный режим, работа по окнам")
            self.refresh_game_list()
            self.game_title.config(text="Выберите игру")
            self.tree.delete(*self.tree.get_children())

    def refresh_global_mappings(self):
        self.tree.delete(*self.tree.get_children())
        for src, dst in self.config.get("global", {}).items():
            self.tree.insert("", END, values=(key_to_display(src), key_to_display(dst)))

    def capture_key(self, field):
        self.was_running = self.remapper.running
        if self.was_running:
            self.remapper.stop()
            self.log("Ремаппер приостановлен для захвата...")
        self.log("Нажмите любую клавишу...")
        # Убедитесь, что capture_mode включается и callback устанавливается
        self.remapper.capture_key(lambda kr: self.root.after(0, lambda: self.on_key_captured(field, kr)))

    def on_key_captured(self, field, key_repr):
        self.remapper.stop_capture()   # это должно сбросить флаги
        if self.was_running:
            self.remapper.start()
        display = key_to_display(key_repr)
        if field == "source":
            self.source_key.set(display)
        else:
            self.target_key.set(display)
        self.log(f"Захвачена: {display}")

    def refresh_game_list(self):
        self.game_listbox.delete(0, END)
        for game in self.config.get("games", {}):
            self.game_listbox.insert(END, game)
        if self.global_mode.get():
            self.refresh_global_mappings()
        else:
            self.tree.delete(*self.tree.get_children())
            self.game_title.config(text="Выберите игру")

    def on_game_select(self, event):
        if self.global_mode.get():
            return
        sel = self.game_listbox.curselection()
        if not sel:
            return
        game = self.game_listbox.get(sel[0])
        self.current_game.set(game)
        self.game_title.config(text=f"Переназначения для: {game}")
        self.tree.delete(*self.tree.get_children())
        for src, dst in self.config["games"].get(game, {}).items():
            self.tree.insert("", END, values=(key_to_display(src), key_to_display(dst)))

    def add_game_dialog(self):
        d = Toplevel(self.root)
        d.title("Добавить игру")
        d.geometry("300x150")
        Label(d, text="Название или часть заголовка:").pack(pady=10)
        e = Entry(d, width=30)
        e.pack(pady=5)
        e.focus()
        def ok():
            name = e.get().strip()
            if name and name not in self.config["games"]:
                self.config["games"][name] = {}
                self.save_config()
                self.refresh_game_list()
                d.destroy()
            else:
                messagebox.showwarning("Ошибка", "Имя пустое или уже есть")
        Button(d, text="OK", command=ok).pack(pady=10)

    def delete_game(self):
        if self.global_mode.get():
            messagebox.showinfo("Инфо", "В глобальном режиме удаление игр недоступно")
            return
        sel = self.game_listbox.curselection()
        if not sel:
            return
        game = self.game_listbox.get(sel[0])
        if messagebox.askyesno("Удалить", f"Удалить игру '{game}'?"):
            del self.config["games"][game]
            self.save_config()
            self.refresh_game_list()

    def show_windows_list(self):
        if not WINDOWS:
            messagebox.showerror("Ошибка", "Установите pywin32")
            return
        wins = get_visible_windows()
        if not wins:
            messagebox.showinfo("Нет окон", "Список пуст")
            return
        d = Toplevel(self.root)
        d.title("Запущенные окна")
        d.geometry("500x400")
        listbox = Listbox(d)
        listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        for w in wins:
            listbox.insert(END, w)
        def add():
            sel = listbox.curselection()
            if not sel:
                return
            title = listbox.get(sel[0])
            if messagebox.askyesno("Добавить", f"Добавить игру с полным названием:\n{title}?"):
                if title not in self.config["games"]:
                    self.config["games"][title] = {}
                    self.save_config()
                    self.refresh_game_list()
                    self.log(f"Добавлена игра: {title}")
                else:
                    messagebox.showinfo("Уже есть", "Такая игра уже в списке")
                d.destroy()
        Button(d, text="Добавить", command=add).pack(pady=5)

    def add_mapping(self):
        if self.global_mode.get():
            # Добавляем в глобальный раздел
            src_disp = self.source_key.get().strip()
            dst_disp = self.target_key.get().strip()
            if not src_disp or not dst_disp:
                messagebox.showwarning("Внимание", "Заполните оба поля")
                return
            src = display_to_key(src_disp)
            dst = display_to_key(dst_disp)
            self.config["global"][src] = dst
            self.save_config()
            self.refresh_global_mappings()
            self.source_key.set("")
            self.target_key.set("")
            self.log(f"Добавлено глобальное: {src_disp} -> {dst_disp}")
        else:
            game = self.current_game.get()
            if not game:
                messagebox.showwarning("Внимание", "Выберите игру")
                return
            src_disp = self.source_key.get().strip()
            dst_disp = self.target_key.get().strip()
            if not src_disp or not dst_disp:
                messagebox.showwarning("Внимание", "Заполните оба поля")
                return
            src = display_to_key(src_disp)
            dst = display_to_key(dst_disp)
            self.config["games"][game][src] = dst
            self.save_config()
            self.refresh_game_list()
            self.on_game_select(None)
            self.source_key.set("")
            self.target_key.set("")
            self.log(f"Добавлено: {src_disp} -> {dst_disp} для '{game}'")

    def delete_mapping(self):
        if self.global_mode.get():
            selected = self.tree.selection()
            if not selected:
                return
            src_disp = self.tree.item(selected[0])["values"][0]
            src = display_to_key(src_disp)
            if messagebox.askyesno("Удалить", f"Удалить глобальное {src_disp}?"):
                del self.config["global"][src]
                self.save_config()
                self.refresh_global_mappings()
        else:
            game = self.current_game.get()
            if not game:
                return
            selected = self.tree.selection()
            if not selected:
                return
            src_disp = self.tree.item(selected[0])["values"][0]
            src = display_to_key(src_disp)
            if messagebox.askyesno("Удалить", f"Удалить {src_disp}?"):
                del self.config["games"][game][src]
                self.save_config()
                self.refresh_game_list()
                self.on_game_select(None)

    def clear_mapping_fields(self):
        self.source_key.set("")
        self.target_key.set("")

    def save_current_config(self):
        if self.save_config():
            messagebox.showinfo("Сохранено", "OK")
            if self.remapper.running:
                self.remapper.update_config(self.config)

    def start_remapper(self):
        if self.remapper.running:
            return
        self.remapper.update_config(self.config)
        self.remapper.set_global_mode(self.global_mode.get())
        self.remapper.start()
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.status_label.config(text="Статус: РАБОТАЕТ", fg="green")

    def stop_remapper(self):
        if not self.remapper.running:
            return
        self.remapper.stop()
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.status_label.config(text="Статус: остановлен", fg="red")

    def update_status(self):
        self.root.after(1000, self.update_status)

    def on_closing(self):
        if self.remapper.running:
            self.remapper.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = Tk()
    app = RemapperGUI(root)
    root.mainloop()