import json
import os

# Define file path to store debug mode status
DEBUG_MODE_FILE = "debug_mode.json"
if not os.path.exists(DEBUG_MODE_FILE):
	with open(DEBUG_MODE_FILE, "w") as f:
		json.dump({"debug_mode": False}, f)

# Global variable for debug mode
_debug_mode = False

def debugmode(enable=None):
	"""
	Toggles or sets debug mode.
	
	Args:
		enable: True to enable debug mode, False to disable, None to toggle
	
	Returns:
		Current debug mode status
	"""
	global _debug_mode
	
	if enable is None:
		# Toggle
		_debug_mode = not _debug_mode
	else:
		# Set specific value
		_debug_mode = bool(enable)
	
	status = "enabled" if _debug_mode else "disabled"
	
	try:
		# Save to file for persistence
		with open(DEBUG_MODE_FILE, "w") as f:
			json.dump({"debug_mode": _debug_mode}, f)
	except Exception as e:
		pass
		
	if _debug_mode:
		# Print capabilities status when debug mode is enabled
		try:
			# Import here to avoid circular import
			from src.Boring.capabilities import get_initialization_status
			status_info = get_initialization_status()
			status_msg = f"""
Debug mode {status}.

Capabilities Status:
- Initialization: {"Complete" if status_info["initialized"] else "Not Initialized"}
- Registered Functions: {status_info["registered_functions"]}
- Registered Schemas: {status_info["registered_schemas"]}
- Loaded Modules: {status_info["loaded_modules"]}
- Total Registration Count: {status_info["registration_count"]}
"""
			try:
				registry_details = inspect_registry()
				if isinstance(registry_details, dict):
					available_functions_list = registry_details.get("available_functions", [])
					if available_functions_list:
						status_msg += "\n\nRegistered Capability Names:\n"
						for func_name in available_functions_list:
							status_msg += f"- {func_name}\n"
					else:
						status_msg += "\n\nRegistered Capability Names: (No functions found or list is empty)\n"
				else: # inspect_registry might return an error string
					status_msg += f"\n\nCould not retrieve list of capability names. inspect_registry reported: {registry_details}\n"
			except Exception as inspect_e:
				status_msg += f"\n\nAn error occurred while trying to list capability names: {inspect_e}\n"
			
			return status_msg
		except Exception as e:
			return f"Debug mode {status}. Could not retrieve capabilities status: {e}"
	else:
		return f"Debug mode {status}."

def get_debug_mode():
	"""Returns the current debug mode setting."""
	global _debug_mode
	
	# Try to read from file first for persistence across runs
	try:
		if os.path.exists(DEBUG_MODE_FILE):
			with open(DEBUG_MODE_FILE, "r") as f:
				data = json.load(f)
				_debug_mode = data.get("debug_mode", False)
	except:
		pass
	
	return _debug_mode

def set_debug_mode(enable):
	"""Sets debug mode to the specified value."""
	global _debug_mode
	_debug_mode = bool(enable)
	
	# Save to file for persistence
	try:
		with open(DEBUG_MODE_FILE, "w") as f:
			json.dump({"debug_mode": _debug_mode}, f)
	except:
		pass
		
	return _debug_mode

def inspect_registry():
	"""
	Inspect the current state of the function registry and schemas.
	"""
	try:
		# Import here to avoid circular import
		from src.Boring.capabilities import get_function_registry, get_function_schemas
		
		registry = get_function_registry()
		schemas = get_function_schemas()
		
		available_functions = list(registry.keys())
		available_functions.sort()  # Sort for easier reading
		
		result = {
			"available_functions": available_functions,
			"function_count": len(available_functions),
			"schema_count": len(schemas)
		}
		
		return result
	except Exception as e:
		return f"Error inspecting registry: {e}"

# These will be imported by capabilities.py later, we don't register here
# to avoid circular imports
