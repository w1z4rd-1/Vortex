import openai
import json
import os
import asyncio
import inspect
from dotenv import load_dotenv
from src.Boring.capabilities import get_function_registry, get_function_schemas
# Import dynamic capabilities and helper functions.
import src.Boring.capabilities as capabilities  # This module should provide:
					 # - get_function_schemas(): returns function schemas (or None if none)
					 # - get_function_registry(): returns a dict mapping function names to callables.
from src.Capabilities.local.memory import retrieve_memory
from src.Capabilities.local.system import read_vortex_code
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode
#from display import display
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
	It retrieves relevant memories, processes function calls, and updates
	the conversation history with the assistant's response.
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
		conversation_history.append({
			"role": "system",
			"content": f"Before answering, remember this: {memory_text}"
		})
	else:
		if get_debug_mode():
			print("[❌ NO MEMORY FOUND] No relevant memories retrieved.")

	max_retries = 10  # Prevent infinite loops
	attempt = 0

	while attempt < max_retries:
		attempt += 1
		if get_debug_mode():
			print(f"[🔄 CALLING OPENAI] Attempt {attempt}/{max_retries}")

		function_schemas = get_function_schemas() if get_function_schemas() else None
		tool_choice_param = "auto" if function_schemas else None

		# Add 'type': 'function' to each schema if missing
		if function_schemas:
			for schema in function_schemas:
				if 'type' not in schema:
					schema['type'] = 'function'

		try:
			response = await asyncio.wait_for(
				client.chat.completions.create(
					model="gpt-4o",  # ✅ Switched to GPT-4o for better function handling
					messages=conversation_history,
					tools=function_schemas,
					tool_choice=tool_choice_param,
				),
				timeout=60
			)
		except asyncio.TimeoutError:
			print("[❌ TIMEOUT ERROR] OpenAI API did not respond within 60 seconds.")
			return "I'm sorry, but I encountered a timeout error."
		except Exception as e:
			print(f"[❌ API ERROR] {e}")
			return "I'm sorry, but I encountered an API error."

		assistant_message = response.choices[0].message
		conversation_history.append(assistant_message)

		if get_debug_mode():
			print(f"[🤖 OPENAI RESPONSE] {assistant_message.content}")

		# ✅ Ensure function calls get a response
		if assistant_message.tool_calls:
			tool_responses = []
			for tool_call in assistant_message.tool_calls:
				function_name = tool_call.function.name
				function_args = json.loads(tool_call.function.arguments)
				function_call_id = tool_call.id

				if get_debug_mode():
					print(f"[🛠 TOOL CALL DETECTED] Function: {function_name} | Args: {function_args}")

				function_to_call = get_function_registry().get(function_name)
				if not function_to_call:
					print(f"[❌ MISSING FUNCTION] '{function_name}' not found.")
					continue

				try:
					# Special safety check for restart function (keep this safety feature)
					if function_name == "restart_vortex":
						print(f"{COLOR_RED}[⚠️ WARNING] Refusing automatic restart from API function call{COLOR_RESET}")
						tool_responses.append({
							"role": "tool",
							"tool_call_id": function_call_id,
							"content": json.dumps({"error": "Automatic restart from API call is not allowed for safety reasons. Please restart manually if needed."})
						})
						continue
						
					if inspect.iscoroutinefunction(function_to_call):
						function_result = await function_to_call(**function_args)
					else:
						function_result = function_to_call(**function_args)

					if get_debug_mode():
						print(f"[✅ FUNCTION SUCCESS] {function_name} returned: {json.dumps(function_result)}")

					tool_responses.append({
						"role": "tool",
						"tool_call_id": function_call_id,
						"content": json.dumps(function_result)
					})

				except Exception as e:
					print(f"[❌ FUNCTION ERROR] {function_name}: {e}")
					tool_responses.append({
						"role": "tool",
						"tool_call_id": function_call_id,
						"content": json.dumps({"error": f"Execution failed: {str(e)}"})
					})

			# ✅ Append tool responses and RESEND to OpenAI
			conversation_history.extend(tool_responses)
			continue  # ✅ Retry OpenAI with updated history

		# ✅ If response has content, return it
		if assistant_message.content:
			print(f"{COLOR_BLUE}[🤖 VORTEX]: {assistant_message.content}{COLOR_RESET}")
			return assistant_message.content

		# 🔴 If no message and no tool call, something went wrong
		print("[❌ ERROR] OpenAI returned an empty response!")
		return "I'm sorry, I couldn't process that request."

	if get_debug_mode():
		print("[🛑 EXITING] Finalizing response; no further function calls.")
	return "I'm sorry, but I encountered an issue processing your request."

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