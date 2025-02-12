import requests

import json
import os
import capabilities
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

# 🔄 AUTO-LOAD NEWLY BUILT FUNCTIONS
generated_file = "generated_capabilities.py"

if os.path.exists(generated_file):
    try:
        with open(generated_file, "r", encoding="utf-8") as f:
            exec(f.read(), globals())  # ✅ Executes the functions in the global scope
        print("[✅ SUCCESS] Dynamically generated functions loaded from 'generated_capabilities.py'")

        # Ensure all functions in generated_capabilities.py are registered
        for func_name, func_obj in globals().items():
            if callable(func_obj) and func_name not in function_registry:
                register_function_in_registry(func_name, func_obj)
                print(f"[✅ REGISTERED] Auto-loaded function: {func_name}")

    except Exception as e:
        print(f"[❌ ERROR] Failed to load generated capabilities: {e}")
else:
    print("[⚠️ WARNING] No 'generated_capabilities.py' file found. No dynamic functions loaded.")

# ✅ Ensure functions and schemas persist dynamically
def persist_dynamic_functions():
    """Writes dynamically registered functions to 'generated_capabilities.py' for persistence."""
    with open("generated_capabilities.py", "w", encoding="utf-8") as f:
        for func_name, func in function_registry.items():
            f.write(f"\n\ndef {func_name}(*args, **kwargs):\n    pass  # Placeholder, actual function logic should be here\n")
            f.write(f"\ncapabilities.register_function_in_registry(\"{func_name}\", {func_name})\n")
    print("[💾 PERSIST] Dynamically registered functions saved to 'generated_capabilities.py'")



# === Auto-Generated Function ===
def multiply_numbers(a: float, b: float) -> float:
    """
    Multiplies two numbers together.
    :param a: First number.
    :param b: Second number.
    :return: The product of the two numbers.
    """
    try:
        return a * b
    except Exception as e:
        return {"error": str(e)}

# Registering the function
capabilities.register_function_in_registry("multiply_numbers", multiply_numbers)

# Schema registration for VORTEX
capabilities.register_function_schema({
    'type': 'function',
    'function': {
        'name': 'multiply_numbers',
        'description': 'Multiplies two numbers together.',
        'parameters': {
            'type': 'object',
            'properties': {
                'a': {'type': 'number', 'description': 'First number.'},
                'b': {'type': 'number', 'description': 'Second number.'}
            },
            'required': ['a', 'b']
        }
    }
})



# === Auto-Generated Function ===
import requests

def get_urban_definition(term: str) -> dict:
    """
    Fetches the definition of a term from Urban Dictionary.
    :param term: The word or phrase to look up.
    :return: Dictionary containing the definition and example.
    """
    try:
        url = f"https://api.urbandictionary.com/v0/define?term={term}"
        response = requests.get(url)
        data = response.json()
        if data['list']:
            top_entry = data['list'][0]
            return {
                "definition": top_entry["definition"],
                "example": top_entry["example"]
            }
        else:
            return {"error": "No definition found."}
    except Exception as e:
        return {"error": str(e)}

# Register the new capability
capabilities.register_function_in_registry("get_urban_definition", get_urban_definition)

# Schema registration for VORTEX
capabilities.register_function_schema({
    'type': 'function',
    'function': {
        'name': 'get_urban_definition',
        'description': 'Fetches the definition of a term from Urban Dictionary.',
        'parameters': {
            'type': 'object',
            'properties': {
                'term': {'type': 'string', 'description': 'The term to look up.'}
            },
            'required': ['term']
        }
    }
})

