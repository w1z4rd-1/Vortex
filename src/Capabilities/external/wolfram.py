# Wolfram Alpha-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import requests
import os
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")

def query_wolfram_alpha(query: str) -> dict:
	"""
	Queries Wolfram Alpha's Full Results API and returns formatted results.

	Parameters:
	- query (str): The question or mathematical expression to solve.

	Returns:
	- dict: Structured response with results from Wolfram Alpha.
	"""
	if not WOLFRAM_APP_ID:
		return {"error": "Wolfram Alpha API key is missing."}

	url = "http://api.wolframalpha.com/v2/query"
	params = {
		"input": query,
		"format": "plaintext",
		"output": "XML",
		"appid": WOLFRAM_APP_ID
	}

	try:
		response = requests.get(url, params=params)
		response.raise_for_status()
		root = ET.fromstring(response.content)

		results = []

		for pod in root.findall(".//pod"):
			title = pod.get("title")
			plaintext = pod.find(".//plaintext")
			if plaintext is not None and plaintext.text:
				results.append(f"**{title}**: {plaintext.text}")

		if not results:
			return {"error": "No relevant information found."}

		return {"result": "\n".join(results)}

	except requests.exceptions.RequestException as e:
		return {"error": f"API request failed: {str(e)}"}

# Register functions and schemas
capabilities.register_function_in_registry("query_wolfram_alpha", query_wolfram_alpha)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "query_wolfram_alpha",
		"description": "Queries Wolfram Alpha for computational knowledge.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {
					"type": "string",
					"description": "The question or mathematical expression to solve."
				}
			},
			"required": ["query"]
		}
	}
}) 