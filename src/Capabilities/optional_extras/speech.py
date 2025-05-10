# Speech-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import os
import asyncio
from openai import OpenAI
from pydub import AudioSegment
from pydub.playback import play
from dotenv import load_dotenv
import re
from src.Capabilities.debug_mode import get_debug_mode
from src.Boring.boring import log_debug_event

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

async def generate_tts_segment(segment):
	"""
	Generates a single TTS audio segment using OpenAI's API.
	
	Parameters:
	- segment (str): Text segment to convert to speech
	
	Returns:
	- AudioSegment: Generated audio segment
	"""
	response = client.audio.speech.create(
		model="tts-1",
		voice="nova",
		input=segment
	)
	
	# Create a temporary file to store the segment
	temp_file = f"temp/tts_segment_{hash(segment)}.mp3"
	
	# Save the audio to the temporary file
	with open(temp_file, "wb") as f:
		f.write(response.content)
	
	# Convert to an AudioSegment object
	audio_segment = AudioSegment.from_mp3(temp_file)
	
	# Clean up the temporary file
	os.remove(temp_file)
	
	return audio_segment

async def speak_text(input_text: str):
	"""
	Converts text to speech with appropriate pauses and plays it.
	
	Parameters:
	- input_text (str): Text to convert to speech
	
	Returns:
	- dict: Result of the text-to-speech operation
	"""
	if not OPENAI_API_KEY:
		return {"error": "OpenAI API key is missing."}
	
	log_debug_event(f"Speaking: {input_text}")
	
	try:
		# Parse speech syntax but don't filter thoughts anymore
		parsed_text = parse_speech_syntax(input_text)
		
		# Split the text at punctuation to create natural pauses
		segments = re.split(r'(?<=[.!?])\s+', parsed_text)
		
		# Generate audio for each segment asynchronously
		tasks = [generate_tts_segment(seg) for seg in segments if seg.strip()]
		audio_segments = await asyncio.gather(*tasks)
		
		# Combine the segments
		combined_audio = AudioSegment.empty()
		for segment in audio_segments:
			combined_audio += segment
			# Add a small pause between segments
			combined_audio += AudioSegment.silent(duration=300)
		
		# Play the combined audio
		play(combined_audio)
		
		return {"status": "success", "message": "Text spoken successfully."}
	
	except Exception as e:
		return {"error": f"Failed to speak text: {str(e)}"}

def extract_thoughts_and_speech(input_text: str):
	"""
	Extracts thoughts (enclosed in * or parentheses) from the text.
	
	Parameters:
	- input_text (str): Text containing thoughts and speech
	
	Returns:
	- tuple: (thoughts, speech) separated
	"""
	# Find all text enclosed in * or ()
	thought_patterns = [r'\*([^*]+)\*', r'\(([^)]+)\)']
	thoughts = []
	
	for pattern in thought_patterns:
		matches = re.findall(pattern, input_text)
		thoughts.extend(matches)
		# Remove thoughts from the input text
		input_text = re.sub(pattern, '', input_text)
	
	return (", ".join(thoughts), input_text.strip())

def parse_speech_syntax(input_text: str):
	"""
	Parses custom syntax for speech with embedded thought markers.
	
	Parameters:
	- input_text (str): Text with embedded thought markers
	
	Returns:
	- str: Processed text
	"""
	# Replace thought markers with standardized format
	input_text = re.sub(r'<think>(.*?)</think>', r'(\1)', input_text)
	
	# Replace pause markers with ellipses
	input_text = re.sub(r'<pause>', '...', input_text)
	
	return input_text

# Register functions and schemas
capabilities.register_function_in_registry("speak_text", speak_text)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "speak_text",
		"description": "Converts text to speech with appropriate pauses and plays it.",
		"parameters": {
			"type": "object",
			"properties": {
				"input_text": {
					"type": "string",
					"description": "Text to convert to speech."
				}
			},
			"required": ["input_text"]
		}
	}
}) 