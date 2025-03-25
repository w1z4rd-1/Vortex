# System-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import os
import sys
import time
import importlib
from dotenv import load_dotenv
import markdown
import webbrowser
from src.Capabilities.debug_mode import get_debug_mode

# ANSI color codes for terminal output
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_RESET = "\033[0m"

def open_link(url: str):
	"""
	Opens a URL in the default web browser.
	
	Parameters:
	- url (str): The URL to open
	
	Returns:
	- str: Success or error message
	"""
	try:
		if not (url.startswith("http://") or url.startswith("https://")):
			url = "https://" + url
		
		webbrowser.open(url)
		return f"✅ Opened {url} in your default browser."
	except Exception as e:
		return f"❌ Error opening link: {e}"

def display_markdown(content: str):
	"""
	Renders markdown content as HTML.
	
	Parameters:
	- content (str): Markdown content to render
	
	Returns:
	- str: HTML representation of the markdown
	"""
	try:
		# Convert markdown to HTML
		html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
		
		# Wrap in basic HTML with light styling
		styled_html = f"""
		<!DOCTYPE html>
		<html>
		<head>
			<meta charset="UTF-8">
			<style>
				body {{
					font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
					line-height: 1.6;
					color: #333;
					max-width: 800px;
					margin: 0 auto;
					padding: 20px;
				}}
				h1, h2, h3, h4, h5, h6 {{
					color: #2c3e50;
					margin-top: 24px;
					margin-bottom: 16px;
				}}
				a {{
					color: #3498db;
					text-decoration: none;
				}}
				a:hover {{
					text-decoration: underline;
				}}
				pre, code {{
					font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
					background-color: #f5f5f5;
					border-radius: 3px;
					padding: 0.2em 0.4em;
				}}
				pre {{
					padding: 16px;
					overflow: auto;
				}}
				pre code {{
					background-color: transparent;
					padding: 0;
				}}
				blockquote {{
					border-left: 4px solid #ddd;
					padding-left: 16px;
					color: #666;
					margin-left: 0;
				}}
				img {{
					max-width: 100%;
				}}
				table {{
					border-collapse: collapse;
					width: 100%;
				}}
				table, th, td {{
					border: 1px solid #ddd;
				}}
				th, td {{
					padding: 10px;
					text-align: left;
				}}
				th {{
					background-color: #f5f5f5;
				}}
			</style>
		</head>
		<body>
			{html_content}
		</body>
		</html>
		"""
		
		# Write to a temporary HTML file
		temp_html_path = os.path.join(os.environ.get("TEMP", "/tmp"), "vortex_markdown.html")
		with open(temp_html_path, "w", encoding="utf-8") as f:
			f.write(styled_html)
		
		# Open in the default browser
		webbrowser.open("file://" + temp_html_path)
		
		return f"✅ Rendered markdown to {temp_html_path} and opened in browser."
	
	except Exception as e:
		return f"❌ Error rendering markdown: {e}"

def read_vortex_code(filename: str, max_file_size: int = 5000):
	"""
	Reads the source code of a VORTEX file or generates a directory tree.
	
	Parameters:
	- filename (str): The name of the file to read or directory to explore
	- max_file_size (int): Maximum file size to read in bytes
	
	Returns:
	- str: File content or directory tree
	"""
	def generate_tree(directory, prefix=""):
		"""Recursively generates a directory tree structure."""
		tree = []
		items = os.listdir(directory)
		items.sort()
		
		for i, item in enumerate(items):
			item_path = os.path.join(directory, item)
			is_last = i == len(items) - 1
			
			# Add current item
			connector = "└── " if is_last else "├── "
			tree.append(f"{prefix}{connector}{item}")
			
			# Recursively process subdirectories
			if os.path.isdir(item_path):
				extension = "    " if is_last else "│   "
				subtree = generate_tree(item_path, prefix + extension)
				tree.extend(subtree)
		
		return tree
	
	try:
		if os.path.isdir(filename):
			# Generate directory tree
			tree = generate_tree(filename)
			tree_str = "\n".join(tree)
			return f"Directory tree for {filename}:\n{tree_str}"
		
		elif os.path.isfile(filename):
			# Check file size
			file_size = os.path.getsize(filename)
			if file_size > max_file_size:
				return f"❌ File is too large ({file_size} bytes). Max size: {max_file_size} bytes."
			
			# Read file content
			with open(filename, "r", encoding="utf-8") as f:
				content = f.read()
			
			return f"Contents of {filename}:\n\n{content}"
		
		else:
			return f"❌ File or directory not found: {filename}"
	
	except Exception as e:
		return f"❌ Error reading file: {e}"

def restart_vortex():
	"""Restarts VORTEX to apply new capabilities and reload memory."""
	print(f"\n{COLOR_RED}[⚠️ WARNING] Restart function was called.{COLOR_RESET}")
	
	# Add a manual confirmation to prevent unexpected restarts
	try:
		confirm = input("Are you sure you want to restart VORTEX? (y/n): ").strip().lower()
		if confirm != 'y':
			print("[✓] Restart cancelled.")
			return False
	except Exception as e:
		print(f"[ERROR] Failed to get confirmation: {e}")
		print("[✓] Restart cancelled.")
		return False
	
	print("[🔄 RESTARTING VORTEX...]")
	# Give the user time to see the restart message
	time.sleep(2)

	# Restart the Python process
	os.execl(sys.executable, sys.executable, *sys.argv)
	
	return True  # This line is never reached but added for completeness

def shutdown_vortex():
	"""Shuts down VORTEX."""
	print("[👋 SHUTTING DOWN VORTEX...]")
	sys.exit(0)

# Register functions and schemas
capabilities.register_function_in_registry("open_link", open_link)
capabilities.register_function_in_registry("display_markdown", display_markdown)
capabilities.register_function_in_registry("read_vortex_code", read_vortex_code)
capabilities.register_function_in_registry("restart_vortex", restart_vortex)
capabilities.register_function_in_registry("shutdown_vortex", shutdown_vortex)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "open_link",
		"description": "Opens a URL in the default web browser.",
		"parameters": {
			"type": "object",
			"properties": {
				"url": {
					"type": "string",
					"description": "The URL to open."
				}
			},
			"required": ["url"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "display_markdown",
		"description": "Renders markdown content as HTML and displays it in the browser.",
		"parameters": {
			"type": "object",
			"properties": {
				"content": {
					"type": "string",
					"description": "Markdown content to render."
				}
			},
			"required": ["content"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "read_vortex_code",
		"description": "Reads the source code of a VORTEX file or generates a directory tree.",
		"parameters": {
			"type": "object",
			"properties": {
				"filename": {
					"type": "string",
					"description": "The name of the file to read or directory to explore."
				},
				"max_file_size": {
					"type": "integer",
					"description": "Maximum file size to read in bytes."
				}
			},
			"required": ["filename"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "restart_vortex",
		"description": "Restarts VORTEX to apply new capabilities and reload memory.",
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
		"name": "shutdown_vortex",
		"description": "Shuts down VORTEX.",
		"parameters": {
			"type": "object",
			"properties": {},
			"required": []
		}
	}
}) 