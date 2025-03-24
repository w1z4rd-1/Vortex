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
from vosk import Model, KaldiRecognizer  # For wake word detection
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode
import warnings
import subprocess # For calling espeak directly

# Try to import msvcrt for keyboard detection on Windows
msvcrt_available = False
try:
    import msvcrt
    msvcrt_available = True
except ImportError:
    pass

from pydub import AudioSegment

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Ensure temp directory exists for audio files
if not os.path.exists("temp"):
	os.makedirs("temp")
	print("Created temp directory for audio files")

# Create models directory if not exists
if not os.path.exists("models"):
    os.makedirs("models")
    print("Created models directory for Vosk")

# TTS settings
TTS_ESPEAK_VOICE = "en"  # Default eSpeak voice
TTS_ESPEAK_SPEED = 150   # Words per minute
TTS_ESPEAK_PITCH = 50    # 0-99

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
    global tts_available
    
    print("Initializing TTS engine...")
    
    # Initialize eSpeak
    try:
        subprocess.run(['espeak', '--version'], capture_output=True)
        print("✅ eSpeak TTS engine initialized")
        tts_available = True
    except Exception as e:
        if get_debug_mode():
            print(f"eSpeak not found: {e}")
        print("⚠️ Error during TTS initialization: {e}")
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
    
    # Add to queue
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
                        print(f"[🔊 Speaking from queue: {text_to_speak}]")
                    
                    try:
                        # Use eSpeak directly via subprocess
                        cmd = [
                            "espeak",
                            "-v", TTS_ESPEAK_VOICE,
                            "-s", str(TTS_ESPEAK_SPEED),
                            "-p", str(TTS_ESPEAK_PITCH),
                            text_to_speak
                        ]
                        subprocess.run(cmd)
                    except Exception as e:
                        print(f"[❌ ERROR in TTS engine: {e}]")
                        # Fallback to print the text that should have been spoken
                        print(f"[TTS TEXT]: {text_to_speak}")
                
                # Whether we succeeded or failed, we're done speaking this item
                with tts_queue_lock:
                    tts_is_speaking = False
            else:
                # No text to speak, sleep briefly
                time.sleep(0.1)
        except Exception as e:
            print(f"[❌ ERROR in TTS queue processor: {e}]")
            time.sleep(1)  # Prevent error loop from consuming CPU

def is_tts_available():
    """Check if TTS is available and working."""
    global tts_available
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
def detect_wake_word(use_porcupine=False, return_buffer=False):
    """
    Detects wake word using Vosk speech recognition.
    Listens for "vortex" or similar variations in speech input.
    
    Args:
        use_porcupine: Parameter kept for compatibility but no longer used.
        return_buffer: If True, returns a pre-buffer of audio data after wake word detection
        
    Returns:
        If return_buffer=False: True if wake word detected, False otherwise
        If return_buffer=True: (True, audio_buffer) if wake word detected, (False, None) otherwise
    """
    # Check for Vosk library
    try:
        from vosk import Model, KaldiRecognizer
        import json
    except ImportError:
        print("[ERROR] Vosk not installed for wake word detection")
        return True
    
    # Check if model exists
    model_path = os.path.join("models", "vosk-model-small-en-us-0.15")
    if not os.path.exists(model_path):
        print("[ERROR] Vosk model not found. Download from: https://alphacephei.com/vosk/models")
        return True
    
    if get_debug_mode():
        print(f"[DEBUG] Listening for wake word 'VORTEX'...")
    else:
        # Always show this basic instruction
        print("[Say 'VORTEX' to activate]")
    
    # Audio parameters for Vosk - reduced chunk size for faster response
    CHUNK = 2048  # Reduced from 4096 to 2048 for more responsive detection
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    p = None
    stream = None
    
    try:
        p = pyaudio.PyAudio()
        
        # Open audio stream
        stream = p.open(format=FORMAT, 
                      channels=CHANNELS, 
                      rate=RATE, 
                      input=True, 
                      frames_per_buffer=CHUNK)
        
        # Load Vosk model for speech recognition
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, RATE)
        recognizer.SetWords(True)  # Enable word timestamps
        
        # Main detection loop
        while True:
            # Read audio chunk with error handling
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
            except IOError as e:
                if get_debug_mode():
                    print(f"[WARNING] Audio stream read error: {e}")
                continue
            
            # Process with Vosk - check partial results FIRST for faster response
            # Check partial results - these are more immediate and processed faster
            partial = json.loads(recognizer.PartialResult())
            if "partial" in partial and partial["partial"]:
                partial_text = partial["partial"].lower()
                
                # Check for wake word in partial recognition
                for variation in WAKE_WORD_VARIATIONS:
                    if variation in partial_text:
                        detected_variation = variation
                        # Always show wake word detection - this is essential
                        print(f"[Wake word '{detected_variation}' detected!]")
                        return True
            
            # Only check full results if no wake word found in partials
            if recognizer.AcceptWaveform(data):
                # Full recognition result
                result = json.loads(recognizer.Result())
                
                if "text" in result and result["text"]:
                    text = result["text"].lower()
                    if get_debug_mode():
                        print(f"[Heard]: {text}")
                    
                    # Check for wake word variations
                    for variation in WAKE_WORD_VARIATIONS:
                        if variation in text:
                            detected_variation = variation
                            # Always show wake word detection - this is essential
                            print(f"[Wake word '{detected_variation}' detected!]")
                            return True
            
            # Check for keyboard interrupt (Enter key) as alternative
            if msvcrt_available:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\r':  # Enter key
                        print("[VORTEX activated via Enter key]")
                        return True
                
    except KeyboardInterrupt:
        print("\n[KeyboardInterrupt in wake word detector]")
    except Exception as e:
        if get_debug_mode():
            print(f"[ERROR] Wake word detection error: {e}")
        else:
            print("[ERROR] Wake word detection failed")
    finally:
        # Clean up resources
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e:
                if get_debug_mode():
                    print(f"[ERROR] Error closing stream: {e}")
                
        if p is not None:
            try:
                p.terminate()
            except Exception as e:
                if get_debug_mode():
                    print(f"[ERROR] Error terminating PyAudio: {e}")
    
    # If we reach here, something went wrong
    if get_debug_mode():
        print("[WARNING] Wake word detection failed, restarting detection...")
    return False

# ------------------------------
# Audio Playback
# ------------------------------
def play_audio(mp3_path):
	"""Plays audio file."""
	try:
		audio = AudioSegment.from_mp3(mp3_path)
		wav_data = io.BytesIO()
		audio.export(wav_data, format="wav")  # Convert to WAV

		wav_data.seek(0)
		sound = AudioSegment.from_wav(wav_data)
		samples = np.array(sound.get_array_of_samples(), dtype=np.int16)

		if get_debug_mode():
			print(f"[🔊 Playing {len(samples)} samples...]")

		# Play audio smoothly
		sd.play(samples, samplerate=sound.frame_rate)
		sd.wait()

		if get_debug_mode():
			print("[✅ Playback Completed]")

	except Exception as e:
		if get_debug_mode():
			print(f"[❌ ERROR in Playback] {e}")

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

def transcribe_audio(audio_path):
    """Transcribes the audio file using Vosk for offline speech recognition."""
    if get_debug_mode():
        print(f"[Transcribing audio: {audio_path}]")
    
    # Check if Vosk is available
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
        # Always show the transcription result, as this is essential information
        print(f"[Transcription]: '{transcript}'")
        
        return transcript if transcript else "I didn't catch that"
    
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return None
