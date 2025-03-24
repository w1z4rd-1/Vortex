print("Initializing VORTEX...")

# Configuration - must be set before any imports
USE_OPTIONAL_EXTRAS = False  # Set to False to disable optional extras
USE_PORCUPINE = False  # Set to False to use energy-based wake word detection instead of Porcupine

# Set as environment variable for child processes
import os
os.environ['USE_OPTIONAL_EXTRAS'] = 'true' if USE_OPTIONAL_EXTRAS else 'false'
os.environ['USE_PORCUPINE'] = 'true' if USE_PORCUPINE else 'false'

import asyncio
import threading
import sys
import time

# Add the src directory to Python's module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Initialize capabilities first - this clears the registry ONCE before any other imports
from src.Boring.capabilities import initialize_capabilities
initialize_capabilities()

# Load core modules - these will register with the already initialized registry
from src.VOICE.voice import detect_wake_word, record_audio, transcribe_audio, tts_speak, wait_for_tts_completion, is_tts_available, list_audio_devices
from src.Boring.boring import call_openai, add_user_input, display_startup_message
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode

# Define an async wrapper for our tts_speak function to maintain compatibility
async def speak_text(text, wait_for_completion=False):
    """
    Speak text using TTS engine.
    
    Args:
        text: The text to speak
        wait_for_completion: If True, wait for TTS to complete before returning
    """
    # Add to the TTS queue
    tts_speak(text)
    
    # Small delay to ensure the queue processing has started
    await asyncio.sleep(0.1)
    
    # Optionally wait for completion
    if wait_for_completion:
        # Wait in small chunks to keep the event loop responsive
        while not wait_for_tts_completion(timeout=0.5):  # Check every 0.5 seconds
            await asyncio.sleep(0.1)

# ANSI Color Codes for Terminal Output
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"  # Added for warning messages
COLOR_RESET = "\033[0m"

async def process_input(user_input):
    """
    Calls OpenAI's API and processes the user input.
    """
    add_user_input(user_input)  # Add user input once
    response = await call_openai()  # Call OpenAI API
    return response # Return the response

async def main():
    while True:
        try:
            print("[Waiting for wake word...]")  # Always show this message
            
            try:
                # Set a timeout for wake word detection to prevent hanging
                wake_word_detected = detect_wake_word(use_porcupine=USE_PORCUPINE)
                if wake_word_detected:
                    # First activate VORTEX with wake word
                    print("[Listening for your command...]")
                    
                    # Now record what the user actually wants to say
                    try:
                        if get_debug_mode():
                            print("[DEBUG] Starting audio recording immediately...")
                        audio_file = record_audio()
                        if get_debug_mode():
                            print(f"[DEBUG] Audio file created: {audio_file}")
                        
                        # Use Vosk to transcribe the recorded audio
                        if os.path.exists(audio_file):
                            transcription = transcribe_audio(audio_file)
                            if transcription and transcription != "I didn't catch that":
                                user_input = transcription
                                if get_debug_mode():
                                    print(f"[DEBUG] Transcription successful: '{user_input}'")
                            else:
                                print(f"{COLOR_RED}[TRANSCRIPTION ERROR]{COLOR_RESET}")
                                user_input = None
                        else:
                            print(f"{COLOR_RED}[TRANSCRIPTION ERROR] Audio file not found: {audio_file}{COLOR_RESET}")
                            user_input = None
                        
                        if user_input:
                            print(f"[Command received: {user_input}]")

                            # Process exit command
                            if user_input.lower() in ['exit', 'quit']:
                                shutdown_message = "Shutting down VORTEX."
                                if get_debug_mode():
                                    print(shutdown_message)
                                # Important system message - wait for completion
                                await speak_text(shutdown_message, wait_for_completion=True)
                                return

                            # Process list devices command
                            if user_input.lower() in ["list devices", "list audio devices", "show devices", "show microphones"]:
                                list_audio_devices()
                                continue

                            # Process normal command through OpenAI
                            response = await process_input(user_input)
                            if response:
                                await speak_text(response)
                        else:
                            print(f"{COLOR_RED}[No command received due to transcription error]{COLOR_RESET}")
                    except Exception as e:
                        print(f"{COLOR_RED}[ERROR] Audio recording/transcription failed: {e}{COLOR_RESET}")
                        if get_debug_mode():
                            print(f"{COLOR_RED}[DEBUG] Exception details: {type(e).__name__}{COLOR_RESET}")
                else:
                    # Allow checking for wake word periodically
                    if get_debug_mode():
                        print(".", end="", flush=True)  # Progress indicator only in debug mode
                    await asyncio.sleep(0.1)  # Short pause before checking again
                    continue
            except Exception as e:
                print(f"{COLOR_RED}[ERROR] Wake word detection failed: {e}{COLOR_RESET}")
                if get_debug_mode():
                    print("Restarting wake word detection...")
                await asyncio.sleep(1)
                continue
                
        except KeyboardInterrupt:
            print(f"\n{COLOR_YELLOW}[KeyboardInterrupt] Exiting VORTEX.{COLOR_RESET}")
            break
        except Exception as e:
            print(f"{COLOR_RED}[ERROR] An unexpected error occurred: {e}{COLOR_RESET}")
            await asyncio.sleep(1)  # Prevent error loops from consuming resources

if __name__ == "__main__":
    # os.system('cls')
    display_startup_message()
   
    # Show which wake word detection method is being used
    if USE_PORCUPINE:
        print(f"{COLOR_GREEN}[✓] Using Porcupine for wake word detection{COLOR_RESET}")
    else:
        print(f"{COLOR_GREEN}[✓] Using Vosk for wake word detection - say 'VORTEX' or similar to activate{COLOR_RESET}")
   
    # Show TTS status
    if is_tts_available():
        print(f"{COLOR_GREEN}[✓] Text-to-Speech is available and working{COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}[!] Text-to-Speech is unavailable - falling back to text output{COLOR_RESET}")
   
    # Start AI loop in a background thread
    def run_asyncio():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    ai_thread = threading.Thread(target=run_asyncio, daemon=True)
    ai_thread.start()

    # Keep VORTEX running indefinitely to prevent unexpected exits
    while True:
        time.sleep(1)  # Prevents high CPU usage
