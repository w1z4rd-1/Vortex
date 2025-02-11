import os
import sys
import time
import numpy as np
import wave
import pyaudio
import whisper
import pvporcupine
from pvrecorder import PvRecorder
from dotenv import load_dotenv
import warnings

# Import debug helper functions from your functions module.
# These should include at least get_debug_mode() (and optionally set_debug_mode() if needed).
from functions import set_debug_mode, get_debug_mode

# Suppress FFMPEG warnings (optional)
warnings.filterwarnings("ignore", category=UserWarning)

# ------------------------------
# Environment & API Keys
# ------------------------------
load_dotenv()
PORCUPINE_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
MODEL_PATH = "VORTEX.ppn"  # Change this to your keyword model path if needed

# ------------------------------
# ANSI Escape Codes for Colors
# ------------------------------
COLOR_GREEN = "\033[92m"  # For success/debug messages
COLOR_BLUE  = "\033[94m"  # For normal responses
COLOR_RED   = "\033[91m"  # For error messages
COLOR_RESET = "\033[0m"   # To reset terminal color

# ------------------------------
# Load Whisper Model
# ------------------------------
if get_debug_mode():
    print(f"{COLOR_GREEN}Loading Whisper model...{COLOR_RESET}")
whisper_model = whisper.load_model("base")  # Change to "tiny", "small", etc. for performance

# ------------------------------
# Wake Word Detection
# ------------------------------
def detect_wake_word():
    """
    Listens for the wake word using Porcupine and PvRecorder.
    Returns True once the wake word is detected.
    """
    if get_debug_mode():
        print(f"{COLOR_GREEN}Listening for wake word...{COLOR_RESET}")
    
    # Create a Porcupine instance using your access key and keyword model.
    porcupine = pvporcupine.create(
        access_key=PORCUPINE_KEY,
        keyword_paths=[MODEL_PATH]
    )
    
    # Create and start the recorder (device_index=-1 selects the default microphone).
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    recorder.start()
    
    detected = False
    try:
        while True:
            # recorder.read() returns a list; convert it to a NumPy array of type int16.
            pcm = np.array(recorder.read(), dtype=np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                print(f"{COLOR_GREEN}Wake word detected!{COLOR_RESET}")
                detected = True
                break
            # A short sleep prevents excessive CPU usage.
            time.sleep(0.01)
    except KeyboardInterrupt:
        print(f"{COLOR_RED}[EXIT] User terminated wake word detection.{COLOR_RESET}")
        sys.exit()
    finally:
        recorder.stop()
        porcupine.delete()
    
    return detected

# ------------------------------
# Speech Recording
# ------------------------------
def record_audio(filename="recorded_audio.wav", silence_threshold=1200, silence_duration=3.0):
    """
    Records audio from the default microphone until a period of silence is detected.
    
    Args:
        filename (str): The filename to save the recorded WAV audio.
        silence_threshold (int): The threshold for determining silence.
        silence_duration (float): The duration (in seconds) of silence required to stop recording.
    
    Returns:
        str: The filename of the saved audio file.
    """
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    if get_debug_mode():
        print(f"{COLOR_GREEN}Recording audio. Speak now...{COLOR_RESET}")

    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK)

    frames = []
    last_audio_time = time.time()
    capturing = True

    try:
        while capturing:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
            # Convert the audio chunk to a NumPy array to calculate its average volume.
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()
            
            # If volume is below the threshold for a sustained duration, stop recording.
            if volume < silence_threshold:
                if time.time() - last_audio_time > silence_duration:
                    if get_debug_mode():
                        print(f"{COLOR_GREEN}Silence detected; stopping recording.{COLOR_RESET}")
                    capturing = False
            else:
                last_audio_time = time.time()
    except KeyboardInterrupt:
        print(f"{COLOR_RED}[EXIT] User interrupted recording.{COLOR_RESET}")
        sys.exit()
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

    # Save the recorded frames to a WAV file.
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
    """
    Transcribes the audio file at the given path using the Whisper model.
    
    Args:
        audio_path (str): The path to the audio file to transcribe.
    
    Returns:
        str: The transcribed text, or None if no speech was detected.
    """
    if get_debug_mode():
        print(f"{COLOR_GREEN}Transcribing audio from file: {audio_path}{COLOR_RESET}")
        
    result = whisper_model.transcribe(audio_path)
    transcript = result["text"].strip()
    
    if get_debug_mode():
        print("=== Transcription ===")
        print(transcript if transcript else "[No speech detected]")
        
    return transcript if transcript else None
