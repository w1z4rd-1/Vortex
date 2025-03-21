print("Initializing VORTEX...")

# Configuration - must be set before any imports
USE_OPTIONAL_EXTRAS = False  # Set to False to disable optional extras

# Set as environment variable for child processes
import os
os.environ['USE_OPTIONAL_EXTRAS'] = 'true' if USE_OPTIONAL_EXTRAS else 'false'

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
from src.VOICE.voice import detect_wake_word, record_audio, transcribe_audio
from src.Boring.boring import call_openai, add_user_input, display_startup_message
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode

# Only import speak_text if optional extras are enabled
if USE_OPTIONAL_EXTRAS:
    try:
        from src.Capabilities.optional_extras.speech import speak_text
        print("✅ Optional TTS capabilities loaded")
    except ImportError as e:
        print(f"⚠️ Could not load TTS capabilities: {e}")
        # Fallback dummy function
        async def speak_text(text):
            print(f"[TTS ERROR]: {text}")
else:
    print("⚠️ Optional TTS capabilities disabled")
    # Define a dummy async function for type compatibility when checking code
    async def speak_text(text):
        pass

# ANSI Color Codes for Terminal Output
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"

async def process_input(user_input):
	"""
	Calls OpenAI's API and processes the user input.
	"""
	add_user_input(user_input)  # Add user input once
	response = await call_openai()  # Call OpenAI API
	return response # Return the response

async def main():
	mode = "text" # Start in text mode by default.
	previous_mode = mode # ✅ Track previous mode to detect changes
	while True:
		if mode == "text":
			user_input = input("You: ").strip()
		else:
			# ✅ Only announce voice mode activation when switching modes
			if mode != previous_mode:
				message = "Voice mode activated. Please speak..."
				if get_debug_mode():
					print(message)  # ✅ Show only in debug mode
				if USE_OPTIONAL_EXTRAS:
					await speak_text(message)  # ✅ Speak mode change
				else:
					print(f"[VOICE]: {message}")
			
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
					if USE_OPTIONAL_EXTRAS:
						await speak_text(error_message)  # ✅ Speak error message
					else:
						print(f"[VOICE]: {error_message}")
					continue  

		# ✅ Update previous mode to track changes
		previous_mode = mode

		if user_input.lower() in ['exit', 'quit']:
			shutdown_message = "Shutting down VORTEX."
			if get_debug_mode():
				print(shutdown_message)  # ✅ Show only in debug mode
			if USE_OPTIONAL_EXTRAS:
				await speak_text(shutdown_message)  # ✅ Speak shutdown message
			else:
				print(f"[VOICE]: {shutdown_message}")
			break

		if user_input.lower() == "toggle":
			mode = "voice" if mode == "text" else "text"
			toggle_message = f"Mode switched to {mode.upper()}."
			if get_debug_mode():
				print(toggle_message)  # ✅ Show only in debug mode
			if USE_OPTIONAL_EXTRAS:
				await speak_text(toggle_message)  # ✅ Speak mode change
			else:
				print(f"[VOICE]: {toggle_message}")
			continue  

		if user_input:
			response = await process_input(user_input)  # ✅ Get AI response
			if response:
				if USE_OPTIONAL_EXTRAS:
					await speak_text(response)  # ✅ Speak only VORTEX's response

if __name__ == "__main__":
	# os.system('cls')
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
