# Powershell-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import os
import json
import tempfile
import subprocess
import time
from dotenv import load_dotenv
from src.Capabilities.debug_mode import get_debug_mode
from src.Boring.boring import log_debug_event
import requests

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
		log_debug_event(f"EXECUTING POWERSHELL: {command}")
		
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
    """Fetches user location details based on their public IP address using ip-api.com."""
    try:
        ip_response = requests.get("https://api64.ipify.org?format=json")
        ip_address = ip_response.json().get("ip")

        if not ip_address:
            return "Unable to retrieve IP address."

        geo_url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,region,regionName,city,zip,lat,lon,timezone,offset,mobile,query"
        geo_response = requests.get(geo_url)
        geo_data = geo_response.json()

        if geo_data.get("status") != "success":
            return f"Geolocation lookup failed: {geo_data.get('message', 'Unknown error')}"

        return {
            "ip": geo_data.get("query"),
            "city": geo_data.get("city"),
            "region": geo_data.get("regionName"),
            "country": geo_data.get("country"),
            "zip": geo_data.get("zip"),
            "timezone": geo_data.get("timezone"),
            "utc_offset": geo_data.get("offset"),
            "latitude": geo_data.get("lat"),
            "longitude": geo_data.get("lon"),
            "mobile_network": geo_data.get("mobile")
        }

    except Exception as e:
        return f"Error retrieving user location: {str(e)}"

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
		"description": "Retrieves information About the user bassed on their ip adress, including latatude and longitude",
		"parameters": {
			"type": "object",
			"properties": {},
			"required": []
		}
	}
}) 