import json

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
    
    # ✅ Prevent duplicate schema registration
    if schema_name not in [s["function"]["name"] for s in function_schemas]:
        function_schemas.append(schema)
        print(f"[✅ SCHEMA REGISTERED] {schema_name} added to schemas.")
    else:
        print(f"[⚠️ SKIPPED] Schema for {schema_name} is already registered.")

# ✅ Accessor function for function registry
def get_function_registry():
    """Returns the global function registry."""
    return function_registry

# ✅ Accessor function for function schemas
def get_function_schemas():
    """Returns the global function schemas."""
    return function_schemas

# ✅ Debugging: Print all registered functions and schemas
print(f"[✅ CAPABILITIES LOADED] Available Functions: {list(function_registry.keys())}")
print(f"[✅ FUNCTION SCHEMAS LOADED] {function_schemas}")
