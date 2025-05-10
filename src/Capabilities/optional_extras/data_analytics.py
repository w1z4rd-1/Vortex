import os
import shutil
import json
import datetime
import traceback
import pandas as pd
import openai
import ast
import warnings
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import openpyxl
import xlsxwriter
import src.Boring.capabilities as capabilities
from src.Capabilities.debug_mode import get_debug_mode
from src.Boring.boring import log_debug_event

# Define directories
TEMP_DIR = "temp"
DATA_ANALYSIS_DIR = os.path.join(TEMP_DIR, "data_analysis")
OUTPUT_DIR = os.path.join(DATA_ANALYSIS_DIR, "output")
LOG_DIR = os.path.join(DATA_ANALYSIS_DIR, "logs")

# Ensure necessary directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(DATA_ANALYSIS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Initialize OpenAI client
client = openai.OpenAI()

def clear_temp_folder():
	"""Deletes everything in the temp folder to start fresh."""
	log_debug_event(f"Clearing temp folder: {TEMP_DIR}")

	for folder in [TEMP_DIR, DATA_ANALYSIS_DIR, OUTPUT_DIR, LOG_DIR]:
		if os.path.exists(folder):
			shutil.rmtree(folder)
			log_debug_event(f"Deleted folder: {folder}")
		os.makedirs(folder)
		log_debug_event(f"Recreated empty folder: {folder}")

def log_error(error_message):
	"""Logs errors to a file in UTF-8 encoding."""
	log_file_path = os.path.join(LOG_DIR, "error_log.txt")
	with open(log_file_path, "a", encoding="utf-8") as log_file:
		log_file.write(f"{datetime.datetime.now()} - {error_message}\n")
		log_file.write(traceback.format_exc() + "\n")
	log_debug_event(f"Logged error to file: {error_message}", is_error=True)

def extract_sample_data(file_path):
	"""Reads the first 10 rows of the spreadsheet to provide AI with context."""
	file_extension = os.path.splitext(file_path)[-1].lower()

	log_debug_event(f"Extracting sample data from file: {file_path}")

	try:
		if file_extension == ".csv":
			df = pd.read_csv(file_path, encoding="utf-8", errors="replace")
		elif file_extension in [".xls", ".xlsx"]:
			df = pd.read_excel(file_path, engine="openpyxl")
		else:
			log_error(f"❌ Unsupported file format: {file_extension}")
			return None

		log_debug_event(f"Successfully extracted first 10 rows from {file_path}")
		return df.head(10).to_json(orient="records")
	except Exception as e:
		log_error(f"❌ Failed to extract sample data: {e}")
		return None

def validate_python_code(code):
	"""Checks for syntax errors and warnings in the AI-generated Python code."""
	syntax_error = None
	warnings_list = []

	log_debug_event(f"Validating AI-generated Python code...")

	try:
		ast.parse(code)
	except SyntaxError as e:
		syntax_error = f"Syntax Error: {e}"

	with warnings.catch_warnings(record=True) as warning_messages:
		warnings.simplefilter("always")
		try:
			compile(code, "<string>", "exec")
		except Exception:
			pass

		for warning in warning_messages:
			warnings_list.append(str(warning.message))

	if syntax_error:
		log_debug_event(f"Detected Syntax Error in AI code: {syntax_error}", is_error=True)
	if warnings_list:
		log_debug_event(f"Detected Warnings in AI code: {warnings_list}", is_error=True)

	return syntax_error, warnings_list

def execute_ai_code(ai_code):
	"""Executes the AI-generated Python code in a controlled environment."""
	try:
		exec_globals = {
			"pd": pd,
			"np": np,
			"plt": plt,
			"os": os,
			"shutil": shutil,
			"openpyxl": openpyxl,
			"xlsxwriter": xlsxwriter,
			"sns": sns,
			"OUTPUT_DIR": OUTPUT_DIR
		}
		
		exec(ai_code, exec_globals)
		log_debug_event("Successfully executed AI-generated code")
		return True
	except (TypeError, ValueError) as e:
		log_error(f"❌ Type Error in AI-generated code: {e}")
		return False
	except Exception as e:
		log_error(f"❌ Code execution failed: {e}")
		return False

def generate_ai_code(file_path, instructions):
	"""Uses OpenAI's `o3mini` model to generate intelligent analysis & reformatting code."""
	sample_data = extract_sample_data(file_path)
	if not sample_data:
		return None

	chat_history = [
		{"role": "system", "content": "You are an advanced data analytics expert, you create extremely visually appealing reports."}
	]

	log_debug_event("Sending request to OpenAI for AI-generated code for data analytics...")

	ai_prompt = f"""
	You are an advanced data analytics expert. Your job is to:
	- Generate Python code to analyze the spreadsheet data.
	- Perform complex data analytics using Pandas, NumPy, or Matplotlib.
	- Format the spreadsheet to improve readability and visual appeal if the instructions require it.
	- Save all results in '{OUTPUT_DIR}'.
	- NEVER modify the original spreadsheet. Instead, create a copy and apply changes to the copy.
	- Convert all numerical columns to floats before performing calculations.
	- Use a valid Seaborn colormap (e.g., 'viridis', 'coolwarm', 'magma', 'Blues'). Avoid using 'spectral'.
	- use pivot tables wherever aplicable
	**Guidelines:**
	- The first 10 rows of the spreadsheet are:
	```json
	{sample_data}
	```
	- Follow these user instructions:
	"{instructions}"

	**Output Requirement:**
	- ONLY output Python code. Do NOT include explanations or markdown.
	- NEVER use triple backticks (```).
	- The input file is at '{file_path}'.
	- You have access to `pandas`, `matplotlib`, `seaborn`, `numpy`, `shutil`, `openpyxl`, `xlsxwriter`, `xlrd`, `pyarrow`.

	Now generate the Python code for this:
	"""

	chat_history.append({"role": "user", "content": ai_prompt})

	max_attempts = 7
	reset_history_after = 3

	for attempt in range(max_attempts):
		if attempt == reset_history_after:
			chat_history = [chat_history[0], {"role": "user", "content": ai_prompt}]
			log_debug_event("Resetting conversation history after repeated syntax failures for data_analytics AI code gen.")

		try:
			response = client.chat.completions.create(
				model="gpt-4o",
				messages=chat_history
			)
			ai_code = response.choices[0].message.content.strip()

			log_debug_event(f"AI-generated code for data_analytics received (Attempt {attempt+1}/{max_attempts})")

			ai_code = ai_code.replace("```python", "").replace("```", "").strip()

			if execute_ai_code(ai_code):
				return ai_code
			else:
				log_debug_event("AI-generated code execution failed for data_analytics. Retrying...", is_error=True)

		except Exception as e:
			log_error(f"❌ AI code generation failed: {e}")
			return None

	return "❌ AI failed to generate valid code after multiple attempts."


# ✅ Register the function in VORTEX
capabilities.register_function_in_registry("data_analytics", generate_ai_code)

capabilities.register_function_schema({
	"type": "function",
	"function": {
		"name": "data_analytics",
		"description": "Analyzes spreadsheet data using Python and generates statistical insights, visualizations, and reports.",
		"parameters": {
			"type": "object",
			"properties": {
				"file_path": {"type": "string", "description": "Path to the spreadsheet file for analysis."},
				"instructions": {"type": "string", "description": "Detailed instructions for how the data should be analyzed."}
			},
			"required": ["file_path", "instructions"]
		}
	}
})

print("[✅ FUNCTION REGISTERED] data_analytics is now available.")
