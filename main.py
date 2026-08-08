import threading
import time
import json
import os
import sys
import ctypes
import pygetwindow as gw
import psutil
import win32process
import winreg

def get_dll_path():
    if getattr(sys, 'frozen', False):
        # Запуск из собранного exe
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "interception.dll")

CONFIG_FILE = "config.json"

# --- ПОДКЛЮЧЕНИЕ НИЗКОУРОВНЕВОГО ДРАЙВЕРА ЧЕРЕЗ CTYPES ---
try:
    # Загружаем системную DLL драйвера Interception
    dll_path = get_dll_path()
    interception_dll = ctypes.WinDLL(dll_path)
    
    # Настройка прототипов функций драйвера для стабильности C-типов
    interception_dll.interception_create_context.restype = ctypes.c_void_p

    interception_dll.interception_is_keyboard.argtypes = [ctypes.c_int]
    interception_dll.interception_is_keyboard.restype = ctypes.c_int

    interception_dll.interception_wait.argtypes = [ctypes.c_void_p]
    interception_dll.interception_wait.restype = ctypes.c_int

    interception_dll.interception_set_filter.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    interception_dll.interception_set_filter.restype = None

    interception_dll.interception_receive.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
    interception_dll.interception_receive.restype = ctypes.c_int

    interception_dll.interception_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
    interception_dll.interception_send.restype = ctypes.c_int

    interception_dll.interception_destroy_context.argtypes = [ctypes.c_void_p]
    interception_dll.interception_destroy_context.restype = None
except Exception as e:
    interception_dll = None
    print(f"Ошибка загрузки interception.dll: {e}")

# Структура stroke (сигнал нажатия), которую ожидает драйвер на уровне ядра
class KeyStroke(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("state", ctypes.c_ushort),
        ("information", ctypes.c_uint)
    ]

INTERCEPTION_KEY_E0 = 0x02


class KeyRebinderCore:
    def __init__(self, status_callback):
        self.is_running = False
        self.rebind_rules = []
        self.auto_start = False
        self.monitor_thread = None
        self.status_callback = status_callback
        
        self.active_rules_dict = {} 
        self.load_config()

        # Карта базовых клавиш в виртуальные скан-коды Windows (для драйвера)
        self.key_map = {
            # --- Буквы (строчные) ---
            'a': 0x1E, 'b': 0x30, 'c': 0x2E, 'd': 0x20, 'e': 0x12,
            'f': 0x21, 'g': 0x22, 'h': 0x23, 'i': 0x17, 'j': 0x24,
            'k': 0x25, 'l': 0x26, 'm': 0x32, 'n': 0x31, 'o': 0x18,
            'p': 0x19, 'q': 0x10, 'r': 0x13, 's': 0x1F, 't': 0x14,
            'u': 0x16, 'v': 0x2F, 'w': 0x11, 'x': 0x2D, 'y': 0x15, 'z': 0x2C,

            # --- Цифры и символы верхнего ряда ---
            '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05, '5': 0x06,
            '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A, '0': 0x0B,
            '-': 0x0C, '=': 0x0D,

            # --- Спецсимволы ---
            '[': 0x1A, ']': 0x1B, ';': 0x27, "'": 0x28, '`': 0x29,
            '\\': 0x2B, ',': 0x33, '.': 0x34, '/': 0x35,

            # --- Функциональные ---
            'f1': 0x3B, 'f2': 0x3C, 'f3': 0x3D, 'f4': 0x3E,
            'f5': 0x3F, 'f6': 0x40, 'f7': 0x41, 'f8': 0x42,
            'f9': 0x43, 'f10': 0x44, 'f11': 0x57, 'f12': 0x58,

            # --- Модификаторы ---
            'left ctrl': 0x1D,   'right ctrl': 0x1D,
            'left alt': 0x38,    'right alt': 0x38,
            'left shift': 0x2A,  'right shift': 0x36,
            'caps lock': 0x3A,
            'num lock': 0x45,
            'scroll lock': 0x46,

            # --- Стрелки (отличаются от numpad флагом E0) ---
            'up': 0x48,
            'down': 0x50,
            'left': 0x4B,
            'right': 0x4D,

            # --- Системные ---
            'escape': 0x01, 'tab': 0x0F, 'backspace': 0x0E,
            'enter': 0x1C, 'space': 0x39,
            'print screen': 0xE0,
            'pause': 0xE1,
            'windows': 0xE0,
            'menu': 0xE0,

            # --- Клавиши numpad ---
            'numeric 0': 0x52,
            'numeric 1': 0x4F,
            'numeric 2': 0x50,
            'numeric 3': 0x51,
            'numeric 4': 0x4B,
            'numeric 5': 0x4C,
            'numeric 6': 0x4D,
            'numeric 7': 0x47,
            'numeric 8': 0x48,
            'numeric 9': 0x49,
            'decimal': 0x53,
            'add': 0x4E,
            'subtract': 0x4A,
            'multiply': 0x37,
            'divide': 0x35,
        }

        # У расширенных клавиш скан-код совпадает с клавишей numpad, но выставлен E0.
        self.extended_keys = {
            'up', 'down', 'left', 'right',
            'right ctrl', 'right alt', 'divide',
        }
        self.key_aliases = {
            **{f'num {digit}': f'numeric {digit}' for digit in range(10)},
            # Физические клавиши русской раскладки -> те же клавиши QWERTY.
            **dict(zip(
                'йцукенгшщзхъфывапролджэячсмитьбю',
                'qwertyuiop[]asdfghjkl;\'zxcvbnm,.'
            )),
            'num decimal': 'decimal',
            'num add': 'add',
            'num subtract': 'subtract',
            'num multiply': 'multiply',
            'num divide': 'divide',
            'arrow up': 'up',
            'arrow down': 'down',
            'arrow left': 'left',
            'arrow right': 'right',
            'left ctrl': 'right ctrl',
            'left shift': 'right shift',
            'left alt': 'right alt',
            'стрелка вверх': 'up',
            'стрелка вниз': 'down',
            'стрелка влево': 'left',
            'стрелка вправо': 'right',
            'вверх': 'up',
            'вниз': 'down',
            'влево': 'left',
            'вправо': 'right',
            'левый ctrl': 'right ctrl',
            'левый shift': 'right shift',
            'левый alt': 'right alt'
        }
        # Старые версии GUI не сохраняли признак numpad и записывали эти кнопки
        # просто как цифры. Точное правило всегда имеет приоритет над совместимым.
        self.compatible_source_keys = {
            'up': ('numeric 8', '8'),
            'down': ('numeric 2', '2'),
            'left': ('numeric 4', '4'),
            'right': ('numeric 6', '6'),
            'numeric 8': ('up', '8'),
            'numeric 2': ('down', '2'),
            'numeric 4': ('left', '4'),
            'numeric 6': ('right', '6'),
            'ctrl': ('right ctrl', 'left ctrl')
        }

        # Код без E0 неоднозначен: 0x48 — numpad 8, а (0x48, E0) — стрелка вверх.
        self.rev_key_map = {
            (code, name in self.extended_keys): name
            for name, code in self.key_map.items()
        }

    def normalize_key_name(self, key_name):
        key_name = key_name.strip().lower()
        return self.key_aliases.get(key_name, key_name)

    def get_stroke_key_name(self, stroke):
        signature = (stroke.code, bool(stroke.state & INTERCEPTION_KEY_E0))
        return self.rev_key_map.get(signature, '')

    def find_rebind_target(self, rules, source_key):
        if source_key in rules:
            return rules[source_key], source_key

        for compatible_key in self.compatible_source_keys.get(source_key, ()):
            if compatible_key in rules:
                return rules[compatible_key], compatible_key
        return None, None

    def rebind_stroke(self, stroke, target_key):
        """Меняет код и E0, сохраняя состояние нажатия/отпускания клавиши."""
        target_key = self.normalize_key_name(target_key)
        target_code = self.key_map.get(target_key)
        if target_code is None:
            return False

        stroke.code = target_code
        if target_key in self.extended_keys:
            stroke.state |= INTERCEPTION_KEY_E0
        else:
            stroke.state &= ~INTERCEPTION_KEY_E0
        return True

    def get_active_process_name(self):
        try:
            active_window = gw.getActiveWindow()
            if not active_window:
                return None
            hwnd = active_window._hWnd
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name().lower()
        except Exception:
            return None

    def start(self):
        if not self.is_running:
            if not interception_dll:
                raise RuntimeError("Ошибка: Драйвер interception.dll не найден в системе!")
                
            self.is_running = True
            self.save_config()
            
            # Собираем правила
            self.active_rules_dict = {}
            for rule in self.rebind_rules:
                proc = rule["process"].lower()
                if proc not in self.active_rules_dict:
                    self.active_rules_dict[proc] = {}
                source_key = self.normalize_key_name(rule["from"])
                target_key = self.normalize_key_name(rule["to"])
                self.active_rules_dict[proc][source_key] = target_key

            self.monitor_thread = threading.Thread(target=self.interception_loop, daemon=True)
            self.monitor_thread.start()

    def interception_loop(self):
        context = interception_dll.interception_create_context()
        if not context:
            self.status_callback("Не удалось инициализировать контекст драйвера", "red")
            self.is_running = False
            return

        interception_dll.interception_set_filter(context, interception_dll.interception_is_keyboard, 0xFFFF)
        self.status_callback("Работает (Драйвер ядра активен)", "green")

        stroke = KeyStroke()
        last_process = None

        try:
            while self.is_running:
                try:
                    device = interception_dll.interception_wait(context)
                    if device <= 0:
                        continue

                    received = interception_dll.interception_receive(context, device, ctypes.byref(stroke), 1)
                    if received <= 0:
                        continue

                    if interception_dll.interception_is_keyboard(device):
                        active_process = self.get_active_process_name()

                        if active_process != last_process:
                            if active_process and active_process in self.active_rules_dict:
                                self.status_callback(f"РЕБИНД АКТИВЕН ({active_process})", "blue")
                            else:
                                self.status_callback("Работает (Поиск окна...)", "green")
                            last_process = active_process

                        if active_process and active_process in self.active_rules_dict:
                            # Для стрелок важен не только скан-код, но и флаг E0.
                            key_name = self.get_stroke_key_name(stroke)
                            print(
                                f"[DEBUG] key_name: {key_name}, code: {hex(stroke.code)}, "
                                f"state: {hex(stroke.state)}, info: {hex(stroke.information)}"
                            )

                            process_rules = self.active_rules_dict[active_process]
                            target_key, matched_source = self.find_rebind_target(
                                process_rules, key_name
                            )
                            if target_key and self.rebind_stroke(stroke, target_key):
                                compatibility_note = (
                                    f" (старое имя правила: {matched_source})"
                                    if matched_source != key_name else ""
                                )
                                print(
                                    f"[REBIND] {key_name} -> {target_key}"
                                    f"{compatibility_note}"
                                )
                            elif target_key is None and key_name:
                                print(
                                    f"[NO RULE] Для {key_name} нет правила. "
                                    f"Настроено: {', '.join(process_rules) or 'ничего'}"
                                )
                            elif target_key is not None:
                                print(
                                    f"[UNSUPPORTED TARGET] Неизвестная целевая клавиша: "
                                    f"{target_key!r} (правило {matched_source!r})"
                                )

                        interception_dll.interception_send(context, device, ctypes.byref(stroke), 1)

                except Exception as e:
                    print(f"Ошибка в цикле драйвера: {e}")
                    time.sleep(0.01)

        except Exception as e:
            print(f"Критическая ошибка: {e}")
        finally:
            self.is_running = False
            if context:
                interception_dll.interception_destroy_context(context)

    def stop(self):
        self.is_running = False
        self.save_config()

    # --- Метод автозапуска Windows ---
    def set_windows_autostart(self, enabled):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "AdvancedProcessRebinder"
        if getattr(sys, 'frozen', False):
            app_path = f'"{sys.executable}"'
        else:
            app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
            else:
                try: winreg.DeleteValue(key, app_name)
                except FileNotFoundError: pass
            winreg.CloseKey(key)
            return True
        except Exception: return False

    def is_windows_autostart_enabled(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "AdvancedProcessRebinder"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except Exception: return False

    def save_config(self):
        config_data = {"auto_start": self.is_running, "rules": self.rebind_rules}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception: pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    self.rebind_rules = config_data.get("rules", [])
                    self.auto_start = config_data.get("auto_start", False)
            except Exception:
                self.rebind_rules, self.auto_start = [], False
