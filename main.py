import json
import sys
import time
from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Controller as KeyboardController

# Попытка импорта Windows‑специфичных модулей
try:
    import win32gui
    import win32process
    import psutil
    WINDOWS = True
except ImportError:
    WINDOWS = False
    print("Предупреждение: для определения активного окна нужны 'pywin32' и 'psutil'.")
    print("Установите: pip install pywin32 psutil")
    sys.exit(1)

# ----------------------------------------------------------------------
#  Конфигурация
# ----------------------------------------------------------------------
CONFIG_FILE = "keymap_config.json"
DEFAULT_CONFIG = {
    "games": {
        "Notepad": {    # Пример: имя окна Notepad
            "a": "b",
            "Key.space": "Key.enter"
        }
        # Добавьте свои игры: "Название окна": {"исходная_клавиша": "целевая_клавиша"}
    }
}

def load_config():
    """Загрузить конфигурацию из JSON‑файла."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config
    except FileNotFoundError:
        # Создать файл с примером
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        print(f"Создан файл конфигурации {CONFIG_FILE}. Отредактируйте его и запустите программу снова.")
        sys.exit(0)
    except json.JSONDecodeError:
        print("Ошибка: файл конфигурации повреждён.")
        sys.exit(1)

# ----------------------------------------------------------------------
#  Определение активного окна (Windows)
# ----------------------------------------------------------------------
def get_active_window_title():
    """Возвращает заголовок активного окна в системе Windows."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        window_title = win32gui.GetWindowText(hwnd)
        return window_title
    except Exception as e:
        print(f"Ошибка получения окна: {e}")
        return ""

# ----------------------------------------------------------------------
#  Преобразование строки в объект клавиши pynput
# ----------------------------------------------------------------------
def parse_key(key_str):
    """
    Преобразует строку из конфигурации в Key или KeyCode.
    Примеры: 'a' -> KeyCode.from_char('a')
             'Key.space' -> Key.space
             'Key.enter' -> Key.enter
    Поддерживаются все стандартные Key из pynput.
    """
    if key_str.startswith("Key."):
        # Специальная клавиша, например Key.space
        attr = key_str.split(".")[1].lower()
        if hasattr(Key, attr):
            return getattr(Key, attr)
        else:
            raise ValueError(f"Неизвестная специальная клавиша: {key_str}")
    else:
        # Обычный символ (буква, цифра, знак)
        # Для корректной работы с пробелом, enter и т.д. лучше явно задавать через Key.
        if len(key_str) == 1:
            return KeyCode.from_char(key_str)
        else:
            # Можно расширить для сочетаний, но в базовом варианте просто символ
            return KeyCode.from_char(key_str)

# ----------------------------------------------------------------------
#  Глобальный обработчик клавиш
# ----------------------------------------------------------------------
class KeyRemapper:
    def __init__(self, config):
        self.config = config
        self.keyboard_controller = KeyboardController()
        self.listener = None

    def on_press(self, key):
        # Получить заголовок активного окна
        active_title = get_active_window_title()
        if not active_title:
            return True  # Не удалось определить – пропускаем

        # Ищем, есть ли настройки для этого окна (по подстроке? можно точное совпадение)
        # В конфиге ключи – названия игр (частичное совпадение регистронезависимо)
        mapping = None
        for game_name, keymap in self.config["games"].items():
            if game_name.lower() in active_title.lower():
                mapping = keymap
                break

        if not mapping:
            return True  # Игра не в списке – без изменений

        # Преобразуем нажатую клавишу в строковое представление для поиска в маппинге
        try:
            if isinstance(key, Key):
                key_repr = f"Key.{key.name}"
            elif isinstance(key, KeyCode):
                if key.char is None:
                    return True  # Неизвестная клавиша
                key_repr = key.char
            else:
                return True
        except Exception:
            return True

        # Проверяем, нужно ли переназначить
        if key_repr in mapping:
            target_repr = mapping[key_repr]
            try:
                target_key = parse_key(target_repr)
                # Подавляем оригинальное нажатие, возвращая False
                self.keyboard_controller.press(target_key)
                self.keyboard_controller.release(target_key)  # Имитируем полное нажатие
                print(f"Переназначение: {key_repr} -> {target_repr} (в окне '{active_title}')")
            except Exception as e:
                print(f"Ошибка отправки клавиши {target_repr}: {e}")
            return False  # Событие поглощено
        return True  # Не требуется переназначение – пропускаем

    def on_release(self, key):
        # Для простоты переназначение делаем только на нажатие.
        # Можно добавить и на отпускание, но обычно достаточно press/release.
        return True

    def start(self):
        print("Запуск переназначения клавиш. Для выхода нажмите Ctrl+C.")
        print(f"Конфигурация загружена из {CONFIG_FILE}")
        if WINDOWS:
            print("Для работы с некоторыми играми может потребоваться запуск от имени администратора.")
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as self.listener:
            self.listener.join()

def main():
    config = load_config()
    remapper = KeyRemapper(config)
    try:
        remapper.start()
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")

if __name__ == "__main__":
    main()