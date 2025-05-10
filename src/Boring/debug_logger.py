from datetime import datetime
# Ensure this path is correct, assuming debug_mode.py is in src/Capabilities/
from src.Capabilities.debug_mode import get_debug_mode

_frontend_debug_emitter = None

def register_frontend_debug_emitter(emitter_func):
    """Registers a callback function to emit debug messages to the frontend."""
    global _frontend_debug_emitter
    _frontend_debug_emitter = emitter_func
    # Consider if this print is still needed here or should be in the calling module
    # For now, keeping it similar to original boring.py
    print("[DEBUG_EMITTER_SETUP] Attempting to register frontend debug emitter (in debug_logger).")
    if get_debug_mode() and _frontend_debug_emitter:
        print("[DEBUG_EMITTER_SETUP] Frontend debug emitter registered successfully (in debug_logger).")

def log_debug_event(message: str, is_error: bool = False):
    """
    Logs a debug message to the console and, if debug mode is on,
    sends it to the frontend via the registered emitter.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = "[BORING_ERROR]" if is_error else "[BORING_DEBUG]" # Or maybe a different prefix like [DEBUG_LOGGER]
    console_message = f"[{timestamp}] {prefix} {message}"
    
    print(console_message) # Always print to console

    if get_debug_mode() and _frontend_debug_emitter:
        try:
            _frontend_debug_emitter(message, is_error)
        except Exception as e:
            error_timestamp = datetime.now().strftime("%H:%M:%S")
            # This print indicates a failure within the logger itself.
            print(f"[{error_timestamp}] [CRITICAL_DEBUG_EMIT_FAIL] Failed to emit to frontend from debug_logger: {e}") 