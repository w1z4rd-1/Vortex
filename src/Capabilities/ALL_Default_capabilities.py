import requests
from datetime import datetime, timedelta, timezone
from src.Google.auth import authorize
from googleapiclient.discovery import build
import subprocess
import os
import importlib
from openai import OpenAI
import sounddevice as sd
import io
from pydub import AudioSegment
from src.Capabilities.debug_mode import get_debug_mode
import tempfile
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode
import glob
import ctypes
from src.Google.auth import authorize
from ctypes import wintypes
import markdown
import webbrowser
import wikipediaapi
from email.mime.text import MIMEText
from googleapiclient.discovery import build
import re
from dotenv import load_dotenv
import openai
import numpy as np
import faiss

import codecs
import json
import sys
import time

import asyncio
import src.Boring.capabilities as capabilities
import base64
import googleapiclient.errors
wiki_wiki = wikipediaapi.Wikipedia(user_agent="VORTEX", language="en")
MEMORY_FILE = "memory.json"
TOKEN_PATH = "token.json"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[96m"
load_dotenv()
registry = capabilities.get_function_registry()
schemas = capabilities.get_function_schemas()
GOOGLE_SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY")
GOOGLE_SEARCH_CSE_ID = os.getenv("GOOGLE_SEARCH_CSE_ID")
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # Add this at the top
JSON_PATH = "powershell.json"
VORTEX_TEMP_DIR = os.path.join(tempfile.gettempdir(), "VORTEX")
if not os.path.exists(VORTEX_TEMP_DIR):
	os.makedirs(VORTEX_TEMP_DIR)
OPENAI_MODEL = "text-embedding-3-small"
with open(JSON_PATH, "r", encoding="utf-8") as f:
	powershell_permissions = json.load(f)

blacklisted = set(powershell_permissions["blacklisted"])
ask_first = set(powershell_permissions["ask_first"])
TEMP_DIR = os.path.join(os.getenv("TEMP", "/tmp"), "VORTEX")
os.makedirs(TEMP_DIR, exist_ok=True)  # Ensure the directory exists
TEMP_IMAGE_PATH = os.path.join(TEMP_DIR, "screenshot.png")  # Path for saving screenshots
# Debug mode function

CAPABILITIES_FILE = "capabilities.py"

def retrieve_project_memory(query: str):
	"""Finds relevant memory related to ongoing projects."""
	project_memories = retrieve_memory(query) or []
	created_functions = retrieve_memory("created functions") or []
	return project_memories + created_functions  # ✅ Merge both for better context


import src.Boring.capabilities as capabilities

def delete_capability(capability_name_or_file: str, get_function_registry):
	"""
	Deletes a capability by name or by file, ensuring no external files are affected.
	After removal, it reinitializes capabilities to ensure consistency.

	Parameters:
		capability_name_or_file (str): The name of the capability or the filename to delete.
		get_function_registry (callable): Function to retrieve the current function registry.
	"""
	CAPABILITIES_DIR = "capabilities"
	DEFAULT_CAPABILITIES_FILE = "all_default_capabilities.py"

	# Validate and ensure we’re only working within the capabilities folder
	file_path = os.path.join(CAPABILITIES_DIR, capability_name_or_file)
	if capability_name_or_file == DEFAULT_CAPABILITIES_FILE or not os.path.commonpath([os.path.abspath(file_path), os.path.abspath(CAPABILITIES_DIR)]) == os.path.abspath(CAPABILITIES_DIR):
		return f"❌ Error: Cannot delete '{capability_name_or_file}' because it is not allowed or is outside the capabilities folder."

	# Check if it's a registered capability
	registry = get_function_registry()
	if capability_name_or_file in registry:
		del registry[capability_name_or_file]  # Remove from registry

	# If it’s a file, attempt to delete
	if os.path.isfile(file_path):
		try:
			os.remove(file_path)
			return f"✅ Deleted capability file: {file_path}"
		except Exception as e:
			return f"❌ Error deleting capability file: {e}"

	return f"❌ Could not find or delete: {capability_name_or_file}"
def add_new_capability(function_name: str, function_code: str):
	"""
	Adds a new capability function to its own file in src/Capabilities/ and registers it dynamically.
	
	This function ensures:
	- Required imports are present at the top of the file.
	- Error handling is included in the function.
	- A valid schema and function registration are included at the bottom.
	
	Parameters:
	- function_name (str): The name of the function.
	- function_code (str): The full function definition.
	"""
	
	# Ensure required imports are included
	required_imports = (
		"from src.Capabilities.debug_mode import get_debug_mode\n"
		"import src.Boring.capabilities as capabilities\n\n"
	)
	
	if not function_code.startswith("from src.Boring.functions import get_debug_mode"):
		function_code = required_imports + function_code
	
	# Ensure the function has try/except error handling
	if "try:" not in function_code or "except" not in function_code:
		function_body_match = re.search(r"def [\w_]+\(.*\):\s*(\n\s+.+)+", function_code)
		if function_body_match:
			function_body = function_body_match.group(0)
			indented_body = "\n".join(["    " + line for line in function_body.split("\n")])
			function_code = function_code.replace(function_body, f"try:\n{indented_body}\nexcept Exception as e:\n    return {{'error': str(e)}}")
	
	# Ensure function registration and schema exist
	schema_pattern = r"capabilities\.register_function_schema\("
	registry_pattern = r"capabilities\.register_function_in_registry\("
	
	if not re.search(schema_pattern, function_code) or not re.search(registry_pattern, function_code):
		return "❌ Error: Function is missing schema or registration. Read the guidelines and try again."
	
	# Ensure Capabilities directory exists
	capabilities_dir = os.path.join("src", "Capabilities")
	os.makedirs(capabilities_dir, exist_ok=True)
	
	capability_file = os.path.join(capabilities_dir, f"{function_name}.py")
	
	# Check if function file already exists
	if os.path.exists(capability_file):
		return f"⚠️ SKIPPED: Function file '{function_name}.py' already exists in src/Capabilities/."
	
	# Write the function code to its own file
	with open(capability_file, "w", encoding="utf-8") as f:
		f.write(f"# === Auto-Generated Function ===\n{function_code}\n")
	
	print(f"[✅ SUCCESS] Function '{function_name}' added to src/Capabilities/{function_name}.py.")
	
	# Load and register the function dynamically
	try:
		spec = importlib.util.spec_from_file_location(function_name, capability_file)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		
		# Retrieve function object dynamically
		func_obj = getattr(module, function_name, None)
		if callable(func_obj):
			capabilities.register_function_in_registry(function_name, func_obj)
			print(f"[✅ REGISTERED] Function '{function_name}' in the registry.")
		else:
			return f"[❌ ERROR] Function '{function_name}' not found in {capability_file}."
	
	except Exception as e:
		return f"[❌ ERROR] Failed to dynamically load function '{function_name}': {e}"
	
	return f"[✅ COMPLETED] Function '{function_name}' added and registered successfully!"

def restart_vortex():
	"""Restarts VORTEX to apply new capabilities and reload memory."""
	print("[🔄 RESTARTING VORTEX...]")

	# ✅ Give the user time to see the restart message
	time.sleep(2)

	# ✅ Restart the Python process
	os.execl(sys.executable, sys.executable, *sys.argv)
import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Load API Key
load_dotenv()
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")

def query_wolfram_alpha(query: str) -> dict:
	"""
	Queries Wolfram Alpha's Full Results API and returns formatted results.

	Parameters:
	- query (str): The question or mathematical expression to solve.

	Returns:
	- dict: Structured response with results from Wolfram Alpha.
	"""
	if not WOLFRAM_APP_ID:
		return {"error": "Wolfram Alpha API key is missing."}

	url = "http://api.wolframalpha.com/v2/query"
	params = {
		"input": query,
		"format": "plaintext",
		"output": "XML",
		"appid": WOLFRAM_APP_ID
	}

	try:
		response = requests.get(url, params=params)
		response.raise_for_status()
		root = ET.fromstring(response.content)

		results = []

		for pod in root.findall(".//pod"):
			title = pod.get("title")
			plaintext = pod.find(".//plaintext")
			if plaintext is not None and plaintext.text:
				results.append(f"**{title}**: {plaintext.text}")

		if not results:
			return {"error": "No relevant information found."}

		return {"result": "\n".join(results)}

	except requests.exceptions.RequestException as e:
		return {"error": f"API request failed: {str(e)}"}





def read_vortex_code(filename: str, max_file_size: int = 5000):
	"""Reads and returns the contents of any file in the src directory or its subdirectories.
	Also displays a directory tree of the src folder."""
	
	def generate_tree(directory, prefix=""):
		tree = ""
		entries = sorted(os.listdir(directory))[:50]  # Limit number of entries
		for index, entry in enumerate(entries):
			path = os.path.join(directory, entry)
			connector = "|-- " if index != len(entries) - 1 else "\-- "
			tree += prefix + connector + entry + "\n"
			if os.path.isdir(path):
				tree += generate_tree(path, prefix + "|   ")
		return tree
	
	src_dir = os.path.join(os.getcwd(), "src")
	if not os.path.exists(src_dir):
		return f"❌ Error: 'src' directory does not exist."
	
	directory_tree = f"Source Directory Structure:\n{generate_tree(src_dir)}"
	
	full_path = os.path.join(src_dir, filename)
	if not os.path.exists(full_path):
		return f"❌ Error: '{filename}' does not exist in the src directory.\n\n" + directory_tree
	
	try:
		with codecs.open(full_path, "r", encoding="utf-8", errors="ignore") as f:
			file_contents = f.read(max_file_size)  # Limit file size to avoid excessive tokens
		truncated_notice = "\n\n⚠️ File content truncated to avoid token overflow." if os.path.getsize(full_path) > max_file_size else ""
		return f"{directory_tree}\n\n--- File Contents ({filename}) ---\n{file_contents}{truncated_notice}"
	except Exception as e:
		return f"❌ Error reading {filename}: {e}\n\n" + directory_tree


def powershell(permission: bool = False, command: str = "", returnoutput: bool = True) -> str:
	"""
	Executes a PowerShell command with permission handling.
	
	Parameters:
	- permission (bool, optional): User's explicit permission (default: False).
	- command (str): The PowerShell command to execute.
	- returnoutput (bool, optional): If True, captures output; if False, starts a new PowerShell window.

	Returns:
	- str: Command output or execution status.
	"""
	if not command.strip():
		return "❌ No command provided."

	# ✅ Extract base command
	base_command = command.split()[0]

	# ✅ Block blacklisted commands
	if base_command in blacklisted:
		return f"❌ Command '{base_command}' is blacklisted and cannot be executed."

	# ✅ Ask for permission if required
	if base_command in ask_first and not permission:
		return "⛔ Command not executed, ask the user for permission."

	try:
		if returnoutput:
			# ✅ Capture PowerShell command output
			result = subprocess.run(
				["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
				capture_output=True, text=True, check=True
			)
			return result.stdout.strip() if result.stdout else "✅ Command executed successfully."
		else:
			# ✅ Launch PowerShell in a new window (non-blocking)
			ps_script = f"Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -Command \"{command}\"' -WindowStyle Normal"
			
			# ✅ Start process and return immediately
			subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], shell=True)
			
			return "✅ Command started in a new PowerShell window."
	
	except subprocess.CalledProcessError as e:
		return f"❌ PowerShell Error: {e.stderr.strip() if e.stderr else str(e)}"
	except Exception as e:
		return f"❌ Unexpected Error: {str(e)}"
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
def get_time():
	"""Returns the current time in the user's timezone in multiple formats."""
	try:
		ip_response = requests.get("https://api64.ipify.org?format=json")
		ip_address = ip_response.json().get("ip")

		if not ip_address:
			return {"error": "Unable to retrieve IP address."}

		geo_url = f"http://ip-api.com/json/{ip_address}?fields=offset,timezone"
		geo_response = requests.get(geo_url)
		geo_data = geo_response.json()

		if "offset" not in geo_data or "timezone" not in geo_data:
			return {"error": "Unable to retrieve timezone information."}

		utc_offset_hours = geo_data["offset"] / 3600
		timezone_name = geo_data["timezone"]
		utc_now = datetime.now(timezone.utc)
		user_time = utc_now + timedelta(hours=utc_offset_hours)

		return {
			"iso_timestamp": user_time.strftime("%Y-%m-%dT%H:%M:%S") + f"{int(utc_offset_hours):+03d}:00",
			"human_readable": user_time.strftime("%A, %B %d, %Y at %I:%M %p"),
			"day_of_week": user_time.strftime("%A"),
			"timezone": timezone_name
		}

	except Exception as e:
		return {"error": f"Failed to retrieve time: {str(e)}"}
def open_link(url: str):
	
	"""Opens a specified URL in the default web browser. AI must not generate fake URLs."""
	if url.startswith("http://") or url.startswith("https://"):
		webbrowser.open(url)
		return f"✅ Opened: {url}"
	return "❌ Invalid or missing URL. AI must not guess links."
def create_event(summary: str, start_time: str, duration: int = 60) -> dict:
	"""
	Creates a Google Calendar event.

	Parameters:
	- summary (str): Title of the event.
	- start_time (str): ISO 8601 format (YYYY-MM-DDTHH:MM:SS).
	- duration (int): Duration in minutes (default is 60).

	Returns:
	- dict: Event details including Event ID.
	"""
	try:
		creds = authorize()
		service = build("calendar", "v3", credentials=creds)

		start_datetime = datetime.fromisoformat(start_time)
		end_datetime = start_datetime + timedelta(minutes=duration)

		event = {
			"summary": summary,
			"start": {"dateTime": start_datetime.isoformat(), "timeZone": "UTC"},
			"end": {"dateTime": end_datetime.isoformat(), "timeZone": "UTC"},
		}

		event_result = service.events().insert(calendarId="primary", body=event).execute()
		return {
			"message": f"✅ Event '{summary}' created successfully!",
			"event_id": event_result.get("id"),
			"start_time": start_datetime.strftime('%Y-%m-%d %H:%M UTC'),
		}

	except Exception as e:
		return {"error": f"❌ Error creating event: {e}"}
# 🚀 ------------------
# Launch a Program
# --------------------
last_multiple_matches = {}
def clarify_and_launch(clarified_name: str):
	"""
	Launches a program if the user clarifies their choice after multiple matches were found.
	"""
	global last_multiple_matches

	if not last_multiple_matches:
		return "⚠️ No previous ambiguous matches found. Try specifying the program again."

	# Find clarified match
	selected_path = last_multiple_matches.get(clarified_name)
	if selected_path:
		subprocess.run(["cmd.exe", "/c", "start", "", selected_path], shell=True)
		last_multiple_matches = {}  # Clear stored matches
		return f"✅ Launched: {clarified_name}"
	
	return f"❌ '{clarified_name}' not found in the previous list. Try again."
def launch_shortcut(program_name: str):
	"""
	Launches a program by name, using the Start Menu shortcuts or a custom shortcut path.
	"""
	shortcut_path = get_shortcut_path(program_name)

	# If multiple matches were found earlier, handle the response properly
	if isinstance(shortcut_path, list):
		return f"⚠️ Multiple matches found: {shortcut_path}"

	# If shortcut path is found, launch it
	if shortcut_path and isinstance(shortcut_path, str):
		try:
			subprocess.run(["cmd.exe", "/c", "start", "", shortcut_path], shell=True)
			return f"✅ Launched: {program_name}"
		except Exception as e:
			return f"❌ Failed to launch {program_name}: {str(e)}"
	
	return f"❌ No valid shortcut found for '{program_name}'."
START_MENU_PATH = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
# Custom shortcut file (user-defined programs)
CUSTOM_SHORTCUTS_FILE = "custom_shortcuts.txt"
def get_shortcut_path(shortcut_name):
	"""
	Given a shortcut name, returns the full path of the shortcut.
	"""
	possible_dirs = [
		os.path.join(os.getenv("PROGRAMDATA"), "Microsoft\\Windows\\Start Menu\\Programs"),
		os.path.join(os.getenv("APPDATA"), "Microsoft\\Windows\\Start Menu\\Programs"),
		os.path.join(os.path.expanduser("~"), "Desktop"),
		os.path.join(os.path.expanduser("~"), "Downloads"),
	]

	for directory in possible_dirs:
		if os.path.exists(directory):
			for shortcut in glob.glob(os.path.join(directory, "**", "*.lnk"), recursive=True):
				if os.path.splitext(os.path.basename(shortcut))[0].lower() == shortcut_name.lower():
					return shortcut  # Return the first match

	return "❌ Shortcut not found."

# Windows Known Folder GUIDs
FOLDERID_Desktop = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDERID_Downloads = "{374DE290-123F-4565-9164-39C4925E467B}"

def get_known_folder(folder_id):
	"""Retrieves the actual path of a Windows Known Folder using its GUID."""
	SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
	SHGetKnownFolderPath.argtypes = [
		wintypes.LPCWSTR, wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)
	]
	SHGetKnownFolderPath.restype = ctypes.c_long  # Fixed: Use c_long instead of HRESULT

	path_ptr = ctypes.c_wchar_p()
	if SHGetKnownFolderPath(folder_id, 0, None, ctypes.byref(path_ptr)) == 0:
		return path_ptr.value
	return None
def youtube_search(query: str) -> str:
	"""
	Searches YouTube for a specific query and opens the results in a browser.

	Parameters:
	- query (str): The search query for YouTube.

	Returns:
	- str: Success message.
	"""
	if not query.strip():
		return "❌ No search query provided."
	
	sanitized_query = re.sub(r"[^\w\s]", "", query).replace(" ", "+")
	search_url = f"https://www.youtube.com/results?search_query={sanitized_query}"
	
	webbrowser.open(search_url)
	return f"✅ Opened YouTube search for: {query}"
def modrinth_search(query: str) -> str:
	"""
	Searches Modrinth for Minecraft mods based on the given query.

	Parameters:
	- query (str): The search query for Modrinth.

	Returns:
	- str: Success message.
	"""
	if not query.strip():
		return "❌ No search query provided."

	sanitized_query = re.sub(r"[^\w\s]", "", query).replace(" ", "+")
	search_url = f"https://modrinth.com/mods?q={sanitized_query}&f=categories:utility&f=categories:optimization&g=categories:fabric&e=client"
	
	webbrowser.open(search_url)
	return f"✅ Opened Modrinth search for: {query}"
def get_shortcuts():
	"""
	Retrieves all program shortcuts from the Start Menu, Desktop, and Downloads.
	Returns a list of shortcut names **only** (without file paths).
	"""
	shortcut_paths = []
	start_menu_paths = [
		os.path.join(os.getenv("PROGRAMDATA"), "Microsoft\\Windows\\Start Menu\\Programs"),
		os.path.join(os.getenv("APPDATA"), "Microsoft\\Windows\\Start Menu\\Programs"),
	]
	user_dirs = [
		os.path.join(os.path.expanduser("~"), "Desktop"),
		os.path.join(os.path.expanduser("~"), "Downloads"),
	]

	# Search all defined directories for shortcuts
	for directory in start_menu_paths + user_dirs:
		if os.path.exists(directory):
			for shortcut in glob.glob(os.path.join(directory, "**", "*.lnk"), recursive=True):
				shortcut_name = os.path.splitext(os.path.basename(shortcut))[0]
				shortcut_paths.append(shortcut_name)

	return shortcut_paths  # Only return names, not paths
def list_events(max_results=10, time_min=None, time_max=None, order_by="startTime"):
	"""
	Retrieves a list of upcoming events from Google Calendar.

	Parameters:
	- max_results (int): Maximum number of events to retrieve (default: 10).
	- time_min (str): ISO formatted start time filter (default: now).
	- time_max (str): ISO formatted end time filter.
	- order_by (str): Sort order (default: 'startTime').

	Returns:
	- list: List of event details including Event ID, summary, and start time.
	"""
	try:
		creds = authorize()
		service = build("calendar", "v3", credentials=creds)

		if not time_min:
			time_min = datetime.utcnow().isoformat() + "Z"

		events_result = service.events().list(
			calendarId="primary",
			timeMin=time_min,
			timeMax=time_max,
			maxResults=max_results,
			singleEvents=True,
			orderBy=order_by
		).execute()

		events = events_result.get("items", [])

		if not events:
			return "📅 No upcoming events found."

		event_list = []
		for event in events:
			event_id = event.get("id")
			event_summary = event.get("summary", "No Title")
			start = event["start"].get("dateTime", event["start"].get("date"))
			event_list.append({"event_id": event_id, "summary": event_summary, "start_time": start})

		return event_list

	except Exception as e:
		return {"error": f"❌ Failed to list events: {str(e)}"}
	
import requests
from datetime import datetime

def get_weather_forecast(latitude: float, longitude: float, forecast_type: str, timezone="auto"):
	"""
	Fetches a weather forecast from the Open-Meteo API.

	Parameters:
	- latitude (float): Geographical latitude.
	- longitude (float): Geographical longitude.
	- forecast_type (str): "day" for daily forecast, "week" for today's hourly forecast.
	- timezone (str): Timezone setting, default is "auto".

	Returns:
	- dict: Weather forecast data or an error message.
	"""

	base_url = "https://api.open-meteo.com/v1/forecast"
	today_date = datetime.utcnow().strftime("%Y-%m-%d")

	# Configure query parameters based on forecast type
	if forecast_type == "day":
		params = {
			"latitude": latitude,
			"longitude": longitude,
			"daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
			"timezone": timezone
		}
	elif forecast_type == "week":
		params = {
			"latitude": latitude,
			"longitude": longitude,
			"hourly": "temperature_2m,precipitation,wind_speed_10m,weather_code",
			"forecast_days": 7,
			"timezone": timezone
		}
	else:
		return {"error": "Invalid forecast_type. Choose 'day' or 'week'."}

	try:
		response = requests.get(base_url, params=params)
		response.raise_for_status()
		data = response.json()

		# Process daily forecast
		if forecast_type == "day":
			forecast = data.get("daily", {})
			human_readable = f"🌡️ High: {forecast['temperature_2m_max'][0]}°C | ❄️ Low: {forecast['temperature_2m_min'][0]}°C | ☔ Rain: {forecast['precipitation_sum'][0]}mm"
			return {
				"location": {"latitude": latitude, "longitude": longitude},
				"timezone": data.get("timezone"),
				"summary": human_readable,
				"daily_forecast": forecast
			}

		# Process weekly forecast but return only today's data
		elif forecast_type == "week":
			hourly_forecast = data.get("hourly", {})
			times = hourly_forecast.get("time", [])

			today_indices = [i for i, time in enumerate(times) if time.startswith(today_date)]

			# Extract only today's hourly data
			filtered_forecast = {
				"time": [hourly_forecast["time"][i] for i in today_indices],
				"temperature_2m": [hourly_forecast["temperature_2m"][i] for i in today_indices],
				"precipitation": [hourly_forecast["precipitation"][i] for i in today_indices],
				"wind_speed_10m": [hourly_forecast["wind_speed_10m"][i] for i in today_indices],
				"weather_code": [hourly_forecast["weather_code"][i] for i in today_indices]
			}

			# Generate human-readable summary
			max_temp = max(filtered_forecast["temperature_2m"])
			min_temp = min(filtered_forecast["temperature_2m"])
			max_wind = max(filtered_forecast["wind_speed_10m"])
			total_rain = sum(filtered_forecast["precipitation"])

			weather_summary = (
				f"🌡️ High: {max_temp}°C | ❄️ Low: {min_temp}°C | 💨 Wind: {max_wind} km/h | ☔ Rain: {total_rain:.1f}mm"
			)

			# Format as list of times & temperatures
			formatted_forecast = [
				f"{time[-5:]} - {temp}°C"
				for time, temp in zip(filtered_forecast["time"], filtered_forecast["temperature_2m"])
			]

			return {
				"location": {"latitude": latitude, "longitude": longitude},
				"timezone": data.get("timezone"),
				"summary": weather_summary,
				"hourly_forecast_today": formatted_forecast
			}

	except requests.exceptions.RequestException as e:
		return {"error": f"API request failed: {str(e)}"}

def search_query(query):
	"""Searches Wikipedia first, and falls back to Google Search API if needed."""
	
	# 🟢 **Step 1: Try Wikipedia First**
	page = wiki_wiki.page(query)
	if page.exists():
		result = f"📖 Wikipedia: {page.summary[:500]}...\nRead more: {page.fullurl}"
		return json.loads(json.dumps(result, ensure_ascii=False))  # Prevent Unicode escaping
	
	# 🔴 **Step 2: Wikipedia Failed, Try Google**
	if GOOGLE_SEARCH_KEY and GOOGLE_SEARCH_CSE_ID:
		google_search_url = "https://www.googleapis.com/customsearch/v1"
		params = {
			"q": query,
			"key": GOOGLE_SEARCH_KEY,
			"cx": GOOGLE_SEARCH_CSE_ID,
			"num": 1
		}
		try:
			response = requests.get(google_search_url, params=params)
			response.raise_for_status()
			data = response.json()

			# Extract top search result
			if "items" in data and data["items"]:
				top_result = data["items"][0]
				result = f"🔍 Google: {top_result['title']}\n{top_result['snippet']}\nRead more: {top_result['link']}"
				return json.loads(json.dumps(result, ensure_ascii=False))  # Prevent Unicode escaping
		
		except requests.exceptions.RequestException as e:
			print(f"Google Search API Error: {e}")

	# ❌ **Step 3: Neither Wikipedia nor Google Worked**
	return "Information inaccessible, do not guess."

import os
import tempfile
import pyautogui
import openai
import base64
import requests
import os
import tempfile
def generate_image(prompt: str, save_path: str = None):
	"""Generates an image using DALL-E and saves it or displays it."""
	try:
		# Default to VORTEX temp directory
		if not save_path:
			save_path = os.path.join(VORTEX_TEMP_DIR, "generated_image.png")
		else:
			save_path = os.path.abspath(os.path.expandvars(save_path))
		
		# Ensure directory exists
		directory = os.path.dirname(save_path)
		if directory:
			os.makedirs(directory, exist_ok=True)

		# OpenAI API call
		response = client.images.generate(
			prompt=prompt,
			size="1024x1024",
			n=1,
			response_format="url"
		)

		# Download and save image
		image_url = response.data[0].url
		image_data = requests.get(image_url).content
		
		with open(save_path, "wb") as f:
			f.write(image_data)
		
		webbrowser.open(save_path)
		return f"✅ Image saved to: {save_path}"

	except Exception as e:
		return f"❌ Error: {str(e)}"
def display_markdown(content: str):
	"""
	Creates a Markdown file, converts it to HTML using markdown package, and opens it in a web browser.

	Parameters:
	- content (str): The markdown-formatted text to display.

	Returns:
	- str: Success message or error.
	"""
	try:
		# Convert Markdown to HTML using the markdown package
		html_body = markdown.markdown(content)

		# Full HTML Template
		html_content = f"""
		<!DOCTYPE html>
		<html lang="en">
		<head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">
			<title>Markdown Viewer</title>
			<style>
				body {{
					font-family: Arial, sans-serif;
					max-width: 800px;
					margin: 40px auto;
					padding: 20px;
					line-height: 1.6;
				}}
				h1, h2, h3 {{
					color: #333;
				}}
				pre {{
					background: #f4f4f4;
					padding: 10px;
					border-radius: 5px;
				}}
				blockquote {{
					border-left: 4px solid #ccc;
					padding-left: 10px;
					color: #666;
					font-style: italic;
				}}
				code {{
					background: #f4f4f4;
					padding: 2px 5px;
					border-radius: 3px;
				}}
			</style>
		</head>
		<body>
			{html_body}
		</body>
		</html>
		"""

		# Create a temporary HTML file
		with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as temp_html:
			temp_html.write(html_content)
			temp_html_path = temp_html.name

		# Open the HTML file in the default web browser
		webbrowser.open(f"file://{temp_html_path}")

		return "✅ Markdown displayed successfully in the browser."

	except Exception as e:
		return f"❌ Error displaying markdown: {e}"
	
client = openai.OpenAI(api_key=OPENAI_API_KEY)

VORTEX_TEMP_DIR = os.path.join(tempfile.gettempdir(), "VORTEX")
if not os.path.exists(VORTEX_TEMP_DIR):
	os.makedirs(VORTEX_TEMP_DIR)
import requests
from datetime import datetime, timedelta
def get_weather_forecast(latitude, longitude, forecast_mode, timezone="auto"):
	"""
	Fetches a weather forecast from the Open-Meteo API.

	Parameters:
	- latitude (float): Latitude of the location.
	- longitude (float): Longitude of the location.
	- forecast_mode (str): "hourly_today" for today's hour-by-hour breakdown, "daily_week" for a 7-day summary.
	- timezone (str, optional): Timezone for formatting (default: "auto").

	Returns:
	- str: A formatted weather forecast.
	"""
	try:
		base_url = "https://api.open-meteo.com/v1/forecast"
		
		# Define API parameters based on forecast mode
		params = {
			"latitude": latitude,
			"longitude": longitude,
			"timezone": timezone,
		}

		if forecast_mode == "hourly_today":
			params.update({
				"hourly": "temperature_2m,weather_code",
				"forecast_days": 1  # Get only today's data
			})
		elif forecast_mode == "daily_week":
			params.update({
				"daily": "temperature_2m_max,temperature_2m_min,weather_code",
				"forecast_days": 7
			})
		else:
			return "❌ Invalid forecast mode. Use 'hourly_today' or 'daily_week'."

		# API request
		response = requests.get(base_url, params=params)
		response.raise_for_status()
		data = response.json()

		# Format response
		if forecast_mode == "hourly_today":
			return format_hourly_forecast(data)
		elif forecast_mode == "daily_week":
			return format_daily_forecast(data)

	except requests.exceptions.RequestException as e:
		return f"❌ Error fetching weather data: {e}"
def format_hourly_forecast(data):
	"""
	Formats the hourly weather forecast for today.

	Parameters:
	- data (dict): The API response.

	Returns:
	- str: Formatted hourly weather forecast.
	"""
	try:
		times = data["hourly"]["time"]
		temperatures = data["hourly"]["temperature_2m"]
		weather_codes = data["hourly"]["weather_code"]

		# Get only today's data (0:00 - 23:59)
		today_date = datetime.utcnow().strftime("%Y-%m-%d")
		formatted_forecast = f"📅 **Today's Hourly Forecast:** {today_date}\n\n"

		for time, temp, code in zip(times, temperatures, weather_codes):
			hour = datetime.strptime(time, "%Y-%m-%dT%H:%M").strftime("%I:%M %p")
			condition = interpret_weather_code(code)
			formatted_forecast += f"🕒 {hour} - 🌡 {temp}°C - {condition}\n"

		return formatted_forecast

	except KeyError:
		return "❌ Error parsing hourly forecast data."
def format_daily_forecast(data):
	"""
	Formats the daily weather forecast for a week.

	Parameters:
	- data (dict): The API response.

	Returns:
	- str: Formatted daily weather forecast.
	"""
	try:
		times = data["daily"]["time"]
		temp_max = data["daily"]["temperature_2m_max"]
		temp_min = data["daily"]["temperature_2m_min"]
		weather_codes = data["daily"]["weather_code"]

		formatted_forecast = "📅 **Weekly Weather Forecast:**\n\n"

		for date, max_temp, min_temp, code in zip(times, temp_max, temp_min, weather_codes):
			day = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %b %d")
			condition = interpret_weather_code(code)
			formatted_forecast += f"📆 {day} - 🌡 High: {max_temp}°C, Low: {min_temp}°C - {condition}\n"

		return formatted_forecast

	except KeyError:
		return "❌ Error parsing daily forecast data."
def interpret_weather_code(code):
	"""
	Converts WMO weather codes into human-readable descriptions.

	Parameters:
	- code (int): WMO weather code.

	Returns:
	- str: Description of the weather condition.
	"""
	weather_conditions = {
		0: "Clear Sky ☀️",
		1: "Mainly Clear 🌤",
		2: "Partly Cloudy ⛅",
		3: "Overcast ☁️",
		45: "Fog 🌫",
		48: "Freezing Fog ❄️🌫",
		51: "Light Drizzle 🌦",
		53: "Moderate Drizzle 🌧",
		55: "Heavy Drizzle 🌧",
		61: "Light Rain 🌦",
		63: "Moderate Rain 🌧",
		65: "Heavy Rain 🌧⛈",
		71: "Light Snow 🌨",
		73: "Moderate Snow ❄️",
		75: "Heavy Snow ❄️❄️",
		80: "Light Showers 🌦",
		81: "Moderate Showers 🌧",
		82: "Heavy Showers ⛈",
		95: "Thunderstorm ⛈",
		96: "Thunderstorm with Hail ⛈🌨",
		99: "Severe Thunderstorm ⛈🔥"
	}
	return weather_conditions.get(code, "Unknown Weather 🤷‍♂️")
def analyze_image(image_path: str = None):
	"""
	Analyzes an image using GPT-4o's vision capabilities. If no path is provided, takes a screenshot instead.
	
	Parameters:
	- image_path (str, optional): Path to the image file. If None, a screenshot is taken.
	
	Returns:
	- str: Description of the image or an error message.
	"""
	try:
		if not image_path:
			# Take a screenshot if no path is provided
			if get_debug_mode():
				print("[📸 IMAGE DEBUG] No image path provided. Taking a screenshot...")

			screenshot = pyautogui.screenshot()
			screenshot.save(TEMP_IMAGE_PATH)
			image_path = TEMP_IMAGE_PATH

		# Check if the file exists
		if not os.path.exists(image_path):
			return f"❌ Error: The image file '{image_path}' does not exist."

		if get_debug_mode():
			print(f"[📊 IMAGE DEBUG] Analyzing image: {image_path}")

		# Open the image file
		with open(image_path, "rb") as image_file:
			response = openai.ChatCompletion.create(
				model="gpt-4o",
				messages=[{"role": "user", "content": "Describe the contents of this image."}],
				images=[{"image": image_file.read()}]  # Read image data
			)

		# Extract response
		analysis_result = response["choices"][0]["message"]["content"]

		if get_debug_mode():
			print(f"[✅ IMAGE DEBUG] Analysis result: {analysis_result}")

		return analysis_result

	except Exception as e:
		if get_debug_mode():
			print(f"[❌ IMAGE DEBUG] Error occurred: {str(e)}")
		return f"❌ Error analyzing image: {str(e)}"
	
def summarize_category(category_name: str):
	try:
		# Load stored memory
		if not os.path.exists(MEMORY_FILE):
			return "🤖 No memory stored yet."

		with open(MEMORY_FILE, "r") as f:
			memory_data = json.load(f)

		if category_name not in memory_data or not memory_data[category_name]:
			return f"🤖 No data found in category '{category_name}'."

		# Get all memory texts in the category
		memory_texts = [entry["text"] for entry in memory_data[category_name]]

		# Ask GPT to summarize similar memories
		response = openai.ChatCompletion.create(
			model="gpt-3.5-turbo",
			messages=[
				{"role": "system", "content": "Merge similar items into a concise statement."},
				{"role": "user", "content": f"Summarize these: {memory_texts}"}
			]
		)

		summarized_text = response["choices"][0]["message"]["content"].strip()

		# Replace category content with the summarized version
		memory_data[category_name] = [{"text": summarized_text}]

		# Save the summarized memory
		with open(MEMORY_FILE, "w") as f:
			json.dump(memory_data, f, indent=4)

		return f"✅ Summarized '{category_name}': {summarized_text}"

	except Exception as e:
		return f"❌ Error summarizing category: {e}"

def generate_embedding(text): # helper function
	"""Generates an embedding for the given text using OpenAI's embedding model."""
	try:
		response = openai.embeddings.create(
			model="text-embedding-3-small",  # ✅ Uses OpenAI embeddings
			input=[text],
			encoding_format="float"
		)
		return np.array(response.data[0].embedding).astype("float32")  # Convert to NumPy array
	except Exception as e:
		print(f"[❌ EMBEDDING ERROR] {str(e)}")
		return None  # Return None if embedding fails

def retrieve_memory(query: str):
	"""Finds relevant memories using FAISS similarity search only (no keyword matching)."""
	
	if not os.path.exists(MEMORY_FILE):
		print("[❌ MEMORY FILE MISSING] No memories.json found.")
		return []

	with open(MEMORY_FILE, "r", encoding="utf-8") as f:
		memory_data = json.load(f)

	if not memory_data:
		print("[❌ EMPTY MEMORY FILE] No memories stored.")
		return []

	query = query.lower().strip()
	results = []

	if get_debug_mode():
		print(f"[🔍 MEMORY DEBUG] Query: {query}")

	# ✅ Step 1: Convert query to an embedding
	query_embedding = generate_embedding(query)
	if query_embedding is None:
		print("[❌ EMBEDDING ERROR] Failed to generate query embedding.")
		return []

	# ✅ Step 2: Search FAISS for similarity matches
	for category, entries in memory_data.items():
		embeddings = np.array([entry["embedding"] for entry in entries]).astype("float32")

		if embeddings.size > 0:
			index = faiss.IndexFlatL2(len(query_embedding))
			index.add(embeddings)
			D, I = index.search(np.array([query_embedding], dtype="float32"), 5)  # Retrieve top 5

			for score, idx in zip(1 - D[0], I[0]):  # Convert L2 distance to similarity
				if score > 0.3:  # ✅ Adjusted similarity threshold (higher = stricter)
					if get_debug_mode():
						print(f"[✅ EMBEDDING MATCH] '{entries[idx]['text']}' (Score: {score:.2f})")
					results.append(entries[idx]['text'])

	if results:
		return results  

	if get_debug_mode():
		print("[❌ MEMORY DEBUG] No relevant memories found.")
	return []


def shutdown_vortex():
	print("[🛑 VORTEX SHUTDOWN] Exiting program...")
	sys.exit(0)  # Exit the program
def store_memory(text: str):
	"""Stores a fact in memory using vector embeddings and FAISS for retrieval."""
	try:
		# ✅ Generate an embedding
		response = openai.embeddings.create(model=OPENAI_MODEL, input=[text], encoding_format="float")
		embedding = np.array(response.data[0].embedding, dtype="float32").tolist()

		# ✅ Load existing memory file or create a new one
		try:
			with open(MEMORY_FILE, "r", encoding="utf-8") as f:
				memory_data = json.load(f)
		except (FileNotFoundError, json.JSONDecodeError):
			memory_data = {}

		# ✅ Assign to "general" category if no category system is defined
		category = "general"
		if category not in memory_data:
			memory_data[category] = []

		# 🔍 **Check for Similar Memories Before Adding a New One**
		index = faiss.IndexFlatL2(len(embedding))
		if memory_data[category]:
			embeddings = np.array([entry["embedding"] for entry in memory_data[category]]).astype("float32")
			index.add(embeddings)

			query_embedding = np.array(embedding).astype("float32").reshape(1, -1)
			D, I = index.search(query_embedding, 1)  # Get the closest match

			similarity_score = 1 - D[0][0]
			if similarity_score > 0.75:  # **If it's over 75% similar, update instead**
				memory_data[category][I[0][0]]["text"] = text
				memory_data[category][I[0][0]]["embedding"] = embedding

				with open(MEMORY_FILE, "w", encoding="utf-8") as f:
					json.dump(memory_data, f, indent=4)

				return f"✅ Updated existing memory: {text} (Similarity Score: {similarity_score:.2f})"

		# **Otherwise, store as a new memory**
		memory_data[category].append({"text": text, "embedding": embedding})

		# ✅ Save memory file
		with open(MEMORY_FILE, "w", encoding="utf-8") as f:
			json.dump(memory_data, f, indent=4)

		return f"✅ Stored new memory: {text}"

	except Exception as e:
		if get_debug_mode():
			print(f"[❌ MEMORY ERROR] {str(e)}")
		return f"❌ Error storing memory: {str(e)}"
def delete_memory(query: str):
	"""Deletes a specific stored memory or clears an entire category."""
	with open(MEMORY_FILE, "r+") as f:
		memory_data = json.load(f)

	# ✅ Allow partial matches instead of requiring an exact match
	deleted = False
	for category, entries in memory_data.items():
		for i, entry in enumerate(entries):
			if query.lower() in entry["text"].lower():  # ✅ Check for partial match
				del memory_data[category][i]
				deleted = True
				break

	if deleted:
		with open(MEMORY_FILE, "w") as f:
			json.dump(memory_data, f, indent=4)
		return f"✅ Memory related to '{query}' has been deleted."
	else:
		return f"🤷 No matching memory found for '{query}'."

def list_memory_categories():
	"""Lists all available memory categories from the memory file."""
	if not os.path.exists(MEMORY_FILE):
		print("[❌ MEMORY FILE MISSING] No memories.json found.")
		return []

	try:
		with open(MEMORY_FILE, "r", encoding="utf-8") as f:
			memory_data = json.load(f)

		categories = list(memory_data.keys())
		if not categories:
			print("[📂 EMPTY MEMORY] No categories available.")
			return []
		
		print(f"[📜 MEMORY CATEGORIES] Available categories: {categories}")
		return categories

	except Exception as e:
		print(f"[❌ ERROR] Failed to list memory categories: {e}")
		return []

def categorize_memory(text):
	"""Uses GPT-4o to determine a category for a memory entry with a strict one-word rule."""
	
	categories = list_memory_categories()  # ✅ Load existing categories
	
	system_prompt = (
		f"Please categorize this fact. "
		f"Only respond with **one** single word, the category name. "
		f"Current categories: {', '.join(categories) if categories else 'None'}. "
		f"If none fit, respond with a new category name."
	)

	try:
		response = openai.ChatCompletion.create(
			model="gpt-4o",
			messages=[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": text}
			]
		)

		category = response.choices[0].message["content"].strip().lower()

		# ✅ Ensure it's only **one word** (remove extra spaces/newlines)
		if " " in category or len(category) == 0:
			print(f"[⚠️ WARNING] Invalid category received: '{category}', defaulting to 'general'.")
			return "general"

		print(f"[📂 CATEGORY ASSIGNED] '{text}' → '{category}'")
		return category

	except Exception as e:
		print(f"[❌ ERROR] Failed to categorize memory: {e}")
		return "general"  # ✅ Safe fallback category



def read_gmail(count: int = 5):
	"""Fetches unread emails from Gmail and returns a summary."""
	try:
		creds = authorize()
		if not creds:
			return "❌ Error: Unable to authenticate with Gmail API."
		
		service = build("gmail", "v1", credentials=creds)

		results = service.users().messages().list(
			userId="me", labelIds=["INBOX"], q="is:unread", maxResults=count
		).execute()

		messages = results.get("messages", [])
		if not messages:
			return "✅ No unread emails."

		email_summaries = []
		for msg in messages:
			msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
			headers = msg_data.get("payload", {}).get("headers", [])

			subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
			sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")

			email_summaries.append(f"📩 **From:** {sender} | **Subject:** {subject}")

		return "\n".join(email_summaries)

	except googleapiclient.errors.HttpError as e:
		return f"❌ Gmail API Error: {e.reason}"
	except Exception as e:
		return f"❌ Unexpected Error: {str(e)}"


def send_email(to: str, subject: str, body: str):
	"""Sends an email using Gmail API."""
	try:
		creds = authorize()
		if not creds:
			return "❌ Error: Unable to authenticate with Gmail API."

		service = build("gmail", "v1", credentials=creds)

		message = MIMEText(body)
		message["to"] = to
		message["subject"] = subject
		raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

		send_result = service.users().messages().send(
			userId="me", body={"raw": raw_message}
		).execute()

		return f"✅ Email sent to {to} (ID: {send_result.get('id')})"

	except googleapiclient.errors.HttpError as e:
		return f"❌ Gmail API Error: {e.reason}"
	except Exception as e:
		return f"❌ Error sending email: {str(e)}"


def modify_email(email_id: str, action: str):
	"""Marks an email as read or deletes it."""
	try:
		creds = authorize()
		if not creds:
			return "❌ Error: Unable to authenticate with Gmail API."

		service = build("gmail", "v1", credentials=creds)

		if action == "read":
			service.users().messages().modify(
				userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
			).execute()
			return f"✅ Email {email_id} marked as read."

		elif action == "delete":
			service.users().messages().trash(userId="me", id=email_id).execute()
			return f"🗑️ Email {email_id} moved to trash."

		else:
			return "❌ Invalid action. Use 'read' or 'delete'."

	except googleapiclient.errors.HttpError as e:
		return f"❌ Gmail API Error: {e.reason}"
	except Exception as e:
		return f"❌ Email modification error: {str(e)}"

import os
import numpy as np
import sounddevice as sd
import io
import re
from openai import OpenAI
from pydub import AudioSegment
from src.Capabilities.debug_mode import get_debug_mode

# Initialize OpenAI Client
import os
import numpy as np
import sounddevice as sd
import io
import re
import asyncio
from openai import OpenAI
from pydub import AudioSegment
from pydub.playback import play
from src.Capabilities.debug_mode import get_debug_mode

client = OpenAI()

async def generate_tts_segment(segment):
	"""Generates a single TTS segment and returns its audio data."""
	voice = segment.get("voice", "nova")
	speed = segment.get("speed", 1.0)
	text = segment.get("text", "").strip()
	
	if not text:
		return None
	
	if get_debug_mode():
		print(f"[🔊 GENERATING] Voice: {voice}, Speed: {speed}, Text: {text}")
	
	try:
		response = client.audio.speech.create(
			model="tts-1",
			voice=voice,
			input=text,
			speed=speed
		)
		temp_audio_path = f"temp/{voice}_{speed}.mp3"
		response.stream_to_file(temp_audio_path)
		return AudioSegment.from_file(temp_audio_path, format="mp3")
	except Exception as e:
		print(f"[❌ ERROR] TTS failed: {e}")
		return None

async def speak_text(input_text: str):
	"""
	Handles the tool call for speaking text using OpenAI's TTS, 
	generating segments in parallel and stitching them together for direct playback.
	"""
	spoken_text, thought_text = extract_thoughts_and_speech(input_text)
	
	if thought_text:
		print(f"\033[93m[THOUGHT]: {thought_text}\033[0m")  # Display inner monologue
	
	segments = parse_speech_syntax(spoken_text)
	tasks = [generate_tts_segment(segment) for segment in segments]
	
	audio_segments = await asyncio.gather(*tasks)
	audio_segments = [seg for seg in audio_segments if seg is not None]
	
	if audio_segments:
		combined_audio = sum(audio_segments)
		play(combined_audio)  # ✅ Directly play the stitched-together speech
	return "its being spoken dont return a blank response, put SOMETHING down for thoughts"

def extract_thoughts_and_speech(input_text: str):
	"""Separates inner monologue (non-spoken) from speech."""
	thought_pattern = r"\[THOUGHT\](.*?)\[/THOUGHT\]"
	thought_matches = re.findall(thought_pattern, input_text, re.DOTALL)
	thought_text = " ".join(thought_matches).strip()
	
	spoken_text = re.sub(thought_pattern, "", input_text).strip()
	return spoken_text, thought_text

def parse_speech_syntax(input_text: str):
	"""Parses structured speech syntax into segments with voice and speed settings."""
	pattern = re.compile(r'\{([^=]+)=([\d.]+)\}(.*?)(?=\{\w+=|\Z)', re.DOTALL)
	segments = []
	last_end = 0

	valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer", "sage"}  # Added 'sage'
	default_voice = "sage"
	default_speed = 1.1
	
	for match in pattern.finditer(input_text):
		start, end = match.span()

		if start > last_end:
			preceding_text = input_text[last_end:start].strip()
			if preceding_text:
				segments.append({"voice": default_voice, "speed": default_speed, "text": preceding_text})

		voice = match.group(1).strip().lower()
		speed_str = match.group(2).strip()
		text = match.group(3).strip()

		if voice not in valid_voices:
			print(f"[⚠️ WARNING] Invalid voice '{voice}', using '{default_voice}'")
			voice = default_voice

		try:
			speed = float(speed_str)
		except ValueError:
			speed = default_speed
		speed = max(0.5, min(2.0, speed))  # Clamp speed

		if text:
			segments.append({"voice": voice, "speed": speed, "text": text})
		
		last_end = end

	if last_end < len(input_text):
		remaining_text = input_text[last_end:].strip()
		if remaining_text:
			segments.append({"voice": default_voice, "speed": default_speed, "text": remaining_text})
	
	return segments

# steam bullshit isnt written by ai (whattttt)
# To use the steam browser protocol(very cool stuff) u may have to remind vortex its ability to do so i have this in my main prompt (VORTEX can interact with Steam via the Steam browser protocol using the command "start steam://example")
import vdf
import winreg
reg = winreg.ConnectRegistry(None,winreg.HKEY_LOCAL_MACHINE)
def get_steam():
	libraryLoc = winreg.OpenKey(reg,r"SOFTWARE\WOW6432Node\Valve\Steam")
	return winreg.QueryValueEx(libraryLoc, "InstallPath")[0]

def get_steam_apps():
	# Get appids of all installed games
	librar = []
	g = vdf.parse(open(f'{get_steam()}/steamapps/libraryfolders.vdf'))
	for i in g['libraryfolders']:
		for x in g['libraryfolders'][f"{i}"]['apps']:
			librar.append(int(x))
	games = {}

	# Get games name by appid
	response = requests.get("https://api.steampowered.com/ISteamApps/GetAppList/v2/").json()
	for i in range(len(response['applist']['apps'])):
		#print(appid, name)
		if (response['applist']['apps'][i]['appid']) in librar and response['applist']['apps'][i]['appid'] not in games:
			print(response['applist']['apps'][i]['name'])
			print(response['applist']['apps'][i]['appid'])
			games.update({response['applist']['apps'][i]['appid'] : response['applist']['apps'][i]['name']})
	print(games)
	return games

def start_steam_app(appid: str):
	os.system(f""""{get_steam()}/steam.exe" steam://run/{appid}""")
	return f"✅ Game may update before launching"

capabilities.register_function_in_registry("get_steam_apps", get_steam_apps)
capabilities.register_function_in_registry("start_steam_app", start_steam_app)
capabilities.register_function_in_registry("get_steam", get_steam)
capabilities.register_function_in_registry("read_gmail", read_gmail)
capabilities.register_function_in_registry("send_email", send_email)
capabilities.register_function_in_registry("modify_email", modify_email)
capabilities.register_function_in_registry("store_memory", store_memory)
capabilities.register_function_in_registry("retrieve_memory", retrieve_memory)
capabilities.register_function_in_registry("delete_memory", delete_memory)
capabilities.register_function_in_registry("list_memory_categories", list_memory_categories)
capabilities.register_function_in_registry("powershell", powershell)
capabilities.register_function_in_registry("search_query", search_query)
#capabilities.register_function_in_registry("read_vortex_code", read_vortex_code)
capabilities.register_function_in_registry("add_new_capability", add_new_capability)
capabilities.register_function_in_registry("restart_vortex", restart_vortex)
capabilities.register_function_in_registry("shutdown_vortex", shutdown_vortex)
capabilities.register_function_in_registry("get_weather_forecast", get_weather_forecast)
capabilities.register_function_in_registry("youtube_search", youtube_search)
capabilities.register_function_in_registry("modrinth_search", modrinth_search)
capabilities.register_function_in_registry("generate_image", generate_image)
capabilities.register_function_in_registry("clarify_and_launch", clarify_and_launch)
capabilities.register_function_in_registry("analyze_image", analyze_image)
capabilities.register_function_in_registry("debugmode", set_debug_mode)
capabilities.register_function_in_registry("open_link", open_link)
capabilities.register_function_in_registry("get_shortcuts", get_shortcuts)
capabilities.register_function_in_registry("get_shortcut_path", get_shortcut_path)
capabilities.register_function_in_registry("launch_shortcut", launch_shortcut)
capabilities.register_function_in_registry("display_markdown", display_markdown)
capabilities.register_function_in_registry("get_user_info", get_user_info)
capabilities.register_function_in_registry("get_time", get_time)
capabilities.register_function_in_registry("create_event", create_event)
capabilities.register_function_in_registry("list_events", list_events)
capabilities.register_function_in_registry("query_wolfram_alpha", query_wolfram_alpha)
capabilities.register_function_in_registry("speak_text", speak_text)

capabilities.register_function_schema({
	"type": "function",
	"function":{
		"name": "get_steam_apps",
		"description": "Gets name and appid of all installed steamapps",
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_steam",
		"description": "Gets location of steam.exe usefull for using the steam browser protocol in console"
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function":{
		"name": "start_steam_app",
		"description": "Opens a steam app by id",
		"parameters": {
			"type": "object",
			"properties": {
				"appid": {
					"type": "string",
					"description": "Steam appid to open"
				}
			},
			"required": ["appid"]
		}
	}
})

# ✅ Register Function Schemas
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "read_gmail",
		"description": "Fetches unread Gmail messages.",
		"parameters": {
			"type": "object",
			"properties": {
				"count": {
					"type": "integer",
					"description": "Number of unread emails to retrieve.",
					"default": 5
				}
			},
			"required": []
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "send_email",
		"description": "Sends an email using Gmail.",
		"parameters": {
			"type": "object",
			"properties": {
				"to": {"type": "string", "description": "Recipient email address."},
				"subject": {"type": "string", "description": "Subject of the email. "},
				"body": {"type": "string", "description": "Email content."}
			},
			"required": ["to", "subject", "body"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "modify_email",
		"description": "Marks an email as read or deletes it.",
		"parameters": {
			"type": "object",
			"properties": {
				"email_id": {"type": "string", "description": "ID of the email to modify."},
				"action": {"type": "string", "enum": ["read", "delete"], "description": "Action to perform on the email."}
			},
			"required": ["email_id", "action"]
		}
	}
})
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "query_wolfram_alpha",
		"description": "Fetches scientific, mathematical, and factual answers from Wolfram Alpha. this is an amazing tool! dont hesitate to use it to answer questions",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {
					"type": "string",
					"description": "The question or equation to solve. Example: 'Solve x^2 - 4x + 4 = 0'"
				}
			},
			"required": ["query"]
		}
	}
})
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "list_events",
		"description": "Lists upcoming events from Google Calendar.",
		"parameters": {
			"type": "object",
			"properties": {
				"max_results": {"type": "integer", "description": "Number of events to fetch."},
				"time_min": {"type": "string", "description": "Start time filter (ISO 8601)."},
				"time_max": {"type": "string", "description": "End time filter (ISO 8601)."}
			},
			"required": []
		}
	}
})
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "modrinth_search",
		"description": "Searches Modrinth for Minecraft mods based on the given query.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {
					"type": "string",
					"description": "The search query for Modrinth."
				}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "clarify_and_launch",
		"description": "Launches a program after the user clarifies their choice from multiple matches.",
		"parameters": {
			"type": "object",
			"properties": {
				"clarified_name": {
					"type": "string",
					"description": "The exact name of the program to launch from the previously listed matches."
				}
			},
			"required": ["clarified_name"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "analyze_image",
		"description": "Analyzes an image to extract details. If no file path is provided, it takes a screenshot and analyzes that instead.",
		"parameters": {
			"type": "object",
			"properties": {
				"image_path": {
					"type": "string",
					"description": "Optional. The file path of the image to analyze. If not provided, a screenshot will be taken."
				}
			},
			"required": []
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_shortcuts",
		"description": "Lists all available program shortcuts from the Start Menu, Desktop, and Downloads. Returns only shortcut names to save tokens.",
		"parameters": {
			"type": "object",
			"properties": {},
			"required": []
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_shortcut_path",
		"description": "Retrieves the file path of a specific shortcut by name.",
		"parameters": {
			"type": "object",
			"properties": {
				"shortcut_name": {
					"type": "string",
					"description": "The name of the shortcut to find."
				}
			},
			"required": ["shortcut_name"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "launch_shortcut",
		"description": "Launches a program based on a shortcut name retrieved from get_shortcuts.",
		"parameters": {
			"type": "object",
			"properties": {
				"program_name": {
					"type": "string",
					"description": "The name of the program to launch."
				}
			},
			"required": ["program_name"]
		}
	}
})
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "store_memory",
		"description": "Stores a memory. If a similar memory already exists, it will be updated instead.",
		"parameters": {
			"type": "object",
			"properties": {
				"text": {"type": "string", "description": "The memory content to store."}
			},
			"required": ["text"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "retrieve_memory",
		"description": "Retrieves memory entries related to a given topic.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "The search query to find stored memories."}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "delete_memory",
		"description": "Deletes a specific stored memory or clears an entire category.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "The memory or category to be deleted."}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "list_memory_categories",
		"description": "Lists all available memory categories."
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "powershell",
		"description": "Executes a PowerShell command and returns the output.",
		"parameters": {
			"type": "object",
			"properties": {
				"command": {"type": "string", "description": "The PowerShell command to execute."}
			},
			"required": ["command"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "search_query",
		"description": "Searches the web using Wikipedia and Google for relevant information.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "The search term or question."}
			},
			"required": ["query"]
		}
	}
})
"""
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "read_vortex_code",
		"description": "Reads and returns the contents of any file in the vortex project directory! if any function or capability runs into an error, please use this to try to help debug the error, or even provide the user with the fix! any time this is ran it also returns a Tree of all the files and directorys in the project directory",
		"parameters": {
			"type": "object",
			"properties": {
				"filename": {"type": "string", "description": "The name of the VORTEX source file to read."}
			},
			"required": ["filename"]
		}
	}
})
"""
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "speak_text",
		"description": "Handles speaking text using TTS. Supports {voice=speed} syntax for multiple voice and speed changes within the same message. Text wrapped in [THOUGHT]...[/THOUGHT] is not spoken and is considered inner monologue.",
		"parameters": {
			"type": "object",
			"properties": {
				"input_text": {
					"type": "string",
					"description": "The text to be spoken.  Supports multiple structured speech syntax elements like {voice=speed} text. Non-spoken text can be enclosed in [THOUGHT]...[/THOUGHT] and will be displayed but not spoken."
				}
			},
			"required": ["input_text"]
		}
	}
})
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "add_new_capability",
		"description": "Creates and registers a new function when explicitly requested by the user. \
						The function code must include the full function definition, required imports, \
						function registry entry, and schema registration.  vortex writes the code, NOT THE USER.  feel free to lookup documentation with search query before running this",
		"parameters": {
			"type": "object",
			"properties": {
				"function_name": {
					"type": "string",
					"description": "The name of the function to be created. It must be a valid Python function name."
				},
				"function_code": {
					"type": "string",
					"description": "The full function definition as a string, including necessary imports, \
									function logic, variable definitions, MUST INCLUDE SCHEMA AND REGISTRATION, OR IT WILL RETURN AN ERROR, \
									remmeber the guidelines! "
				}
			},
			"required": ["function_name", "function_code"]
		}
	}
})


capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "restart_vortex",
		"description": "Restarts the VORTEX system."
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "shutdown_vortex",
		"description": "Shuts down the VORTEX AI system immediately."
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_weather_forecast",
		"description": "Retrieves a weather forecast for a given location. if you dont know the users location use getinfo",
		"parameters": {
			"type": "object",
			"properties": {
				"latitude": {"type": "number", "description": "Geographical latitude of the location."},
				"longitude": {"type": "number", "description": "Geographical longitude of the location."},
				"forecast_mode": {"type": "string", "enum": ["hourly_today", "daily_week"], "description": "Forecast mode: 'hourly_today' or 'daily_week'."}
			},
			"required": ["latitude", "longitude", "forecast_mode"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "youtube_search",
		"description": "Searches YouTube for a specific query and opens the results in a browser.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "The search query for YouTube."}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "generate_image",
		"description": "Generates an image using DALL-E based on a given prompt.",
		"parameters": {
			"type": "object",
			"properties": {
				"prompt": {"type": "string", "description": "A detailed prompt describing the image to generate."}
			},
			"required": ["prompt"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "debugmode",
		"description": "Enables or disables debug mode.",
		"parameters": {
			"type": "object",
			"properties": {
				"enable": {"type": "boolean", "description": "Set to true to enable debug mode, false to disable it."}
			},
			"required": ["enable"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "display_markdown",
		"description": "Displays markdown-formatted text in a browser.",
		"parameters": {
			"type": "object",
			"properties": {
				"content": {"type": "string", "description": "The markdown-formatted text to display."}
			},
			"required": ["content"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_user_info",
		"description": "Retrieves the user's geolocation details."
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_time",
		"description": "Gets the current time in the user's timezone in ISO 8601 format."
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "create_event",
		"description": "Creates an event in Google Calendar.",
		"parameters": {
			"type": "object",
			"properties": {
				"summary": {"type": "string", "description": "Event title."},
				"start_time": {"type": "string", "description": "ISO 8601 format start time."},
				"duration": {"type": "integer", "description": "Duration in minutes."}
			},
			"required": ["summary", "start_time"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "open_link",
		"description": "Opens a URL in the default web browser.",
		"parameters": {
			"type": "object",
			"properties": {
				"url": {"type": "string", "description": "The full URL to open (must start with http:// or https://)."}
			},
			"required": ["url"]
		}
	}
})
