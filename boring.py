import openai
import json
import os
from dotenv import load_dotenv
from functions import function_registry, function_schemas
from functions import set_debug_mode, get_debug_mode

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

async def call_openai():
    """Processes user input, executes functions, and returns results."""
    global conversation_history

    # Call OpenAI with conversation history and available functions
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history,
        tools=function_schemas,  
        tool_choice="auto"
    )

    assistant_message = response.choices[0].message
    conversation_history.append(assistant_message)

    # If OpenAI calls a function
    if assistant_message.tool_calls:
        tool_responses = []

        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            function_call_id = tool_call.id

            # Check if function exists
            function_to_call = function_registry.get(function_name)
            if not function_to_call:
                if get_debug_mode():
                    print(f"{COLOR_RED}\n[❌ ERROR] Function not found: {function_name}{COLOR_RESET}")
                continue

            try:
                # Log function execution if debug mode is enabled
                if get_debug_mode():
                    print(f"{COLOR_GREEN}\n[🔧 RUNNING FUNCTION] {function_name}({json.dumps(function_args)}){COLOR_RESET}")

                # Execute function
                function_result = function_to_call(**function_args)

                # Log success if debug mode is enabled
                if get_debug_mode():
                    print(f"{COLOR_YELLOW}[✅ FUNCTION SUCCESS] {function_name} returned: {json.dumps(function_result)}{COLOR_RESET}")

                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": function_call_id,
                    "content": json.dumps(function_result)  # Convert result to JSON
                })

            except Exception as e:
                if get_debug_mode():
                    print(f"{COLOR_RED}[❌ FUNCTION ERROR] Failed to execute {function_name}: {e}{COLOR_RESET}")
                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": function_call_id,
                    "content": json.dumps({"error": f"Execution failed: {str(e)}"})
                })

        # Append function results to conversation history
        conversation_history.extend(tool_responses)

        # Re-run OpenAI to process the function results
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_history,
            tools=function_schemas,
            tool_choice="none"
        )

        final_message = response.choices[0].message
        conversation_history.append(final_message)
        print(f"{COLOR_CYAN}[🤖 VORTEX]: {COLOR_BLUE}{final_message.content}{COLOR_RESET}")

    else:
        print(f"{COLOR_CYAN}[🤖 VORTEX]: {COLOR_BLUE}{assistant_message.content}{COLOR_RESET}")


def add_user_input(user_input):
    """Adds user input to the conversation history."""
    conversation_history.append({"role": "user", "content": user_input})

def display_startup_message():
    """Displays the startup message for VORTEX with an ASCII banner."""
    clear_console()
    
    vortex_ascii = f"""{COLOR_CYAN}
       __      __  _____ _______  ________  __
      /  \\    /  \\/  _  \\\\_  __ \\/  ___/  |/ /
      \\   \\/\\/   /  /_\\  \\|  | \\/\\___ \\|    < 
       \\        /|  | |  ||  |  /____  >__|_ \\
        \\__/\\__/ \\__| |__/ |__|       \\/____/
    {COLOR_RESET}"""

    box_width = 65  # Adjust width dynamically if needed
    top_bottom_border = "═" * (box_width - 2)

    startup_text = f"""{COLOR_CYAN}
    ╔{top_bottom_border}╗
    ║ {COLOR_YELLOW}VORTEX - Voice-Operated Omniscient Responsive Task Execution eXpert {" " * (box_width - 55)}║
    ║ {COLOR_YELLOW}Version: {VORTEX_VERSION} {" " * (box_width - (12 + len(VORTEX_VERSION)))}║
    ╠{top_bottom_border}╣
    ║ {COLOR_YELLOW}Created by: {COLOR_GREEN}Wizard1 {" " * (box_width - 32)}║
    ╠{top_bottom_border}╣
    ║ {COLOR_YELLOW}Future Plans: {" " * (box_width - 16)}║
    ║ - {COLOR_GREEN}TTS w/ Audio-Responsive Visuals {" " * (box_width - 35)}║
    ║ - {COLOR_GREEN}Integration with Additional APIs {" " * (box_width - 37)}║
    ║ - {COLOR_GREEN}Limited Command Line Access {" " * (box_width - 33)}║
    ╚{top_bottom_border}╝
    {COLOR_RESET}"""

    print(vortex_ascii)  # Print the ASCII VORTEX logo first
    print(startup_text)
