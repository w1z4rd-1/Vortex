import requests
import asyncio
import subprocess
import time
import psutil
import src.Boring.capabilities as capabilities
# API Configuration
API_URL = "http://127.0.0.1:8888"
POLL_INTERVAL = 10  # Check every 5 seconds
TIMEOUT = 180  # Max wait time before timeout
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9222  # Change if needed

def launchChrome():
    """Check if Chrome is already running with remote debugging; if not, launch it."""
    # Check if Chrome is running with debugging
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        if 'chrome' in proc.info['name'].lower():
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == DEBUG_PORT:
                    return
    
    # If not running, launch Chrome with debugging enabled
    cmd = f'start "" "{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT} --new-window'
    subprocess.Popen(cmd, shell=True)
    print("Chrome launched with remote debugging.")
    time.sleep(5)  # Allow time for Chrome to start

async def sendApiRequest(task):
    """Send a request to the FastAPI server if no task is currently running."""
    if await isTaskRunning():
        return "A task is already running. Please wait for it to complete."

    url = f"{API_URL}/run"
    data = {"task": task}
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return "Task started running."
        return f"API Error: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return str(e)

async def getLastResponse():
    """Fetch the latest response from the API."""
    url = f"{API_URL}/lastResponses?limit=1"
    
    try:
        response = requests.get(url)
        if response.status_code == 200 and response.json():
            return response.json()[0]  # Return the latest task record
    except requests.exceptions.RequestException:
        return None

async def isTaskRunning():
    """Check if a task is currently running."""
    taskData = await getLastResponse()
    return taskData and taskData.get("status") == "running"

async def waitForResult():
    """Keep checking the API until the task is completed or timeout occurs."""
    startTime = asyncio.get_event_loop().time()

    while True:
        taskData = await getLastResponse()
        if taskData:
            if taskData.get("status", "unknown") == "completed":
                resultData = taskData.get("result", {})
                history = resultData.get("history", [])

                if history:
                    lastEntry = history[-1]  # Get the last recorded step
                    resultsList = lastEntry.get("result", [])

                    for res in resultsList:
                        if res.get("is_done", False) and "extracted_content" in res:
                            return res["extracted_content"]

                return "No relevant Wikipedia data found."
            
            if taskData.get("status") == "failed":
                return f"Task failed: {taskData.get('error', 'Unknown error')}"

        if asyncio.get_event_loop().time() - startTime > TIMEOUT:
            return "Timeout: Task took too long to complete."

        await asyncio.sleep(POLL_INTERVAL)  # **Wait before checking again**

async def asyncWebSurf(task):
    """Run webSurf asynchronously (send request + wait for result)."""
    launchChrome()
    await sendApiRequest(task)
    return await waitForResult()

def syncWebSurf(task):
    """Run webSurf synchronously (send request only, no waiting)."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If an event loop is already running, run the coroutine in it
        asyncio.ensure_future(sendApiRequest(task))
    else:
        loop.run_until_complete(sendApiRequest(task))
    return "Task started running."




#capabilities.register_function_in_registry("asyncWebSurf", asyncWebSurf)

capabilities.register_function_schema({
    "type": "function",
    "function": {
        "name": "asyncWebSurf",
        "description": "Performs web automation using a browser with human-like interaction.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed instructions for the web automation task."
                }
            },
            "required": ["task"]
        }
    }
})