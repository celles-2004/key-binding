import threading
import time
import json
import os
import sys
import ctypes
import subprocess
import pygetwindow as gw
import psutil
import win32process

def get_dll_path():
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "interception.dll")

CONFIG_FILE = "config.json"
TASK_NAME = "AdvancedProcessRebinder"

# --- ПОДКЛЮЧЕНИЕ ДРАЙВЕРА INTERCEPTION ---
try:
    dll_path = get_dll_path()
    interception_dll = ctypes.WinDLL(dll_path)

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
        self.run_as_admin = True
        self.monitor_thread = None
        self.status_callback = status_callback
        self.active_rules_dict = {}
        self.load_config()

        self.key_map = {
            'a': 0x1E, 'b': 0x30, 'c': 0x2E, 'd': 0x20, 'e': 0x12,
            'f': 0x21, 'g': 0x22, 'h': 0x23, 'i': 0x17, 'j': 0x24,
            'k': 0x25, 'l': 0x26, 'm': 0x32, 'n': 0x31, 'o': 0x18,
            'p': 0x19, 'q': 0x10, 'r': 0x13, 's': 0x1F, 't': 0x14,
            'u': 0x16, 'v': 0x2F, 'w': 0x11, 'x': 0x2D, 'y': 0x15, 'z': 0x2C,
            '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05, '5': 0x06,
            '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A, '0': 0x0B,
            '-': 0x0C, '=': 0x0D,
            '[': 0x1A, ']': 0x1B, ';': 0x27, "'": 0x28, '`': 0x29,
            '\\': 0x2B, ',': 0x33, '.': 0x34, '/': 0x35,
            'f1': 0x3B, 'f2': 0x3C, 'f3': 0x3D, 'f4': 0x3E,
            'f5': 0x3F, 'f6': 0x40, 'f7': 0x41, 'f8': 0x42,
            'f9': 0x43, 'f10': 0x44, 'f11': 0x57, 'f12': 0x58,
            'left ctrl': 0x1D,   'right ctrl': 0x1D,
            'left alt': 0x38,    'right alt': 0x38,
            'left shift': 0x2A,  'right shift': 0x36,
            'caps lock': 0x3A, 'num lock': 0x45, 'scroll lock': 0x46,
            'up': 0x48, 'down': 0x50, 'left': 0x4B, 'right': 0x4D,
            'escape': 0x01, 'tab': 0x0F, 'backspace': 0x0E,
            'enter': 0x1C, 'space': 0x39,
            'print screen': 0xE0, 'pause': 0xE1,
            'windows': 0xE0, 'menu': 0xE0,
            'numeric 0': 0x52, 'numeric 1': 0x4F, 'numeric 2': 0x50,
            'numeric 3': 0x51, 'numeric 4': 0x4B, 'numeric 5': 0x4C,
            'numeric 6': 0x4D, 'numeric 7': 0x47, 'numeric 8': 0x48,
            'numeric 9': 0x49, 'decimal': 0x53,
            'add': 0x4E, 'subtract': 0x4A, 'multiply': 0x37, 'divide': 0x35,
        }

        self.extended_keys = {
            'up', 'down', 'left', 'right',
            'right ctrl', 'right alt', 'divide',
        }
        self.key_aliases = {
            **{f'num {digit}': f'numeric {digit}' for digit in range(10)},
            **dict(zip(
                'йцукенгшщзхъфывапролджэячсмитьбю',
                'qwertyuiop[]asdfghjkl;\'zxcvbnm,.' 
            )),
            'num decimal': 'decimal', 'num add': 'add',
            'num subtract': 'subtract', 'num multiply': 'multiply',
            'num divide': 'divide',
            'arrow up': 'up', 'arrow down': 'down',
            'arrow left': 'left', 'arrow right': 'right',
            'left ctrl': 'right ctrl',
            'left shift': 'right shift',
            'left alt': 'right alt',
            'стрелка вверх': 'up', 'стрелка вниз': 'down',
            'стрелка влево': 'left', 'стрелка вправо': 'right',
            'вверх': 'up', 'вниз': 'down', 'влево': 'left', 'вправо': 'right',
            'левый ctrl': 'right ctrl',
            'левый shift': 'right shift',
            'левый alt': 'right alt',
        }
        self.compatible_source_keys = {
            'up': ('numeric 8', '8'),
            'down': ('numeric 2', '2'),
            'left': ('numeric 4', '4'),
            'right': ('numeric 6', '6'),
            'numeric 8': ('up', '8'),
            'numeric 2': ('down', '2'),
            'numeric 4': ('left', '4'),
            'numeric 6': ('right', '6'),
            'ctrl': ('right ctrl', 'left ctrl'),
        }
        self.rev_key_map = {
            (code, name in self.extended_keys): name
            for name, code in self.key_map.items()
        }

    # ---------- УТИЛИТЫ КЛАВИШ ----------
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

    # ---------- СЛУЖБА ----------
    def start(self):
        if not self.is_running:
            if not interception_dll:
                raise RuntimeError("Ошибка: драйвер interception.dll не найден!")
            self.is_running = True
            self.save_config()
            self.active_rules_dict = {}
            for rule in self.rebind_rules:
                proc = rule["process"].lower()
                self.active_rules_dict.setdefault(proc, {})
                src = self.normalize_key_name(rule["from"])
                dst = self.normalize_key_name(rule["to"])
                self.active_rules_dict[proc][src] = dst
            self.monitor_thread = threading.Thread(target=self.interception_loop, daemon=True)
            self.monitor_thread.start()

    def interception_loop(self):
        context = interception_dll.interception_create_context()
        if not context:
            self.status_callback("Не удалось создать контекст драйвера", "red")
            self.is_running = False
            return
        interception_dll.interception_set_filter(context, interception_dll.interception_is_keyboard, 0xFFFF)
        self.status_callback("Работает (драйвер ядра активен)", "green")
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
                                self.status_callback(f"РЕБИНД: {active_process}", "blue")
                            else:
                                self.status_callback("Работает (ожидание окна)", "green")
                            last_process = active_process
                        if active_process and active_process in self.active_rules_dict:
                            key_name = self.get_stroke_key_name(stroke)
                            rules = self.active_rules_dict[active_process]
                            target_key, matched = self.find_rebind_target(rules, key_name)
                            if target_key and self.rebind_stroke(stroke, target_key):
                                print(f"[REBIND] {key_name} -> {target_key}")
                            elif target_key is not None:
                                print(f"[UNSUPPORTED TARGET] {target_key!r}")
                        interception_dll.interception_send(context, device, ctypes.byref(stroke), 1)
                except Exception as e:
                    print(f"Ошибка в цикле драйвера: {e}")
                    time.sleep(0.01)
        finally:
            self.is_running = False
            if context:
                interception_dll.interception_destroy_context(context)

    def stop(self):
        self.is_running = False
        self.save_config()

    # ---------- АВТОЗАПУСК ЧЕРЕЗ ПЛАНИРОВЩИК ЗАДАЧ ----------
    def _build_launch_command(self):
        if getattr(sys, 'frozen', False):
            return f'"{sys.executable}"'
        return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

    def _run_schtasks(self, args):
        try:
            r = subprocess.run(
                ["schtasks"] + args,
                capture_output=True, text=True,
                creationflags=0x08000000,   # CREATE_NO_WINDOW
                errors="replace",
            )
            output = ((r.stdout or "") + (r.stderr or "")).strip()
            return r.returncode == 0, output
        except Exception as e:
            return False, str(e)

    def _create_task(self):
        cmd = self._build_launch_command()
        args = [
            "/Create",
            "/TN", TASK_NAME,
            "/TR", cmd,
            "/SC", "ONLOGON",
            "/F",
        ]
        if self.run_as_admin:
            args += ["/RL", "HIGHEST"]
        ok, msg = self._run_schtasks(args)
        if ok:
            self.auto_start = True
            self.save_config()
        return ok, msg

    def _delete_task(self):
        ok, msg = self._run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
        low = msg.lower()
        # Если задачи нет — считаем успехом
        if ok or any(t in low for t in
                     ("не удалось найти", "cannot find", "не найдена", "not found")):
            self.auto_start = False
            self.save_config()
            return True, msg
        return False, msg

    def set_windows_autostart(self, enabled):
        if enabled:
            return self._create_task()
        return self._delete_task()

    def set_run_as_admin(self, enabled):
        self.run_as_admin = enabled
        self.save_config()
        # Пересоздаём задачу, если она уже установлена
        if self.is_windows_autostart_enabled():
            return self._create_task()
        return True, ""

    def is_windows_autostart_enabled(self):
        ok, _ = self._run_schtasks(["/Query", "/TN", TASK_NAME])
        return ok

    # ---------- КОНФИГ ----------
    def save_config(self):
        data = {
            "auto_start": self.auto_start,
            "run_as_admin": self.run_as_admin,
            "rules": self.rebind_rules,
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.rebind_rules = data.get("rules", [])
            self.auto_start = data.get("auto_start", False)
            self.run_as_admin = data.get("run_as_admin", True)
        except Exception:
            self.rebind_rules, self.auto_start, self.run_as_admin = [], False, True