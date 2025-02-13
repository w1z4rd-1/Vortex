from openai import OpenAI
import sounddevice as sd
import numpy as np
import io
from pydub import AudioSegment

client = OpenAI()  # ✅ Initialize OpenAI client

def stream_tts(text):
    """Streams OpenAI's TTS and plays it in real-time without waiting for the full response."""
    print(f"[🔊 Streaming TTS for: {text}]")

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )

        audio_buffer = io.BytesIO()

        # 🔹 Read the audio stream in chunks
        for chunk in response.iter_bytes():
            audio_buffer.write(chunk)

            # 🔹 Convert MP3 chunk to WAV and play it immediately
            audio_buffer.seek(0)
            play_streamed_audio(audio_buffer)

        print("[✅ TTS Finished]")

    except Exception as e:
        print(f"[❌ ERROR in TTS] {e}")

def play_streamed_audio(mp3_bytes):
    """Converts streamed MP3 chunks to WAV and plays them in real-time."""
    try:
        # 🔹 Convert MP3 to WAV using pydub
        audio = AudioSegment.from_file(mp3_bytes, format="mp3")
        samples = np.array(audio.get_array_of_samples(), dtype=np.int16)

        print(f"[🔊 Playing {len(samples)} samples...]")

        # 🔹 Play audio immediately
        sd.play(samples, samplerate=audio.frame_rate)
        sd.wait()  # ✅ Wait for playback to finish

    except Exception as e:
        print(f"[❌ ERROR in Playback] {e}")

if __name__ == "__main__":
    test_text = "This is a test of OpenAI's real-time text-to-speech streaming."
    stream_tts(test_text)
