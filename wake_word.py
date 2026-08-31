import sounddevice as sd
import numpy as np
import requests
from openwakeword.model import Model
import time

#Cool Down Reset
last_detected= 0
COOLDOWN = 3 #seconds

#Load the hey jarvis model
model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

CHUNK = 1280
RATE = 16000

print("Listening for 'Hey Jarvis'....")

def audio_callback(indata, frames, time_info, status, *args):
    global last_detected
    audio_array = np.frombuffer(indata, dtype=np.int16)
    prediction = model.predict(audio_array)

    now = time.time()
    if prediction['hey_jarvis'] > 0.5 and (now - last_detected) > COOLDOWN:
        last_detected = now
        print("Wake word detected! Signaling Flask...")
        try:
            requests.post("http://127.0.0.1:5000/wake-detected")
        except:
            pass

with sd.RawInputStream(samplerate=RATE, blocksize=CHUNK, dtype='int16', channels=1, callback=audio_callback):
    while True:
        sd.sleep(100)