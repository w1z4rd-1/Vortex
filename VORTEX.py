print("Initializing VORTEX...")
import asyncio
import os
import threading
import time
from voice import detect_wake_word, record_audio, transcribe_audio, tts_speak
from boring import call_openai, add_user_input, display_startup_message
from functions import get_debug_mode

# ANSI Color Codes for Terminal Output
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"

async def process_input(user_input):
    """
    Calls OpenAI's API, gets the full response, and speaks it.
    """
    add_user_input(user_input)
    response = await call_openai()  # ✅ AI waits for full response before speaking

    if response:
        tts_speak(response)  # ✅ Speak full response after receiving it

async def main():
    mode = "text"  # Start in text mode by default.
    previous_mode = mode  # ✅ Track previous mode to detect changes

    while True:
        if mode == "text":
            user_input = input("You: ").strip()
        else:
            # ✅ Only announce voice mode activation when switching modes
            if mode != previous_mode:
                message = "Voice mode activated. Please speak..."
                if get_debug_mode():
                    print(message)  # ✅ Show only in debug mode
                tts_speak(message)  # ✅ Speak mode change
            
            if detect_wake_word():
                audio_file = record_audio()
                user_input = transcribe_audio(audio_file)

                if user_input:
                    if get_debug_mode():
                        print(f"[User]: {user_input}")  # ✅ Show only in debug mode
                else:
                    error_message = "No voice input detected."
                    if get_debug_mode():
                        print(error_message)  # ✅ Show only in debug mode
                    tts_speak(error_message)  # ✅ Speak error message
                    continue  

        # ✅ Update previous mode to track changes
        previous_mode = mode

        if user_input.lower() in ['exit', 'quit']:
            shutdown_message = "Shutting down VORTEX."
            if get_debug_mode():
                print(shutdown_message)  # ✅ Show only in debug mode
            tts_speak(shutdown_message)  # ✅ Speak shutdown message
            break
        
        if user_input.lower() == "toggle":
            mode = "voice" if mode == "text" else "text"
            toggle_message = f"Mode switched to {mode.upper()}."
            if get_debug_mode():
                print(toggle_message)  # ✅ Show only in debug mode
            tts_speak(toggle_message)  # ✅ Speak mode change
            continue  

        if user_input:
            response = await process_input(user_input)  # ✅ Get AI response
            if response:
                tts_speak(response)  # ✅ Speak only VORTEX's response

if __name__ == "__main__":
    os.system('cls')

    display_startup_message()

    # ✅ Start AI loop in a background thread
    def run_asyncio():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())

    ai_thread = threading.Thread(target=run_asyncio, daemon=True)
    ai_thread.start()

    # ✅ Keep VORTEX running indefinitely to prevent unexpected exits
    while True:
        time.sleep(1)  # ✅ Prevents high CPU usage
