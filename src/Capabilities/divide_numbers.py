# === Auto-Generated Function ===
from src.Boring.functions import get_debug_mode

import src.Boring.capabilities as capabilities

def divide_numbers(a: int, b: int) -> float:
    """Divides two numbers and returns the result."""
    try:
        if get_debug_mode():
            print('[DEBUG] Dividing:', a, 'by', b)
        result = a / b
        return result
    except Exception as e:
        return str(e)

divide_numbers.schema = {
    'a': int,
    'b': int
}

capabilities.register_function_schema({"type": "function", "function": {
    "name": "divide_numbers",
    "description": "Divides two numbers and returns the result.",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"}
        },
        "required": ["a", "b"]
    }
}})

capabilities.register_function_in_registry("divide_numbers", divide_numbers)
