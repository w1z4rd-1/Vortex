import requests
import json
import src.Boring.capabilities as capabilities # For self-registration
from src.Boring.boring import log_debug_event

APIS_GURU_LIST_URL = "https://api.apis.guru/v2/list.json"

def search_public_apis(keyword: str = None, category: str = None, limit: int = 10):
    """
    Searches for public APIs using the apis.guru directory.
    Results can be filtered by keyword and/or category (category is part of the API ID).

    Args:
        keyword (str, optional): A keyword to search for in API titles or descriptions. Defaults to None.
        category (str, optional): A category to filter by (e.g., 'gov', 'cloud', 'collaboration'). 
                                   This often appears as the first part of the API ID (e.g., 'adyen.com', 'github.com').
                                   Defaults to None.
        limit (int, optional): The maximum number of results to return. Defaults to 10.

    Returns:
        list: A list of dictionaries, each representing an API and its preferred version details.
              Returns an error message string if an issue occurs.
    """
    log_debug_event(f"Searching public APIs with keyword='{keyword}', category='{category}', limit={limit}")
    try:
        response = requests.get(APIS_GURU_LIST_URL, timeout=30)
        response.raise_for_status()  # Raise an exception for HTTP errors
        all_apis = response.json()
    except requests.exceptions.RequestException as e:
        log_debug_event(f"Error fetching API list from apis.guru: {e}", is_error=True)
        return f"Error fetching API list: {e}"
    except json.JSONDecodeError as e:
        log_debug_event(f"Error decoding JSON response from apis.guru: {e}", is_error=True)
        return f"Error decoding API list response: {e}"

    found_apis = []
    for api_id, api_data in all_apis.items():
        if len(found_apis) >= limit:
            break

        # Category filter (checks if api_id starts with the category, common pattern)
        if category:
            main_domain_part = api_id.split(':')[0]
            if not main_domain_part.lower().startswith(category.lower()):
                continue
        
        preferred_version_key = api_data.get("preferred")
        if not preferred_version_key:
            log_debug_event(f"API '{api_id}' has no preferred version, skipping.", is_error=True)
            continue
            
        preferred_version_data = api_data.get("versions", {}).get(preferred_version_key)
        if not preferred_version_data:
            log_debug_event(f"API '{api_id}' preferred version '{preferred_version_key}' data not found, skipping.", is_error=True)
            continue

        info = preferred_version_data.get("info", {})
        title = info.get("title", "")
        description = info.get("description", "")

        # Keyword filter (checks title and description)
        if keyword:
            if not (keyword.lower() in title.lower() or keyword.lower() in description.lower()):
                continue
        
        entry = {
            "id": api_id,
            "title": title,
            "description": description,
            "preferred_version": preferred_version_key,
            "provider": api_id.split('.')[0] if '.' in api_id else api_id,
            "added": api_data.get("added"),
            "swagger_json_url": preferred_version_data.get("swaggerUrl"),
            "swagger_yaml_url": preferred_version_data.get("swaggerYamlUrl")
        }
        found_apis.append(entry)

    if not found_apis:
        return "No APIs found matching your criteria."
        
    log_debug_event(f"Found {len(found_apis)} APIs matching criteria.")
    return found_apis

def get_api_specification(api_id: str, version: str = None):
    """
    Retrieves the OpenAPI/Swagger specification for a given API ID and optionally a specific version.
    If no version is provided, it attempts to get the preferred version's specification.

    Args:
        api_id (str): The ID of the API (e.g., 'github.com', 'adyen.com:AccountService').
        version (str, optional): The specific version of the API to fetch. If None, uses the preferred version.

    Returns:
        dict or str: The OpenAPI specification as a dictionary (if JSON) or string (if YAML/unknown).
                     Returns an error message string if an issue occurs.
    """
    log_debug_event(f"Getting API specification for API ID='{api_id}', version='{version}'")
    try:
        list_response = requests.get(APIS_GURU_LIST_URL, timeout=30)
        list_response.raise_for_status()
        all_apis = list_response.json()
    except requests.exceptions.RequestException as e:
        log_debug_event(f"Error fetching API list for spec retrieval: {e}", is_error=True)
        return f"Error fetching API list to get specification: {e}"
    except json.JSONDecodeError as e:
        log_debug_event(f"Error decoding API list JSON for spec retrieval: {e}", is_error=True)
        return f"Error decoding API list response for spec retrieval: {e}"

    api_data = all_apis.get(api_id)
    if not api_data:
        return f"API with ID '{api_id}' not found in the directory."

    version_to_fetch = version if version else api_data.get("preferred")
    if not version_to_fetch:
        return f"No version specified and no preferred version found for API ID '{api_id}'."

    version_data = api_data.get("versions", {}).get(version_to_fetch)
    if not version_data:
        return f"Version '{version_to_fetch}' not found for API ID '{api_id}'."

    spec_url = version_data.get("swaggerUrl")  # Prefer JSON
    if not spec_url:
        spec_url = version_data.get("swaggerYamlUrl") # Fallback to YAML
    
    if not spec_url:
        return f"No OpenAPI specification URL found for API ID '{api_id}', version '{version_to_fetch}'."

    log_debug_event(f"Fetching specification from URL: {spec_url}")
    try:
        spec_response = requests.get(spec_url, timeout=30)
        spec_response.raise_for_status()
        
        if spec_url.endswith('.json'):
            specification = spec_response.json()
        elif spec_url.endswith(('.yaml', '.yml')):
            log_debug_event("Fetched YAML specification. Returning as text. Consider adding PyYAML for parsing.", is_error=False)
            # Returning dict for consistency with how AI might expect tool output, even if content is text
            return {"format": "yaml", "content": spec_response.text, "message": "YAML content returned as text. Parsing requires PyYAML."}
        else:
            try:
                specification = spec_response.json() # Try JSON by default
            except json.JSONDecodeError:
                log_debug_event("Could not determine spec format from URL, and failed to parse as JSON. Returning as text.", is_error=True)
                return {"format": "unknown", "content": spec_response.text, "message": "Unknown format, returned as text."}

        log_debug_event(f"Successfully fetched and parsed specification for {api_id} v{version_to_fetch}")
        return specification
        
    except requests.exceptions.RequestException as e:
        log_debug_event(f"Error fetching API specification from {spec_url}: {e}", is_error=True)
        return f"Error fetching API specification from {spec_url}: {e}"
    except json.JSONDecodeError as e: 
        log_debug_event(f"Error decoding API specification JSON from {spec_url}: {e}", is_error=True)
        return f"Error decoding API specification JSON from {spec_url}: {e}"

# --- Self-registration ---
try:
    capabilities.register_function_in_registry("search_public_apis", search_public_apis)
    capabilities.register_function_schema({
        "type": "function",
        "function": {
            "name": "search_public_apis",
            "description": "Searches for public APIs using the apis.guru directory. Allows filtering by keyword and category. Useful for finding new APIs to integrate or explore.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "A keyword to search for in API titles or descriptions (e.g., 'weather', 'translation', 'geocoding')."
                    },
                    "category": {
                        "type": "string",
                        "description": "A category to filter by, often part of the API ID (e.g., 'gov', 'cloud', 'collaboration', 'google.com', 'github.com')."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of API results to return. Defaults to 10 if not specified."
                    }
                },
                "required": []
            }
        }
    })

    capabilities.register_function_in_registry("get_api_specification", get_api_specification)
    capabilities.register_function_schema({
        "type": "function",
        "function": {
            "name": "get_api_specification",
            "description": "Retrieves the detailed OpenAPI (Swagger) specification for a specific public API from the apis.guru directory. This specification contains the API's documentation, including endpoints, parameters, and response structures.",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_id": {
                        "type": "string",
                        "description": "The unique ID of the API as found in the search_public_apis results (e.g., 'github.com', 'adyen.com:AccountService')."
                    },
                    "version": {
                        "type": "string",
                        "description": "Optional. The specific version of the API to fetch the specification for (e.g., 'v1', '2.2.0'). If omitted, the preferred version is used."
                    }
                },
                "required": ["api_id"]
            }
        }
    })
    log_debug_event("api_discovery.py: Self-registration of functions and schemas complete.")
except Exception as e:
    log_debug_event(f"api_discovery.py: Error during self-registration: {e}", is_error=True) 