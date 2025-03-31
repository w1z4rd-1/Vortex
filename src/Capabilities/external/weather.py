# Weather-related functions extracted from ALL_Default_capabilities.py

import src.Boring.capabilities as capabilities
import requests
from datetime import datetime
from src.Capabilities.debug_mode import get_debug_mode

def get_weather_forecast(latitude: float, longitude: float, forecast_type: str, timezone="auto"):
	"""
	Gets weather forecast for a specific location.
	
	Parameters:
	- latitude (float): Latitude of the location
	- longitude (float): Longitude of the location
	- forecast_type (str): Type of forecast (current, hourly, daily)
	- timezone (str): Timezone for the forecast data (default: auto)
	
	Returns:
	- dict: Weather forecast information
	"""
	url = "https://api.open-meteo.com/v1/forecast"
	
	params = {
		"latitude": latitude,
		"longitude": longitude,
		"timezone": timezone,
		"temperature_unit": "fahrenheit",
		"windspeed_unit": "mph",
		"precipitation_unit": "inch"
	}
	
	if forecast_type.lower() == "current":
		params.update({
			"current": ",".join([
				"temperature_2m",
				"relative_humidity_2m",
				"apparent_temperature",
				"is_day",
				"precipitation",
				"rain",
				"showers",
				"snowfall",
				"weather_code",
				"cloud_cover",
				"pressure_msl",
				"surface_pressure",
				"wind_speed_10m",
				"wind_direction_10m",
				"wind_gusts_10m"
			])
		})
	
	elif forecast_type.lower() == "hourly":
		params.update({
			"hourly": ",".join([
				"temperature_2m",
				"relative_humidity_2m",
				"apparent_temperature",
				"precipitation_probability",
				"precipitation",
				"weather_code",
				"cloud_cover",
				"visibility",
				"wind_speed_10m",
				"wind_direction_10m",
				"wind_gusts_10m",
				"uv_index",
				"is_day"
			]),
			"forecast_hours": 24  # Next 24 hours
		})
	
	elif forecast_type.lower() == "daily":
		params.update({
			"daily": ",".join([
				"weather_code",
				"temperature_2m_max",
				"temperature_2m_min",
				"apparent_temperature_max",
				"apparent_temperature_min",
				"sunrise",
				"sunset",
				"uv_index_max",
				"precipitation_sum",
				"precipitation_hours",
				"precipitation_probability_max",
				"wind_speed_10m_max",
				"wind_gusts_10m_max",
				"wind_direction_10m_dominant"
			]),
			"forecast_days": 7  # Next 7 days
		})
	
	else:
		return {"error": f"Invalid forecast type: {forecast_type}. Use 'current', 'hourly', or 'daily'."}
	
	try:
		response = requests.get(url, params=params)
		response.raise_for_status()
		data = response.json()
		
		if forecast_type.lower() == "current":
			# Format current weather data
			current = data.get("current", {})
			if not current:
				return {"error": "No current weather data available."}
			
			weather_code = current.get("weather_code")
			weather_description = interpret_weather_code(weather_code)
			
			return {
				"temperature": f"{current.get('temperature_2m')}°F",
				"feels_like": f"{current.get('apparent_temperature')}°F",
				"humidity": f"{current.get('relative_humidity_2m')}%",
				"wind_speed": f"{current.get('wind_speed_10m')} mph",
				"wind_direction": f"{current.get('wind_direction_10m')}°",
				"pressure": f"{current.get('surface_pressure')} hPa",
				"cloud_cover": f"{current.get('cloud_cover')}%",
				"precipitation": f"{current.get('precipitation')} in",
				"weather": weather_description,
				"is_day": bool(current.get("is_day")),
				"units": {
					"temperature": "°F",
					"wind_speed": "mph",
					"precipitation": "in"
				}
			}
		
		elif forecast_type.lower() == "hourly":
			return format_hourly_forecast(data)
		
		elif forecast_type.lower() == "daily":
			return format_daily_forecast(data)
	
	except requests.exceptions.RequestException as e:
		return {"error": f"API request failed: {str(e)}"}
	except Exception as e:
		return {"error": f"Error processing weather data: {str(e)}"}

def format_hourly_forecast(data):
	"""
	Formats hourly forecast data from Open-Meteo API.
	
	Parameters:
	- data (dict): Raw API response data
	
	Returns:
	- dict: Formatted hourly forecast
	"""
	hourly = data.get("hourly", {})
	if not hourly:
		return {"error": "No hourly forecast data available."}
	
	time_data = hourly.get("time", [])
	forecast_hours = []
	
	for i in range(min(24, len(time_data))):
		hour_data = {
			"time": datetime.fromisoformat(time_data[i]).strftime("%I %p"),
			"temperature": f"{hourly.get('temperature_2m', [])[i]}°F",
			"feels_like": f"{hourly.get('apparent_temperature', [])[i]}°F",
			"humidity": f"{hourly.get('relative_humidity_2m', [])[i]}%",
			"precipitation_prob": f"{hourly.get('precipitation_probability', [])[i]}%",
			"precipitation": f"{hourly.get('precipitation', [])[i]} in",
			"weather": interpret_weather_code(hourly.get('weather_code', [])[i]),
			"wind_speed": f"{hourly.get('wind_speed_10m', [])[i]} mph",
			"is_day": bool(hourly.get("is_day", [])[i])
		}
		forecast_hours.append(hour_data)
	
	return {
		"forecast_type": "hourly",
		"forecast": forecast_hours,
		"units": {
			"temperature": "°F",
			"wind_speed": "mph",
			"precipitation": "in"
		}
	}

def format_daily_forecast(data):
	"""
	Formats daily forecast data from Open-Meteo API.
	
	Parameters:
	- data (dict): Raw API response data
	
	Returns:
	- dict: Formatted daily forecast
	"""
	daily = data.get("daily", {})
	if not daily:
		return {"error": "No daily forecast data available."}
	
	time_data = daily.get("time", [])
	forecast_days = []
	
	for i in range(min(7, len(time_data))):
		day_data = {
			"date": datetime.fromisoformat(time_data[i]).strftime("%A, %b %d"),
			"high": f"{daily.get('temperature_2m_max', [])[i]}°F",
			"low": f"{daily.get('temperature_2m_min', [])[i]}°F",
			"feels_like_high": f"{daily.get('apparent_temperature_max', [])[i]}°F",
			"feels_like_low": f"{daily.get('apparent_temperature_min', [])[i]}°F",
			"sunrise": datetime.fromisoformat(daily.get('sunrise', [])[i]).strftime("%I:%M %p"),
			"sunset": datetime.fromisoformat(daily.get('sunset', [])[i]).strftime("%I:%M %p"),
			"precipitation_prob": f"{daily.get('precipitation_probability_max', [])[i]}%",
			"precipitation_sum": f"{daily.get('precipitation_sum', [])[i]} in",
			"precipitation_hours": daily.get('precipitation_hours', [])[i],
			"wind_speed": f"{daily.get('wind_speed_10m_max', [])[i]} mph",
			"wind_gusts": f"{daily.get('wind_gusts_10m_max', [])[i]} mph",
			"weather": interpret_weather_code(daily.get('weather_code', [])[i]),
			"uv_index": daily.get('uv_index_max', [])[i]
		}
		forecast_days.append(day_data)
	
	return {
		"forecast_type": "daily",
		"forecast": forecast_days,
		"units": {
			"temperature": "°F",
			"wind_speed": "mph",
			"precipitation": "in"
		}
	}

def interpret_weather_code(code):
	"""
	Converts WMO weather code to human-readable description.
	
	Parameters:
	- code (int): WMO weather code
	
	Returns:
	- str: Human-readable weather description
	"""
	weather_codes = {
		0: "Clear sky",
		1: "Mainly clear",
		2: "Partly cloudy",
		3: "Overcast",
		45: "Fog",
		48: "Depositing rime fog",
		51: "Light drizzle",
		53: "Moderate drizzle",
		55: "Dense drizzle",
		56: "Light freezing drizzle",
		57: "Dense freezing drizzle",
		61: "Slight rain",
		63: "Moderate rain",
		65: "Heavy rain",
		66: "Light freezing rain",
		67: "Heavy freezing rain",
		71: "Slight snow fall",
		73: "Moderate snow fall",
		75: "Heavy snow fall",
		77: "Snow grains",
		80: "Slight rain showers",
		81: "Moderate rain showers",
		82: "Violent rain showers",
		85: "Slight snow showers",
		86: "Heavy snow showers",
		95: "Thunderstorm",
		96: "Thunderstorm with slight hail",
		99: "Thunderstorm with heavy hail"
	}
	
	return weather_codes.get(code, "Unknown")

# Register functions and schemas
capabilities.register_function_in_registry("get_weather_forecast", get_weather_forecast)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "get_weather_forecast",
		"description": "Gets weather forecast for a specific location, to get the users location, use get_user_info first",
		"parameters": {
			"type": "object",
			"properties": {
				"latitude": {
					"type": "number",
					"description": "Latitude of the location."
				},
				"longitude": {
					"type": "number",
					"description": "Longitude of the location."
				},
				"forecast_type": {
					"type": "string",
					"description": "Type of forecast: 'current', 'hourly', or 'daily'."
				},
				"timezone": {
					"type": "string",
					"description": "Timezone for the forecast data (default: auto)."
				}
			},
			"required": ["latitude", "longitude", "forecast_type"]
		}
	}
}) 