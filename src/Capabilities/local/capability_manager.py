"""
Capability manager for VORTEX
Allows adding new capabilities dynamically.
"""

import src.Boring.capabilities as capabilities
import os
import re
import importlib
from src.Capabilities.debug_mode import get_debug_mode
from src.Capabilities.local.utils import add_new_capability

# Register the add_new_capability function
capabilities.register_function_in_registry("add_new_capability", add_new_capability)

# Register the schema
capabilities.register_function_schema({
	"function": {
		"name": "add_new_capability",
		"description": "Dynamically adds a new capability (function) to VORTEX.",
		"parameters": {
			"type": "object",
			"properties": {
				"function_name": {
					"type": "string",
					"description": "Name of the function to add."
				},
				"function_code": {
					"type": "string",
					"description": "Python code for the function, following the capability creation guidelines."
				}
			},
			"required": ["function_name", "function_code"]
		}
	}
})