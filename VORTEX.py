# VORTEX.py
import os
import sys
import asyncio
import threading
import time

print("Initializing VORTEX...")

# Configuration - must be set before any imports
USE_OPTIONAL_EXTRAS = False  # Set to False to disable optional extras
USE_WEB_INTERFACE = True     # Set to False to disable web interface
WEB_INTERFACE_PORT = 25566   # Port for web interface

# Set as environment variable for child processes
os.environ['USE_OPTIONAL_EXTRAS'] = 'true' if USE_OPTIONAL_EXTRAS else 'false'
os.environ['VORTEX_WEB_PORT'] = str(WEB_INTERFACE_PORT)

# Add a simple flag to prevent re-initialization
_VORTEX_INITIALIZED = False

# Global for web interface thread
web_thread = None

# Check if we've already gone through initialization
if _VORTEX_INITIALIZED:
    print("WARNING: VORTEX trying to initialize multiple times, skipping...")
else:
    _VORTEX_INITIALIZED = True
    print(f"Starting VORTEX initialization (Process ID: {os.getpid()})")
    
    # Add the src directory to Python's module search path
    # Ensure this points correctly to the directory *containing* the 'src' folder
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root) # Add project root first
    # sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # Original - might be incorrect depending on execution context

    # Initialize capabilities first - this clears the registry ONCE before any other imports
    try:
        from src.Boring.capabilities import initialize_capabilities
        initialize_capabilities()
    except ImportError as e:
        print(f"FATAL ERROR: Could not import or run initialize_capabilities. Ensure src/Boring/capabilities.py exists and src is in PYTHONPATH.")
        print(f"Python Path: {sys.path}")
        print(f"Error details: {e}")
        sys.exit(1) # Exit if core capabilities can't load
    except Exception as e:
        print(f"FATAL ERROR: Unexpected error during capability initialization: {e}")
        sys.exit(1)

    # Load core modules - these will register with the already initialized registry
    try:
        from src.VOICE.voice import detect_wake_word, record_audio, transcribe_audio, tts_speak, wait_for_tts_completion, is_tts_available, list_audio_devices
        # --- VORTEX.PY CHANGE: Import the renamed function ---
        from src.Boring.boring import call_ai_provider, add_user_input, display_startup_message, initialize_ai_client_for_loop
        from src.Boring.debug_logger import log_debug_event
        # -----------------------------------------------------
        from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode
    except ImportError as e:
        print(f"FATAL ERROR: Could not import core VORTEX modules (voice, boring, debug). Check paths and dependencies.")
        print(f"Python Path: {sys.path}")
        print(f"Error details: {e}")
        sys.exit(1)
    except Exception as e:
         print(f"FATAL ERROR: Unexpected error importing core modules: {e}")
         sys.exit(1)

# Define an async wrapper for our tts_speak function to maintain compatibility
async def speak_text(text, wait_for_completion=False):
    """
    Speak text using TTS engine. If TTS is unavailable, prints to console.

    Args:
        text: The text to speak
        wait_for_completion: If True, wait for TTS to complete before returning
    """
    if not text: # Don't try to speak empty strings
        return

    if is_tts_available():
        tts_speak(text) # Add to the TTS queue
        await asyncio.sleep(0.1) # Small delay to ensure the queue processing has started
        if wait_for_completion:
            # Wait in small chunks to keep the event loop responsive
            while not wait_for_tts_completion(timeout=0.5):  # Check every 0.5 seconds
                await asyncio.sleep(0.1)
    else:
        # Fallback if TTS is not working
        print(f"{COLOR_YELLOW}[TTS UNAVAILABLE] VORTEX would say: {text}{COLOR_RESET}")


# ANSI Color Codes for Terminal Output
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_RESET = "\033[0m"

async def process_input(user_input):
    """
    Adds user input to history, calls the configured AI Provider's API,
    and processes the response.
    """
    add_user_input(user_input)  # Add user input to conversation history

    # --- VORTEX.PY CHANGE: Call the renamed function ---
    response = await call_ai_provider()
    # -------------------------------------------------

    return response # Return the response text (or None/error message)

async def main():
    """Main asynchronous loop for VORTEX operation."""
    while True:
        try:
            # --- VORTEX.PY CHANGE: Wait for TTS to complete before listening for wake word ---
            # Make sure any previous TTS has finished before we start listening
            await asyncio.sleep(0.1)  # Small delay to ensure TTS queue is updated
            if is_tts_available():
                if not wait_for_tts_completion(timeout=0.5):
                    log_debug_event("Waiting for TTS to complete before listening...")
                    while not wait_for_tts_completion(timeout=0.5):
                        await asyncio.sleep(0.1)
                    # Add a small pause after speech completion before listening
                    await asyncio.sleep(0.3)
            # --- End of VORTEX.PY CHANGE ---
            
            # --- VORTEX.PY CHANGE: Wake word detection disabled --- 
            # log_debug_event("Wake word detection is currently disabled in VORTEX.py main loop.")
            # print("[Waiting for wake word...]")
            
            # try:
            #     # Consider adding a timeout or making detect_wake_word async if it blocks indefinitely
            #     wake_word_detected = detect_wake_word(ignore_if_speaking=True) # Use the new parameter to ignore wake words when TTS is active

            #     if wake_word_detected:
            #         print("[Wake word detected! Listening for command...]")
                    
            #         try:
            #             if get_debug_mode(): print("[DEBUG] Starting audio recording...")
            #             # Visual indicator that VORTEX is actively listening
            #             print(f"{COLOR_BLUE}[🎤 VORTEX Listening...]{COLOR_RESET}")
            #             audio_file = record_audio()
            #             print(f"{COLOR_BLUE}[✓ VORTEX Done Listening]{COLOR_RESET}")
            #             if not audio_file or not os.path.exists(audio_file):
            #                 print(f"{COLOR_YELLOW}[AUDIO] No audio recorded or file not found.{COLOR_RESET}")
            #                 continue

            #             if get_debug_mode(): print(f"[DEBUG] Audio file created: {audio_file}")

            #             # Use Vosk/Whisper to transcribe the recorded audio
            #             transcription = await transcribe_audio(audio_file)

            #             if transcription and transcription != "I didn't catch that":
            #                 user_input = transcription.strip()
            #                 if get_debug_mode(): print(f"[DEBUG] Transcription successful: '{user_input}'")
            #             else:
            #                 print(f"{COLOR_YELLOW}[TRANSCRIPTION] Could not understand audio or transcription empty.{COLOR_RESET}")
            #                 await speak_text("Sorry, I didn't catch that.")
            #                 user_input = None

            #             if user_input:
            #                 print(f"{COLOR_BLUE}[User] {user_input}{COLOR_RESET}")

            #                 # --- Command Processing ---
            #                 lower_input = user_input.lower()

            #                 # Check for exit command
            #                 if lower_input in ['exit vortex', 'quit vortex', 'shutdown vortex', 'goodbye vortex']:
            #                     shutdown_message = "Shutting down VORTEX. Goodbye!"
            #                     print(f"{COLOR_YELLOW}{shutdown_message}{COLOR_RESET}")
            #                     # Important system message - wait for completion
            #                     await speak_text(shutdown_message, wait_for_completion=True)
            #                     # Potentially add cleanup tasks here
            #                     return # Exit the main loop (and thus the thread)

            #                 # Check for list devices command
            #                 if lower_input in ["list devices", "list audio devices", "show devices", "show microphones", "audio devices"]:
            #                     print("[INFO] Listing audio devices...")
            #                     list_audio_devices() # Assuming this prints to console
            #                     await speak_text("I've listed the available audio devices in the console.")
            #                     continue # Go back to waiting for wake word

            #                 # --- Process normal command through AI ---
            #                 print("[AI Processing...]")
            #                 ai_response = await process_input(user_input)

            #                 if ai_response:
            #                     # Speak the AI's response
            #                     await speak_text(ai_response)
            #                 else:
            #                     # Handle cases where process_input returned None or an error message already printed
            #                     if get_debug_mode(): print("[DEBUG] AI processing returned no speakable response.")
            #                     await speak_text("I encountered an issue processing that request.")

            #             # else: No user input after wake word -> loop back

            #         except Exception as e:
            #             print(f"{COLOR_RED}[ERROR] Audio recording, transcription, or command processing failed: {e}{COLOR_RESET}")
            #             import traceback
            #             if get_debug_mode(): traceback.print_exc()
            #             await speak_text("Sorry, I ran into an error while handling your command.")
            #             # Avoid immediate retry loops for persistent errors
            #             await asyncio.sleep(1)

            #     else:
            #         # Allow checking for wake word periodically if detect_wake_word has a timeout
            #         # If detect_wake_word is fully blocking, this part might not be reached often
            #         # Consider adding a very short sleep if detect_wake_word returns False immediately
            #         # await asyncio.sleep(0.1) # Short pause if wake word detection isn't blocking
            #         pass # If detect_wake_word is blocking, loop continues naturally

            # except Exception as e:
            #     # This catches errors specifically in the wake word detection phase
            #     print(f"{COLOR_RED}[ERROR] Wake word detection failed: {e}{COLOR_RESET}")
            #     if get_debug_mode():
            #         import traceback
            #         traceback.print_exc()
            #         print(f"{COLOR_RED}[DEBUG] Continuing wake word detection loop...{COLOR_RESET}")
            #     # Don't restart VORTEX, just wait a bit and continue the loop
            #     await asyncio.sleep(2) # Longer sleep after wake word error
            #     continue
            # --- End of VORTEX.PY CHANGE: Wake word detection disabled --- 

            # Keep the loop alive but prevent it from spinning too fast
            await asyncio.sleep(1) 

        except KeyboardInterrupt:
            print(f"\n{COLOR_YELLOW}[KeyboardInterrupt] Exiting VORTEX.{COLOR_RESET}")
            break # Exit the main loop

        except Exception as e:
            # Catch-all for unexpected errors in the main loop itself
            print(f"{COLOR_RED}[ERROR] An unexpected critical error occurred in the main loop: {e}{COLOR_RESET}")
            if get_debug_mode():
                import traceback
                traceback.print_exc()
                log_debug_event(f"Traceback printed for critical main loop error: {e}", is_error=True)
            print(f"{COLOR_YELLOW}[INFO] Attempting to continue...{COLOR_RESET}")
            await asyncio.sleep(5) # Wait significantly longer after a major loop error

def start_web_interface():
    """Start the VORTEX web interface in a separate thread"""
    global web_thread
    
    if not USE_WEB_INTERFACE:
        print(f"{COLOR_YELLOW}[INFO] Web interface disabled in configuration.{COLOR_RESET}")
        return
    
    try:
        from src.remote.app import app, socketio
        
        def run_web_server():
            print(f"{COLOR_GREEN}[INFO] Starting VORTEX Web Interface on port {WEB_INTERFACE_PORT}{COLOR_RESET}")
            print(f"{COLOR_GREEN}[INFO] Web interface available at http://127.0.0.1:{WEB_INTERFACE_PORT}{COLOR_RESET}")
            socketio.run(app, host='0.0.0.0', port=WEB_INTERFACE_PORT, debug=False, allow_unsafe_werkzeug=True, use_reloader=False)
        
        web_thread = threading.Thread(target=run_web_server, name="VortexWebThread", daemon=True)
        web_thread.start()
        
    except ImportError as e:
        print(f"{COLOR_YELLOW}[WARN] Could not start web interface: {e}{COLOR_RESET}")
        print(f"{COLOR_YELLOW}[WARN] Make sure you have installed the required dependencies: flask flask-socketio flask-cors{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}[ERROR] Failed to start web interface: {e}{COLOR_RESET}")
        if get_debug_mode():
            import traceback
            traceback.print_exc()
            log_debug_event(f"Traceback printed for web interface startup error: {e}", is_error=True)

def stop_web_interface():
    """Stop the VORTEX web interface"""
    global web_thread
    
    if web_thread and web_thread.is_alive():
        print(f"{COLOR_YELLOW}[INFO] Stopping VORTEX Web Interface...{COLOR_RESET}")
        # The thread is daemon, so it will be terminated when the main program exits
        # But we can do cleanup here if needed in the future

# --- Main Execution Block ---
if __name__ == "__main__":
    # Optional: Clear console on startup (consider platform compatibility)
    # os.system('cls' if os.name == 'nt' else 'clear')

    # Display startup message from boring.py
    try:
        display_startup_message()
    except NameError:
        print("[ERROR] display_startup_message not found. Check imports.")
    except Exception as e:
        print(f"[ERROR] Failed to display startup message: {e}")

    # Start web interface
    start_web_interface()

    # Show wake word detection message
    # TODO: Potentially get wake word from config/voice module?
    print(f"{COLOR_GREEN}[INFO] Using Vosk for wake word detection. Say 'VORTEX' (or similar) to activate.{COLOR_RESET}")

    # Show TTS status
    try:
        if is_tts_available():
            print(f"{COLOR_GREEN}[INFO] Text-to-Speech is available.{COLOR_RESET}")
        else:
            print(f"{COLOR_YELLOW}[WARN] Text-to-Speech is unavailable. Falling back to text output.{COLOR_RESET}")
    except NameError:
         print(f"{COLOR_YELLOW}[WARN] Could not check TTS status (is_tts_available not found).{COLOR_RESET}")
    except Exception as e:
         print(f"{COLOR_RED}[ERROR] Error checking TTS status: {e}{COLOR_RESET}")


    # --- Threading Setup ---
    # Use a flag or event to signal shutdown from the main thread or KeyboardInterrupt
    shutdown_event = threading.Event()

    def run_asyncio_loop():
        """Runs the main async loop and handles graceful shutdown."""
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Initialize AI client within the new loop/thread context
            try:
                initialize_ai_client_for_loop()
            except Exception as client_init_e:
                print(f"{COLOR_RED}[FATAL ERROR] AI Client initialization failed in thread: {client_init_e}{COLOR_RESET}")
                # Log to debug logger if available
                try: log_debug_event(f"AI Client init failed: {client_init_e}", is_error=True) 
                except: pass # Avoid error in error handling
                # Signal shutdown or exit if client is critical
                shutdown_event.set()
                return # Exit this function, thread will stop

            # Run until main() completes OR shutdown_event is set
            main_task = loop.create_task(main())
            monitor_task = loop.create_task(monitor_shutdown(shutdown_event, main_task))
            
            try:
                loop.run_until_complete(asyncio.gather(main_task, monitor_task))
            finally:
                # Ensure cleanup happens even if there's an error
                try:
                    from src.Boring.boring import cleanup_ai_client
                    loop.run_until_complete(cleanup_ai_client())
                except Exception as cleanup_e:
                    print(f"{COLOR_RED}[WARN] Error during AI client cleanup: {cleanup_e}{COLOR_RESET}")
                finally:
                    loop.close()
                    
        except KeyboardInterrupt:
            print("\n[INFO] KeyboardInterrupt caught in thread. Signaling shutdown...")
            shutdown_event.set()
        except Exception as e:
             print(f"{COLOR_RED}[ERROR] Critical error in async loop runner: {e}{COLOR_RESET}")
             if get_debug_mode():
                 import traceback
                 traceback.print_exc()
                 log_debug_event(f"Traceback printed for critical error in async loop runner: {e}", is_error=True)
             shutdown_event.set() # Signal shutdown on unexpected error too

    async def monitor_shutdown(event, task_to_monitor):
        """Coroutine to wait for shutdown signal and cancel the main task."""
        while not event.is_set():
            if task_to_monitor.done(): # Exit if main task finishes naturally
                break
            await asyncio.sleep(0.5) # Check periodically
        print("[INFO] Shutdown signal received, cancelling main task...")
        if not task_to_monitor.done():
            task_to_monitor.cancel()
            try:
                await task_to_monitor # Allow cancellation to propagate
            except asyncio.CancelledError:
                print("[INFO] Main task cancelled successfully.")
        # Signal main thread that shutdown is complete? (optional)


    print("[INFO] Starting AI processing thread...")
    ai_thread = threading.Thread(target=run_asyncio_loop, name="VortexAIThread", daemon=True)
    ai_thread.start()

    # Keep the main thread alive to catch KeyboardInterrupt and manage shutdown
    try:
        while ai_thread.is_alive():
            # Keep main thread responsive, sleep allows signal handling
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}[KeyboardInterrupt] Caught in main thread. Signaling AI thread to shut down...{COLOR_RESET}")
        shutdown_event.set() # Signal the async loop to stop

    # Wait for the AI thread to finish cleaning up
    print("[INFO] Waiting for AI thread to terminate...")
    ai_thread.join(timeout=5.0) # Wait max 5 seconds

    if ai_thread.is_alive():
        print(f"{COLOR_RED}[ERROR] AI thread did not terminate gracefully.{COLOR_RESET}")
        # Consider os._exit(1) here if forceful exit is required

    # Stop web interface before exiting
    stop_web_interface()
    
    print(f"{COLOR_GREEN}[INFO] VORTEX shut down complete.{COLOR_RESET}")