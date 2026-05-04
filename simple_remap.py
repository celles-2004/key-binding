from pynput import keyboard
from pynput.keyboard import Controller

ctrl = Controller()

def on_press(key):
    try:
        if key.char == 'a':
            print('a нажата -> отправляем b')
            ctrl.press('b')
            ctrl.release('b')
            return False  # подавляем a
    except AttributeError:
        pass
    return True

print("Переназначение a -> b глобально. Нажми Ctrl+C для выхода.")
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()