🔥 VORTEX - AI-Powered Voice Assistant

Welcome to VORTEX – a local AI assistant designed to be fast, powerful, and completely under your control.It features text-to-speech (TTS), voice recognition, and future integrations for phone calls and automation.

🎯 Current Features

✅ Fast Text-to-Speech (TTS) with OpenAI's tts-1 model.✅ Wake word detection with Porcupine for hands-free activation.✅ Voice-to-text transcription using Whisper AI.✅ AI-powered conversations with OpenAI's gpt-4o.✅ Flexible command recognition for automating tasks.

🚀 How to Use VORTEX

📌 1️⃣ Install Dependencies

Ensure you have Python 3.10+ installed, then run:

pip install -r requirements.txt

▶ 2️⃣ Run VORTEX

Start the assistant:

python VORTEX.py

Say the wake word, then speak naturally!

🔮 Planned Future Features

✨ Two-Way Communication with iPhone via Siri Shortcuts📞 Phone Call Handling (Making & Receiving Calls with AI Responses)🎨 Real-Time Audio-Responsive OpenGL Visuals (Paused for now, but it's fire! 🔥)🔌 Local API for External Commands & Smart Home Control🛠 Integration with Custom Task Automations🗣 Support for More Wake Words & Multi-User Profiles🔐 Encrypted AI Conversations & Memory Retention

📌 Customization & Settings

Modify config.py (if it exists) or directly edit:

🖥 VORTEX.py – Main assistant logic.

🎙 voice.py – Handles wake word detection, speech recognition, and TTS.

🔗 boring.py – Manages OpenAI API requests.

🎛 display.py (Disabled, but can be re-enabled for OpenGL visuals.)

❓ Troubleshooting

If VORTEX exits immediately, try:

python VORTEX.py --debug

For slow responses, consider:

⚡ Switching TTS to streaming mode.

⚙ Using "gpt-3.5-turbo" instead of "gpt-4o" in boring.py.

🎤 Reducing silence threshold in voice.py.

🎤 Why I Built This

This is just for me, but damn – it's fun.VORTEX is evolving into a fully local AI that feels like JARVIS.Let's keep pushing the boundaries. 🚀🔥

⚠ Disclaimer

This project is purely experimental.If it accidentally calls Elon Musk, that's on you. 🤖📞💥

💙 Made with Passion by Me

