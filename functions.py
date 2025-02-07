import requests
from datetime import datetime, timedelta, timezone
from auth import authorize
from googleapiclient.discovery import build
import subprocess
import os
import tempfile
import glob
import ctypes
from ctypes import wintypes
import markdown
import webbrowser
import wikipediaapi
import json
import re
import openai  # Add this import
from dotenv import load_dotenv
wiki_wiki = wikipediaapi.Wikipedia(user_agent="VORTEX", language="en")
debug_mode = False
TOKEN_PATH = "token.json"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[96m"
load_dotenv()
GOOGLE_SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY")
GOOGLE_SEARCH_CSE_ID = os.getenv("GOOGLE_SEARCH_CSE_ID")
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # Add this at the top
JSON_PATH = "powershell.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    powershell_permissions = json.load(f)

blacklisted = set(powershell_permissions["blacklisted"])
ask_first = set(powershell_permissions["ask_first"])

# Debug mode function
def set_debug_mode(value: bool):
    """Sets the global debug mode."""
    global debug_mode
    debug_mode = value
def powershell(permission: bool, command: str, returnoutput: bool = True) -> str:
    """
    Executes a PowerShell command with permission checking.
    
    Parameters:
    - permission (bool): Did the user explicitly give permission to run this command?
    - command (str): The PowerShell command to execute (may include arguments).
    - returnoutput (bool, optional): Whether to capture and return output (default: True).
    
    Returns:
    - str: Command output or execution status.
    """
    if not command.strip():
        return "❌ No command provided."

    # Extract the base command (first word)
    base_command = command.split()[0]

    # Check if command is blacklisted
    if base_command in blacklisted:
        return f"❌ Command '{base_command}' is blacklisted and cannot be executed."

    # Check if command requires permission
    if base_command in ask_first and not permission:
        return "⛔ Command not executed, ask the user for permission."

    try:
        if returnoutput:
            # Run PowerShell command headlessly and capture output
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip() if result.stdout else "✅ Command executed successfully."
        else:
            # Open a new PowerShell window and execute the command
            ps_script = f"Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -Command {command}' -WindowStyle Normal"
            error_check_script = f"Start-Sleep -Seconds 3; if ($?) {{ '✅ Command executed' }} else {{ '❌ Command failed' }}"
            
            # Run first command
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], check=True)

            # Check for errors after 3 seconds
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", error_check_script],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
            
    except subprocess.CalledProcessError as e:
        return f"❌ Error executing command: {e}"
def get_debug_mode():
    """Returns the current debug mode state."""
    return debug_mode
# ---------------------------
# 🏠 GET USER GEOLOCATION INFO
# ---------------------------
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

# ---------------------------
# 🕒 GET CURRENT TIME IN A TIMEZONE
# ---------------------------
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
# 🔗 ------------------
# Open a Web Link
# --------------------
def open_link(url: str):
    
    """Opens a specified URL in the default web browser. AI must not generate fake URLs."""
    if url.startswith("http://") or url.startswith("https://"):
        webbrowser.open(url)
        return f"✅ Opened: {url}"
    return "❌ Invalid or missing URL. AI must not guess links."

# ---------------------------
# 📅 CREATE EVENT FUNCTION
# ---------------------------
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
import subprocess

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


# 🗂️ -----------------------------
# Get All Start Menu Shortcuts
# -------------------------------
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

# ---------------------------
# 📅 LIST UPCOMING EVENTS FUNCTION
# ---------------------------
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

VORTEX_TEMP_DIR = os.path.join(tempfile.gettempdir(), "VORTEX")

# Ensure the VORTEX directory exists
if not os.path.exists(VORTEX_TEMP_DIR):
    os.makedirs(VORTEX_TEMP_DIR)


import os
import webbrowser
import requests

import os
import webbrowser
import requests

import os
import webbrowser
import requests
import openai

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

def analyze_image(image_path: str = None):
    """
    Analyzes an image using GPT-4o's vision capabilities.
    If no path is provided, it captures a screenshot.

    Parameters:
    - image_path (str, optional): The file path of the image to analyze. If None, takes a screenshot.

    Returns:
    - dict: Description of the analyzed image.
    """
    try:
        if not image_path:
            # Take a screenshot
            screenshot_path = os.path.join(VORTEX_TEMP_DIR, "screenshot.png")
            screenshot = pyautogui.screenshot()
            screenshot.save(screenshot_path)
            image_path = screenshot_path

        if not os.path.exists(image_path):
            return {"error": "❌ Image file not found."}

        # Convert image to base64
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        # Call OpenAI's GPT-4o vision API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Describe the image in detail."},
                {"role": "user", "content": [
                    {"type": "text", "text": "What do you see in this image?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]}
            ]
        )
        
        description = response.choices[0].message.content
        return {"message": "✅ Image analyzed successfully!", "description": description}

    except Exception as e:
        return {"error": f"❌ Error analyzing image: {e}"}


# ---------------------------
# 🔗 FUNCTION REGISTRY FOR OpenAI FUNCTION CALLING
# ---------------------------
function_registry = {
    "powershell": powershell,
    "open_link": open_link,
    "get_shortcut_path": get_shortcut_path,
    "get_shortcuts": get_shortcuts,
    "clarify_and_launch": clarify_and_launch,
    "launch_shortcut": launch_shortcut,
    "get_user_info": get_user_info,  # based on IP address
    "get_time": get_time,
    "create_event": create_event,  # use my Google Calendar
    "list_events": list_events,
    "display_markdown": display_markdown,
    "search_query": search_query,  # use Wikipedia and Google to find info
    "debugmode": set_debug_mode,
    "generate_image": generate_image,
    "analyze_image": analyze_image,
    "modrinth_search": modrinth_search,
    "youtube_search": youtube_search
}

function_schemas = [
    {
        "type": "function",
        "function": {
            "name": "youtube_search",
            "description": "Searches YouTube for a specific query and opens the results in a browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for YouTube."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
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
    },
    {
    "type": "function",
    "function": {
        "name": "powershell",
        "description": "Executes a PowerShell command with permission handling.",
        "parameters": {
            "type": "object",
            "properties": {
                "permission": {
                    "type": "boolean",
                    "description": "Did the user explicitly give permission to run this command?"
                },
                "command": {
                    "type": "string",
                    "description": "The PowerShell command to execute. Can include arguments."
                },
                "returnoutput": {
                    "type": "boolean",
                    "description": "If true, captures and returns the command output. If false, runs the command in a new PowerShell window and checks for errors after 3 seconds.",
                    "default": True
                }
            },
            "required": ["permission", "command"]
        }
    }
},

    {
    "type": "function",
    "function": {
        "name": "youtube_search",
        "description": "Searches YouTube for a specific query and opens the results in a browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query for YouTube."
                }
            },
            "required": ["query"]
        }
    }
},
{
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
},
{
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": "Generates an image using DALL-E based on a given prompt. Optionally, specify a file path to save the image.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A detailed prompt describing the image to generate."
                },
                "save_path": {
                    "type": "string",
                    "description": "Optional. The file path to save the generated image. If not specified, it will be saved in the %temp%/VORTEX directory."
                }
            },
            "required": ["prompt"]
        }
    }
},
{
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
},
{
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
},

    {
    "type": "function",
    "function": {
        "name": "debugmode",
        "description": "Enables or disables debug mode, when debug mode is on, additional information about what tools/functions were used as well as what they returned and what arguments were used gets printed accepts true/false ONLY",
        "parameters": {
            "type": "object",
            "properties": {
                "enable": {
                    "type": "boolean",
                    "description": "Set to true to enable debug mode, false to disable it."
                }
            },
            "required": ["enable"]
        }
    }
    },
    {
        "type": "function",
        "function": {
            "name": "open_link",
            "description": "Opens a URL in the default web browser. AI must not guess URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to open (must start with http:// or https://)."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
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
},
{
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
},

    {
        "type": "function",
        "function": {
            "name": "launch_shortcut",
            "description": "Lauches a program based on whatever name u got from get_shortcuts",
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
    },
    {
        "type": "function",
        "function": {
            "name": "display_markdown",
            "description": "displays markdown to the user, it will open their browser to do so.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The markdown-formatted text to display."
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_info",
            "description": "Retrieves user's geolocation details.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Gets the current time in the user's timezone in ISO 8601 format.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Creates an event in Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Event title."
                    },
                    "start_time": {
                        "type": "string",
                        "description": "ISO 8601 format start time."
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Duration in minutes."
                    }
                },
                "required": ["summary", "start_time"]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "search_query",
        "description": "Searches for a specific wikipidia page, if none exist, then we google it",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up."
                }
            },
            "required": ["query"]
        }
    }
},
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "Lists upcoming events from Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Number of events to fetch."
                    },
                    "time_min": {
                        "type": "string",
                        "description": "Start time filter (ISO 8601)."
                    },
                    "time_max": {
                        "type": "string",
                        "description": "End time filter (ISO 8601)."
                    }
                },
                "required": []
            }
        }
    }
]
