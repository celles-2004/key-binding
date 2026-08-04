import threading
import time
import json
import os
import sys
import keyboard
import pygetwindow as gw
import psutil
import win32process
import winreg

CONFIG_FILE = "config.json"

class KeyRebinderCore:
    def __init__(self, status_callback):
        self.is_running = False
        self.rebind_rules = []
        self.auto_start = False  # Флаг автоматического старта службы (СТАРТ)
        self.monitor_thread = None
        self.status_callback = status_callback
        
        self.load_config()

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
            self.is_running = True
            self.save_config()
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()

    def stop(self):
        self.is_running = False
        self.save_config()
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

    # --- Управление автозагрузкой Windows ---
    def set_windows_autostart(self, enabled):
        """Включает или выключает запуск программы при старте ОС через реестр."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "AdvancedProcessRebinder"
        
        # Получаем полный путь к запущенному .exe или .py файлу
        if getattr(sys, 'frozen', False):
            # Если скомпилировано в .exe через PyInstaller
            app_path = f'"{sys.executable}"'
        else:
            # Если запускается как скрипт .py
            app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Ошибка изменения автозапуска в реестре: {e}")
            return False

    def is_windows_autostart_enabled(self):
        """Проверяет, прописана ли программа в автозагрузке."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "AdvancedProcessRebinder"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    # --- Логика сохранений настроек ---
    def save_config(self):
        config_data = {
            "auto_start": self.is_running,
            "rules": self.rebind_rules
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    self.rebind_rules = config_data.get("rules", [])
                    self.auto_start = config_data.get("auto_start", False)
            except Exception as e:
                print(f"Ошибка загрузки конфига: {e}")
                self.rebind_rules = []
                self.auto_start = False
