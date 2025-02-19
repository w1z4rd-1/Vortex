import json
import os

# ✅ Define file path to store debug mode status
DEBUG_MODE_FILE = os.path.join(os.path.dirname(__file__), "debug_mode.json")

# ✅ Ensure the file exists with a default value
if not os.path.exists(DEBUG_MODE_FILE):
    with open(DEBUG_MODE_FILE, "w") as f:
        json.dump({"debug_mode": False}, f)

def set_debug_mode(enable: bool = None):
    """Enables or disables debug mode and persists it in a file."""
    if enable is None:
        return "❌ Missing 'enable' argument. Use true or false."

    with open(DEBUG_MODE_FILE, "w") as f:
        json.dump({"debug_mode": enable}, f)

    print(f"[🛠 DEBUG MODE] Now set to: {'ON' if enable else 'OFF'}")
    return f"✅ Debug mode {'enabled' if enable else 'disabled'}."

def get_debug_mode():
    """Retrieves the debug mode state from the persistent file."""
    try:
        with open(DEBUG_MODE_FILE, "r") as f:
            data = json.load(f)
            return data.get("debug_mode", False)
    except Exception as e:
        print(f"[❌ ERROR] Failed to read debug mode file: {e}")
        return False  # Default to False if file read fails
