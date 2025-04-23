print("[Автозапуск] VOSK диктовка активирована")

# 📌 Меняем имя процесса, чтобы в системном мониторинге было "VOSK Dictation"
import ctypes
libc = ctypes.cdll.LoadLibrary("libc.so.6")
libc.prctl(15, b"VOSK Dictation", 0, 0, 0)

import os, json, queue, time, threading, subprocess, sys, signal
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from pynput import keyboard
from pystray import Icon, Menu, MenuItem
from PIL import Image

# 📌 ДОБАВЛЕНО для поддержки GTK3 через PyGObject внутри AppImage
APPDIR = os.path.dirname(os.path.abspath(__file__))
os.environ["GI_TYPELIB_PATH"] = os.path.join(APPDIR, "usr", "lib", "girepository-1.0")
os.environ["LD_LIBRARY_PATH"] = os.path.join(APPDIR, "usr", "lib") + ":" + os.environ.get("LD_LIBRARY_PATH", "")

# 📌 ДОБАВЛЕНО: путь к notify-send внутри AppImage
NOTIFY_SEND = os.path.join(APPDIR, "usr", "bin", "notify-send")

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

MODEL_PATH = os.path.join(APPDIR, "vosk-model-small-ru-0.22")
SAMPLERATE = 16000
TRIGGER_KEY = keyboard.Key.alt_l
HOLD_TIME = 1.2

model = Model(MODEL_PATH)
q = queue.Queue()
recording = False
stream = None
pressed_time = None

def notify(msg):
    try:
        subprocess.Popen(["paplay", os.path.join(APPDIR, "dialog-information.ogg")])
    except Exception as e:
        print(f"[WARN] Звук: {e}")
    try:
        subprocess.run([
            NOTIFY_SEND, "--app-name=VOSK", "--urgency=normal",
            "--hint=string:x-canonical-private-synchronous:vosk", msg
        ])
    except Exception as e:
        print(f"[WARN] notify-send: {e}")

def notify_startup():
    try:
        subprocess.Popen(["paplay", os.path.join(APPDIR, "dialog-information.ogg")])
    except Exception as e:
        print(f"[WARN] Звук: {e}")
    try:
        subprocess.run([
            NOTIFY_SEND, "--app-name=VOSK", "--urgency=normal",
            "--icon=dialog-information",
            "✅ VOSK Dictation запущен"
        ])
    except Exception as e:
        print(f"[WARN] notify-send: {e}")


def audio_callback(indata, frames, time_, status_):
    if status_:
        print("⚠️", status_)
    q.put(bytes(indata))

def start_recording():
    global stream, recording
    print("[INFO] ▶️ Начало записи")
    notify("🎙 Начало записи")
    q.queue.clear()
    recording = True
    stream = sd.RawInputStream(
        samplerate=SAMPLERATE,
        blocksize=8000,
        dtype='int16',
        channels=1,
        callback=audio_callback
    )
    stream.start()

def stop_and_process():
    global stream, recording
    print("[INFO] ⏳ Обработка...")
    notify("⏳ Распознаём...")
    recording = False
    if stream:
        stream.stop()
        stream.close()

    rec = KaldiRecognizer(model, SAMPLERATE)
    text = ""
    while not q.empty():
        data = q.get()
        if rec.AcceptWaveform(data):
            text += json.loads(rec.Result()).get("text", "") + " "
    text += json.loads(rec.FinalResult()).get("text", "")
    text = text.strip()

    if text:
        print(f"[INFO] ✅ Готово: {text}")
        notify("✅ Готово")
        threading.Thread(target=type_directly, args=(text,)).start()
    else:
        print("[INFO] ⚠️ Пусто")
        notify("⚠️ Пусто")

def type_directly(text):
    print("[INFO] 🪄 Вставка текста...")
    time.sleep(0.3)
    for chunk in [text[i:i+80] for i in range(0, len(text), 80)]:
        subprocess.run(["xdotool", "type", "--delay", "1", chunk])
        time.sleep(0.05)
    print("[INFO] ✅ Вставка завершена")

pressed = False
def on_press(key):
    global pressed_time, pressed
    if key == TRIGGER_KEY and not pressed:
        pressed_time = time.time()
        pressed = True
        threading.Thread(target=monitor_hold).start()

def on_release(key):
    global pressed
    if key == TRIGGER_KEY:
        pressed = False

def monitor_hold():
    global recording
    while pressed:
        if time.time() - pressed_time >= HOLD_TIME:
            if not recording:
                threading.Thread(target=start_recording).start()
            else:
                threading.Thread(target=stop_and_process).start()
            break
        time.sleep(0.1)

def on_stop(icon, item):
    print("[TRAY] ⛔ Остановка по кнопке")
    icon.stop()
    os._exit(0)

def run_tray():
    from gi.repository import Gtk, Gdk
    icon = Gtk.StatusIcon()
    icon.set_from_file(os.path.join(APPDIR, "icon.png"))
    icon.set_visible(True)

    def on_left_click(icon):  # ЛКМ
        print("[TRAY] ЛКМ — показать меню")
        show_menu()

    def on_right_click(icon, button, time):  # ПКМ
        print("[TRAY] ПКМ — показать меню")
        show_menu(button, time)

    def on_stop_action(menu_item):
        print("[TRAY] ⛔ Остановка по кнопке")
        Gtk.main_quit()
        os._exit(0)

    def show_menu(button=1, time=Gtk.get_current_event_time()):
        menu = Gtk.Menu()
        stop_item = Gtk.MenuItem(label="❌ Завершить")
        stop_item.connect("activate", on_stop_action)
        stop_item.show()
        menu.append(stop_item)
        menu.popup(None, None, None, None, button, time)

    icon.connect("activate", on_left_click)           # ЛКМ
    icon.connect("popup-menu", on_right_click)        # ПКМ

    Gtk.main()

keyboard.Listener(on_press=on_press, on_release=on_release).start()
threading.Thread(target=run_tray, daemon=True).start()

notify_startup()
print("[INFO] VOSK диктовка запущена.")
while True:
    time.sleep(1)

