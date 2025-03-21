import os
import importlib.util
import sys
import inspect

# Track if initialization has already occurred
_initialization_complete = False
_modules_loaded = set()
_registered_functions = set()
_registered_schemas = set()

# ✅ Ensure global function registry and schemas are always initialized
if 'function_registry' not in globals():
	function_registry = {}

if 'function_schemas' not in globals():
	function_schemas = []

def register_function_in_registry(name, func):
	"""Registers a function in the global function registry."""
	global function_registry
	
	# Check if function name already exists
	if name not in function_registry:
		function_registry[name] = func
		print(f"[✅ REGISTERED] {name} in function registry.")
	else:
		# Get module name directly from the function if possible
		module_name = getattr(func, "__module__", None)
		if not module_name:
			# Fallback to frame inspection
			frame = inspect.currentframe().f_back
			module_name = frame.f_globals.get('__name__', 'unknown')
			
		print(f"[⚠️ SKIPPED] Function {name} is already registered (from {module_name}).")

def register_function_schema(schema):
	"""Registers a function schema in the global function schemas list."""
	global function_schemas
	
	# Ensure the schema has a type field
	if 'type' not in schema:
		schema['type'] = 'function'
		
	schema_name = schema["function"]["name"]

	# Check if schema already exists
	existing_names = [s["function"]["name"] for s in function_schemas]
	
	if schema_name not in existing_names:
		function_schemas.append(schema)
		
		# Get calling module - use callstack to get exact module
		frame = inspect.currentframe().f_back
		module_name = frame.f_globals.get('__name__', 'unknown')
		print(f"[✅ SCHEMA REGISTERED] {schema_name} added to schemas (from {module_name}).")
	else:
		# Get calling module
		frame = inspect.currentframe().f_back
		module_name = frame.f_globals.get('__name__', 'unknown')
		print(f"[⚠️ SKIPPED] Schema for {schema_name} is already registered (from {module_name}).")

def get_function_registry():
	"""Returns the global function registry."""
	return function_registry

def get_function_schemas():
	"""Returns the global function schemas."""
	return function_schemas

def initialize_capabilities():
	"""Clears the function registry and auto-loads all Python files in the capabilities folder and its subdirectories."""
	global _initialization_complete, function_registry, _modules_loaded
	global _registered_functions, _registered_schemas
	
	# If already initialized, don't clear registry again
	if _initialization_complete:
		print("[ℹ️ INFO] Capabilities already initialized, skipping reinitialization.")
		return
		
	# ✅ Fix the case sensitivity issue by using the correct case
	CAPABILITIES_DIR = "src/Capabilities"  # Capital C to match actual directory
	
	# Clear the function registry only on first initialization
	function_registry.clear()
	_registered_functions.clear()
	_registered_schemas.clear()
	print("Function registry cleared.")

	# Check if optional extras should be loaded - simpler approach to avoid import issues
	USE_OPTIONAL_EXTRAS = False
	try:
		# Check if the VORTEX module is already loaded
		if 'VORTEX' in sys.modules:
			USE_OPTIONAL_EXTRAS = getattr(sys.modules['VORTEX'], 'USE_OPTIONAL_EXTRAS', False)
		else:
			# Fall back to environment variable if available
			USE_OPTIONAL_EXTRAS = os.environ.get('USE_OPTIONAL_EXTRAS', '').lower() == 'true'
		
		print(f"[CONFIG] USE_OPTIONAL_EXTRAS = {USE_OPTIONAL_EXTRAS}")
	except Exception as e:
		print(f"[⚠️ WARNING] Error checking USE_OPTIONAL_EXTRAS: {e}")
		print("[⚠️ WARNING] Defaulting to not loading optional extras")

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
		# Skip optional_extras directory if USE_OPTIONAL_EXTRAS is False
		if not USE_OPTIONAL_EXTRAS and "optional_extras" in root:
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
		# Skip if we've already loaded this module
		if module_path in _modules_loaded:
			continue
			
		# Get relative path for import using correct module structure
		rel_path = os.path.relpath(module_path, os.path.dirname(os.path.dirname(CAPABILITIES_DIR)))
		rel_path = rel_path.replace("\\", "/")  # Normalize path separators for import
		module_name = os.path.splitext(rel_path)[0].replace("/", ".")
		
		try:
			print(f"Loading module: {module_name}")
			spec = importlib.util.spec_from_file_location(module_name, module_path)
			module = importlib.util.module_from_spec(spec)
			
			# Add to sys.modules BEFORE executing module
			sys.modules[module_name] = module
			
			# Execute the module
			spec.loader.exec_module(module)
			
			# Track loaded module to prevent reloading
			_modules_loaded.add(module_path)
		except Exception as e:
			print(f"Failed to load module '{os.path.basename(module_path)}': {str(e)[:100]}")
	
	# Mark initialization as complete
	_initialization_complete = True

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

