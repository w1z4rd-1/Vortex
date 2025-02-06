import requests
from datetime import datetime, timedelta, timezone
from auth import authorize
from googleapiclient.discovery import build
import subprocess
import os
import tempfile
import markdown
import webbrowser
import wikipediaapi
import json
import glob
wiki_wiki = wikipediaapi.Wikipedia(user_agent="VORTEX", language="en")
debug_mode = False
TOKEN_PATH = "token.json"
GOOGLE_SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY")
GOOGLE_SEARCH_CSE_ID = os.getenv("GOOGLE_SEARCH_CSE_ID")
# Debug mode function
def set_debug_mode(value: bool):
    """Sets the global debug mode."""
    global debug_mode
    debug_mode = value

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
def launch_shortcut(program_name: str):
    """
    Launches a program by name, using the Start Menu shortcuts or custom shortcuts.
    If multiple programs match, it returns a list instead of launching immediately.
    """
    shortcuts = get_start_menu_shortcuts()

    # 🔍 Find matching programs
    matches = {name: path for name, path in shortcuts.items() if program_name.lower() in name.lower()}

    if not matches:
        return f"❌ No program found matching '{program_name}'."

    if len(matches) > 1:
        return f"⚠️ Multiple matches found: {list(matches.keys())}"

    # ✅ Launch the program
    program_path = list(matches.values())[0]
    subprocess.run(["cmd.exe", "/c", "start", "", program_path], shell=True)
    return f"✅ Launched: {program_name}"
# 🗂️ -----------------------------
# Get All Start Menu Shortcuts
# -------------------------------
START_MENU_PATH = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
CUSTOM_SHORTCUTS_FILE = "custom_shortcuts.txt"
def get_start_menu_shortcuts():
    """
    Retrieves all program shortcuts from the Windows Start Menu folder + a custom text file.
    Returns a dictionary with program names and their full paths.
    """
    shortcuts = {}

    # 🔍 Search for .lnk (shortcut) files in Start Menu folders
    for shortcut_path in glob.glob(os.path.join(START_MENU_PATH, "**", "*.lnk"), recursive=True):
        program_name = os.path.splitext(os.path.basename(shortcut_path))[0]
        shortcuts[program_name] = shortcut_path

    # 📄 Load additional shortcuts from custom_shortcuts.txt
    if os.path.exists(CUSTOM_SHORTCUTS_FILE):
        with open(CUSTOM_SHORTCUTS_FILE, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and "=" in line:
                    name, path = line.split("=", 1)
                    shortcuts[name.strip()] = path.strip()

    return shortcuts
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
    
# ---------------------------
# 🔗 FUNCTION REGISTRY FOR OpenAI FUNCTION CALLING
# ---------------------------
function_registry = {
    "open_link": open_link,
    "get_start_menu_shortcuts": get_start_menu_shortcuts,
    "launch_shortcut": launch_shortcut,
    "get_user_info": get_user_info, #based on ip adress HACKKKKERRRR
    "get_time": get_time,
    "create_event": create_event, # use my google calender :>
    "list_events": list_events,
    "display_markdown": display_markdown,
    "search_query": search_query, #use wikipidia and google to find info
    "debugmode": set_debug_mode,
}

function_schemas = [
    {
    "type": "function",
    "function": {
        "name": "debugmode",
        "description": "Enables or disables debug mode, when debug mode is on, additional information about what tools/functions were used as well as what they returned and what arguments were used gets printed",
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
            "name": "get_start_menu_shortcuts",
            "description": "Retrieves a list of all installed programs from the Windows Start Menu and custom shortcuts.",
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
            "name": "launch_shortcut",
            "description": "Launches a program by name using its Start Menu shortcut or a custom-defined shortcut.",
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
