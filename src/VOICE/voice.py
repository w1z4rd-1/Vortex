import os
import sys
import time
import numpy as np
import wave
import pyaudio
import whisper
import openai
import pvporcupine
import sounddevice as sd
import io
import threading
import librosa
from openai import OpenAI
from pvrecorder import PvRecorder
from scipy.fftpack import fft
from dotenv import load_dotenv
import warnings
#from display import display
from src.Boring.functions import set_debug_mode, get_debug_mode
from pydub import AudioSegment

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORCUPINE_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
MODEL_PATH = os.path.join("src", "voice", "vortex.ppn")

client = OpenAI()  # ✅ Initialize OpenAI client

# ------------------------------
# Wake Word Detection
# ------------------------------
def detect_wake_word():
    """Listens for the wake word using Porcupine."""
    if get_debug_mode():
        print("[Listening for wake word...]")

    porcupine = pvporcupine.create(
        access_key=PORCUPINE_KEY,
        keyword_paths=[MODEL_PATH]
    )
    
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    recorder.start()
    
    detected = False
    try:
        while True:
            pcm = np.array(recorder.read(), dtype=np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                print("[Wake word detected!]")
                detected = True
                break
            time.sleep(0.01)
    finally:
        recorder.stop()
        porcupine.delete()
    
    return detected

# ------------------------------
# Speech Recording & Transcription
# ------------------------------
def record_audio(filename="recorded_audio.wav", silence_threshold=1300, silence_duration=1.2):
    """Records audio until silence is detected."""
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    if get_debug_mode():
        print("[Recording audio...]")

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
            
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()
            
            if volume < silence_threshold:
                if time.time() - last_audio_time > silence_duration:
                    if get_debug_mode():
                        print("[Silence detected; stopping recording.]")
                    capturing = False
            else:
                last_audio_time = time.time()
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    return filename

def transcribe_audio(audio_path):
    """Transcribes the audio file using the Whisper model."""
    if get_debug_mode():
        print(f"[Transcribing: {audio_path}]")

    result = whisper.load_model("tiny").transcribe(audio_path)
    transcript = result["text"].strip()
    
    if get_debug_mode():
        print(f"== Transcription: {transcript} ==")
        
    return transcript if transcript else None

# ------------------------------
# OpenAI TTS with MP3-Based Visualization
# ------------------------------
def tts_speak(text):
    """Generates OpenAI's TTS audio, saves it to an MP3, and plays it while triggering visualizer."""
    if get_debug_mode():
        print(f"[🔊 Speaking: {text}]")

    try:
        speech_file_path = "tts_output.mp3"
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text
        )

        response.stream_to_file(speech_file_path)  # ✅ Save full speech to MP3

        # ✅ Start visualizer reaction **before playback**
        # threading.Thread(target=display.react_to_audio, args=(speech_file_path,), daemon=True).start() #audio responsive visuals later

        # ✅ Play the saved MP3
        play_audio(speech_file_path)

    except Exception as e:
        if get_debug_mode():
            print(f"[❌ ERROR in TTS] {e}")

def play_audio(mp3_path):
    """Plays the generated TTS audio while updating visuals based on actual speech."""
    try:
        audio = AudioSegment.from_mp3(mp3_path)
        wav_data = io.BytesIO()
        audio.export(wav_data, format="wav")  # ✅ Convert to WAV

        wav_data.seek(0)
        sound = AudioSegment.from_wav(wav_data)
        samples = np.array(sound.get_array_of_samples(), dtype=np.int16)

        if get_debug_mode():
            print(f"[🔊 Playing {len(samples)} samples...]")

        # ✅ Play audio smoothly
        sd.play(samples, samplerate=sound.frame_rate)
        sd.wait()

        if get_debug_mode():
            print("[✅ Playback Completed]")

    except Exception as e:
        if get_debug_mode():
            print(f"[❌ ERROR in Playback] {e}")
