print("Initalizing")
import asyncio
from voice import detect_wake_word, record_audio, transcribe_audio, get_debug_mode
from boring import call_openai, add_user_input, display_startup_message
import os

# ANSI Color Codes for Terminal Output
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"

async def process_input(user_input):
    """
    Adds the user input to conversation history and calls the OpenAI API.
    Then prints the assistant's response.
    """
    add_user_input(user_input)
    response = await call_openai()
    if response:
        print(f"[🤖 VORTEX]: {response}")

async def main():
    mode = "text"  # Start in text mode by default.
    
    while True:
        if get_debug_mode():
            print(f"\nCurrent mode: {mode.upper()}")
            print(f"{COLOR_BLUE}Type your input or enter 'toggle' to switch mode (or 'exit' to quit).{COLOR_RESET}")
        
        # If in text mode, simply get input from the keyboard.
        if mode == "text":
            user_input = input("You: ").strip()
        else:
            # In voice mode, prompt for the wake word.
            print("Voice mode: Please speak the wake word to initiate voice input...")
            # detect_wake_word() should block until the wake word is detected.
            if detect_wake_word():
                # Once the wake word is detected, record and transcribe audio.
                audio_file = record_audio()
                user_input = transcribe_audio(audio_file)
                if user_input:
                    print(f"{COLOR_GREEN}User said (voice): {user_input}{COLOR_RESET}")
                else:
                    print(f"{COLOR_RED}[Error]: No voice input detected.{COLOR_RESET}")
                    continue  # Skip processing if nothing was captured.
            else:
                # If detect_wake_word() returns False (shouldn't normally happen), loop again.
                continue
        
        # Process control commands.
        if user_input.lower() in ['exit', 'quit']:
            print(f"{COLOR_RED}[🛑 VORTEX SHUTDOWN] Exiting...{COLOR_RESET}")
            break
        
        if user_input.lower() == "toggle":
            mode = "voice" if mode == "text" else "text"
            print(f"{COLOR_GREEN}[🔄] Mode toggled to {mode.upper()}.{COLOR_RESET}")
            continue  # Skip sending a message when toggling.
        
        # Process valid user input.
        if user_input:
            await process_input(user_input)

if __name__ == "__main__":
    # Display the startup message (ASCII art, version info, etc.)
    os.system('cls')

    display_startup_message()
    asyncio.run(main())
