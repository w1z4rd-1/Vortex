# Utility functions for VORTEX

import os
import src.Boring.capabilities as capabilities
from src.Capabilities.debug_mode import get_debug_mode
import json
import openai
from dotenv import load_dotenv
import numpy as np
import faiss
import platform
import re
import sys
import subprocess

# Import existing functions if they're registered elsewhere
try:
    from src.Capabilities.local.powershell import powershell
    _has_powershell = True
except ImportError:
    _has_powershell = False

try:
    from src.Capabilities.local.capability_manager import add_new_capability
    _has_capability_manager = True
except ImportError:
    _has_capability_manager = False

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = "text-embedding-3-small"

def generate_embedding(text):
    """Creates an embedding vector for the provided text using OpenAI's API."""
    try:
        response = client.embeddings.create(
            model=OPENAI_MODEL,
            input=text.replace("\n", " ")
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Embedding error: {e}")
        return None

# Only register functions that aren't imported from elsewhere
capabilities.register_function_in_registry("generate_embedding", generate_embedding)

# Only register powershell if not already registered
if not _has_powershell:
    # Define powershell function here
    def powershell(permission: bool = False, command: str = "", returnoutput: bool = True) -> str:
        """
        Executes a PowerShell command, but only if it's safe or the user has given permission.
        
        Parameters:
        - permission (bool): Whether the user has explicitly granted permission for this command
        - command (str): The PowerShell command to execute
        - returnoutput (bool): Whether to return the command's output
        
        Returns:
        - str: Command output or status message
        """
        # Function implementation
        # ...
        pass
    
    # Register powershell
    capabilities.register_function_in_registry("powershell", powershell)
    
    # Register schema
    capabilities.register_function_schema({
        "type": "function",
        "function": {
            "name": "powershell",
            "description": "Executes a PowerShell command. Some commands require explicit permission for security reasons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "permission": {
                        "type": "boolean",
                        "description": "Whether the user has explicitly granted permission for this command."
                    },
                    "command": {
                        "type": "string", 
                        "description": "The PowerShell command to execute."
                    },
                    "returnoutput": {
                        "type": "boolean",
                        "description": "Whether to return command output (true) or run in a new window (false)."
                    }
                },
                "required": ["command"]
            }
        }
    })

# Only register add_new_capability if not already registered
if not _has_capability_manager:
    # Define add_new_capability function here
    def add_new_capability(function_name: str, function_code: str) -> str:
        """
        Dynamically adds a new capability (function) to VORTEX.
        
        Parameters:
        - function_name (str): Name of the function to add
        - function_code (str): Python code for the function
        
        Returns:
        - str: Success or error message
        """
        # Function implementation
        # ...
        pass
    
    # Register add_new_capability
    capabilities.register_function_in_registry("add_new_capability", add_new_capability)
    
    # Register schema
    capabilities.register_function_schema({
        "type": "function",
        "function": {
            "name": "add_new_capability",
            "description": "Dynamically adds a new capability (function) to VORTEX.",
            "parameters": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the function to add."
                    },
                    "function_code": {
                        "type": "string",
                        "description": "Python code for the function, following the capability creation guidelines."
                    }
                },
                "required": ["function_name", "function_code"]
            }
        }
    }) 