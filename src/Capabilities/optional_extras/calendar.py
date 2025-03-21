# Calendar-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from googleapiclient.discovery import build
import googleapiclient.errors
from src.Google.auth import authorize
import os
from dotenv import load_dotenv
import base64

# Load environment variables
load_dotenv()
TOKEN_PATH = "token.json"

def get_time():
	"""
	Gets the current time in different formats.
	
	Returns:
	- dict: Current time in various formats
	"""
	now = datetime.now()
	utc_now = datetime.now(timezone.utc)
	
	return {
		"time": now.strftime("%I:%M %p"),  # 12-hour format with AM/PM
		"time_24h": now.strftime("%H:%M"),  # 24-hour format
		"date": now.strftime("%B %d, %Y"),  # Full month name, day, year
		"day_of_week": now.strftime("%A"),  # Full weekday name
		"date_iso": now.strftime("%Y-%m-%d"),  # ISO format date
		"datetime_iso": now.strftime("%Y-%m-%d %H:%M:%S"),  # ISO format datetime
		"unix_timestamp": int(now.timestamp()),  # Unix timestamp
		"utc_time": utc_now.strftime("%Y-%m-%d %H:%M:%S %Z"),  # UTC time
		"timezone": datetime.now().astimezone().tzname(),  # Local timezone name
		"timezone_offset": datetime.now().astimezone().strftime("%z")  # Timezone offset
	}

def create_event(summary: str, start_time: str, duration: int = 60) -> dict:
	"""
	Creates a calendar event using Google Calendar API.
	
	Parameters:
	- summary (str): Event title/summary
	- start_time (str): Start time in format YYYY-MM-DD HH:MM
	- duration (int): Event duration in minutes
	
	Returns:
	- dict: Success or error message
	"""
	try:
		# Authorize and build the service
		creds = authorize()
		service = build("calendar", "v3", credentials=creds)
		
		# Parse start time and calculate end time
		start_dt = datetime.fromisoformat(start_time.replace(" ", "T"))
		end_dt = start_dt + timedelta(minutes=duration)
		
		# Format times for Google Calendar API
		start = start_dt.isoformat()
		end = end_dt.isoformat()
		
		event = {
			"summary": summary,
			"start": {
				"dateTime": start,
				"timeZone": "America/Los_Angeles",
			},
			"end": {
				"dateTime": end,
				"timeZone": "America/Los_Angeles",
			},
		}
		
		event = service.events().insert(calendarId="primary", body=event).execute()
		
		return {"status": "success", "message": f"Event created: {event.get('htmlLink')}"}
	
	except Exception as e:
		return {"status": "error", "message": f"Failed to create event: {str(e)}"}

def list_events(max_results=10, time_min=None, time_max=None, order_by="startTime"):
	"""
	Lists upcoming events from Google Calendar.
	
	Parameters:
	- max_results (int): Maximum number of events to return
	- time_min (str): Earliest time to include events from (ISO format)
	- time_max (str): Latest time to include events to (ISO format)
	- order_by (str): Order of events ('startTime' or 'updated')
	
	Returns:
	- dict: List of events or error message
	"""
	try:
		# Authorize and build the service
		creds = authorize()
		service = build("calendar", "v3", credentials=creds)
		
		# Set time constraints
		now = datetime.utcnow()
		
		if not time_min:
			time_min = now.isoformat() + "Z"  # 'Z' indicates UTC time
		
		if not time_max:
			# Default to events in the next 7 days
			time_max = (now + timedelta(days=7)).isoformat() + "Z"
		
		# Get events
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
			return {"status": "success", "message": "No upcoming events found.", "events": []}
		
		# Format events
		formatted_events = []
		for event in events:
			start = event.get("start", {}).get("dateTime")
			if not start:
				start = event.get("start", {}).get("date")
			
			formatted_events.append({
				"summary": event.get("summary", "No title"),
				"start": start,
				"location": event.get("location", "No location"),
				"link": event.get("htmlLink", "")
			})
		
		return {
			"status": "success",
			"message": f"Found {len(formatted_events)} events.",
			"events": formatted_events
		}
	
	except Exception as e:
		return {"status": "error", "message": f"Failed to list events: {str(e)}"}

def read_gmail(count: int = 5):
	"""
	Reads the most recent emails from Gmail.
	
	Parameters:
	- count (int): Number of emails to read
	
	Returns:
	- dict: List of emails or error message
	"""
	try:
		# Authorize and build the service
		creds = authorize()
		service = build("gmail", "v1", credentials=creds)
		
		# Get messages
		results = service.users().messages().list(userId="me", maxResults=count).execute()
		messages = results.get("messages", [])
		
		if not messages:
			return {"status": "success", "message": "No emails found.", "emails": []}
		
		# Format emails
		emails = []
		for message in messages:
			msg = service.users().messages().get(userId="me", id=message["id"]).execute()
			
			# Extract subject and sender from headers
			headers = msg["payload"]["headers"]
			subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No subject")
			sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown sender")
			
			emails.append({
				"id": msg["id"],
				"subject": subject,
				"sender": sender,
				"snippet": msg["snippet"],
				"date": datetime.fromtimestamp(int(msg["internalDate"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
			})
		
		return {
			"status": "success",
			"message": f"Found {len(emails)} emails.",
			"emails": emails
		}
	
	except Exception as e:
		return {"status": "error", "message": f"Failed to read emails: {str(e)}"}

def send_email(to: str, subject: str, body: str):
	"""
	Sends an email using Gmail.
	
	Parameters:
	- to (str): Recipient email address
	- subject (str): Email subject
	- body (str): Email body
	
	Returns:
	- dict: Success or error message
	"""
	try:
		# Authorize and build the service
		creds = authorize()
		service = build("gmail", "v1", credentials=creds)
		
		# Create message
		message = MIMEText(body)
		message["to"] = to
		message["subject"] = subject
		
		# Encode the message
		raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
		
		# Send message
		send_message = service.users().messages().send(userId="me", body={"raw": raw}).execute()
		
		return {"status": "success", "message": f"Email sent. Message ID: {send_message['id']}"}
	
	except Exception as e:
		return {"status": "error", "message": f"Failed to send email: {str(e)}"}

def modify_email(email_id: str, action: str):
	"""
	Modifies an email (mark as read, trash, etc.).
	
	Parameters:
	- email_id (str): The ID of the email to modify
	- action (str): The action to perform (read, unread, trash, untrash)
	
	Returns:
	- dict: Success or error message
	"""
	try:
		# Authorize and build the service
		creds = authorize()
		service = build("gmail", "v1", credentials=creds)
		
		if action.lower() == "read":
			# Remove UNREAD label
			service.users().messages().modify(
				userId="me",
				id=email_id,
				body={"removeLabelIds": ["UNREAD"]}
			).execute()
			return {"status": "success", "message": "Email marked as read."}
		
		elif action.lower() == "unread":
			# Add UNREAD label
			service.users().messages().modify(
				userId="me",
				id=email_id,
				body={"addLabelIds": ["UNREAD"]}
			).execute()
			return {"status": "success", "message": "Email marked as unread."}
		
		elif action.lower() == "trash":
			# Move to trash
			service.users().messages().trash(userId="me", id=email_id).execute()
			return {"status": "success", "message": "Email moved to trash."}
		
		elif action.lower() == "untrash":
			# Remove from trash
			service.users().messages().untrash(userId="me", id=email_id).execute()
			return {"status": "success", "message": "Email removed from trash."}
		
		else:
			return {"status": "error", "message": f"Unknown action: {action}"}
	
	except Exception as e:
		return {"status": "error", "message": f"Failed to modify email: {str(e)}"}

# Register functions and schemas
capabilities.register_function_in_registry("get_time", get_time)
capabilities.register_function_in_registry("create_event", create_event)
capabilities.register_function_in_registry("list_events", list_events)
capabilities.register_function_in_registry("read_gmail", read_gmail)
capabilities.register_function_in_registry("send_email", send_email)
capabilities.register_function_in_registry("modify_email", modify_email)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_time",
		"description": "Gets the current time in different formats.",
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
		"name": "create_event",
		"description": "Creates a calendar event using Google Calendar API.",
		"parameters": {
			"type": "object",
			"properties": {
				"summary": {
					"type": "string",
					"description": "Event title/summary."
				},
				"start_time": {
					"type": "string",
					"description": "Start time in format YYYY-MM-DD HH:MM."
				},
				"duration": {
					"type": "integer",
					"description": "Event duration in minutes."
				}
			},
			"required": ["summary", "start_time"]
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
				"max_results": {
					"type": "integer",
					"description": "Maximum number of events to return."
				},
				"time_min": {
					"type": "string",
					"description": "Earliest time to include events from (ISO format)."
				},
				"time_max": {
					"type": "string",
					"description": "Latest time to include events to (ISO format)."
				},
				"order_by": {
					"type": "string",
					"enum": ["startTime", "updated"],
					"description": "Order of events ('startTime' or 'updated')."
				}
			},
			"required": []
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "read_gmail",
		"description": "Reads the most recent emails from Gmail.",
		"parameters": {
			"type": "object",
			"properties": {
				"count": {
					"type": "integer",
					"description": "Number of emails to read."
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
				"to": {
					"type": "string",
					"description": "Recipient email address."
				},
				"subject": {
					"type": "string",
					"description": "Email subject."
				},
				"body": {
					"type": "string",
					"description": "Email body."
				}
			},
			"required": ["to", "subject", "body"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "modify_email",
		"description": "Modifies an email (mark as read, trash, etc.).",
		"parameters": {
			"type": "object",
			"properties": {
				"email_id": {
					"type": "string",
					"description": "The ID of the email to modify."
				},
				"action": {
					"type": "string",
					"enum": ["read", "unread", "trash", "untrash"],
					"description": "The action to perform."
				}
			},
			"required": ["email_id", "action"]
		}
	}
}) 