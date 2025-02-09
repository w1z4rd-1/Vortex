print("Initializing")
import asyncio
from voice import detect_wake_word, record_audio, transcribe_audio
from boring import call_openai, add_user_input, display_startup_message
import os
#os.system("cls")
VORTEX_VERSION = "Alpha"

# os.system("cls")
display_startup_message()
async def main():
    """Main loop that waits for wake word, records audio, transcribes, and interacts with AI"""
    while True:
        if detect_wake_word():
            audio_file = record_audio()
            user_input = transcribe_audio(audio_file)
            if user_input:
                print(f"User said: {user_input}")
                add_user_input(user_input)  # Store input in conversation history
                await call_openai()  # Process with OpenAI

if __name__ == "__main__":
    asyncio.run(main())