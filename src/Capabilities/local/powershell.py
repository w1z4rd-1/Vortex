# Powershell-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import os
import json
import tempfile
import subprocess
import time
from dotenv import load_dotenv
from src.Capabilities.debug_mode import get_debug_mode

# Constants
JSON_PATH = "powershell.json"
VORTEX_TEMP_DIR = os.path.join(tempfile.gettempdir(), "VORTEX")

if not os.path.exists(VORTEX_TEMP_DIR):
	os.makedirs(VORTEX_TEMP_DIR)

# Load powershell permissions
with open(JSON_PATH, "r", encoding="utf-8") as f:
	powershell_permissions = json.load(f)

blacklisted = set(powershell_permissions["blacklisted"])
ask_first = set(powershell_permissions["ask_first"])

def powershell(permission: bool = False, command: str = "", returnoutput: bool = True) -> str:
	"""
	Execute a PowerShell command if it's permitted or the user has given explicit permission.
	
	Parameters:
	- permission (bool): Whether the user has given explicit permission
	- command (str): The PowerShell command to execute
	- returnoutput (bool): Whether to return the command output
	
	Returns:
	- str: Command output if returnoutput is True, otherwise a status message
	"""
	
	if not command.strip():
		return "❌ No command specified."
	
	# Check for blacklisted commands
	if any(bad_cmd in command.lower() for bad_cmd in blacklisted):
		return "❌ Command contains blacklisted operations."
	
	# Check if command requires permission
	needs_permission = any(cmd in command.lower() for cmd in ask_first)
	
	if needs_permission and not permission:
		return f"⚠️ This command requires explicit permission: {command}"
	
	try:
		if get_debug_mode():
			print(f"[EXECUTING POWERSHELL] {command}")
		
		# Execute the PowerShell command
		process = subprocess.Popen(
			["powershell", "-Command", command],
			stdout=subprocess.PIPE, 
			stderr=subprocess.PIPE,
			universal_newlines=True
		)
		
		stdout, stderr = process.communicate()
		
		if stderr:
			return f"❌ Error: {stderr.strip()}"
		
		if returnoutput:
			return stdout.strip()
		else:
			return "✅ Command executed successfully."
	
	except Exception as e:
		return f"❌ Error executing command: {e}"

def get_user_info():
	"""Retrieves information about the current user and system."""
	try:
		# Get username
		username = powershell(True, "echo $env:USERNAME")
		
		# Get computer name
		computer_name = powershell(True, "echo $env:COMPUTERNAME")
		
		# Get Windows version
		windows_version = powershell(True, "(Get-WmiObject -class Win32_OperatingSystem).Caption")
		
		# Get current directory
		current_dir = powershell(True, "Get-Location | Select-Object -ExpandProperty Path")
		
		# Get system uptime
		uptime_script = "((Get-Date) - (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime).ToString('dd\\.hh\\:mm\\:ss')"
		system_uptime = powershell(True, uptime_script)
		
		# Format the information
		user_info = f"""
		✅ System Information:
		👤 Username: {username}
		💻 Computer Name: {computer_name}
		🏠 Current Directory: {current_dir}
		🖥️ Windows Version: {windows_version}
		⏱️ System Uptime: {system_uptime}
		"""
		
		return user_info.strip()
	
	except Exception as e:
		return f"❌ Error retrieving user information: {e}"

# Register functions and schemas
capabilities.register_function_in_registry("powershell", powershell)
capabilities.register_function_in_registry("get_user_info", get_user_info)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "powershell",
		"description": "Execute a PowerShell command if permitted.",
		"parameters": {
			"type": "object",
			"properties": {
				"permission": {
					"type": "boolean",
					"description": "Whether the user has given explicit permission for this command."
				},
				"command": {
					"type": "string",
					"description": "The PowerShell command to execute."
				},
				"returnoutput": {
					"type": "boolean",
					"description": "Whether to return the command output (default: True)."
				}
			},
			"required": ["command"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_user_info",
		"description": "Retrieves information about the current user and system.",
		"parameters": {
			"type": "object",
			"properties": {},
			"required": []
		}
	}
}) 