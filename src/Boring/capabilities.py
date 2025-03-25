import os
import importlib.util
import sys
import inspect

# Track initialization status
_registry_initialized = False

# Track modules that have been loaded
_loaded_modules = set()

# Initialize global registries
function_registry = {}
function_schemas = []

# Debug counter for registrations
_registration_count = 0

def register_function_in_registry(name, func):
	"""Registers a function in the global function registry."""
	global function_registry, _registration_count
	
	# Get calling module for tracking
	frame = inspect.currentframe().f_back
	module_name = frame.f_globals.get('__name__', 'unknown')
	
	# Create a unique key for this function registration
	registration_key = f"{module_name}:{name}"
	
	# Skip if already registered from this module
	if name in function_registry:
		# Only print if in debug mode to reduce console spam
		print(f"[⚠️ SKIPPED] Function {name} already registered (from {module_name})")
		return
		
	# Register the function
	function_registry[name] = func
	_registration_count += 1
	print(f"[✅ REGISTERED #{_registration_count}] {name} in function registry (from {module_name})")

def register_function_schema(schema):
	"""Registers a function schema in the global function schemas list."""
	global function_schemas, _registration_count
	
	# Ensure the schema has a type field
	if 'type' not in schema:
		schema['type'] = 'function'
		
	schema_name = schema["function"]["name"]

	# Get calling module for tracking
	frame = inspect.currentframe().f_back
	module_name = frame.f_globals.get('__name__', 'unknown')
	
	# Check if schema already exists
	existing_names = [s["function"]["name"] for s in function_schemas]
	
	if schema_name not in existing_names:
		function_schemas.append(schema)
		_registration_count += 1
		print(f"[✅ SCHEMA REGISTERED #{_registration_count}] {schema_name} (from {module_name})")
	else:
		# Only print if in debug mode to reduce console spam
		print(f"[⚠️ SKIPPED] Schema for {schema_name} already registered (from {module_name})")

def get_function_registry():
	"""Returns the global function registry."""
	return function_registry

def get_function_schemas():
	"""Returns the global function schemas."""
	return function_schemas

def initialize_capabilities():
	"""Initializes capability registry."""
	global function_registry, function_schemas, _registry_initialized, _loaded_modules, _registration_count
	
	# Print prominent message if re-initialization attempt
	if _registry_initialized:
		print("\n" + "="*80)
		print(" NOTICE: Capabilities registry already initialized - SKIPPING reinitialization ")
		print("="*80 + "\n")
		return
	
	print("\n" + "="*80)
	print(" Initializing capabilities registry (first time) ")
	print("="*80 + "\n")
	
	# Clear everything on first initialization
	function_registry.clear()
	function_schemas.clear()
	_loaded_modules.clear()
	_registration_count = 0
	
	# Mark as initialized
	_registry_initialized = True
	
	try:
		# Check if using optional extras
		use_optional_extras = os.environ.get("USE_OPTIONAL_EXTRAS", "false").lower() == "true"
		print(f"[CONFIG] USE_OPTIONAL_EXTRAS = {use_optional_extras}")
		
		# Load capabilities
		load_capabilities(use_optional_extras=use_optional_extras)
		
		# Manually register debug functions last to avoid circular imports
		register_debug_functions()
		
		print("\n" + "="*80)
		print(f" Capabilities initialization complete. Registered {_registration_count} items. ")
		print("="*80 + "\n")
	except Exception as e:
		print(f"[ERROR] Failed to initialize capabilities: {e}")

def load_capabilities(use_optional_extras=False):
	"""Load all capability modules from the Capabilities directory."""
	global _loaded_modules
	
	# Fix the case sensitivity issue by using the correct case
	CAPABILITIES_DIR = "src/Capabilities"  # Capital C to match actual directory
	
	# Create a priority order for loading modules
	def module_priority(file_path):
		# Load debug_mode first, then local modules before external
		if "debug_mode.py" in file_path:
			return 0
		elif "/local/" in file_path:
			return 1
		elif "/external/" in file_path:
			return 2
		else:
			return 3
	
	# Find all modules to load
	module_paths = []
	for root, dirs, files in os.walk(CAPABILITIES_DIR):
		# Skip optional_extras directory if not enabled
		if not use_optional_extras and "optional_extras" in root:
			print(f"[⚠️ SKIPPED] Optional extras directory: {root}")
			continue
			
		for filename in files:
			if filename.endswith(".py") and filename != "__init__.py":
				module_path = os.path.join(root, filename)
				module_paths.append(module_path)
				
	# Sort modules by priority
	module_paths.sort(key=module_priority)
				
	# Load modules in priority order
	for module_path in module_paths:
		# Get relative path for import using correct module structure
		rel_path = os.path.relpath(module_path, os.path.dirname(os.path.dirname(CAPABILITIES_DIR)))
		rel_path = rel_path.replace("\\", "/")  # Normalize path separators for import
		module_name = os.path.splitext(rel_path)[0].replace("/", ".")
		
		# Skip if already loaded
		if module_name in _loaded_modules:
			print(f"[⚠️ SKIPPED] Module already loaded: {module_name}")
			continue
			
		# Mark as loaded before importing to prevent circular import issues
		_loaded_modules.add(module_name)
		
		try:
			print(f"[⏳ LOADING] Module: {module_name}")
			spec = importlib.util.spec_from_file_location(module_name, module_path)
			module = importlib.util.module_from_spec(spec)
			
			# Add to sys.modules BEFORE executing module
			sys.modules[module_name] = module
			
			# Execute the module
			spec.loader.exec_module(module)
			print(f"[✅ LOADED] Module: {module_name}")
		except Exception as e:
			print(f"[❌ FAILED] Module '{os.path.basename(module_path)}': {str(e)[:100]}")
			# Remove from loaded modules if it failed
			_loaded_modules.remove(module_name)

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

# Functions to help with debugging
def get_initialization_status():
	"""Returns the current initialization status for debugging."""
	return {
		"initialized": _registry_initialized,
		"registered_functions": len(function_registry),
		"registered_schemas": len(function_schemas),
		"loaded_modules": len(_loaded_modules),
		"registration_count": _registration_count
	}

def register_debug_functions():
	"""Register debug-related functions after other modules are loaded."""
	try:
		from src.Capabilities.debug_mode import debugmode, set_debug_mode, inspect_registry
		
		# Register the functions
		register_function_in_registry("debugmode", debugmode)
		register_function_in_registry("set_debug_mode", set_debug_mode)
		register_function_in_registry("inspect_registry", inspect_registry)
		
		# Register the schemas
		register_function_schema({
			"type": "function",
			"function": {
				"name": "debugmode",
				"description": "Toggles or sets debug mode",
				"parameters": {
					"type": "object",
					"properties": {
						"enable": {
							"type": "boolean",
							"description": "True to enable, False to disable, omit to toggle"
						}
					},
					"required": []
				}
			}
		})
		
		register_function_schema({
			"type": "function",
			"function": {
				"name": "set_debug_mode",
				"description": "Enable or disable VORTEX's debug mode",
				"parameters": {
					"type": "object",
					"properties": {
						"enable": {
							"type": "boolean",
							"description": "Set to true to enable debug mode, false to disable it"
						}
					},
					"required": ["enable"]
				}
			}
		})
		
		register_function_schema({
			"type": "function",
			"function": {
				"name": "inspect_registry",
				"description": "Inspect the current state of the function registry and schemas",
				"parameters": {
					"type": "object",
					"properties": {},
					"required": []
				}
			}
		})
		
		print("[✅ REGISTERED] Debug functions added to registry")
	except Exception as e:
		print(f"[❌ ERROR] Could not register debug functions: {e}")

