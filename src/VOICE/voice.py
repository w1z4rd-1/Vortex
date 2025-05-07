import os
import sys
import time
import numpy as np
import wave
import pyaudio
import sounddevice as sd
import io
import threading
import json       # For processing Vosk JSON output
import warnings
import pyttsx3    # TTS engine
import subprocess # For subprocess-based TTS as fallback
import multiprocessing  # For process-based TTS
from vosk import Model, KaldiRecognizer  # For wake word detection
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode
# Using ffmpeg directly instead of pydub (which requires pyaudioop)
# from pydub import AudioSegment
from openai import AsyncOpenAI
from dotenv import load_dotenv
import asyncio
import requests

# Check for ffmpeg availability (used for audio conversion instead of pydub)
FFMPEG_AVAILABLE = False
try:
    result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        FFMPEG_AVAILABLE = True
        print("FFmpeg is available for audio conversion")
    else:
        print("FFmpeg command exists but returned an error. Audio conversion may be limited.")
except FileNotFoundError:
    print("FFmpeg not found. You'll need to install FFmpeg for audio processing.")
    print("Download from: https://ffmpeg.org/download.html")
except Exception as e:
    print(f"Error checking for FFmpeg: {e}")

# Audio conversion function to replace pydub functionality
def convert_audio(input_path, output_path, sample_rate=16000, channels=1):
    """Convert audio using ffmpeg instead of pydub"""
    if not FFMPEG_AVAILABLE:
        print("WARNING: FFmpeg not available, audio conversion will fail")
        return False
        
    try:
        # Use ffmpeg to convert audio
        cmd = [
            "ffmpeg", "-y", 
            "-i", input_path,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-acodec", "pcm_s16le",
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Audio conversion error: {e}")
        return False

# Generate silent audio with ffmpeg instead of pydub
def generate_silence(output_path, duration_ms=500, sample_rate=16000, channels=1):
    """Create a silent WAV file using ffmpeg"""
    if not FFMPEG_AVAILABLE:
        print("WARNING: FFmpeg not available, silent audio generation will fail")
        return False
        
    duration_sec = duration_ms / 1000.0
    
    try:
        # Use ffmpeg to generate silence
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl=mono",
            "-t", str(duration_sec),
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-acodec", "pcm_s16le",
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Silent audio generation error: {e}")
        return False

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "local").lower()

# Initialize OpenAI client if using OpenAI
openai_client = None
if AI_PROVIDER == "openai":
    if not OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY missing but AI_PROVIDER='openai'")
    else:
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

COLOR_GREEN = "\033[92m"
COLOR_RESET = "\033[0m"
# Try to import msvcrt for keyboard detection on Windows
msvcrt_available = False
try:
    import msvcrt
    msvcrt_available = True
except ImportError:
    pass

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Ensure temp directory exists for audio files
if not os.path.exists("temp"):
	os.makedirs("temp", exist_ok=True)
	print("Created temp directory for audio files")

# Create models directory if not exists
if not os.path.exists("models"):
    os.makedirs("models", exist_ok=True)
    print("Created models directory for Vosk")

# TTS settings
TTS_RATE = 180       # Default speaking rate
TTS_VOLUME = 1.0     # Default volume (0.0 to 1.0)

# Wake word settings
WAKE_WORD = "vortex"  # The primary wake word
# Additional variations that sound similar and might be recognized instead
WAKE_WORD_VARIATIONS = [
    "vortex",
    "more tax",
    "whoa tax", 
    "what tax",
    "war tax",
    "for tax",
    "cortex",
    "vortech",
    "four tex",
    "for tex",
    "vor tex",
    "where next"
]  # Common misrecognitions
WAKE_WORD_CONFIDENCE = 0.7  # Minimum confidence level (0-1)

# TTS queue setup
tts_queue = []
tts_queue_lock = threading.Lock()
tts_is_speaking = False
tts_available = False
tts_thread = None

# Load Vosk model if available
vosk_model = None
vosk_available = False

# Add near the top with other OpenAI setup
# TTS_MODEL = "tts-1"  # OpenAI's TTS model -- No longer needed, will be hardcoded
TTS_VOICE = "nova"   # OpenAI's voice option for CLI

# Function for process-based TTS
def speak_in_process(text, rate=TTS_RATE, volume=TTS_VOLUME):
    """Run TTS in a separate process to avoid resource conflicts"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', rate)
        engine.setProperty('volume', volume)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"Process TTS error: {e}")

def load_vosk_model():
    """Load the Vosk model for wake word detection."""
    global vosk_model, vosk_available
    
    try:
        # Check for model in the models directory
        model_path = os.path.join("models", "vosk-model-small-en-us-0.15")
        if not os.path.exists(model_path):
            print("[!] Vosk model not found. Using fallback wake word detection.")
            print("    Download the model from https://alphacephei.com/vosk/models")
            print("    Extract to 'models/vosk-model-small-en-us-0.15'")
            return False
            
        print("[Loading Vosk speech recognition model...]")
        vosk_model = Model(model_path)
        print("[✓] Vosk model loaded successfully")
        vosk_available = True
        return True
    except Exception as e:
        print(f"[❌ ERROR loading Vosk model: {e}]")
        vosk_available = False
        return False

# Try to load Vosk model in background
vosk_load_thread = threading.Thread(target=load_vosk_model)
vosk_load_thread.daemon = True
vosk_load_thread.start()

# Initialize TTS
def init_tts():
    """Initialize TTS functionality by testing pyttsx3."""
    global tts_available
    
    print("Initializing TTS engine...")
    
    try:
        # Test pyttsx3 initialization
        engine = pyttsx3.init()
        if engine:
            # Try to get available voices to verify it's properly initialized
            voices = engine.getProperty('voices')
            
            # Test with an empty string to check run functionality
            engine.setProperty('rate', TTS_RATE)
            engine.setProperty('volume', TTS_VOLUME)
            
            # Use a simpler method to test TTS that doesn't rely on multiprocessing
            try:
                # Just test the engine directly
                engine.say("TTS test")
                engine.runAndWait()
                engine.stop()
                print("✅ Text-to-Speech initialized successfully (direct mode)")
                tts_available = True
            except Exception as e:
                print(f"⚠️ TTS direct test failed: {e}")
                print("⚠️ Using fallback text output mode")
                tts_available = False
                
            # Clean up the test engine
            try:
                engine.stop()
                del engine
            except:
                pass
            
    except Exception as e:
        if get_debug_mode():
            print(f"⚠️ TTS initialization error: {e}")
        print(f"⚠️ Error during TTS initialization")
        tts_available = False

# Start TTS init
try:
    # Initialize in a separate thread to prevent blocking
    init_thread = threading.Thread(target=init_tts)
    init_thread.daemon = True
    init_thread.start()
    
    # Continue initialization while TTS engine starts up
    if get_debug_mode():
        print("TTS initialization running in background...")
    
except Exception as e:
    print(f"⚠️ Error starting TTS initialization: {e}")
    tts_available = False

def tts_speak(text):
    """Add text to the TTS queue for speaking."""
    global tts_queue, tts_thread
    
    if not text or text.strip() == "":
        return
    
    # Visual indicator that VORTEX is speaking
    print(f"{COLOR_GREEN}[�� VORTEX Speaking...]{COLOR_RESET}")
    
    # If using OpenAI, handle TTS differently
    if AI_PROVIDER == "openai" and openai_client:
        try:
            # Create temp directory if it doesn't exist
            if not os.path.exists("temp"):
                os.makedirs("temp", exist_ok=True)
            
            # Generate speech using OpenAI's TTS
            speech_file_path = "temp/tts_output.mp3"
            
            # Instead of creating a new event loop, use a synchronous approach
            # Use the requests library directly to avoid asyncio conflicts
            
            # Print debug info
            if get_debug_mode():
                print(f"[🔊 OpenAI TTS] Generating speech for: {text[:50]}...")
            
            # OpenAI API key for authorization
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }
            
            # API endpoint for TTS
            url = "https://api.openai.com/v1/audio/speech"
            
            # Request body
            data = {
                "model": "tts-1", # Hardcoded to tts-1 for speed
                "voice": TTS_VOICE, # Uses the hardcoded TTS_VOICE for CLI
                "input": text
            }
            
            # Make the API request
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                # Save the audio to a file
                with open(speech_file_path, "wb") as f:
                    f.write(response.content)
                
                if get_debug_mode():
                    print(f"[✅ OpenAI TTS] Generated audio saved to {speech_file_path}")
                
                # Play the generated audio
                play_audio(speech_file_path)
                return
            else:
                print(f"[ERROR] OpenAI TTS API request failed with status {response.status_code}: {response.text}")
                # Fall through to local TTS as backup
        except Exception as e:
            print(f"[ERROR] OpenAI TTS failed: {e}. Falling back to local TTS.")
            # Fall through to local TTS as backup
    
    # Local TTS handling (existing code)
    with tts_queue_lock:
        tts_queue.append(text)
        if get_debug_mode():
            print(f"[Added to TTS queue]: {text[:30]}{'...' if len(text) > 30 else ''}")
    
    # Start the TTS thread if not already running
    if tts_thread is None or not tts_thread.is_alive():
        tts_thread = threading.Thread(target=process_tts_queue)
        tts_thread.daemon = True
        tts_thread.start()

def process_tts_queue():
    """Process the TTS queue in a separate thread."""
    global tts_is_speaking, tts_queue, tts_available
    
    print("[✅ TTS queue processor started and running]")
    
    while True:
        try:
            text_to_speak = None
            with tts_queue_lock:
                if tts_queue:
                    text_to_speak = tts_queue.pop(0)
                    tts_is_speaking = True
                    # Only print in debug mode
                    if get_debug_mode():
                        print(f"[🔊 Processing speech: {text_to_speak[:30]}{'...' if len(text_to_speak) > 30 else ''}]")
            
            if text_to_speak:
                # If TTS is not available, just print the text
                if not tts_available:
                    print(f"[TTS TEXT]: {text_to_speak}")
                    time.sleep(len(text_to_speak) * 0.05)  # Simulate speaking time
                else:
                    # Only print in debug mode
                    if get_debug_mode():
                        print(f"[🔊 Speaking: {text_to_speak}]")
                    
                    try:
                        # Direct TTS - safer but may block the thread
                        engine = pyttsx3.init()
                        engine.setProperty('rate', TTS_RATE)
                        engine.setProperty('volume', TTS_VOLUME)
                        engine.say(text_to_speak)
                        engine.runAndWait()
                        engine.stop()
                    except Exception as e:
                        print(f"[❌ ERROR in TTS engine: {e}]")
                        # Final fallback - print the text
                        print(f"[TTS TEXT]: {text_to_speak}")
                
                # Whether we succeeded or failed, we're done speaking this item
                with tts_queue_lock:
                    tts_is_speaking = False
                    
                # Visual indicator when finished speaking
                if tts_queue:
                    # More to speak
                    if get_debug_mode():
                        print(f"{COLOR_GREEN}[🔄 VORTEX continuing...]{COLOR_RESET}")
                else:
                    # Done with all speech
                    print(f"{COLOR_GREEN}[✓ VORTEX finished speaking]{COLOR_RESET}")
            
            # Small pause before checking again
            time.sleep(0.1)
            
        except Exception as e:
            if get_debug_mode():
                print(f"[❌ ERROR in TTS queue processor: {e}]")
            time.sleep(0.5)  # Wait a bit before trying again

def is_tts_available():
    """Check if TTS is available and working."""
    global tts_available
    
    # If using OpenAI, check if client is initialized
    if AI_PROVIDER == "openai":
        return openai_client is not None
    
    # Otherwise check local TTS
    return tts_available

def wait_for_tts_completion(timeout=30):
    """
    Wait for the TTS queue to be empty and not speaking.
    
    Args:
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if the queue is empty and not speaking, False if still speaking or timeout
    """
    global tts_queue, tts_is_speaking
    
    # If TTS is not available, no need to wait
    if not tts_available:
        return True
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check if queue is empty and not speaking
        with tts_queue_lock:
            if not tts_queue and not tts_is_speaking:
                return True
        
        # Short sleep to prevent CPU spinning
        time.sleep(0.1)
    
    # If we got here, we timed out
    return False

# ------------------------------
# Wake Word Detection Options
# ------------------------------
def detect_wake_word(return_buffer=False, ignore_if_speaking=True):
    """
    Detects wake word using Vosk speech recognition.
    Listens for "vortex" or similar variations in speech input.

    Args:
        return_buffer: If True, returns a pre-buffer of audio data after wake word detection
        ignore_if_speaking: If True, ignores wake word detections if TTS is currently speaking

    Returns:
        If return_buffer=False: True if wake word detected, False otherwise
        If return_buffer=True: (True, audio_buffer) if wake word detected, (False, None) otherwise
    """
    try:
        from vosk import Model, KaldiRecognizer
        import json
    except ImportError:
        print("[ERROR] Vosk not installed for wake word detection")
        return False # Return False on import error

    # Check if TTS is currently active - if it is, avoid wake word detection when requested
    if ignore_if_speaking:
        with tts_queue_lock:
            if tts_is_speaking or tts_queue:
                if get_debug_mode():
                    print("[DEBUG] Ignoring potential wake word - TTS is active")
                return False
    
    model_path = os.path.join("models", "vosk-model-small-en-us-0.15")
    if not os.path.exists(model_path):
        print("[ERROR] Vosk model not found. Download from: https://alphacephei.com/vosk/models")
        # If no model, maybe fallback to keyboard? For now, return False
        return False

    if get_debug_mode():
        print(f"[DEBUG] Listening for wake word '{WAKE_WORD}' (and variations)...")
    # Don't print basic instruction here, VORTEX.py does it.

    CHUNK = 2048
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = None
    stream = None

    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                      channels=CHANNELS,
                      rate=RATE,
                      input=True,
                      frames_per_buffer=CHUNK)

        model = Model(model_path)
        recognizer = KaldiRecognizer(model, RATE)
        recognizer.SetWords(True)

        while True:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
            except IOError as e:
                if get_debug_mode(): print(f"[WARNING] Audio stream read error: {e}")
                continue

            # Check TTS status periodically during wake word detection
            if ignore_if_speaking:
                with tts_queue_lock:
                    if tts_is_speaking or tts_queue:
                        if get_debug_mode():
                            print("[DEBUG] TTS started speaking, exiting wake word detection")
                        return False

            partial = json.loads(recognizer.PartialResult())
            if "partial" in partial and partial["partial"]:
                partial_text = partial["partial"].lower()
                for variation in WAKE_WORD_VARIATIONS:
                    # More precise matching - match whole words rather than substrings
                    # This prevents false positives from words containing the wake word
                    words = partial_text.split()
                    if variation in words:
                        # Get confidence if available
                        confidence = 1.0  # Default high confidence
                        if "result" in partial and partial["result"]:
                            for word_info in partial["result"]:
                                if word_info.get("word", "").lower() == variation:
                                    confidence = word_info.get("conf", 1.0)
                                    break
                        
                        if confidence >= WAKE_WORD_CONFIDENCE:
                            detected_variation = variation
                            print(f"{COLOR_GREEN}[Wake word '{detected_variation}' detected! (Confidence: {confidence:.2f})]{COLOR_RESET}")
                            return True
                        elif get_debug_mode():
                            print(f"[DEBUG] Low confidence wake word detection: {variation} ({confidence:.2f})")

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if "text" in result and result["text"]:
                    text = result["text"].lower()
                    words = text.split()
                    
                    for variation in WAKE_WORD_VARIATIONS:
                        # More precise matching - match whole words 
                        if variation in words:
                            # Get confidence if available
                            confidence = 1.0  # Default high confidence
                            if "result" in result:
                                for word_info in result["result"]:
                                    if word_info.get("word", "").lower() == variation:
                                        confidence = word_info.get("conf", 1.0)
                                        break
                            
                            if confidence >= WAKE_WORD_CONFIDENCE:
                                detected_variation = variation
                                print(f"{COLOR_GREEN}[Wake word '{detected_variation}' detected! (Confidence: {confidence:.2f})]{COLOR_RESET}")
                                return True
                            elif get_debug_mode():
                                print(f"[DEBUG] Low confidence wake word detection: {variation} ({confidence:.2f})")

            # Check keyboard only if available
            if msvcrt_available and msvcrt.kbhit():
                 key = msvcrt.getch()
                 if key == b'\r':
                     print("[VORTEX activated via Enter key]")
                     return True

    except KeyboardInterrupt:
        print("\n[KeyboardInterrupt in wake word detector]")
        return False # Indicate stop
    except Exception as e:
        if get_debug_mode(): print(f"[ERROR] Wake word detection error: {e}")
        else: print("[ERROR] Wake word detection failed")
        return False # Indicate error, let main loop retry
    finally:
        if stream is not None:
            try: stream.stop_stream(); stream.close()
            except Exception: pass
        if p is not None:
            try: p.terminate()
            except Exception: pass

    return False # Default return if loop exits unexpectedly

# ------------------------------
# Audio Playback
# ------------------------------
def play_audio(mp3_path):
    """Play an MP3 file, first converting it to WAV using ffmpeg if needed."""
    if not os.path.exists(mp3_path):
        print(f"Audio file not found: {mp3_path}")
        return False
        
    try:
        # If it's an MP3, convert to WAV first using ffmpeg
        if mp3_path.lower().endswith('.mp3'):
            wav_path = mp3_path.replace('.mp3', '.wav')
            if not convert_audio(mp3_path, wav_path):
                print(f"Failed to convert MP3 to WAV: {mp3_path}")
                return False
        else:
            wav_path = mp3_path
            
        # Play the WAV file directly using PyAudio
        with wave.open(wav_path, 'rb') as wf:
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                           channels=wf.getnchannels(),
                           rate=wf.getframerate(),
                           output=True)
            
            # Read data in chunks
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            
            # Play audio
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(chunk_size)
                
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Delete temporary WAV file if we converted from MP3
            if mp3_path.lower().endswith('.mp3') and os.path.exists(wav_path):
                os.remove(wav_path)
                
            return True
                
    except Exception as e:
        print(f"Error playing audio: {e}")
        return False

def list_audio_devices():
    """Lists all available audio devices and shows which one is currently the default."""
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    num_devices = info.get('deviceCount')
    default_input = p.get_default_input_device_info().get('index')
    
    print("\n=== Available Audio Input Devices ===")
    for i in range(num_devices):
        device_info = p.get_device_info_by_index(i)
        
        # Only show input devices (max input channels > 0)
        if device_info.get('maxInputChannels') > 0:
            is_default = " (DEFAULT)" if device_info.get('index') == default_input else ""
            print(f"{i}: {device_info.get('name')}{is_default}")
    
    print("\nVORTEX is using the default input device. To change it, use your system's audio settings.")
    p.terminate()
    return default_input

def record_audio(filename="temp/recorded_audio.wav", silence_threshold=100, silence_duration=1.0):
    """Records audio until silence is detected, using a ring buffer for pre-recording."""
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    if get_debug_mode():
        print("[DEBUG] record_audio: Starting recording function")
    
    # Ensure temp directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    if get_debug_mode():
        print(f"[DEBUG] record_audio: Ensured temp directory exists at {os.path.dirname(filename)}")

    # Set up a ring buffer for pre-recording (5 chunks = ~0.3 seconds)
    ring_buffer_size = 5
    ring_buffer = [b'\x00' * (CHUNK * 2)] * ring_buffer_size  # Initialize with silence
    ring_buffer_index = 0
    
    try:
        audio = pyaudio.PyAudio()
        if get_debug_mode():
            print("[DEBUG] record_audio: PyAudio initialized")
        
        # Start stream immediately to capture any initial words
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                            input=True, frames_per_buffer=CHUNK)
        if get_debug_mode():
            print("[DEBUG] record_audio: Audio stream opened")

        # All frames that will be saved to the file
        frames = []
        
        # Wait a brief moment before capturing to handle any silence
        # between wake word detection and the start of actual speech
        time.sleep(0.2)  # Brief wait to ensure we're ready
        
        # Fill the ring buffer with initial audio
        if get_debug_mode():
            print("[DEBUG] Capturing pre-recording buffer...")
        for i in range(ring_buffer_size):
            data = stream.read(CHUNK, exception_on_overflow=False)
            ring_buffer[i] = data
            ring_buffer_index = (ring_buffer_index + 1) % ring_buffer_size
        
        # Add the ring buffer contents to frames
        for i in range(ring_buffer_size):
            idx = (ring_buffer_index + i) % ring_buffer_size
            frames.append(ring_buffer[idx])
        
        last_audio_time = time.time()
        capturing = True
        seconds_recorded = 0
        max_recording_time = 10  # Maximum recording time in seconds

        if get_debug_mode():
            print("[DEBUG] record_audio: Starting recording loop")
        start_time = time.time()
        
        # Wait for speech to actually start by detecting when audio rises above threshold
        # This ensures we start with actual speech not silence
        speech_started = False
        if get_debug_mode():
            print("[DEBUG] Waiting for speech to start...")
        timeout_start = time.time()
        
        # Wait up to 2 seconds for speech to start
        while not speech_started and time.time() - timeout_start < 2.0:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)  # Keep this buffer
            
            # Update ring buffer
            ring_buffer[ring_buffer_index] = data
            ring_buffer_index = (ring_buffer_index + 1) % ring_buffer_size
            
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()
            
            if volume > silence_threshold * 1.5:  # Higher threshold to ensure it's actually speech
                speech_started = True
                if get_debug_mode():
                    print(f"[DEBUG] Speech detected! Volume: {volume}")
            else:
                # Every 0.5 seconds, show the volume level while waiting
                if get_debug_mode() and int((time.time() - timeout_start) * 2) > int((time.time() - timeout_start - 0.1) * 2):
                    print(f"[DEBUG] Waiting for speech... Volume: {volume}")
        
        # If speech didn't start, use the buffer we collected anyway
        if not speech_started and get_debug_mode():
            print("[DEBUG] No clear speech start detected, using collected buffer")
        
        # Reset the speech timing
        last_audio_time = time.time()
        start_time = time.time()
        
        while capturing:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
            # Update ring buffer (continuous updating even during recording)
            ring_buffer[ring_buffer_index] = data
            ring_buffer_index = (ring_buffer_index + 1) % ring_buffer_size
            
            # Calculate current recording duration
            seconds_recorded = time.time() - start_time
            
            # Enforce maximum recording time
            if seconds_recorded > max_recording_time:
                if get_debug_mode():
                    print(f"[DEBUG] record_audio: Maximum recording time reached ({max_recording_time}s)")
                capturing = False
                break
                
            # Process audio to detect silence
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()
            
            # Every second, print the current volume
            if get_debug_mode() and int(seconds_recorded) > int(seconds_recorded - 0.1):
                print(f"[DEBUG] record_audio: Current volume: {volume}")
            
            if volume < silence_threshold:
                silence_time = time.time() - last_audio_time
                if silence_time > silence_duration:
                    if get_debug_mode():
                        print(f"[DEBUG] record_audio: Silence detected for {silence_time:.2f}s, stopping recording")
                    capturing = False
            else:
                last_audio_time = time.time()
                
    except Exception as e:
        print(f"[ERROR] record_audio exception: {e}")
        print(f"[ERROR] record_audio exception type: {type(e).__name__}")
        raise
    finally:
        if get_debug_mode():
            print("[DEBUG] record_audio: Closing audio stream")
        try:
            stream.stop_stream()
            stream.close()
            audio.terminate()
        except Exception as e:
            print(f"[ERROR] record_audio cleanup exception: {e}")

    if get_debug_mode():
        print(f"[DEBUG] record_audio: Recorded {len(frames)} frames, {seconds_recorded:.2f} seconds")
        print(f"[DEBUG] record_audio: Saving to {filename}")
    
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
        if get_debug_mode():
            print(f"[DEBUG] record_audio: File saved successfully, size: {os.path.getsize(filename)} bytes")
    except Exception as e:
        print(f"[ERROR] record_audio save exception: {e}")
        raise

    return filename

async def transcribe_audio(audio_path):
    """
    Transcribes the audio file using either Whisper (OpenAI) or Vosk (offline).
    Returns the transcription text or None on error.
    """
    if get_debug_mode():
        print(f"[Transcribing audio: {audio_path}]")
    
    # Check if we should use OpenAI's Whisper
    if AI_PROVIDER == "openai" and openai_client:
        try:
            with open(audio_path, "rb") as audio_file:
                transcription = await openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
                transcript = transcription.text.strip()
                print(f"[Transcription]: '{transcript}'")
                return transcript if transcript else "I didn't catch that"
        except Exception as e:
            print(f"[ERROR] OpenAI transcription failed: {e}")
            return None
    
    # Fallback to Vosk for offline transcription
    try:
        from vosk import Model, KaldiRecognizer
        import json
        import wave
    except ImportError:
        print("[ERROR] Vosk not installed for transcription")
        return None
    
    # Check if the model exists
    model_path = os.path.join("models", "vosk-model-small-en-us-0.15")
    if not os.path.exists(model_path):
        print("[ERROR] Vosk model not found for transcription")
        return None
    
    try:
        # Load the audio file
        wf = wave.open(audio_path, "rb")
        
        # Check audio format - Vosk expects 16kHz mono PCM
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
            print("[ERROR] Audio file must be WAV format 16kHz mono PCM")
            return None
        
        # Load the Vosk model
        model = Model(model_path)
        rec = KaldiRecognizer(model, wf.getframerate())
        
        # Process the entire audio file
        transcript = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if "text" in result and result["text"]:
                    transcript += " " + result["text"]
        
        # Get final result
        final_result = json.loads(rec.FinalResult())
        if "text" in final_result and final_result["text"]:
            transcript += " " + final_result["text"]
        
        transcript = transcript.strip()
        print(f"[Transcription]: '{transcript}'")
        
        return transcript if transcript else "I didn't catch that"
    
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return None
