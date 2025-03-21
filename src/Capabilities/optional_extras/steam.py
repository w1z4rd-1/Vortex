# steam bullshit isnt written by ai (whattttt) to use the steam browser protocol(very cool stuff)

from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode
import src.Boring.capabilities as capabilities

import vdf
import winreg
import requests
import os

REG = winreg.ConnectRegistry(None,winreg.HKEY_LOCAL_MACHINE) # May need to be changed for 32bit windows
URL = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"

def get_steam_path():
	# Returns string
	libraryLoc = winreg.OpenKey(REG,r"SOFTWARE\WOW6432Node\Valve\Steam")
	return winreg.QueryValueEx(libraryLoc, "InstallPath")[0]

def get_steam_apps(): # Should rewrite this
	# Returns dictionary

	librar = []
	g = vdf.parse(open(f'{get_steam_path()}/steamapps/libraryfolders.vdf'))
	for i in g['libraryfolders']:
		for x in g['libraryfolders'][f"{i}"]['apps']:
			librar.append(int(x))
	games = {}

	# Get games name by appid
	response = requests.get(URL).json()
	for i in range(len(response['applist']['apps'])):
		#print(appid, name)
		if (response['applist']['apps'][i]['appid']) in librar and response['applist']['apps'][i]['appid'] not in games:
			print(response['applist']['apps'][i]['name'])
			print(response['applist']['apps'][i]['appid'])
			games.update({response['applist']['apps'][i]['appid'] : response['applist']['apps'][i]['name']})
	print(games)
	return games

def start_steam_app(appid: str):
	# Returns string
	os.system(f""""{get_steam_path()}/steam.exe" steam://run/{appid}""")
	return f"✅ Game may update before launching"

capabilities.register_function_in_registry("get_steam_apps", get_steam_apps)
capabilities.register_function_in_registry("start_steam_app", start_steam_app)
capabilities.register_function_in_registry("get_steam", get_steam_path)

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
		"name": "get_steam_path",
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