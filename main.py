import threading
import time
import keyboard
import pygetwindow as gw
import psutil
import win32process

class KeyRebinderCore:
    def __init__(self, status_callback):
        self.is_running = False
        self.rebind_rules = []
        self.monitor_thread = None
        self.status_callback = status_callback  # Функция для обновления статуса в GUI

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
        if not self.is_running and self.rebind_rules:
            self.is_running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()

    def stop(self):
        self.is_running = False
        keyboard.unhook_all()

    def monitor_loop(self):
        last_process = None
        rebinds_active = False
        
        while self.is_running:
            active_process = self.get_active_process_name()
            current_rules = [r for r in self.rebind_rules if r["process"] == active_process]

            if current_rules:
                if active_process != last_process or not rebinds_active:
                    keyboard.unhook_all()
                    self.status_callback(f"РЕБИНД АКТИВЕН ({active_process})", "blue")
                    
                    for rule in current_rules:
                        keyboard.remap_key(rule["from"], rule["to"])
                    
                    rebinds_active = True
                    last_process = active_process
            else:
                if rebinds_active:
                    self.status_callback("Работает (Поиск окна...)", "green")
                    keyboard.unhook_all()
                    rebinds_active = False
                    last_process = None

            time.sleep(0.4)
        
        keyboard.unhook_all()
