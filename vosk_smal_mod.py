print("[Автозапуск] VOSK диктовка активирована")
import os, json, queue, time, threading, subprocess, sys, signal
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from pynput import keyboard
from pystray import Icon, Menu, MenuItem
from PIL import Image

APPDIR = os.path.dirname(os.path.abspath(__file__))
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
    subprocess.Popen(["paplay", os.path.join(APPDIR, "dialog-information.ogg")])
    subprocess.run([
        "notify-send", "--app-name=VOSK", "--urgency=normal",
        "--hint=string:x-canonical-private-synchronous:vosk", msg
    ])

def notify_startup():
    subprocess.Popen(["paplay", os.path.join(APPDIR, "dialog-information.ogg")])
    subprocess.run([
        "notify-send", "--app-name=VOSK", "--urgency=normal",
        "--icon=dialog-information",
        "✅ VOSK Dictation запущен"
    ])

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
    import time
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
    icon_path = os.path.join(APPDIR, "icon.png")
    image = Image.open(icon_path)

    icon = Icon("VOSK", image, menu=Menu(
        MenuItem("Остановить", on_stop, default=True)
    ))

    icon.run()

keyboard.Listener(on_press=on_press, on_release=on_release).start()
threading.Thread(target=run_tray, daemon=True).start()

notify_startup()
print("[INFO] VOSK диктовка запущена.")
while True:
    time.sleep(1)

