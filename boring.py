import openai
import json
import os
import asyncio
import inspect
from dotenv import load_dotenv

# Import dynamic capabilities and helper functions.
import capabilities  # This module should provide:
                     # - get_function_schemas(): returns function schemas (or None if none)
                     # - get_function_registry(): returns a dict mapping function names to callables.
from functions import set_debug_mode, get_debug_mode, retrieve_memory, read_vortex_code

# ------------------------------
# VORTEX Version & Environment Setup
# ------------------------------
VORTEX_VERSION = "Alpha"

# Load environment variables (e.g., API keys)
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize the OpenAI async client.
client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

# ------------------------------
# ANSI Escape Codes for Colors
# ------------------------------
COLOR_BLUE   = "\033[94m"
COLOR_GREEN  = "\033[92m"
COLOR_RED    = "\033[91m"
COLOR_RESET  = "\033[0m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN   = "\033[96m"

# ------------------------------
# System Prompt & Conversation History
# ------------------------------
def load_system_prompt():
    """
    Loads the system prompt from 'systemprompt.txt' if it exists and is non-empty;
    otherwise returns a default system prompt.
    """
    file_path = "systemprompt.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if content:
                return content
    return "You are VORTEX, a highly intelligent assistant."

# Initialize conversation history with a system prompt.
conversation_history = [{"role": "system", "content": load_system_prompt()}]

# ------------------------------
# OpenAI Call & Function Processing
# ------------------------------
async def call_openai():
    """
    Processes the current conversation history by calling the OpenAI API.
    It retrieves relevant memories, passes any requested function calls,
    and updates the conversation history with the assistant's response.
    """
    global conversation_history
    user_input = conversation_history[-1]["content"]

    if get_debug_mode():
        print(f"[🧠 MEMORY CHECK] Searching for memories related to: {user_input}")

    memories = retrieve_memory(user_input)
    if memories:
        memory_text = "\n".join(memories)
        if get_debug_mode():
            print(f"[✅ MEMORY FOUND] Retrieved: {memory_text}")
        # Append the memory as a SYSTEM message to remind the model.
        conversation_history.append({
            "role": "system",
            "content": f"Before answering, remember this: {memory_text}"
        })
    else:
        if get_debug_mode():
            print(f"[❌ NO MEMORY FOUND] No relevant memories retrieved.")

    max_retries = 10  # Prevent infinite loops
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        if get_debug_mode():
            print(f"[🔄 CALLING OPENAI] Attempt {attempt}/{max_retries}")

        # Retrieve function schemas if available.
        function_schemas = capabilities.get_function_schemas() if capabilities.get_function_schemas() else None
        tool_choice_param = "auto" if function_schemas else None

        try:
            # Call the OpenAI API with timeouts to prevent indefinite hanging.
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4o",
                    messages=conversation_history,
                    tools=function_schemas,
                    tool_choice=tool_choice_param,
                    timeout=15
                ),
                timeout=20
            )
        except asyncio.TimeoutError:
            print(f"{COLOR_RED}[❌ TIMEOUT ERROR] OpenAI API did not respond within 20 seconds.{COLOR_RESET}")
            return
        except Exception as e:
            print(f"{COLOR_RED}[❌ API ERROR] {e}{COLOR_RESET}")
            return

        assistant_message = response.choices[0].message
        conversation_history.append(assistant_message)

        if get_debug_mode():
            print(f"[🤖 OPENAI RESPONSE] {assistant_message.content}")

        # Display the assistant's response.
        if assistant_message.content:
            print(f"{COLOR_BLUE}[🤖 VORTEX]: {assistant_message.content}{COLOR_RESET}")
        elif assistant_message.tool_calls:
            if get_debug_mode():
                print(f"[🛠 TOOL CALL ONLY] OpenAI returned tool calls without message content.")
        else:
            print(f"{COLOR_RED}[❌ ERROR] OpenAI returned an empty response!{COLOR_RESET}")

        # Exit if no tool calls are requested.
        if not assistant_message.tool_calls:
            break

        # Process any tool calls.
        tool_responses = []
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            function_call_id = tool_call.id

            if get_debug_mode():
                print(f"[🔄 CHECKING FUNCTION] ID: {tool_call.id} | Name: {function_name}")

            function_to_call = capabilities.get_function_registry().get(function_name)
            if not function_to_call:
                print(f"{COLOR_RED}[❌ MISSING FUNCTION] '{function_name}' not found.{COLOR_RESET}")

                # Suggest similar function names if available.
                similar_functions = [f for f in capabilities.get_function_registry().keys() if function_name.lower() in f]
                if similar_functions:
                    print(f"{COLOR_YELLOW}[💡 SUGGESTED FIX] Did you mean: {', '.join(similar_functions)}?{COLOR_RESET}")
                continue

            try:
                if get_debug_mode():
                    print(f"[🚀 EXECUTING] Running {function_name}({json.dumps(function_args)})")
                # Await async functions automatically.
                if inspect.iscoroutinefunction(function_to_call):
                    function_result = await function_to_call(**function_args)
                else:
                    function_result = function_to_call(**function_args)

                # Log any change in debug mode if applicable.
                if function_name == "debugmode":
                    print(f"[🛠 DEBUG MODE] New state: {'ON' if get_debug_mode() else 'OFF'}")

                if get_debug_mode():
                    print(f"[✅ FUNCTION SUCCESS] {function_name} returned: {json.dumps(function_result)}")

                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": function_call_id,
                    "content": json.dumps(function_result)
                })
            except Exception as e:
                if get_debug_mode():
                    print(f"{COLOR_RED}[❌ FUNCTION ERROR] {function_name}: {e}{COLOR_RESET}")
                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": function_call_id,
                    "content": json.dumps({"error": f"Execution failed: {str(e)}"})
                })

        # Append tool responses to the conversation and retry the OpenAI call.
        conversation_history.extend(tool_responses)
        continue

    if get_debug_mode():
        print("[🛑 EXITING] Finalizing response; no further function calls.")

# ------------------------------
# Conversation History Helpers
# ------------------------------
def add_user_input(user_input):
    """Adds a user message to the conversation history."""
    global conversation_history
    conversation_history.append({"role": "user", "content": user_input})

def display_startup_message():
    """Displays VORTEX's startup banner with ASCII art and version information."""
    COLOR_CYAN = "\033[96m"
    vortex_ascii = r"""
          __
  _(\    |@@|
 (__/\__ \--/ __
    \___|----|  |   __
        \ }}{{ /\ )_ / _\
        /\__/\ \__O (__
       (--/\--)    \__/
       _)(  )(_
      `---''---`
    """
    box_width = 45
    top_bottom_border = "═" * (box_width - 2)

    startup_text = f"""{COLOR_CYAN}
    ╔{top_bottom_border}╗ 
    ║ VORTEX: Wizard's Virtual Assistant        ║ 
    ║ Version: {VORTEX_VERSION}{' ' * (box_width - (12 + len(VORTEX_VERSION)))}║ 
    ╠{top_bottom_border}╣ 
    ║ Created by: {COLOR_GREEN}Wizard1{' ' * 23}{COLOR_GREEN}║ 
    ╚{top_bottom_border}╝{COLOR_RESET}"""

    print(COLOR_CYAN + vortex_ascii + COLOR_RESET)
    print(startup_text)
