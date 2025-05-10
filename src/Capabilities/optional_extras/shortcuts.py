# Shortcuts-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import os
import ctypes
from ctypes import wintypes
import glob
import subprocess
from src.Capabilities.debug_mode import get_debug_mode
from src.Boring.boring import log_debug_event

def clarify_and_launch(clarified_name: str):
	"""
	Identifies and launches a program or file based on clarified name.
	
	Parameters:
	- clarified_name (str): The clarified name of the program to launch
	
	Returns:
	- str: Success or error message
	"""
	shortcut_path = get_shortcut_path(clarified_name)
	
	if shortcut_path:
		return launch_shortcut(shortcut_path)
	else:
		return f"❌ Could not find a shortcut for '{clarified_name}'"

def launch_shortcut(program_name: str):
	"""
	Launches a program or file using subprocess.
	
	Parameters:
	- program_name (str): The path of the program to launch
	
	Returns:
	- str: Success or error message
	"""
	try:
		# Launch the program
		log_debug_event(f"LAUNCHING: {program_name}")
		
		subprocess.Popen(program_name, shell=True)
		return f"✅ Launched: {os.path.basename(program_name)}"
	
	except Exception as e:
		return f"❌ Error launching {program_name}: {e}"

def get_shortcut_path(shortcut_name):
	"""
	Finds the full path to a shortcut by its name.
	
	Parameters:
	- shortcut_name (str): The name of the shortcut to find
	
	Returns:
	- str or None: The path of the shortcut if found, None otherwise
	"""
	# Get standard Windows folders
	desktop_path = get_known_folder("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}")  # Desktop
	start_menu_path = get_known_folder("{625B53C3-AB48-4EC1-BA1F-A1EF4146FC19}")  # Start menu
	
	# Define locations to search
	search_locations = [
		os.path.join(desktop_path, "*.lnk"),
		os.path.join(start_menu_path, "*.lnk"),
		os.path.join(start_menu_path, "Programs", "*.lnk")
	]
	
	# Search for the shortcut
	for location in search_locations:
		shortcuts = glob.glob(location)
		for shortcut in shortcuts:
			if shortcut_name.lower() in os.path.basename(shortcut).lower():
				return shortcut
	
	return None

def get_known_folder(folder_id):
	"""
	Gets the path to a special Windows folder.
	
	Parameters:
	- folder_id (str): The GUID of the folder to find
	
	Returns:
	- str: The path of the folder
	"""
	path_buffer = wintypes.LPWSTR()
	ctypes.windll.shell32.SHGetKnownFolderPath(
		ctypes.byref(ctypes.create_unicode_buffer(folder_id)),
		0, None, ctypes.byref(path_buffer)
	)
	path = path_buffer.value
	ctypes.windll.ole32.CoTaskMemFree(path_buffer)
	return path

def get_shortcuts():
	"""
	Gets a list of available shortcuts on the desktop and in the Start menu.
	
	Returns:
	- dict: Dictionary with categories as keys and lists of shortcut names as values
	"""
	# Get standard Windows folders
	desktop_path = get_known_folder("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}")  # Desktop
	start_menu_path = get_known_folder("{625B53C3-AB48-4EC1-BA1F-A1EF4146FC19}")  # Start menu
	
	# Get shortcuts
	desktop_shortcuts = [os.path.basename(s).replace(".lnk", "") for s in glob.glob(os.path.join(desktop_path, "*.lnk"))]
	start_menu_shortcuts = [os.path.basename(s).replace(".lnk", "") for s in glob.glob(os.path.join(start_menu_path, "*.lnk"))]
	programs_shortcuts = [os.path.basename(s).replace(".lnk", "") for s in glob.glob(os.path.join(start_menu_path, "Programs", "*.lnk"))]
	
	# Organize by category
	shortcuts = {
		"Desktop": desktop_shortcuts,
		"Start Menu": start_menu_shortcuts,
		"Programs": programs_shortcuts
	}
	
	return shortcuts

# Register functions and schemas
capabilities.register_function_in_registry("clarify_and_launch", clarify_and_launch)
capabilities.register_function_in_registry("launch_shortcut", launch_shortcut)
capabilities.register_function_in_registry("get_shortcut_path", get_shortcut_path)
capabilities.register_function_in_registry("get_shortcuts", get_shortcuts)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "clarify_and_launch",
		"description": "Launches a program based on a clarified program name.",
		"parameters": {
			"type": "object",
			"properties": {
				"clarified_name": {
					"type": "string",
					"description": "Clarified name of the program to launch."
				}
			},
			"required": ["clarified_name"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "launch_shortcut",
		"description": "Launches a program shortcut.",
		"parameters": {
			"type": "object",
			"properties": {
				"program_name": {
					"type": "string",
					"description": "Path of the program to launch."
				}
			},
			"required": ["program_name"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_shortcut_path",
		"description": "Gets the full path to a shortcut by its name.",
		"parameters": {
			"type": "object",
			"properties": {
				"shortcut_name": {
					"type": "string",
					"description": "Name of the shortcut to find."
				}
			},
			"required": ["shortcut_name"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_shortcuts",
		"description": "Gets a list of available shortcuts on the system.",
		"parameters": {
			"type": "object",
			"properties": {},
			"required": []
		}
	}
}) 