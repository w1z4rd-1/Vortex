import os
import subprocess
import src.Boring.capabilities as capabilities
def wget(url: str) -> str:
    """
    Downloads content from the specified URL using wget, saves it in 'temp/wget/',
    and returns a preview of the contents.

    Parameters:
    - url (str): The URL from where the content will be downloaded.

    Returns:
    - str: Preview of the downloaded HTML content (capped for reasonable length).
    """
    try:
        temp_dir = os.path.join("temp", "wget")
        os.makedirs(temp_dir, exist_ok=True)  # Ensure the directory exists

        output_file = os.path.join(temp_dir, "downloaded_page.html")

        # Run wget command directly using subprocess
        command = ["wget", "-O", output_file, url]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            return f"❌ wget error: {result.stderr}"

        # Read and return contents, capping length
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(5000)  # Cap the length to avoid excessive output
            return content + ("\n\n⚠️ Content truncated..." if len(content) == 5000 else "")
        else:
            return "❌ Failed to download content or file not found."
    except Exception as e:
        return f'Error executing wget: {str(e)}'

capabilities.register_function_in_registry('wget_execution_revised', wget)
capabilities.register_function_schema({
    "type": "function",
    "function": {
        "name": "wget",
        "description": "Downloads content from the specified URL using wget and saves it in 'temp/wget/'.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL from where the content will be downloaded."}
            },
            "required": ["url"]
        }
    }
})