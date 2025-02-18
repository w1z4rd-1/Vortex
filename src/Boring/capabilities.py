import os
import importlib.util

# Ensure Capabilities folder exists
CAPABILITIES_DIR = "Capabilities"
os.makedirs(CAPABILITIES_DIR, exist_ok=True)

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

# 🔄 AUTO-LOAD FUNCTIONS FROM THE CAPABILITIES FOLDER
for filename in os.listdir(CAPABILITIES_DIR):
    if filename.endswith(".py") and filename != "__init__.py":
        module_name = filename[:-3]
        module_path = os.path.join(CAPABILITIES_DIR, filename)
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for func_name in dir(module):
                func_obj = getattr(module, func_name)
                if callable(func_obj) and func_name not in function_registry:
                    register_function_in_registry(func_name, func_obj)
                    print(f"[✅ REGISTERED] Auto-loaded function: {func_name}")
        except Exception as e:
            print(f"[❌ ERROR] Failed to load capability '{filename}': {e}")

def persist_dynamic_function(function_name, function_code):
    """Writes a dynamically registered function to a separate file in the Capabilities folder."""
    function_file = os.path.join(CAPABILITIES_DIR, f"{function_name}.py")
    with open(function_file, "w", encoding="utf-8") as f:
        f.write(function_code)
    print(f"[💾 PERSIST] Function '{function_name}' saved to '{function_file}'")
