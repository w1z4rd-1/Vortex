import openai
import json
import os
import asyncio
from dotenv import load_dotenv
import capabilities  # ✅ Import capabilities dynamically
from functions import set_debug_mode, get_debug_mode, retrieve_memory, read_vortex_code

VORTEX_VERSION = "Alpha"

# Load API key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)  # ✅ Ensure async client

# ANSI Escape Codes for Colors
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[96m"

def load_system_prompt():
    """Loads the system prompt from systemprompt.txt or defaults if the file is missing."""
    file_path = "systemprompt.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if content:
                return content
    return "You are VORTEX, a highly intelligent assistant."

conversation_history = [{"role": "system", "content": load_system_prompt()}]

import inspect  # ✅ Import to check if a function is async

async def call_openai():
    """Processes user input, retrieves relevant memories, executes functions, and expands capabilities if needed."""
    
    global conversation_history
    user_input = conversation_history[-1]["content"]

    if get_debug_mode():
        print(f"[🧠 MEMORY CHECK] Searching for memories related to: {user_input}")

    memories = retrieve_memory(user_input)

    if memories:
        memory_text = "\n".join(memories[:2])
        if get_debug_mode():
            print(f"[✅ MEMORY FOUND] Retrieved: {memory_text}")
        conversation_history.append({"role": "system", "content": f"Before answering, recall this stored information: {memory_text}"})
    else:
        if get_debug_mode():
            print(f"[❌ NO MEMORY FOUND] No relevant memories retrieved.")

    max_retries = 3  # ✅ Prevents infinite looping
    attempt = 0

    while attempt < max_retries:
        attempt += 1  # ✅ Count retries
        if get_debug_mode():
            print(f"[🔄 CALLING OPENAI] Attempt {attempt}/{max_retries}")

        function_schemas = capabilities.get_function_schemas() if capabilities.get_function_schemas() else None
        tool_choice_param = "auto" if function_schemas else None

        if get_debug_mode():
            print(f"[🔍 SCHEMA DEBUG] Using function schemas: {function_schemas}")

        # ✅ Add timeout to prevent indefinite hanging
        try:
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
            print("[❌ TIMEOUT ERROR] OpenAI API did not respond within 20 seconds.")
            return
        except Exception as e:
            print(f"[❌ API ERROR] {e}")
            return

        assistant_message = response.choices[0].message
        conversation_history.append(assistant_message)

        if get_debug_mode():
            print(f"[🤖 OPENAI RESPONSE] {assistant_message.content}")

        # ✅ Ensure the response is visible to the user
        if assistant_message.content:
            print(f"{COLOR_BLUE}[🤖 VORTEX]: {assistant_message.content}{COLOR_RESET}")
        elif assistant_message.tool_calls:
            if get_debug_mode():
                print(f"[🛠 TOOL CALL ONLY] OpenAI did not return a message, only tool calls.")
        else:
            print(f"{COLOR_RED}[❌ ERROR] OpenAI returned an empty response with no tool call!{COLOR_RESET}")

        # ✅ Exit if no tool calls are requested
        if not assistant_message.tool_calls:
            break  

        # ✅ Process tool calls
        tool_responses = []
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            function_call_id = tool_call.id

            if get_debug_mode():
                print(f"[🔄 CHECKING FUNCTION] ID: {tool_call.id} | Name: {function_name}")

            function_to_call = capabilities.get_function_registry().get(function_name)
            if not function_to_call:
                print(f"[❌ MISSING FUNCTION] '{function_name}' not found.")

                # ✅ Suggest similar function names
                similar_functions = [f for f in capabilities.get_function_registry().keys() if function_name.lower() in f]
                if similar_functions:
                    print(f"[💡 SUGGESTED FIX] Did you mean: {', '.join(similar_functions)}?")
                continue

            try:
                if get_debug_mode():
                    print(f"[🚀 EXECUTING] Running {function_name}({json.dumps(function_args)})")

                # ✅ Automatically await async functions
                if inspect.iscoroutinefunction(function_to_call):
                    function_result = await function_to_call(**function_args)
                else:
                    function_result = function_to_call(**function_args)

                # ✅ Ensure debug mode state change is logged
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
                    print(f"[❌ FUNCTION ERROR] {function_name}: {e}")
                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": function_call_id,
                    "content": json.dumps({"error": f"Execution failed: {str(e)}"})
                })

        # ✅ Store function results and retry OpenAI
        conversation_history.extend(tool_responses)
        continue  

    if get_debug_mode():
        print("[🛑 EXITING] No more function calls. Finalizing response...")


def add_user_input(user_input):
    """Adds user input to the conversation history."""
    global conversation_history
    conversation_history.append({"role": "user", "content": user_input})

def display_startup_message():
    """Displays the startup message for VORTEX with an ASCII banner and a highlighted acronym."""

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

    box_width = 45  # Compact box width for balance
    top_bottom_border = "═" * (box_width - 2)

    startup_text = f"""{COLOR_CYAN}
    ╔{top_bottom_border}╗ 
    ║ VORTEX: Wizard's Virtual Assistant        ║ 
    ║ Version: {VORTEX_VERSION}{" " * (box_width - (12 + len(VORTEX_VERSION)))}║ 
    ╠{top_bottom_border}╣ 
    ║ Created by: {COLOR_GREEN}Wizard1{" " * 23}{COLOR_GREEN}║ 
    ╚{top_bottom_border}╝{COLOR_RESET}"""

    print(COLOR_CYAN + vortex_ascii + COLOR_RESET)
    print(startup_text)
