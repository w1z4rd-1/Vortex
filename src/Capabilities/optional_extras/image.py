# Image-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import os
import base64
import tempfile
import openai
from dotenv import load_dotenv
from src.Capabilities.debug_mode import get_debug_mode
from src.Boring.boring import log_debug_event
from PIL import Image
import io

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

TEMP_DIR = os.path.join(os.getenv("TEMP", "/tmp"), "VORTEX")
os.makedirs(TEMP_DIR, exist_ok=True)  # Ensure the directory exists
TEMP_IMAGE_PATH = os.path.join(TEMP_DIR, "screenshot.png")  # Path for saving screenshots

def generate_image(prompt: str, save_path: str = None):
	"""
	Generates an image using OpenAI's DALL-E API.
	
	Parameters:
	- prompt (str): Text description of the image to generate
	- save_path (str, optional): Path to save the image (default: temp directory)
	
	Returns:
	- dict: Result of the image generation
	"""
	if not OPENAI_API_KEY:
		return {"error": "OpenAI API key is missing."}
	
	log_debug_event(f"Generating image with prompt: {prompt}")
	
	try:
		# Generate the image
		response = client.images.generate(
			model="dall-e-3",
			prompt=prompt,
			size="1024x1024",
			quality="standard",
			n=1,
			response_format="b64_json"
		)
		
		# Get the image data
		image_data = response.data[0].b64_json
		image_bytes = base64.b64decode(image_data)
		
		# If save path is not provided, save to temp directory
		if not save_path:
			temp_dir = os.path.join(tempfile.gettempdir(), "VORTEX")
			os.makedirs(temp_dir, exist_ok=True)
			save_path = os.path.join(temp_dir, "generated_image.png")
		
		# Save the image
		with open(save_path, "wb") as f:
			f.write(image_bytes)
		
		# Open the image to display it
		image = Image.open(io.BytesIO(image_bytes))
		image.show()
		
		return {
			"status": "success", 
			"message": f"Image generated and saved to {save_path}",
			"path": save_path
		}
	
	except Exception as e:
		return {"error": f"Failed to generate image: {str(e)}"}

def encode_image(image_path):
	"""
	Encodes an image to base64 for API use.
	
	Parameters:
	- image_path (str): Path to the image file
	
	Returns:
	- str: Base64-encoded image
	"""
	with open(image_path, "rb") as image_file:
		return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_image(image_path: str):
	"""
	Analyzes an image using OpenAI's Vision API.
	
	Parameters:
	- image_path (str): Path to the image file
	
	Returns:
	- dict: Analysis results
	"""
	if not OPENAI_API_KEY:
		return {"error": "OpenAI API key is missing."}
	
	if not os.path.exists(image_path):
		return {"error": f"Image file not found: {image_path}"}
	
	log_debug_event(f"Analyzing image at path: {image_path}")
	
	try:
		# Read and encode the image
		base64_image = encode_image(image_path)
		
		# Send the image to the API for analysis
		response = client.chat.completions.create(
			model="gpt-4-vision-preview",
			messages=[
				{
					"role": "user",
					"content": [
						{"type": "text", "text": "Analyze this image and describe what you see in detail."},
						{
							"type": "image_url",
							"image_url": {
								"url": f"data:image/jpeg;base64,{base64_image}",
								"detail": "high"
							}
						}
					]
				}
			],
			max_tokens=500
		)
		
		analysis = response.choices[0].message.content
		return {"analysis": analysis}
	
	except Exception as e:
		return {"error": f"Failed to analyze image: {str(e)}"}

# Register image functions
capabilities.register_function_in_registry("generate_image", generate_image)
capabilities.register_function_in_registry("analyze_image", analyze_image)

# Register schemas for image functions
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "generate_image",
		"description": "Generates an image using OpenAI's DALL-E API based on a text prompt.",
		"parameters": {
			"type": "object",
			"properties": {
				"prompt": {
					"type": "string",
					"description": "Detailed description of the image to generate."
				},
				"save_path": {
					"type": "string",
					"description": "Optional path to save the generated image."
				}
			},
			"required": ["prompt"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "analyze_image",
		"description": "Analyzes an image using OpenAI's Vision API.",
		"parameters": {
			"type": "object",
			"properties": {
				"image_path": {
					"type": "string",
					"description": "Path to the image file to analyze."
				}
			},
			"required": ["image_path"]
		}
	}
}) 