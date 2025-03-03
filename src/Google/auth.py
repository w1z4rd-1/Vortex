import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ---------------------------
# 🌐 GOOGLE AUTH CONFIG
# ---------------------------
SCOPES = [
	"https://www.googleapis.com/auth/gmail.readonly",  # Read emails
	"https://www.googleapis.com/auth/gmail.send",
	"https://www.googleapis.com/auth/gmail.modify",  # Mark emails as read, delete, etc.
	"https://www.googleapis.com/auth/calendar"
]
CREDENTIALS_PATH = "creds.json"
TOKEN_PATH = "token.json"

# ---------------------------
# 🔄 LOAD SAVED CREDENTIALS
# ---------------------------
def load_saved_credentials():
	"""Loads saved credentials from token.json if they exist."""
	try:
		if os.path.exists(TOKEN_PATH):
			with open(TOKEN_PATH, "r") as token_file:
				creds_data = json.load(token_file)
				return Credentials.from_authorized_user_info(creds_data, SCOPES)
		return None  # No saved credentials found
	except Exception as e:
		print(f"⚠️ Error loading saved credentials: {e}")
		return None

# ---------------------------
# 💾 SAVE NEW CREDENTIALS
# ---------------------------
def save_credentials(creds):
	"""Saves credentials to token.json after successful authentication."""
	try:
		creds_data = {
			"token": creds.token,
			"refresh_token": creds.refresh_token,
			"token_uri": creds.token_uri,
			"client_id": creds.client_id,
			"client_secret": creds.client_secret,
			"scopes": creds.scopes
		}
		with open(TOKEN_PATH, "w") as token_file:
			json.dump(creds_data, token_file)
		print("✅ Credentials saved successfully.")
	except Exception as e:
		print(f"⚠️ Error saving credentials: {e}")

# ---------------------------
# 🔑 AUTHORIZE & GET CREDENTIALS
# ---------------------------
def authorize():
	"""Handles Google OAuth2 authorization flow."""
	creds = load_saved_credentials()

	if creds and creds.valid:
		print("🔓 Loaded existing credentials.")
		return creds
	elif creds and creds.expired and creds.refresh_token:
		try:
			creds.refresh(Request())
			save_credentials(creds)
			print("🔄 Refreshed expired credentials.")
			return creds
		except Exception as e:
			print(f"⚠️ Error refreshing credentials: {e}")

	print("🔑 No valid credentials found. Starting OAuth flow...")
	flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
	creds = flow.run_local_server(port=0)

	save_credentials(creds)
	return creds

# ---------------------------
# 🛠️ TESTING AUTH (Optional)
# ---------------------------
if __name__ == "__main__":
	creds = authorize()
	if creds:
		print("✅ Google OAuth2 Authentication Successful!")
	else:
		print("❌ Authentication failed.")
