import os
import time
import numpy as np
import wave
import pyaudio
import whisper
import pvporcupine
from pvrecorder import PvRecorder
from dotenv import load_dotenv
import sys
import warnings
from functions import set_debug_mode, get_debug_mode

warnings.filterwarnings("ignore", category=UserWarning)  # Suppress FFMPEG warning

# Load environment variables
load_dotenv()

# API keys and model paths
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY", "8/P39p9rRTTjHIHY49yYs76jv8hy5IXH7NDJpheYfSMSSau2E+TFHw==")
MODEL_PATH = "C:/Users/Terac/ALFRED/Jarvis.ppn"  # Adjust this path if needed

# ANSI Escape Codes for Colors
COLOR_GREEN = "\033[92m"  # Debug Green
COLOR_BLUE = "\033[94m"   # Light Blue (Normal Responses)
COLOR_RED = "\033[91m"    # Red (Errors)
COLOR_RESET = "\033[0m"   # Reset Color

# Initialize Whisper Model (Only Show Message in Debug Mode)
if get_debug_mode():
    print(f"{COLOR_GREEN}Loading Whisper model...{COLOR_RESET}")
whisper_model = whisper.load_model("base")  # Change to "tiny", "small", etc. for performance

# ------------------------------
# Wake Word Detection
# ------------------------------
def detect_wake_word():
    """Listens for the wake word and returns True when detected."""
    if get_debug_mode():
        print(f"{COLOR_GREEN}\nListening for wake word...{COLOR_RESET}")

    porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keyword_paths=[MODEL_PATH])
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    recorder.start()

    try:
        while True:
            pcm = np.array(recorder.read(), dtype=np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                if get_debug_mode():
                    print(f"{COLOR_GREEN}Wake word detected! Starting transcription...{COLOR_RESET}")
                return True
    except KeyboardInterrupt:
        print(f"{COLOR_RED}\n[EXIT] User terminated wake word detection.{COLOR_RESET}")
        sys.exit()
        return False
    finally:
        recorder.stop()
        porcupine.delete()

# ------------------------------
# Speech Recording
# ------------------------------
def record_audio(filename="recorded_audio.wav", silence_threshold=1200, silence_duration=3.0):
    """
    Records audio after wake word detection.
    Stops recording when silence is detected for `silence_duration` seconds.
    Saves audio to `filename` and returns the file path.
    """
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    if get_debug_mode():
        print(f"{COLOR_GREEN}Listening... Speak now.{COLOR_RESET}")
        
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    frames = []
    last_audio_time = time.time()
    capturing = True

    try:
        while capturing:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

            # Convert audio to numpy array & check volume
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()

            if volume < silence_threshold:
                if time.time() - last_audio_time > silence_duration:
                    if get_debug_mode():
                        print(f"{COLOR_GREEN}Silence detected. Stopping recording.{COLOR_RESET}")
                    capturing = False
            else:
                last_audio_time = time.time()

    except KeyboardInterrupt:
        print(f"{COLOR_RED}\n[EXIT] User interrupted recording.{COLOR_RESET}")
        sys.exit()
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

    # Save to WAV file
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    return filename

# ------------------------------
# Audio Transcription
# ------------------------------
def transcribe_audio(audio_path):
    """Transcribes recorded audio file using Whisper and returns the text."""
    if get_debug_mode():
        print(f"{COLOR_GREEN}Transcribing audio...{COLOR_RESET}")
        
    result = whisper_model.transcribe(audio_path)
    transcript = result["text"].strip()
    
    if get_debug_mode():
        print("\n=== Transcription ===")
        print(transcript if transcript else "[No speech detected]")

    return transcript if transcript else None
