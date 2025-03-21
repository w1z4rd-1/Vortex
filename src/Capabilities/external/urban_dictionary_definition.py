# === Auto-Generated Function ===
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode
import src.Boring.capabilities as capabilities

import requests

def urban_dictionary_definition(word: str) -> str:
	"""Get the definition of a word from Urban Dictionary API."""
	url = f'https://api.urbandictionary.com/v0/define?term={word}'
	response = requests.get(url)
	if response.status_code == 200:
		json_data = response.json()
		if len(json_data['list']) > 0:
			definition = json_data['list'][0]['definition']
			return definition
		else:
			return 'Definition not found.'
	else:
		return 'Error fetching definition.'
	
urban_dictionary_definition.schema = {
	'word': str
}

capabilities.register_function_schema({"type": "function", "function": {
	"name": "urban_dictionary_definition",
	"description": "Get the definition of a word from Urban Dictionary API.",
	"parameters": {
		"type": "object",
		"properties": {
			"word": {"type": "string"}
		},
		"required": ["word"]
	}
}})

capabilities.register_function_in_registry("urban_dictionary_definition", urban_dictionary_definition)
