from src.Boring.capabilities import get_function_registry, get_function_schemas, register_function_in_registry, register_function_schema
import json
import os

# ✅ Define file path to store debug mode status
DEBUG_MODE_FILE = os.path.join(os.path.dirname(__file__), "debug_mode.json")

# ✅ Ensure the file exists with a default value
if not os.path.exists(DEBUG_MODE_FILE):
	with open(DEBUG_MODE_FILE, "w") as f:
		json.dump({"debug_mode": False}, f)

def set_debug_mode(mode=True):
	"""
	Set the debug mode for VORTEX.
	
	Args:
		mode (bool): True to enable debug mode, False to disable it.
	"""
	try:
		with open(DEBUG_MODE_FILE, "w") as f:
			json.dump({"debug_mode": mode}, f)
		print(f"Debug mode {'enabled' if mode else 'disabled'}.")
		return True
	except Exception as e:
		print(f"Error setting debug mode: {e}")
		return False

def get_debug_mode():
	"""
	Get the current debug mode state.
	
	Returns:
		bool: True if debug mode is enabled, False otherwise.
	"""
	try:
		if os.path.exists(DEBUG_MODE_FILE):
			with open(DEBUG_MODE_FILE, "r") as f:
				data = json.load(f)
				return data.get("debug_mode", False)
		return False
	except Exception:
		# If there's any error, default to debug mode off
		return False

def inspect_registry():
	"""
	Print information about the current registry state.
	
	This function will display all registered functions and schemas 
	when debug mode is enabled.
	"""
	if not get_debug_mode():
		return "Debug mode is disabled. Enable it to inspect registry."
	
	registry = get_function_registry()
	schemas = get_function_schemas()
	
	print("\n===== FUNCTION REGISTRY INSPECTION =====")
	print(f"Total registered functions: {len(registry)}")
	for name in sorted(registry.keys()):
		print(f"  - {name}")
	
	print(f"\nTotal registered schemas: {len(schemas)}")
	for schema in schemas:
		print(f"  - {schema['function']['name']}")
	
	return {
		"function_count": len(registry),
		"schema_count": len(schemas),
		"functions": list(registry.keys()),
		"schemas": [s['function']['name'] for s in schemas]
	}

# Register the functions with the capabilities system
register_function_in_registry("set_debug_mode", set_debug_mode)
register_function_in_registry("inspect_registry", inspect_registry)

# Register the function schemas
set_debug_schema = {
	"function": {
		"name": "set_debug_mode",
		"description": "Enable or disable VORTEX's debug mode",
		"parameters": {
			"type": "object",
			"properties": {
				"mode": {
					"type": "boolean",
					"description": "Set to true to enable debug mode, false to disable it"
				}
			},
			"required": ["mode"]
		}
	}
}

inspect_registry_schema = {
	"function": {
		"name": "inspect_registry",
		"description": "Inspect the current state of the function registry and schemas",
		"parameters": {
			"type": "object",
			"properties": {},
			"required": []
		}
	}
}

register_function_schema(set_debug_schema)
register_function_schema(inspect_registry_schema)
