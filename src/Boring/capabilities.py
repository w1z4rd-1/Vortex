import os
import importlib.util



# ✅ Ensure global function registry and schemas are always initialized
if 'function_registry' not in globals():
	function_registry = {}

if 'function_schemas' not in globals():
	function_schemas = []

def register_function_in_registry(name, func):
	"""Registers a function in the global function registry."""
	global function_registry
	if name not in function_registry:
		function_registry[name] = func
		print(f"[✅ REGISTERED] {name} in function registry.")
	else:
		print(f"[⚠️ SKIPPED] Function {name} is already registered.")

def register_function_schema(schema):
	"""Registers a function schema in the global function schemas list."""
	global function_schemas
	schema_name = schema["function"]["name"]

	if schema_name not in [s["function"]["name"] for s in function_schemas]:
		function_schemas.append(schema)
		print(f"[✅ SCHEMA REGISTERED] {schema_name} added to schemas.")
	else:
		print(f"[⚠️ SKIPPED] Schema for {schema_name} is already registered.")

def get_function_registry():
	"""Returns the global function registry."""
	return function_registry

def get_function_schemas():
	"""Returns the global function schemas."""
	return function_schemas

def initialize_capabilities():
	"""Clears the function registry and auto-loads all Python files in the capabilities folder."""
	CAPABILITIES_DIR = "src/capabilities"

	# Clear the function registry
	global function_registry
	function_registry.clear()
	print("Function registry cleared.")

	# Auto-load functions from the capabilities folder
	for filename in os.listdir(CAPABILITIES_DIR):
		if filename.endswith(".py") and filename != "__init__.py":
			module_name = filename[:-3]
			module_path = os.path.join(CAPABILITIES_DIR, filename)
			try:
				print(f"Loading module: {module_name}")
				spec = importlib.util.spec_from_file_location(module_name, module_path)
				module = importlib.util.module_from_spec(spec)
				spec.loader.exec_module(module)
				
				for func_name in dir(module):
					func_obj = getattr(module, func_name)
					if callable(func_obj) and func_name not in function_registry:
						print(f"Registering function: {func_name}")
						register_function_in_registry(func_name, func_obj)
			except Exception as e:
				print(f"Failed to load module '{filename}': {e}")

def persist_dynamic_function(function_name, function_code):
	"""Writes a dynamically registered function to a separate file in the Capabilities folder."""

	# Determine the path to the 'Capabilities' folder inline
	SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
	capabilities_folder = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "Capabilities"))

	# Ensure the Capabilities folder exists
	if not os.path.exists(capabilities_folder):
		os.makedirs(capabilities_folder, exist_ok=True)

	# Save the function to a new file in the Capabilities folder
	function_file = os.path.join(capabilities_folder, f"{function_name}.py")
	with open(function_file, "w", encoding="utf-8") as f:
		f.write(function_code)
	print(f"[💾 PERSIST] Function '{function_name}' saved to '{function_file}'")

