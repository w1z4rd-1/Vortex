import openai
import json
import os
from dotenv import load_dotenv
from functions import function_registry, function_schemas
from functions import set_debug_mode, get_debug_mode

VORTEX_VERSION = "Alpha"

# Load API key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ANSI Escape Codes for Colors
COLOR_BLUE = "\033[94m"   # Light Blue (VORTEX Responses)
COLOR_GREEN = "\033[92m"  # Hacker Green (Debug Messages)
COLOR_RED = "\033[91m"    # Red (Errors)
COLOR_RESET = "\033[0m"   # Reset Color
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[96m"

def load_system_prompt():
    """Loads the system prompt from systemprompt.txt or defaults if the file is missing."""
    file_path = "systemprompt.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if content:
                return content  # Return the file content if it's not empty
    return "You are VORTEX, a highly intelligent assistant."

conversation_history = [
    {"role": "system", "content": load_system_prompt()}
]

def load_system_prompt():
    """Loads the system prompt from systemprompt.txt or defaults if the file is missing."""
    file_path = "systemprompt.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if content:
                return content  # Return the file content if it's not empty
    return "You are VORTEX, a highly intelligent assistant."

conversation_history = [
    {"role": "system", "content": load_system_prompt()}
]

async def call_openai():
    """Processes user input, executes functions, and returns results."""
    global conversation_history

    if get_debug_mode():
        print(f"{COLOR_GREEN}[🔄 STARTING call_openai()] Initial conversation history:{COLOR_RESET}")
        for i, msg in enumerate(conversation_history):
            print(f"{COLOR_YELLOW}[{i}] Type: {type(msg)} | Content: {msg}{COLOR_RESET}")

    while True:  # 🔄 Loop while handling function calls
        if get_debug_mode():
            print(f"{COLOR_GREEN}[🔄 CALLING OPENAI] Sending updated conversation history...{COLOR_RESET}")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=conversation_history,
            tools=function_schemas,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message
        conversation_history.append(assistant_message)

        if get_debug_mode():
            print(f"{COLOR_CYAN}[🤖 OPENAI RESPONSE] {COLOR_BLUE}{assistant_message.content}{COLOR_RESET}")

        # ✅ Check if OpenAI requests tool calls
        if assistant_message.tool_calls:
            tool_responses = []

            if get_debug_mode():
                print(f"{COLOR_GREEN}[🔧 TOOL CALL DETECTED] OpenAI requested {len(assistant_message.tool_calls)} function calls.{COLOR_RESET}")

            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                function_call_id = tool_call.id

                if get_debug_mode():
                    print(f"{COLOR_YELLOW}[🔄 CHECKING FUNCTION] ID: {tool_call.id} | Name: {function_name}{COLOR_RESET}")

                # Check if function exists
                function_to_call = function_registry.get(function_name)
                if not function_to_call:
                    print(f"{COLOR_RED}[❌ ERROR] Function not found: {function_name}{COLOR_RESET}")
                    continue

                try:
                    if get_debug_mode():
                        print(f"{COLOR_YELLOW}[🚀 EXECUTING] Running {function_name}({json.dumps(function_args)}){COLOR_RESET}")

                    # Special handling for debug mode toggle
                    if function_name == "debugmode":
                        enable = function_args.get("enable", None)
                        function_result = set_debug_mode(enable) if enable is not None else "❌ Missing 'enable' argument."
                    else:
                        function_result = function_to_call(**function_args)

                    if get_debug_mode():
                        print(f"{COLOR_GREEN}[✅ FUNCTION SUCCESS] {function_name} returned: {json.dumps(function_result)}{COLOR_RESET}")

                    tool_responses.append({
                        "role": "tool",
                        "tool_call_id": function_call_id,
                        "content": json.dumps(function_result)  # Convert result to JSON
                    })
                except Exception as e:
                    print(f"{COLOR_RED}[❌ FUNCTION ERROR] Failed to execute {function_name}: {e}{COLOR_RESET}")
                    tool_responses.append({
                        "role": "tool",
                        "tool_call_id": function_call_id,
                        "content": json.dumps({"error": f"Execution failed: {str(e)}"})
                    })

            # 🔍 DEBUG: Check conversation history before appending
            if get_debug_mode():
                print(f"{COLOR_YELLOW}[📜 HISTORY BEFORE APPEND] Last message: {conversation_history[-1] if conversation_history else 'Empty'}{COLOR_RESET}")

            # Store function results in history
            conversation_history.extend(tool_responses)

            # 🔍 DEBUG: Check conversation history after appending
            if get_debug_mode():
                print(f"{COLOR_GREEN}[📜 HISTORY AFTER APPEND] Last added message: {tool_responses[-1] if tool_responses else 'No tool responses'}{COLOR_RESET}")

            # 🚨 CALL OpenAI AGAIN TO GET FINAL RESPONSE
            continue  # Ensures OpenAI is re-called ONLY ONCE per function execution

        # 🛑 No more function calls → Break loop
        if get_debug_mode():
            print(f"{COLOR_GREEN}[🛑 EXITING] No more function calls. Finalizing response...{COLOR_RESET}")
        break  

    # 🏁 Final AI response after all tool calls
    print(f"{COLOR_CYAN}[🤖 VORTEX]: {COLOR_BLUE}{assistant_message.content}{COLOR_RESET}")






def add_user_input(user_input):
    """Adds user input to the conversation history."""
    conversation_history.append({"role": "user", "content": user_input})


def display_startup_message():
    """Displays the startup message for VORTEX with an ASCII banner and a highlighted acronym."""

    vortex_ascii = rf"""{COLOR_CYAN}
          __
  _(\    |@@|
 (__/\__ \--/ __
    \___|----|  |   __
        \ }}{{ /\ )_ / _\
        /\__/\ \__O (__
       (--/\--)    \__/
       _)(  )(_
      `---''---`
  {COLOR_RESET}"""

    box_width = 45  # Compact box width for balance
    top_bottom_border = "═" * (box_width - 2)

    # Highlighted VORTEX acronym with bold first letters
    vortex_acronym = [
        f"{COLOR_YELLOW}\033[1mV{COLOR_CYAN}oice      ",
        f"{COLOR_YELLOW}\033[1mO{COLOR_CYAN}perated   ",
        f"{COLOR_YELLOW}\033[1mR{COLOR_CYAN}esponsive ",
        f"{COLOR_YELLOW}\033[1mT{COLOR_CYAN}ask       ",
        f"{COLOR_YELLOW}\033[1mE{COLOR_CYAN}xecution  ",
        f"{COLOR_YELLOW}\033[1mX{COLOR_CYAN}pert      "
    ]

    # Startup text with the aligned acronym (keeping colors consistent)
    startup_text = f"""{COLOR_CYAN}
    ╔{top_bottom_border}╗ {vortex_acronym[0]}
    ║ VORTEX: Wizard's Virtual Secratary        ║ {vortex_acronym[1]}
    ║ Version: {VORTEX_VERSION}{" " * (box_width - (12 + len(VORTEX_VERSION)))}║ {vortex_acronym[2]}
    ╠{top_bottom_border}╣ {vortex_acronym[3]}
    ║ Created by: {COLOR_GREEN}Wizard1{" " * 23}{COLOR_GREEN}║ {vortex_acronym[4]}{COLOR_GREEN}
    ╠{top_bottom_border}╣ {vortex_acronym[5]}{COLOR_GREEN}
    ║ Future Plans:                             ║
    ║ - {COLOR_GREEN}TTS w/ Audio-Responsive Visuals{" " * (box_width - 36)}║
    ║ - {COLOR_GREEN}Integration with Additional APIs{" " * (box_width - 37)}║
    ║ - {COLOR_GREEN}Limited Command Line Access{" " * (box_width - 32)}║
    ╚{top_bottom_border}╝{COLOR_RESET}"""

    # Print everything together
    print(vortex_ascii)  # Print the ASCII art
    print(startup_text)  # Print the formatted startup text
