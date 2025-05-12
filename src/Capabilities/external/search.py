# Consolidated search functions for VORTEX

import os
import requests
import wikipediaapi
import src.Boring.capabilities as capabilities
from src.Capabilities.debug_mode import get_debug_mode
from src.Boring.boring import log_debug_event
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY")
GOOGLE_SEARCH_CSE_ID = os.getenv("GOOGLE_SEARCH_CSE_ID")

# Initialize Wikipedia API
wiki_wiki = wikipediaapi.Wikipedia(user_agent="VORTEX", language="en")

def search_query(query: str, search_type: str = "google") -> dict:
	"""
	Search for information using Google Search or Wikipedia.
	
	Parameters:
	- query (str): The search query
	- search_type (str): Type of search ('google' or 'wikipedia')
	
	Returns:
	- dict: Search results
	"""
	search_type = search_type.lower()
	
	log_debug_event(f"SEARCH ({search_type.capitalize()}): {query}")
	
	if search_type == "google":
		return google_search(query)
	elif search_type == "wikipedia":
		return wikipedia_search(query)
	else:
		return {"error": f"Invalid search type: {search_type}. Use 'google' or 'wikipedia'."}

def google_search(query: str) -> dict:
	"""
	Performs a Google search and returns formatted results.
	
	Parameters:
	- query (str): The search query
	
	Returns:
	- dict: Google search results
	"""
	if not GOOGLE_SEARCH_KEY or not GOOGLE_SEARCH_CSE_ID:
		return {"error": "Google Search API credentials are missing."}
	
	try:
		url = "https://www.googleapis.com/customsearch/v1"
		params = {
			"key": GOOGLE_SEARCH_KEY,
			"cx": GOOGLE_SEARCH_CSE_ID,
			"q": query,
			"num": 5  # Number of results to return
		}
		
		response = requests.get(url, params=params)
		data = response.json()
		
		if "items" not in data:
			return {"error": "No results found."}
		
		results = []
		for item in data["items"]:
			title = item.get("title", "No Title")
			link = item.get("link", "")
			snippet = item.get("snippet", "No Description").replace("\n", " ")
			results.append(f"{title}\nURL: {link}\n{snippet}\n")
		
		return {"result": "\n".join(results)}
	
	except requests.exceptions.RequestException as e:
		return {"error": f"API request failed: {str(e)}"}

def wikipedia_search(query: str) -> dict:
	"""
	Performs a Wikipedia search and returns page summaries.
	
	Parameters:
	- query (str): The search query
	
	Returns:
	- dict: Wikipedia search results
	"""
	try:
		# Find the closest matching page
		page = wiki_wiki.page(query)
		
		if not page.exists():
			# Try searching for related pages
			search_results = wiki_wiki.opensearch(query, results=3)
			if not search_results:
				return {"error": "No Wikipedia pages found."}
			
			results = []
			for title in search_results:
				page = wiki_wiki.page(title)
				if page.exists():
					summary = page.summary[0:500] + "..." if len(page.summary) > 500 else page.summary
					results.append(f"{title}: {summary}")
			
			return {"result": "\n\n".join(results)}
		
		# Return the summary of the page
		summary = page.summary[0:1000] + "..." if len(page.summary) > 1000 else page.summary
		return {"result": f"{page.title}: {summary}"}
	
	except Exception as e:
		return {"error": f"Wikipedia search failed: {str(e)}"}

def youtube_search(query: str) -> dict:
	"""
	Searches YouTube for the query and returns a direct search URL.
	
	Parameters:
	- query (str): The search query
	
	Returns:
	- dict: YouTube search URL
	"""
	formatted_query = query.replace(" ", "+")
	search_url = f"https://www.youtube.com/results?search_query={formatted_query}"
	return {"result": f"YouTube search results: {search_url}"}

def modrinth_search(query: str) -> dict:
	"""
	Searches Modrinth for Minecraft mods.
	
	Parameters:
	- query (str): The search query
	
	Returns:
	- dict: Modrinth search results
	"""
	try:
		url = f"https://api.modrinth.com/v2/search"
		params = {
			"query": query,
			"limit": 5,
			"facets": [["categories:forge"], ["categories:fabric"]]
		}
		
		response = requests.get(url, params=params)
		data = response.json()
		
		if "hits" not in data or not data["hits"]:
			return {"error": "No mods found on Modrinth."}
		
		results = []
		for mod in data["hits"]:
			mod_id = mod["project_id"]
			title = mod["title"]
			description = mod["description"]
			author = mod["author"]
			downloads = mod["downloads"]
			url = f"https://modrinth.com/mod/{mod_id}"
			
			results.append(f"{title} by {author}\nDownloads: {downloads:,}\nURL: {url}\n{description}\n")
		
		return {"result": "\n".join(results)}
	
	except requests.exceptions.RequestException as e:
		# Fallback to simple URL if API fails
		formatted_query = query.replace(" ", "+")
		search_url = f"https://modrinth.com/mods?q={formatted_query}"
		return {"result": f"Modrinth search results: {search_url}"}

# Register functions and schemas
capabilities.register_function_in_registry("search_query", search_query)
capabilities.register_function_in_registry("youtube_search", youtube_search)
capabilities.register_function_in_registry("modrinth_search", modrinth_search)

# Register schemas
capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "search_query",
		"description": "Search for information using Google Search or Wikipedia.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {
					"type": "string",
					"description": "The search query"
				},
				"search_type": {
					"type": "string",
					"enum": ["google", "wikipedia"],
					"description": "Type of search to perform"
				}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "youtube_search",
		"description": "Search YouTube for videos related to a query.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {
					"type": "string",
					"description": "The search query for YouTube"
				}
			},
			"required": ["query"]
		}
	}
})

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "modrinth_search",
		"description": "Search Modrinth for Minecraft mods.",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {
					"type": "string",
					"description": "The search query for Modrinth"
				}
			},
			"required": ["query"]
		}
	}
}) 