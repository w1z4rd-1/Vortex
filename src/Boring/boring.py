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
from .debug_logger import log_debug_event, register_frontend_debug_emitter # MOVED log_debug_event

# ------------------------------
# Debug Logging Setup
# ------------------------------
# MOVED TO debug_logger.py
# _frontend_debug_emitter = None
# def register_frontend_debug_emitter(emitter_func):
# ...
# def log_debug_event(message: str, is_error: bool = False):
# ...

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
# AI Client Initialization (Deferred)
# ------------------------------
ai_client = None

def initialize_ai_client_for_loop():
    """Initializes the AI client. Should be called from the asyncio event loop thread."""
    global ai_client
    if ai_client is not None: # Prevent re-initialization
        log_debug_event("AI client already initialized.")
        return

    log_debug_event(f"Initializing AI client for provider: {AI_PROVIDER}")

    if AI_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY missing for AI_PROVIDER='openai'")
        ai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        print(f"[CONFIG] Using AI Provider: OpenAI (Model: {OPENAI_MODEL})")
    elif AI_PROVIDER == "ollama":
        try:
            ollama_options = {}
            if OLLAMA_SERVER:
                ollama_options['host'] = OLLAMA_SERVER
            
            # Create client with explicit timeout
            ai_client = ollama.AsyncClient(
                **ollama_options,
                timeout=60.0  # 60 second timeout
            )
            # Sync check for connectivity (this is fine here as it's part of init)
            try:
                sync_client = ollama.Client(**ollama_options) # For sync check only
                models = sync_client.list()
                if isinstance(models, dict) and 'models' in models:
                    model_names = [m.get('name', str(m)) for m in models['models']]
                    print(f"[CONFIG] Using AI Provider: Ollama (Model: {OLLAMA_MODEL}, Server: {OLLAMA_SERVER or 'Default'}) - Connection OK")
                    print(f"Available models: {model_names}")
                else:
                    print(f"[CONFIG] Using AI Provider: Ollama (Model: {OLLAMA_MODEL}, Server: {OLLAMA_SERVER or 'Default'}) - Connection OK")
            except Exception as conn_err:
                 print(f"[WARN] Ollama connection check failed (Server: {OLLAMA_SERVER or 'Default'}): {conn_err}. Proceeding...")
        except Exception as e:
            # Log the error before raising, to ensure it's visible
            log_debug_event(f"Failed to initialize Ollama client: {e}", is_error=True)
            raise RuntimeError(f"Failed to initialize Ollama client: {e}")
    else:
        raise ValueError(f"Unsupported AI_PROVIDER: {AI_PROVIDER}. Choose 'openai' or 'ollama'.")

    if ai_client is None:
        # This case should ideally be caught by the specific provider logic
        log_debug_event(f"AI client remained None after initialization attempt for {AI_PROVIDER}", is_error=True)
        raise RuntimeError(f"AI Client could not be initialized for provider: {AI_PROVIDER}")
    log_debug_event("AI client initialization complete.")

async def cleanup_ai_client():
    """Cleanup function to properly close AI client connections."""
    global ai_client
    if ai_client is not None:
        try:
            if AI_PROVIDER == "ollama":
                # Close all connections in the Ollama client's connection pool
                await ai_client.aclose()
            log_debug_event("AI client cleanup completed successfully.")
        except Exception as e:
            log_debug_event(f"Error during AI client cleanup: {e}", is_error=True)
        finally:
            ai_client = None

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
                    log_debug_event(f"System prompt loaded from {file_path}")
                    return content
        except Exception as e:
            print(f"{COLOR_YELLOW}[WARN] Failed to read systemprompt.txt: {e}. Using default.{COLOR_RESET}")
    log_debug_event("Using default system prompt.")
    return default_prompt

conversation_history = []
def initialize_conversation_history():
    """Initializes conversation history with the system prompt."""
    global conversation_history
    conversation_history = [{"role": "system", "content": load_system_prompt()}]
initialize_conversation_history() # Initial call

# ------------------------------
# Tokenizer for Debug Info Only
# ------------------------------
_tokenizer = None
def get_tokenizer():
    """Gets a tiktoken tokenizer, caching it."""
    global _tokenizer
    if _tokenizer is None:
        try:
            _tokenizer = tiktoken.get_encoding("cl100k_base")
            log_debug_event("Loaded cl100k_base tokenizer.")
        except Exception as e:
            print(f"{COLOR_RED}[ERROR] Failed to load tiktoken tokenizer: {e}.{COLOR_RESET}")
            _tokenizer = None
    return _tokenizer

def estimate_tokens(text):
    """Estimates token count for a string using the cached tokenizer."""
    tokenizer = get_tokenizer()
    if tokenizer and isinstance(text, str):
        try:
            return len(tokenizer.encode(text, disallowed_special=()))
        except Exception as e:
            log_debug_event(f"Token encoding failed: {e}", is_error=True)
            return len(text) // 4
    elif isinstance(text, str):
         return len(text) // 4
    return 0

# ------------------------------
# AI Call & Function Processing
# ------------------------------
async def _call_openai(conversation_history, tools_param=None, tool_choice_param=None):
    """Helper function to call the OpenAI API with the given parameters."""
    if not ai_client: 
        raise ConnectionError("OpenAI client missing")
        
    log_debug_event(f"Calling OpenAI API with {len(conversation_history)} messages.")
        
    response = await asyncio.wait_for(ai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=conversation_history,
        tools=tools_param,
        tool_choice=tool_choice_param), 
        timeout=60
    )
    
    assistant_message = response.choices[0].message
    return {
        "content": assistant_message.content,
        "tool_calls": assistant_message.tool_calls
    }

async def _call_ollama(conversation_history, tools_param=None):
    """Helper function to call the Ollama API with the given parameters."""
    if not ai_client: 
        raise ConnectionError("Ollama client missing")
        
    log_debug_event(f"Calling Ollama API with {len(conversation_history)} messages.")
    
    # Create options for better context maintenance
    ollama_options = {
        'num_ctx': 8192,  # Larger context window
        'top_k': 40,      # Consider more tokens
        'top_p': 0.9,     # Nucleus sampling
        'repeat_penalty': 1.1  # Reduce repetition
    }
    
    # Increase context size if we have many tools
    if tools_param and len(tools_param) > 5:
        ollama_options["num_ctx"] = 16384
        log_debug_event(f"Increased Ollama context window to 16384 due to {len(tools_param)} tools")
    
    # Following Ollama docs with added options for better context maintenance
    response = await ai_client.chat(
        model=OLLAMA_MODEL,
        messages=conversation_history,
        tools=tools_param,
        stream=False,
        options=ollama_options
    )
    
    assistant_message = response.message
    return {
        "content": assistant_message.content,
        "tool_calls": getattr(assistant_message, 'tool_calls', None)
    }

async def call_ai_provider():
    """
    Processes the conversation using the configured AI provider.
    Includes memory retrieval, tool call handling, and response processing.
    NO history limiting.
    """
    global conversation_history
    # Initial history checks
    if not conversation_history: initialize_conversation_history()
    if not conversation_history or conversation_history[0]['role'] != 'system':
        print(f"{COLOR_RED}[ERROR] History malformed. Reinitializing.{COLOR_RESET}")
        initialize_conversation_history()
    if len(conversation_history) < 2 or conversation_history[-1]['role'] != 'user':
        if not any(msg['role'] == 'user' for msg in conversation_history):
             print(f"{COLOR_RED}[ERROR] No user message in history.{COLOR_RESET}")
             return "Error: I need user input to respond."

    # --- Memory Retrieval ---
    user_input_for_memory = next((msg["content"] for msg in reversed(conversation_history) if msg["role"] == "user"), None)
    if user_input_for_memory:
        log_debug_event(f"Memory Check Input: {user_input_for_memory[:50]}...")
        try:
            memories = retrieve_memory(user_input_for_memory)
            if memories:
                memory_text = "\n".join(memories); memory_system_message = {"role": "system", "content": f"Context/Memory:\n{memory_text}"}
                # Insert memory after the system prompt, if it exists
                insert_pos = 1 if (conversation_history and conversation_history[0]['role'] == 'system') else 0
                conversation_history.insert(insert_pos, memory_system_message)
                log_debug_event("Memory inserted after system prompt.")
        except Exception as mem_e: print(f"{COLOR_YELLOW}[WARN] Memory retrieval error: {mem_e}{COLOR_RESET}")

    # --- Debug History Info Only ---
    if get_debug_mode():
        log_debug_event("--- Pre-API Call History & Token Estimation ---")
        for i, msg in enumerate(conversation_history):
            content_preview = str(msg.get("content", ""))[:50].replace("\n", "\\n")
            print(f"  [{i}] {msg.get('role')}: {content_preview}...")
        
        # Calculate total tokens for information only
        try:
            total_tokens = sum(estimate_tokens(msg.get('content', '')) + 5 for msg in conversation_history)
            log_debug_event(f"Estimated total tokens for API call: ~{total_tokens}")
        except Exception as e:
            log_debug_event(f"Token estimation failed: {e}", is_error=True)

    # --- AI Call Loop ---
    max_retries = 5; attempt = 0
    while attempt < max_retries:
        attempt += 1
        log_debug_event(f"Calling {AI_PROVIDER.upper()} API - Attempt {attempt}/{max_retries}")

        # --- Debug Print for History if needed ---
        if get_debug_mode():
            log_debug_event("--- Sending Full History to AI (JSON Dump) ---")
            try: 
                print(json.dumps(conversation_history, indent=2))
            except Exception as dump_e: 
                log_debug_event(f"Error dumping history to JSON: {dump_e}. Raw history: {conversation_history}", is_error=True)
            log_debug_event("--- End of Full History JSON Dump ---")

        # --- Prepare tools/functions ---
        function_schemas = get_function_schemas() or []
        tools_param = function_schemas if function_schemas else None
        tool_choice_param = "auto" if tools_param else None
        if tools_param:
            for schema in tools_param: schema.setdefault('type', 'function')

        # Store history state before API call in case of error/retry
        history_before_call = [msg.copy() for msg in conversation_history]

        assistant_message_content = None
        assistant_tool_calls = None
        raw_response_content = None

        try:
            # --- Call the appropriate API based on provider ---
            if AI_PROVIDER == "openai":
                response = await _call_openai(
                    conversation_history=conversation_history,
                    tools_param=tools_param,
                    tool_choice_param=tool_choice_param
                )
                assistant_message_content = response["content"]
                assistant_tool_calls = response["tool_calls"]
                raw_response_content = assistant_message_content
                
            elif AI_PROVIDER == "ollama":
                response = await _call_ollama(
                    conversation_history=conversation_history,
                    tools_param=tools_param
                )
                assistant_message_content = response["content"]
                assistant_tool_calls = response["tool_calls"]
                raw_response_content = assistant_message_content
                
            else:
                raise ValueError(f"Invalid AI_PROVIDER '{AI_PROVIDER}'")

            # --- Shared Logic After Successful API Call ---
            # --- Append Assistant Message to History ---
            message_to_append = {"role": "assistant"}
            if raw_response_content:
                 message_to_append["content"] = raw_response_content

            # Store tool calls in the message if they exist
            if assistant_tool_calls:
                 message_to_append["tool_calls"] = assistant_tool_calls

            # Append the assistant's turn *once* if there's content or tool calls
            if message_to_append.get("content") or message_to_append.get("tool_calls"):
                # Important: We append to history *in place* for consistency
                conversation_history.append(message_to_append)
                if get_debug_mode():
                     content_str = str(assistant_message_content)[:200] if assistant_message_content else "[No Text Content/Tool Call]"
                     print(f"[🤖 {AI_PROVIDER.upper()} RESPONSE (Processed)] Content: {content_str}...")
                     if assistant_tool_calls: print(f"  Tool Calls Requested/Parsed: {len(assistant_tool_calls)}")
                     print("[CONVERSATION HISTORY AFTER RESPONSE]")
                     for i, msg in enumerate(conversation_history):
                         content_preview = str(msg.get("content", ""))[:50].replace("\n", "\\n") 
                         print(f"  [{i}] {msg.get('role')}: {content_preview}...")

            # --- Tool Call Processing ---
            if assistant_tool_calls:
                tool_responses_for_api = []
                function_registry = get_function_registry()

                for tool_call in assistant_tool_calls:
                    function_name = None
                    function_args = None
                    function_call_id = None
                    result_content_json = None

                    try:
                        if AI_PROVIDER == 'openai':
                             if hasattr(tool_call, 'function'):
                                 function_name = tool_call.function.name
                                 function_args_str = tool_call.function.arguments
                                 function_call_id = tool_call.id
                                 try:
                                     function_args = json.loads(function_args_str)
                                 except json.JSONDecodeError:
                                     print(f"{COLOR_RED}[❌ JSON ERROR] Invalid JSON args for OpenAI tool {function_name}{COLOR_RESET}")
                                     continue
                             else: continue
                        elif AI_PROVIDER == 'ollama':
                             # tool_call is an object from ollama.py (e.g., ollama.ToolCall)
                             if hasattr(tool_call, 'function') and tool_call.function and \
                                hasattr(tool_call.function, 'name') and \
                                hasattr(tool_call.function, 'arguments'):

                                 function_name = tool_call.function.name
                                 function_args = tool_call.function.arguments # This should be a dict

                                 # Ollama's library ToolCall object does not consistently define an 'id' attribute.
                                 # Attempt to get 'id' if present on tool_call itself using getattr.
                                 # The 'name' field in the tool response message is primarily used.
                                 function_call_id = getattr(tool_call, 'id', None)

                                 # Ensure arguments are a dictionary. The ollama library should provide this.
                                 if not isinstance(function_args, dict):
                                     print(f"{COLOR_RED}[❌ ARG TYPE ERROR] Ollama tool {function_name} arguments not a dict: {type(function_args)}{COLOR_RESET}")
                                     # Attempt to parse if it's a string, as a fallback.
                                     if isinstance(function_args, str):
                                         try:
                                             function_args = json.loads(function_args)
                                         except json.JSONDecodeError:
                                             print(f"{COLOR_RED}[❌ JSON ERROR] Invalid JSON string args for Ollama tool {function_name}{COLOR_RESET}")
                                             continue
                                     else:
                                         # If not a dict and not a parsable string, skip this tool call.
                                         if get_debug_mode(): print(f"[DEBUG] Skipping Ollama tool {function_name} due to unparsable arguments.")
                                         continue
                             else:
                                 if get_debug_mode(): print(f"[DEBUG] Skipping Ollama tool_call due to missing function/name/arguments attributes: {tool_call}")
                                 continue
                        else: continue

                        if not function_name or function_args is None: continue

                        if get_debug_mode(): print(f"[🛠️ TOOL CALL] Fn: {function_name}, Args: {function_args}")

                        # --- Execute function ---
                        function_to_call = function_registry.get(function_name)
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

                                if get_debug_mode(): print(f"[✅ FN SUCCESS] Function: {function_name} -> {result_content_json[:100]}...")
                            except Exception as e:
                                print(f"{COLOR_RED}[❌ FN ERROR] Function: {function_name}: {e}{COLOR_RESET}")
                                result_content_json = json.dumps({"error": f"Execution failed: {str(e)}"})

                    except Exception as tool_parse_exec_error:
                         print(f"{COLOR_RED}[❌ TOOL PARSE/EXEC ERR] {tool_parse_exec_error}{COLOR_RESET}")
                         result_content_json = json.dumps({"error": f"Failed to parse or execute tool call: {tool_parse_exec_error}"})
                         if function_name is None and isinstance(tool_call, dict):
                              function_name = tool_call.get('function', {}).get('name', 'unknown_function')
                         elif function_name is None and hasattr(tool_call, 'function'):
                              function_name = getattr(tool_call.function, 'name', 'unknown_function')
                         else:
                              function_name = 'unknown_function'

                    # --- Format Tool Result for Next API Call ---
                    if result_content_json is not None:
                         if AI_PROVIDER == 'openai':
                              if function_call_id:
                                   tool_responses_for_api.append({
                                       "role": "tool",
                                       "tool_call_id": function_call_id,
                                       "name": function_name,
                                       "content": result_content_json
                                   })
                         elif AI_PROVIDER == 'ollama':
                              # For Ollama, ensure a consistent format (either with or without tool_call_id)
                              tool_response = {
                                  "role": "tool",
                                  "name": function_name,
                                  "content": result_content_json
                              }
                              # Add ID if we have one (some Ollama versions support this)
                              if function_call_id:
                                  tool_response["tool_call_id"] = function_call_id
                                  
                              tool_responses_for_api.append(tool_response)

                # --- Send Tool Responses Back to AI ---
                if tool_responses_for_api:
                    if get_debug_mode(): 
                        print(f"[🔄 SENDING TOOL RESULTS] {len(tool_responses_for_api)} results being added to history.")
                        for resp in tool_responses_for_api:
                            print(f"  - Tool response for {resp.get('name')}: {resp.get('content')[:50]}...")
                    
                    # Add tool responses to history
                    conversation_history.extend(tool_responses_for_api)
                    
                    # For Ollama, specifically make a followup call instead of returning
                    # This helps maintain context when using tool calls
                    if AI_PROVIDER == 'ollama':
                        if get_debug_mode():
                            print("[OLLAMA TOOL HANDLING] Making follow-up call for tool responses")
                        continue  # This will loop back to make another API call with the updated history
                    else:
                        continue  # Standard behavior for OpenAI

            # --- Handle Final Response with Content ---
            if assistant_message_content:
                 response_text = assistant_message_content
                 print(f"{COLOR_CYAN}[Vortex]: {response_text}{COLOR_RESET}")
                 # Remove temporary memory message AFTER successful final response
                 conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
                 return response_text # Success

            # --- Handle Cases with No Content/Tools ---
            print(f"{COLOR_YELLOW}[WARN] {AI_PROVIDER.upper()} returned no usable content or tool calls on attempt {attempt}. Retrying if possible.{COLOR_RESET}")
            conversation_history = history_before_call
            # Allow loop to retry if attempts remain

        # --- Error Handling for API Calls ---
        except asyncio.TimeoutError:
            print(f"{COLOR_RED}[❌ TIMEOUT ERROR] {AI_PROVIDER.upper()} API timed out on attempt {attempt}.{COLOR_RESET}")
            conversation_history = history_before_call
        except (openai.APIConnectionError, ollama.RequestError) as e:
            print(f"{COLOR_RED}[❌ CONNECTION ERROR] {AI_PROVIDER.upper()} on attempt {attempt}: {e}{COLOR_RESET}")
            conversation_history = history_before_call
        except Exception as e:
            import traceback
            print(f"{COLOR_RED}[❌ UNEXPECTED API/PROCESSING ERROR] on attempt {attempt}: {e}{COLOR_RESET}")
            if get_debug_mode(): traceback.print_exc()
            conversation_history = history_before_call

        # --- Pause before retry ---
        if attempt < max_retries:
             await asyncio.sleep(1)

    # --- Reached Max Retries ---
    print(f"{COLOR_RED}[❌ MAX RETRIES REACHED] Failed after {max_retries} attempts. No valid response received.{COLOR_RESET}")
    # Clean up memory message from potentially failed final attempt's history
    conversation_history = [msg for msg in conversation_history if not (msg["role"] == "system" and "Context/Memory:" in msg["content"])]
    return "I'm sorry, the AI failed to provide a valid response after multiple attempts."

# ------------------------------
# Conversation History Helpers
# ------------------------------
def add_user_input(user_input):
    """Adds a user message to the conversation history. VORTEX.py handles printing."""
    global conversation_history
    # Make sure we're not duplicating the user message - it should only be added once
    if len(conversation_history) > 0 and conversation_history[-1].get('role') == 'user' and conversation_history[-1].get('content') == user_input:
        if get_debug_mode(): print(f"[WARN] Skipping duplicate user message: {user_input[:30]}...")
        return
    conversation_history.append({"role": "user", "content": user_input})
    if get_debug_mode():
        print(f"[USER INPUT ADDED] {user_input[:50]}...")
        print("[CONVERSATION HISTORY AFTER USER INPUT]")
        for i, msg in enumerate(conversation_history):
            content_preview = str(msg.get("content", ""))[:50].replace("\n", "\\n")
            print(f"  [{i}] {msg.get('role')}: {content_preview}...")

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