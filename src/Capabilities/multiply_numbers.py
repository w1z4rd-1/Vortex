# === Auto-Generated Function ===
from src.Boring.functions import get_debug_mode

import src.Boring.capabilities as capabilities

def multiply_numbers(a: int, b: int) -> int:
    """Multiplies two numbers and returns the result."""
    try:
        if get_debug_mode():
            print('[DEBUG] Multiplying:', a, 'and', b)
        result = a * b
        return result
    except Exception as e:
        return str(e)

multiply_numbers.schema = {
    'a': int,
    'b': int
}

capabilities.register_function_schema({"type": "function", "function": {
    "name": "multiply_numbers",
    "description": "Multiplies two numbers and returns the result.",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"}
        },
        "required": ["a", "b"]
    }
}})

capabilities.register_function_in_registry("multiply_numbers", multiply_numbers)
