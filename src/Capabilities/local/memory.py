# Memory-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import json
import os
import openai
import numpy as np
import faiss
from dotenv import load_dotenv
from src.Capabilities.debug_mode import get_debug_mode

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MEMORY_FILE = "memory.json"
OPENAI_MODEL = "text-embedding-3-small"

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def retrieve_project_memory(query: str):
	"""Finds relevant memory related to ongoing projects."""
	project_memories = retrieve_memory(query) or []
	created_functions = retrieve_memory("created functions") or []
	return project_memories + created_functions  # ✅ Merge both for better context

def retrieve_memory(query: str):
	"""
	Finds relevant memories based on the query.
	
	Parameters:
	- query (str): The search query to find relevant memories
	
	Returns:
	- list: Relevant memories
	"""
	try:
		if not query:
			return []
		
		if get_debug_mode():
			print(f"[🧠 MEMORY CHECK] Searching for memories related to: {query}")
		
		if not os.path.exists(MEMORY_FILE):
			return []
	
		with open(MEMORY_FILE, "r", encoding="utf-8") as f:
			memory_data = json.load(f)
		
		# Handle the case where memory_data is a dictionary with categories
		if isinstance(memory_data, dict):
			all_memories = []
			for category, memories in memory_data.items():
				if isinstance(memories, list):
					all_memories.extend(memories)
			memory_data = all_memories
		
		if not memory_data:
			return []
	
		# Handle both string-only memories and structured memory items
		memory_texts = []
		for item in memory_data:
			if isinstance(item, dict) and "text" in item:
				memory_texts.append(item["text"])
			elif isinstance(item, str):
				memory_texts.append(item)
		
		if not memory_texts:
			return []
		
		try:
			# Generate embedding for the query
			query_embedding = generate_embedding(query)
			
			# Create FAISS index for memories
			embeddings = []
			for i, item in enumerate(memory_data):
				if isinstance(item, dict) and "embedding" in item:
					embeddings.append(item["embedding"])
				else:
					# Generate embedding for the text
					text = item["text"] if isinstance(item, dict) and "text" in item else item
					embeddings.append(generate_embedding(text))
			
			# Ensure all embeddings have the same dimensionality
			if len(embeddings) > 0:
				embedding_dim = len(embeddings[0])
				index = faiss.IndexFlatL2(embedding_dim)
				index.add(np.array(embeddings).astype('float32'))
				
				# Search for similar memories using cosine similarity
				k = min(5, len(memory_data))  # Return up to 5 results
				_, indices = index.search(np.array([query_embedding]).astype('float32'), k)
				
				# Return found memories
				results = []
				for i in indices[0]:
					if i < len(memory_data):
						item = memory_data[i]
						if isinstance(item, dict) and "text" in item:
							results.append(item["text"])
						elif isinstance(item, str):
							results.append(item)
				return results
			else:
				return []
				
		except Exception as e:
			if get_debug_mode():
				print(f"[❌ MEMORY ERROR] Error searching memories: {e}")
			return []
	
	except Exception as e:
		if get_debug_mode():
			print(f"[❌ MEMORY ERROR] Error reading memories: {e}")
		return []

def store_memory(text: str):
	"""Stores a new memory with its embedding."""
	if not text.strip():
		return "❌ Cannot store empty memory."
	
	try:
		memory_data = []
		if os.path.exists(MEMORY_FILE):
			with open(MEMORY_FILE, "r", encoding="utf-8") as f:
				try:
					memory_data = json.load(f)
				except json.JSONDecodeError:
					memory_data = []
	
		# Generate embedding for the memory
		embedding = generate_embedding(text)
		
		# Add category to the memory
		category = categorize_memory(text)
		
		memory_entry = {
			"text": text,
			"embedding": embedding,
			"category": category
		}
		
		memory_data.append(memory_entry)
		
		with open(MEMORY_FILE, "w", encoding="utf-8") as f:
			json.dump(memory_data, f, ensure_ascii=False)
		
		return f"✅ Memory stored in category: {category}"
	
	except Exception as e:
		print(f"[❌ ERROR] Failed to store memory: {e}")
		return f"❌ Failed to store memory: {e}"

def delete_memory(query: str):
	"""Finds and removes memories matching the query."""
	if not os.path.exists(MEMORY_FILE):
		return "❌ No memory file found."
	
	try:
		with open(MEMORY_FILE, "r", encoding="utf-8") as f:
			memory_data = json.load(f)
		
		initial_count = len(memory_data)
		memory_data = [item for item in memory_data if query.lower() not in item["text"].lower()]
		deleted_count = initial_count - len(memory_data)
		
		with open(MEMORY_FILE, "w", encoding="utf-8") as f:
			json.dump(memory_data, f, ensure_ascii=False)
		
		return f"✅ Deleted {deleted_count} memories matching '{query}'."
	
	except Exception as e:
		return f"❌ Error deleting memories: {e}"

def list_memory_categories():
	"""List all unique memory categories and counts."""
	try:
		if not os.path.exists(MEMORY_FILE):
			return {"error": "No memory file exists."}
		
		with open(MEMORY_FILE, "r", encoding="utf-8") as f:
			memory_data = json.load(f)
		
		categories = {}
		for item in memory_data:
			category = item.get("category", "Uncategorized")
			categories[category] = categories.get(category, 0) + 1
		
		return {"categories": categories}
	
	except Exception as e:
		return {"error": f"Failed to list categories: {e}"}

def categorize_memory(text):
	"""Automatically categorize memory based on content."""
	categories = [
		"System Configuration",
		"Code Snippets", 
		"User Preferences",
		"Project Ideas",
		"Instructions",
		"Contact Information",
		"Learning Resources",
		"Reminders",
		"Notes",
		"Miscellaneous"
	]
	
	# Default category if no match is found
	default_category = "Miscellaneous"
	
	# Simple keyword matching - can be improved with AI categorization
	if any(kw in text.lower() for kw in ["code", "function", "script", "programming", "python", "javascript"]):
		return "Code Snippets"
	elif any(kw in text.lower() for kw in ["prefer", "like", "want", "don't like", "setting"]):
		return "User Preferences"  
	elif any(kw in text.lower() for kw in ["idea", "project", "create", "build", "develop"]):
		return "Project Ideas"
	elif any(kw in text.lower() for kw in ["how to", "instruction", "guide", "tutorial", "steps"]):
		return "Instructions"
	elif any(kw in text.lower() for kw in ["contact", "email", "phone", "address", "person"]):
		return "Contact Information"
	elif any(kw in text.lower() for kw in ["learn", "resource", "article", "book", "video"]):
		return "Learning Resources"
	elif any(kw in text.lower() for kw in ["remind", "remember", "don't forget", "deadline"]):
		return "Reminders"
	elif any(kw in text.lower() for kw in ["config", "system", "setup", "install", "path", "environment"]):
		return "System Configuration"
	elif any(kw in text.lower() for kw in ["note", "think", "thought", "consider"]):
		return "Notes"
	
	return default_category

def generate_embedding(text):
	"""Generate an embedding for the provided text."""
	try:
		response = client.embeddings.create(
			model=OPENAI_MODEL,
			input=text
		)
		return response.data[0].embedding
	except Exception as e:
		print(f"[❌ ERROR] Failed to generate embedding: {e}")
		# Return a zero vector as fallback
		return [0.0] * 1536  # Default embedding dimension for OpenAI

def summarize_category(category_name: str):
	"""Summarize memories in a specific category."""
	try:
		if not os.path.exists(MEMORY_FILE):
			return {"error": "No memory file exists."}
		
		with open(MEMORY_FILE, "r", encoding="utf-8") as f:
			memory_data = json.load(f)
		
		# Filter memories by category
		category_memories = [memory["text"] for memory in memory_data 
							if memory.get("category", "Uncategorized") == category_name]
		
		if not category_memories:
			return {"summary": f"No memories found in category '{category_name}'"}
		
		# If there are too many memories, summarize them
		if len(category_memories) > 5:
			category_text = "\n- ".join(category_memories[:5]) + f"\n...and {len(category_memories)-5} more items."
		else:
			category_text = "\n- ".join(category_memories)
		
		return {"summary": f"Category '{category_name}' contains {len(category_memories)} memories:\n- {category_text}"}
		
	except Exception as e:
		return {"error": f"Failed to summarize category: {e}"}

# Register functions and schemas
capabilities.register_function_in_registry("retrieve_memory", retrieve_memory)
capabilities.register_function_in_registry("retrieve_project_memory", retrieve_project_memory)
capabilities.register_function_in_registry("store_memory", store_memory)
capabilities.register_function_in_registry("delete_memory", delete_memory)
capabilities.register_function_in_registry("list_memory_categories", list_memory_categories)
capabilities.register_function_in_registry("summarize_category", summarize_category)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "retrieve_memory",
		"description": "Finds relevant memories based on the query.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "Search query to find relevant memories."}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "retrieve_project_memory",
		"description": "Finds relevant memories related to ongoing projects.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "Search query to find relevant project memories."}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "store_memory",
		"description": "Stores a new memory with its embedding.",
		"parameters": {
			"type": "object",
			"properties": {
				"text": {"type": "string", "description": "Text content to store as a memory."}
			},
			"required": ["text"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "delete_memory",
		"description": "Finds and removes memories matching the query.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "Text to match for deleting memories."}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "list_memory_categories",
		"description": "Lists all unique memory categories and counts.",
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
		"name": "summarize_category",
		"description": "Summarize memories in a specific category.",
		"parameters": {
			"type": "object",
			"properties": {
				"category_name": {"type": "string", "description": "Name of the category to summarize."}
			},
			"required": ["category_name"]
		}
	}
}) 