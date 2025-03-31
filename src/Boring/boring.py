# src/Boring/boring.py
import openai
import ollama
import json
import os
import asyncio
import inspect
import re # For stripping <think> tags
import tiktoken # For history limiting
from dotenv import load_dotenv
from src.Boring.capabilities import get_function_registry, get_function_schemas
import src.Boring.capabilities as capabilities
from src.Capabilities.local.memory import retrieve_memory # Ensure this handles errors gracefully
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode

# ------------------------------
# VORTEX Version & Environment Setup
# ------------------------------
VORTEX_VERSION = "Alpha"
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwq:32b")
OLLAMA_SERVER = os.getenv("OLLAMA_SERVER")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ------------------------------
# AI Client Initialization
# ------------------------------
ai_client = None
if AI_PROVIDER == "openai":
    if not OPENAI_API_KEY: raise ValueError("OPENAI_API_KEY missing for AI_PROVIDER='openai'")
    ai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    print(f"[CONFIG] Using AI Provider: OpenAI (Model: {OPENAI_MODEL})")
elif AI_PROVIDER == "ollama":
    try:
        ollama_options = {'host': OLLAMA_SERVER} if OLLAMA_SERVER else {}
        ai_client = ollama.AsyncClient(**ollama_options)
        # Sync check for connectivity
        try:
            ollama.Client(**ollama_options).list() # Simple synchronous check
            print(f"[CONFIG] Using AI Provider: Ollama (Model: {OLLAMA_MODEL}, Server: {OLLAMA_SERVER or 'Default'}) - Connection OK")
        except Exception as conn_err:
             print(f"[WARN] Ollama connection check failed (Server: {OLLAMA_SERVER or 'Default'}): {conn_err}. Proceeding...")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Ollama client: {e}")
else:
    raise ValueError(f"Unsupported AI_PROVIDER: {AI_PROVIDER}. Choose 'openai' or 'ollama'.")

# ------------------------------
# ANSI Escape Codes for Colors
# ------------------------------
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[96m"

# ------------------------------
# System Prompt & Conversation History
# ------------------------------
def load_system_prompt():
    """Loads the system prompt from file or returns default."""
    file_path = "systemprompt.txt"
    default_prompt = "You are VORTEX, a highly intelligent assistant."
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read().strip()
                if content:
                    if get_debug_mode(): print(f"[SYSTEM PROMPT] Loaded from {file_path}")
                    return content
        except Exception as e:
            print(f"{COLOR_YELLOW}[WARN] Failed to read systemprompt.txt: {e}. Using default.{COLOR_RESET}")
    if get_debug_mode(): print(f"[SYSTEM PROMPT] Using default.")
    return default_prompt

conversation_history = []
def initialize_conversation_history():
    """Initializes conversation history with the system prompt."""
    global conversation_history
    conversation_history = [{"role": "system", "content": load_system_prompt()}]
initialize_conversation_history() # Initial call

# ------------------------------
# Tokenizer & History Limiting
# ------------------------------
_tokenizer = None
def get_tokenizer():
    """Gets a tiktoken tokenizer, caching it."""
    global _tokenizer
    if _tokenizer is None:
        try:
            _tokenizer = tiktoken.get_encoding("cl100k_base")
            if get_debug_mode(): print("[TOKENIZER] Loaded cl100k_base tokenizer.")
        except Exception as e:
            print(f"{COLOR_RED}[ERROR] Failed to load tiktoken tokenizer: {e}. History limiting by message count only.{COLOR_RESET}")
            _tokenizer = None
    return _tokenizer

def estimate_tokens(text):
    """Estimates token count for a string using the cached tokenizer."""
    tokenizer = get_tokenizer()
    if tokenizer and isinstance(text, str):
        try:
            return len(tokenizer.encode(text, disallowed_special=()))
        except Exception as e:
            if get_debug_mode(): print(f"[WARN] Token encoding failed: {e}")
            return len(text) // 4
    elif isinstance(text, str):
         return len(text) // 4
    return 0

def limit_conversation_history(max_tokens=1800, max_messages=20):
    """
    Limits conversation history size based on estimated tokens and message count.
    Keeps the system prompt and the most recent messages.
    """
    global conversation_history
    tokenizer = get_tokenizer()
    if not conversation_history: return

    current_tokens = 0; message_count = len(conversation_history)
    system_prompt_present = conversation_history[0]['role'] == 'system'
    system_prompt_tokens = 0

    try:
        if system_prompt_present:
            system_prompt_tokens = estimate_tokens(conversation_history[0].get('content', '')) + 5
            current_tokens += system_prompt_tokens
        for msg in conversation_history[1 if system_prompt_present else 0:]:
            tokens = estimate_tokens(msg.get('content', '')) + 5
            current_tokens += tokens
    except Exception as e:
        print(f"{COLOR_YELLOW}[WARN] Token estimation failed: {e}. Relying on msg count.{COLOR_RESET}"); current_tokens = max_tokens + 1

    if get_debug_mode(): print(f"[✂️ HISTORY CHECK] Current: {message_count} msgs, ~{current_tokens} tokens (Limit: {max_messages} msgs, {max_tokens} tokens)")

    tokens_over_limit = current_tokens - max_tokens
    messages_over_limit = message_count - max_messages
    if tokens_over_limit <= 0 and messages_over_limit <= 0:
        if get_debug_mode(): print("[✂️ HISTORY CHECK] History within limits.")
        return

    num_removed = 0; temp_history = []
    if system_prompt_present: temp_history.append(conversation_history[0])
    messages_to_consider = conversation_history[1 if system_prompt_present else 0:]
    kept_messages = []; current_kept_tokens = system_prompt_tokens; current_kept_message_count = len(temp_history)

    for msg in reversed(messages_to_consider):
        msg_tokens = estimate_tokens(msg.get('content', '')) + 5
        can_keep_by_token = (current_kept_tokens + msg_tokens <= max_tokens)
        can_keep_by_count = (current_kept_message_count < max_messages)
        if can_keep_by_token and can_keep_by_count:
            kept_messages.append(msg); current_kept_tokens += msg_tokens; current_kept_message_count += 1
        else: num_removed += 1

    temp_history.extend(reversed(kept_messages))
    if num_removed > 0:
         if get_debug_mode(): print(f"[✂️ HISTORY TRIMMED] Removed {num_removed}. New: {len(temp_history)} msgs, ~{current_kept_tokens} tokens.")
         conversation_history = temp_history
    elif get_debug_mode(): print("[✂️ HISTORY CHECK] Limits approached or variance occurred.")

# ------------------------------
# AI Call & Function Processing
# ------------------------------
async def call_ai_provider():
    """
    Processes the conversation using the configured AI provider.
    Includes memory retrieval, history limiting, tool call handling (QwQ format),
    and response processing (stripping <think>, adding prefix).
    """
    global conversation_history
    # Initial history checks (same as before)
    if not conversation_history: initialize_conversation_history()
    if not conversation_history or conversation_history[0]['role'] != 'system':
        print(f"{COLOR_RED}[ERROR] History malformed. Reinitializing.{COLOR_RESET}")
        initialize_conversation_history()
    if len(conversation_history) < 2 or conversation_history[-1]['role'] != 'user':
        if not any(msg['role'] == 'user' for msg in conversation_history):
             print(f"{COLOR_RED}[ERROR] No user message in history.{COLOR_RESET}")
             return "Error: I need user input to respond."

    # --- Memory Retrieval (same as before) ---
    user_input_for_memory = next((msg["content"] for msg in reversed(conversation_history) if msg["role"] == "user"), None)
    if user_input_for_memory:
        if get_debug_mode(): print(f"[🧠 MEMORY CHECK] Input: {user_input_for_memory[:50]}...")
        try:
            memories = retrieve_memory(user_input_for_memory)
            if memories:
                memory_text = "\n".join(memories); memory_system_message = {"role": "system", "content": f"Context/Memory:\n{memory_text}"}
                conversation_history.insert(1, memory_system_message)
                if get_debug_mode(): print(f"[✅ MEMORY INSERTED] after system prompt.")
            # else: if get_debug_mode(): print("[❌ NO MEMORY FOUND]") # Removed redundant print
        except Exception as mem_e: print(f"{COLOR_YELLOW}[WARN] Memory retrieval error: {mem_e}{COLOR_RESET}")
    # else: if get_debug_mode(): print("[❌ NO USER INPUT FOR MEMORY CHECK]") # Removed redundant print

    # --- History Limiting (same as before) ---
    try: limit_conversation_history()
    except Exception as e: print(f"{COLOR_RED}[ERROR] History limiting failed: {e}{COLOR_RESET}")

    # --- AI Call Loop ---
    max_retries = 5; attempt = 0
    while attempt < max_retries:
        attempt += 1
        if get_debug_mode(): print(f"\n[🔄 CALLING {AI_PROVIDER.upper()}] Attempt {attempt}/{max_retries}")

        # --- Add Debug Print for History ---
        if get_debug_mode():
            print("--- Sending History to AI ---")
            try: print(json.dumps(conversation_history, indent=2))
            except Exception as dump_e: print(f"(Error dumping history: {dump_e})\n{conversation_history}")
            print("-----------------------------")
        # --- End Debug Print ---

        # Prepare tools/functions (same as before)
        function_schemas = get_function_schemas() or []; tools_param = function_schemas if function_schemas else None
        tool_choice_param = "auto" if tools_param else None
        if tools_param:
            for schema in tools_param: schema.setdefault('type', 'function')

        history_before_call = [msg.copy() for msg in conversation_history]
        assistant_message_content = None; assistant_tool_calls = None; raw_response_content = None

        try:
            # --- Conditional API Call (same as before) ---
            if AI_PROVIDER == "openai":
                if not ai_client: raise ConnectionError("OpenAI client missing");
                response = await asyncio.wait_for(ai_client.chat.completions.create(
                    model=OPENAI_MODEL, messages=conversation_history, tools=tools_param, tool_choice=tool_choice_param), timeout=60)
                assistant_message = response.choices[0].message; assistant_message_content = assistant_message.content
                assistant_tool_calls = assistant_message.tool_calls; raw_response_content = assistant_message_content
            elif AI_PROVIDER == "ollama":
                if get_debug_mode(): print(f"[INFO] Using Ollama Python client API...")
                try:
                    # Convert the conversation history to the format expected by Ollama
                    # Only send the last few messages to avoid context length issues
                    max_history = 10  # Adjust as needed
                    truncated_history = conversation_history[-max_history:] if len(conversation_history) > max_history else conversation_history
                    
                    if not ai_client:
                        raise ConnectionError("Ollama client missing")
                    
                    # Use the Ollama client's chat method
                    response = await ai_client.chat(
                        model=OLLAMA_MODEL,
                        messages=truncated_history,
                        stream=False
                    )
                    
                    # Extract the content directly using the API
                    assistant_message_content = response['message']['content']
                    
                    # Add the assistant's response to conversation history
                    conversation_history.append({"role": "assistant", "content": assistant_message_content})
                    
                    # Return the response
                    return assistant_message_content
                    
                except Exception as e:
                    print(f"{COLOR_RED}[ERROR] Ollama API error: {str(e)}{COLOR_RESET}")
                    import traceback
                    traceback.print_exc()
                    return f"I'm sorry, an error occurred with Ollama: {str(e)}"
            else: raise ValueError(f"Invalid AI_PROVIDER '{AI_PROVIDER}'")

            # --- Append Assistant Message to History (same as before) ---
            message_to_append = {"role": "assistant"};
            if raw_response_content: message_to_append["content"] = raw_response_content
            if AI_PROVIDER == 'openai' and assistant_tool_calls: message_to_append["tool_calls"] = assistant_tool_calls
            if message_to_append.get("content") or message_to_append.get("tool_calls"): conversation_history.append(message_to_append)

            if get_debug_mode():
                content_str = str(assistant_message_content)[:200] if assistant_message_content else "[No Text Content/Tool Call]"
                print(f"[🤖 {AI_PROVIDER.upper()} RESPONSE (Processed)] Content: {content_str}...")
                if assistant_tool_calls: print(f"  Tool Calls Requested/Parsed: {len(assistant_tool_calls)}")

            # --- Tool Call Processing ---
            if assistant_tool_calls:
                tool_responses_for_api = []; function_registry = get_function_registry()
                for tool_call in assistant_tool_calls:
                    if AI_PROVIDER == 'openai':
                        function_name = tool_call.function.name
                        function_args_str = tool_call.function.arguments
                        function_call_id = tool_call.id
                        try: function_args = json.loads(function_args_str)
                        except json.JSONDecodeError: print(f"{COLOR_RED}Invalid JSON args{COLOR_RESET}"); continue
                    elif AI_PROVIDER == 'ollama':
                        function_name = tool_call['function']['name']
                        function_args = tool_call['function']['arguments_parsed']
                        function_call_id = tool_call['id']
                    else: continue

                    if get_debug_mode(): print(f"[🛠 TOOL CALL] ID: {function_call_id}, Fn: {function_name}, Args: {function_args}")
                    
                    function_to_call = function_registry.get(function_name)
                    result_content_json = ""
                    
                    # Execute function and get result
                    if not function_to_call:
                        print(f"{COLOR_RED}[❌ MISSING FN] '{function_name}' not found.{COLOR_RESET}")
                        result_content_json = json.dumps({"error": f"Function '{function_name}' not registered."})
                    else:
                        try:
                            if inspect.iscoroutinefunction(function_to_call):
                                function_result = await function_to_call(**function_args)
                            else:
                                loop = asyncio.get_running_loop()
                                function_result = await loop.run_in_executor(None, lambda: function_to_call(**function_args))
                            
                            try: result_content_json = json.dumps(function_result)
                            except TypeError: result_content_json = json.dumps({"result": str(function_result)})
                            
                            if get_debug_mode(): print(f"[✅ FN SUCCESS] ID: {function_call_id} -> {result_content_json[:100]}...")
                        except Exception as e:
                            print(f"{COLOR_RED}[❌ FN ERROR] ID: {function_call_id}, {function_name}: {e}{COLOR_RESET}")
                            result_content_json = json.dumps({"error": f"Execution failed: {str(e)}"})

                    # Format Tool Result for Next API Call - FIXED: Only append tool response, not duplicate assistant message
                    if AI_PROVIDER == 'openai':
                        tool_responses_for_api.append({
                            "role": "tool",
                            "tool_call_id": function_call_id,
                            "name": function_name,
                            "content": result_content_json
                        })
                    elif AI_PROVIDER == 'ollama':
                        tool_responses_for_api.append({
                            "role": "user",
                            "content": f"<tool_response>{result_content_json}</tool_response>"
                        })

                # Send Tool Responses Back to AI - FIXED: Only extend with tool responses
                if tool_responses_for_api:
                    conversation_history.extend(tool_responses_for_api)
                    continue # Retry API call

            # --- Handle Final Response with Content (same as before) ---
            if assistant_message_content:
                response_text = assistant_message_content
                print(f"{COLOR_CYAN}[Vortex]: {response_text}{COLOR_RESET}")
                conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
                return response_text

            # --- Handle Cases with No Content/Tools ---
            # Adjusted logic: If the response is empty NOW, warn and retry/fail.
            # Don't automatically return "OK." just because it's attempt > 1.
            print(f"{COLOR_YELLOW}[WARN] {AI_PROVIDER.upper()} returned no usable content or tool calls on attempt {attempt}. Retrying if possible.{COLOR_RESET}")
            conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
            # Allow loop to retry if attempts remain

        # --- Error Handling for API Calls (same as before) ---
        except asyncio.TimeoutError:
             print(f"{COLOR_RED}[❌ TIMEOUT ERROR] {AI_PROVIDER.upper()} API timed out.{COLOR_RESET}")
             conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
             return f"I'm sorry, the {AI_PROVIDER} API timed out."
        except (openai.APIConnectionError, ollama.RequestError) as e:
             print(f"{COLOR_RED}[❌ CONNECTION ERROR] {AI_PROVIDER.upper()}: {e}{COLOR_RESET}")
             conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
             return f"I'm sorry, I couldn't connect to the {AI_PROVIDER} API."
        except Exception as e:
            import traceback; print(f"{COLOR_RED}[❌ UNEXPECTED API/PROCESSING ERROR] {e}{COLOR_RESET}")
            if get_debug_mode(): traceback.print_exc()
            conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
            return f"I'm sorry, an unexpected error occurred processing the request with {AI_PROVIDER.upper()}."

    # --- Reached Max Retries ---
    print(f"{COLOR_RED}[❌ MAX RETRIES REACHED] Failed after {max_retries} attempts. No tool call generated or final response received.{COLOR_RESET}")
    conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
    # Return a more specific error message
    return "I'm sorry, the AI failed to provide a valid response or action after multiple attempts."

# ------------------------------
# Conversation History Helpers
# ------------------------------
def add_user_input(user_input):
    """Adds a user message to the conversation history. VORTEX.py handles printing."""
    global conversation_history
    conversation_history.append({"role": "user", "content": user_input})

# ------------------------------
# Startup Message
# ------------------------------
def display_startup_message():
    """Displays VORTEX's startup banner."""
    COLOR_CYAN = "\033[96m"; VORTEX_VERSION="Alpha"; COLOR_GREEN = "\033[92m"; COLOR_RESET = "\033[0m"
    # vortex_ascii = r"""...""" # Your ASCII art here
    box_width = 45; top_bottom_border = "═" * (box_width - 2)
    provider_info = f"AI: {AI_PROVIDER.upper()}"
    if AI_PROVIDER == 'ollama': provider_info += f" ({OLLAMA_MODEL})"
    elif AI_PROVIDER == 'openai': provider_info += f" ({OPENAI_MODEL})"
    startup_text = f"""{COLOR_CYAN}
    ╔{top_bottom_border}╗
    ║ VORTEX: Wizard's Virtual Assistant        ║
    ║ Version: {VORTEX_VERSION}{' ' * (box_width - 12 - len(VORTEX_VERSION))}║
    ║ {provider_info}{' ' * (box_width - 5 - len(provider_info))}║
    ╠{top_bottom_border}╣
    ║ Created by: {COLOR_GREEN}Wizard1{' ' * (box_width - 25)}{COLOR_GREEN}║
    ╚{top_bottom_border}╝{COLOR_RESET}"""
    # print(COLOR_CYAN + vortex_ascii + COLOR_RESET) # Uncomment for ASCII art
    print(startup_text)

# --- Final check ---
if not conversation_history:
    print(f"{COLOR_YELLOW}[WARN] History empty after init, reinitializing.{COLOR_RESET}")
    initialize_conversation_history()