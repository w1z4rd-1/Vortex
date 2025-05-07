#!/usr/bin/env python
# VORTEX Web Interface Server
# A simple web server that provides a browser-based interface to VORTEX
# Requirements: flask flask-socketio flask-cors

import os
import sys
import json
import asyncio
import threading
import base64
import tempfile
import wave
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
import io
import time
import logging
import traceback
from typing import Optional, Tuple
import requests

# Add the project root to the Python path to import VORTEX modules
project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Import Flask and related extensions
from flask import Flask, render_template, request, jsonify, send_from_directory, Response
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Check for FFmpeg availability
FFMPEG_AVAILABLE = False
try:
    result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        FFMPEG_AVAILABLE = True
        print("FFmpeg is available for audio conversion")
    else:
        print("FFmpeg command exists but returned an error. Audio conversion may be limited.")
except FileNotFoundError:
    print("FFmpeg not found. You'll need to install FFmpeg for reliable audio conversion.")
    print("Download from: https://ffmpeg.org/download.html")
except Exception as e:
    print(f"Error checking for FFmpeg: {e}")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'vortex-remote-secret-key'
CORS(app)  # Enable Cross-Origin Resource Sharing
socketio = SocketIO(app, cors_allowed_origins="*")

# Setup logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app.logger.setLevel(logging.INFO)

# Create directories for storing temporary audio files
TEMP_DIR = Path(tempfile.gettempdir()) / "vortex_web"
TEMP_DIR.mkdir(exist_ok=True)

# Patch for TTS file access issue
def setup_tts_temp_dir():
    """Create a separate temp directory for TTS to avoid file access conflicts"""
    tts_temp_dir = Path(tempfile.gettempdir()) / "vortex_tts"
    tts_temp_dir.mkdir(exist_ok=True)
    
    # Check if we need to modify the main VORTEX temp directory
    vortex_temp_dir = Path("temp")
    if vortex_temp_dir.exists():
        # Create a symlink or copy the directory if it doesn't exist yet
        try:
            # Use the new directory for TTS outputs
            os.environ["VORTEX_TTS_DIR"] = str(tts_temp_dir)
            app.logger.info(f"Set TTS directory to: {tts_temp_dir}")
        except Exception as e:
            app.logger.error(f"Failed to set up TTS directory: {e}")

# Call during startup
setup_tts_temp_dir()

# Import VORTEX functionality
try:
    from src.Boring.boring import call_ai_provider, add_user_input
    from src.VOICE.voice import transcribe_audio
    from src.Capabilities.debug_mode import get_debug_mode, set_debug_mode
    VORTEX_IMPORTS_OK = True
except ImportError as e:
    app.logger.error(f"Failed to import VORTEX modules: {e}")
    app.logger.error("Web interface will operate in limited mode.")
    VORTEX_IMPORTS_OK = False

# Try to import OpenAI for Whisper transcription when needed
OPENAI_AVAILABLE = False
try:
    import openai
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if OPENAI_API_KEY:
        OPENAI_AVAILABLE = True
        app.logger.info("OpenAI API is available for Whisper transcription")
    else:
        app.logger.warning("OpenAI API key not found in environment variables")
except ImportError:
    app.logger.warning("OpenAI package not installed, will use local transcription")

# Fix for file access issues - safety copy function
def safe_copy_file(src_path, dest_path):
    """Safely copy a file, handling any file access errors"""
    max_retries = 3
    retry_delay = 0.5  # seconds
    
    for attempt in range(max_retries):
        try:
            # Make sure destination directory exists
            os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
            
            # Check if source file exists and is readable
            if not os.path.exists(src_path):
                app.logger.error(f"Source file does not exist: {src_path}")
                return False
                
            # First try a safe copy operation
            shutil.copy2(src_path, dest_path)
            app.logger.info(f"Successfully copied file: {src_path} -> {dest_path}")
            return True
        except (IOError, PermissionError) as e:
            app.logger.warning(f"File access error (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(retry_delay)
        except Exception as e:
            app.logger.error(f"Unexpected error copying file: {e}")
            return False
    
    app.logger.error(f"Failed to copy file after {max_retries} attempts: {src_path}")
    return False

# Function to convert audio using FFmpeg
def convert_to_wav(input_path, output_path):
    """Convert audio to WAV format using FFmpeg"""
    if not FFMPEG_AVAILABLE:
        app.logger.error("FFmpeg not available for audio conversion")
        return False
        
    input_path_str = str(input_path)
    output_path_str = str(output_path)
    
    try:
        # Explicitly specify input format for WebM files to avoid detection issues
        input_format = "-f webm" if input_path_str.endswith(".webm") else ""
        
        # Use ffmpeg to convert the file
        command = f'ffmpeg -y {input_format} -i "{input_path_str}" -acodec pcm_s16le -ar 16000 -ac 1 "{output_path_str}"'
        app.logger.info(f"Running conversion command: {command}")
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            app.logger.error(f"FFmpeg error: {result.stderr}")
            return False
        
        # Check if output file exists and has size
        if os.path.exists(output_path_str) and os.path.getsize(output_path_str) > 0:
            app.logger.info(f"Successfully converted to WAV: {output_path_str} ({os.path.getsize(output_path_str)} bytes)")
            return True
        else:
            app.logger.error(f"Output file missing or empty: {output_path_str}")
            return False
    except Exception as e:
        app.logger.error(f"Conversion error: {str(e)}")
        app.logger.error(traceback.format_exc())
        return False

# Use Whisper via OpenAI API for transcription when enabled
async def transcribe_with_whisper(audio_file_path):
    """Use OpenAI Whisper API to transcribe audio when OpenAI is the provider"""
    if not OPENAI_AVAILABLE:
        app.logger.warning("OpenAI not available for Whisper transcription, using local method")
        return await transcribe_audio(audio_file_path)
    
    try:
        app.logger.info(f"Transcribing with OpenAI Whisper: {audio_file_path}")
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        with open(audio_file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"
            )
        
        transcription = response.text
        app.logger.info(f"Whisper transcription: {transcription}")
        return transcription
    except Exception as e:
        app.logger.error(f"Whisper transcription error: {e}")
        app.logger.error(traceback.format_exc())
        # Fall back to local transcription
        app.logger.info("Falling back to local transcription")
        return await transcribe_audio(audio_file_path)

# Determine whether to use Whisper based on AI provider
def should_use_whisper():
    """Check if we should use Whisper for transcription"""
    try:
        # Get the AI provider name directly from environment variable
        provider = os.getenv("AI_PROVIDER", "openai").lower()
        app.logger.debug(f"Current AI provider: {provider}")
        
        # Use Whisper when OpenAI is the provider
        if provider == "openai" and OPENAI_AVAILABLE:
            app.logger.info("AI Provider is OpenAI, enabling Whisper transcription")
            return True
        else:
            app.logger.info(f"AI Provider is {provider}, using local transcription")
            return False
    except Exception as e:
        app.logger.error(f"Error checking AI provider: {e}")
        return False

def _create_silent_wav(output_path, duration_ms=500):
    """Create a silent WAV file of specified duration in milliseconds"""
    try:
        # Convert the output_path to a string to handle Path objects
        output_path_str = str(output_path)
        
        # First try using pydub if available
        try:
            from pydub import AudioSegment
            silence = AudioSegment.silent(duration=duration_ms)
            silence.export(output_path_str, format="wav")
            app.logger.info(f"Created silent WAV using pydub: {output_path_str}")
            return os.path.exists(output_path_str)
        except (ImportError, ModuleNotFoundError):
            app.logger.info("pydub not available, falling back to ffmpeg")
        except Exception as e:
            app.logger.warning(f"pydub error: {e}, falling back to ffmpeg")
        
        # Fall back to ffmpeg if pydub fails or isn't available
        if FFMPEG_AVAILABLE:
            duration_sec = duration_ms / 1000.0
            
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=16000:cl=mono",
                "-t", str(duration_sec),
                "-ar", "16000",
                "-ac", "1",
                "-acodec", "pcm_s16le",
                output_path_str
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            app.logger.info(f"Created silent WAV using ffmpeg: {output_path_str}")
            return os.path.exists(output_path_str)
        
        # Manual WAV file creation as last resort
        app.logger.warning("Creating silent WAV manually as last resort")
        # Create a minimal WAV file manually
        wav_file = wave.open(output_path_str, 'wb')
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz
        
        # Create 16kHz * (duration_ms/1000) silent samples
        num_frames = int(16000 * (duration_ms / 1000.0))
        silence_data = b'\x00\x00' * num_frames  # 16-bit silence
        wav_file.writeframes(silence_data)
        wav_file.close()
        
        app.logger.info(f"Created silent WAV manually: {output_path_str}")
        return os.path.exists(output_path_str)
    except Exception as e:
        app.logger.error(f"Failed to create silent WAV: {e}")
        try:
            # Emergency minimal WAV header
            with open(output_path_str, 'wb') as f:
                # Write WAV header
                f.write(b'RIFF')
                f.write((36).to_bytes(4, byteorder='little'))  # Size
                f.write(b'WAVE')
                # Format chunk
                f.write(b'fmt ')
                f.write((16).to_bytes(4, byteorder='little'))  # Chunk size
                f.write((1).to_bytes(2, byteorder='little'))   # PCM format
                f.write((1).to_bytes(2, byteorder='little'))   # Channels
                f.write((16000).to_bytes(4, byteorder='little'))  # Sample rate
                f.write((32000).to_bytes(4, byteorder='little'))  # Byte rate
                f.write((2).to_bytes(2, byteorder='little'))   # Block align
                f.write((16).to_bytes(2, byteorder='little'))  # Bits per sample
                # Data chunk
                f.write(b'data')
                f.write((0).to_bytes(4, byteorder='little'))   # Data size
                # No actual data
            app.logger.info("Created emergency minimal WAV header")
            return os.path.exists(output_path_str)
        except Exception as inner_e:
            app.logger.error(f"Emergency WAV creation failed: {inner_e}")
            return False
    except Exception as e:
        app.logger.error(f"FFmpeg error creating silent WAV: {result.stderr}")
        return False

def validate_audio_data(audio_bytes, expected_format="webm"):
    """Simple validation of audio data"""
    if not audio_bytes:
        return False, "Empty audio data"
    
    # Check minimum size
    if len(audio_bytes) < 100:
        return False, f"Audio data too small: {len(audio_bytes)} bytes"
    
    # For WebM, check for common header bytes
    if expected_format == "webm" and not audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        # Not technically an error, just a warning
        app.logger.warning("WebM header not detected, but proceeding anyway")
    
    return True, "Audio data looks valid"

def cleanup_temp_files(file_paths, delay=0):
    """Clean up temporary files with optional delay"""
    def _cleanup():
        if delay > 0:
            time.sleep(delay)
        
        for path in file_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    app.logger.debug(f"Removed temp file: {path}")
            except Exception as e:
                app.logger.warning(f"Failed to remove temp file {path}: {e}")
    
    # Run cleanup in background if delay is set
    if delay > 0:
        threading.Thread(target=_cleanup, daemon=True).start()
    else:
        _cleanup()

@app.route('/')
def index():
    """Serve the main web interface page"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/health')
def health():
    """Health check endpoint"""
    status = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "ai_provider": os.getenv("AI_PROVIDER", "local").lower(),
        "ffmpeg_available": FFMPEG_AVAILABLE,
        "vortex_imports_ok": VORTEX_IMPORTS_OK,
        "whisper_available": OPENAI_AVAILABLE,
        "using_whisper": should_use_whisper()
    }
    return jsonify(status)

@app.route('/api/text', methods=['POST'])
def process_text():
    """Process text input directly from the web interface"""
    data = request.json
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    if not VORTEX_IMPORTS_OK:
        return jsonify({"error": "VORTEX modules not available"}), 500
    
    try:
        # Add user input to conversation history
        add_user_input(text)
        
        # Process with VORTEX and get response
        # Use a thread event to coordinate async
        response_event = threading.Event()
        response_data = {"response": None, "error": None}
        
        async def process_async():
            try:
                result = await call_ai_provider()
                response_data["response"] = result
            except Exception as e:
                response_data["error"] = str(e)
            response_event.set()
            
        # Start async processing in a new thread
        asyncio.run(process_async())
        
        # Wait for response with timeout
        if not response_event.wait(timeout=60):
            return jsonify({"error": "Request timed out"}), 504
            
        if response_data["error"]:
            return jsonify({"error": response_data["error"]}), 500
            
        return jsonify({"response": response_data["response"]})
        
    except Exception as e:
        app.logger.error(f"Error processing text: {e}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/audio', methods=['POST'])
def process_audio():
    """Process audio input from the web interface"""
    if not VORTEX_IMPORTS_OK:
        return jsonify({"error": "VORTEX modules not available"}), 500
    
    temp_files = []  # Keep track of temp files for cleanup
    
    try:
        # Check if we received audio data
        if 'audio' not in request.files:
            app.logger.error("No audio file in request")
            return jsonify({"error": "No audio file provided"}), 400
        
        # Get the audio file
        audio_file = request.files['audio']
        if not audio_file:
            return jsonify({"error": "Empty audio file"}), 400
        
        # Save the audio file to a temporary location
        timestamp = int(time.time())
        temp_audio_path = TEMP_DIR / f"vortex_audio_{timestamp}.webm"
        audio_file.save(temp_audio_path)
        temp_files.append(temp_audio_path)
        
        app.logger.info(f"Saved audio file to {temp_audio_path}")
        
        # Convert audio to WAV for processing
        wav_path = TEMP_DIR / f"vortex_audio_{timestamp}.wav"
        temp_files.append(wav_path)
        
        if not convert_to_wav(temp_audio_path, wav_path):
            cleanup_temp_files(temp_files)
            return jsonify({"error": "Failed to convert audio to WAV"}), 500
        
        # Process the audio file
        response_event = threading.Event()
        response_data = {"transcription": None, "response": None, "error": None}
        
        async def process_audio_async():
            try:
                # Determine whether to use Whisper or local transcription
                use_whisper = should_use_whisper()
                
                # Transcribe the audio
                if use_whisper:
                    app.logger.info("Using Whisper transcription")
                    transcription = await transcribe_with_whisper(str(wav_path))
                else:
                    app.logger.info("Using local transcription")
                    transcription = await transcribe_audio(str(wav_path))
                
                response_data["transcription"] = transcription
                
                if not transcription or transcription == "I didn't catch that":
                    response_data["error"] = "Could not understand audio"
                    response_event.set()
                    return
                
                # Add transcription to conversation history
                add_user_input(transcription)
                
                # Process with VORTEX and get response
                result = await call_ai_provider()
                response_data["response"] = result
                
            except Exception as e:
                app.logger.error(f"Error processing audio: {e}")
                app.logger.error(traceback.format_exc())
                response_data["error"] = str(e)
            
            response_event.set()
        
        # Run async processing
        thread = threading.Thread(target=lambda: asyncio.run(process_audio_async()))
        thread.daemon = True
        thread.start()
        
        # Wait for response with timeout
        if not response_event.wait(timeout=60):
            cleanup_temp_files(temp_files)
            return jsonify({"error": "Request timed out"}), 504
        
        # Clean up temporary files with a delay to ensure they're not in use
        cleanup_temp_files(temp_files, delay=1)
        
        if response_data["error"]:
            return jsonify({"error": response_data["error"]}), 500
        
        return jsonify({
            "transcription": response_data["transcription"],
            "response": response_data["response"]
        })
        
    except Exception as e:
        app.logger.error(f"Error processing audio: {e}")
        app.logger.error(traceback.format_exc())
        cleanup_temp_files(temp_files)
        return jsonify({"error": str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    app.logger.info(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    app.logger.info(f"Client disconnected: {request.sid}")

@socketio.on('audio_stream')
def handle_audio_stream(data):
    """Process audio stream from the client"""
    temp_files = []  # Keep track of temp files for cleanup
    
    try:
        if not VORTEX_IMPORTS_OK:
            emit('error', {"message": "VORTEX modules not available"})
            return
        
        # Check that we received audio data
        audio_data = data.get('audio')
        if not audio_data:
            emit('error', {"message": "No audio data received"})
            return
        
        # Decode base64 audio data
        try:
            audio_bytes = base64.b64decode(audio_data.split(',')[1] if ',' in audio_data else audio_data)
        except Exception as e:
            emit('error', {"message": f"Failed to decode audio data: {e}"})
            return
        
        # Validate audio data
        valid, reason = validate_audio_data(audio_bytes)
        if not valid:
            emit('error', {"message": reason})
            return
        
        # Save to temporary file
        timestamp = int(time.time())
        temp_audio_path = TEMP_DIR / f"vortex_stream_{timestamp}.webm"
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_bytes)
        temp_files.append(temp_audio_path)
        
        # Convert to WAV
        wav_path = TEMP_DIR / f"vortex_stream_{timestamp}.wav"
        temp_files.append(wav_path)
        
        if not convert_to_wav(temp_audio_path, wav_path):
            emit('error', {"message": "Failed to convert audio format"})
            cleanup_temp_files(temp_files)
            return
        
        # Process audio asynchronously
        async def process_stream_async():
            try:
                # Emit status update
                emit('status', {"status": "processing"})
                
                # Determine whether to use Whisper or local transcription
                use_whisper = should_use_whisper()
                
                # Transcribe audio
                if use_whisper:
                    emit('status', {"status": "transcribing with Whisper"})
                    transcription = await transcribe_with_whisper(str(wav_path))
                else:
                    emit('status', {"status": "transcribing locally"})
                    transcription = await transcribe_audio(str(wav_path))
                
                if not transcription or transcription == "I didn't catch that":
                    emit('error', {"message": "Could not understand audio"})
                    return
                
                # Send transcription to client
                emit('transcription', {"text": transcription})
                
                # Add to conversation history
                add_user_input(transcription)
                
                # Get AI response
                ai_response = await call_ai_provider()
                
                # Send response to client
                emit('response', {"text": ai_response})
                
            except Exception as e:
                app.logger.error(f"Error processing stream: {e}")
                app.logger.error(traceback.format_exc())
                emit('error', {"message": str(e)})
            finally:
                # Clean up with a delay to ensure files aren't in use
                cleanup_temp_files(temp_files, delay=1)
        
        # Run async processing in a thread
        threading.Thread(target=lambda: asyncio.run(process_stream_async())).start()
        
    except Exception as e:
        app.logger.error(f"Error in audio stream handler: {e}")
        app.logger.error(traceback.format_exc())
        cleanup_temp_files(temp_files)
        emit('error', {"message": str(e)})

@app.route('/api/tts', methods=['POST'])
async def api_tts():
    if not VORTEX_IMPORTS_OK:
        return jsonify({"error": "VORTEX core modules not loaded"}), 500

    raw_data = request.data          # Get raw data (synchronous)
    data = json.loads(raw_data)       # Then parse JSON
    text_to_speak = data.get('text')

    if not text_to_speak:
        return jsonify({"error": "No text provided"}), 400

    # Check if OpenAI TTS should be used (from .env)
    # This logic is similar to src/VOICE/voice.py
    # Ensure OPENAI_API_KEY and AI_PROVIDER are accessible here
    # For simplicity, we assume they are loaded via load_dotenv() at the top of app.py
    # and OPENAI_API_KEY is already checked by OPENAI_AVAILABLE
    
    ai_provider_env = os.getenv("AI_PROVIDER", "local").lower()
    openai_api_key_env = os.getenv("OPENAI_API_KEY")

    if ai_provider_env == "openai" and openai_api_key_env:
        try:
            selected_voice = data.get('voice', 'nova') # Get voice from request, default to nova
            
            headers = {
                "Authorization": f"Bearer {openai_api_key_env}"
            }
            api_url = "https://api.openai.com/v1/audio/speech"
            payload = {
                "model": "tts-1", # Hardcoded to tts-1 for speed
                "voice": selected_voice, # Use selected voice
                "input": text_to_speak,
                "response_format": "mp3"
            }
            
            # Use asyncio.to_thread to run the blocking requests.post call
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.post(api_url, headers=headers, json=payload))

            if response.status_code == 200:
                # Create a temporary file for the audio
                # Using a BytesIO buffer is cleaner for sending response
                audio_io = io.BytesIO(response.content)
                return Response(audio_io.getvalue(), mimetype="audio/mpeg")
            else:
                error_message = f"OpenAI TTS API request failed with status {response.status_code}: {response.text}"
                app.logger.error(error_message)
                return jsonify({"error": "Failed to generate speech with OpenAI", "details": error_message}), 500
        except Exception as e:
            app.logger.error(f"OpenAI TTS failed: {e}")
            app.logger.error(traceback.format_exc())
            return jsonify({"error": "OpenAI TTS processing error", "details": str(e)}), 500
    else:
        # If not using OpenAI, we indicate that the client should use browser's speech synthesis
        return jsonify({"message": "OpenAI TTS not configured, use client-side synthesis."}), 202 # 202 Accepted, but not processed by this endpoint for TTS

# This is only run when the script is executed directly, not when imported
if __name__ == '__main__':
    # Set debug mode for the web interface
    set_debug_mode(True)
    
    # Get port from environment variable or use default
    port = int(os.environ.get('VORTEX_WEB_PORT', 25566))
    
    print(f"Starting VORTEX Web Interface on port {port}")
    print(f"Web interface available at http://127.0.0.1:{port}")
    
    # Start the Flask application
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True, use_reloader=False) 