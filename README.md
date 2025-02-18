# VORTEX: **Voice Operated Responsive Task Execution Expert**  

---

![VORTEX](https://img.shields.io/badge/VORTEX-Alpha-blue?style=for-the-badge)  
![Python](https://img.shields.io/badge/Built%20with-Python-3776AB?style=for-the-badge&logo=python)  
![AI-Powered](https://img.shields.io/badge/AI-Powered-brightgreen?style=for-the-badge)  

> **"what we do sugest is that the human race might easily permit itself to drift into a possition of such dependance on the mashines that it would have no practicle choice but to accept all the mashine's decisons "**  -The Unabomber

---

## 🌟 **What is VORTEX?**

VORTEX (**Voice Operated Responsive Task Execution Expert**) is an advanced AI assistant designed to process **voice and text commands** with deep system integration. Inspired by J.A.R.V.I.S., it combines **AI, automation, and real-world device control** using:

🚀 **Google Assistant API** - Execute smart queries & control Google services.  
📱 **iOS Shortcuts API** - Send & receive texts, trigger automations remotely.  
🖥 **PowerShell & System Commands** - Direct control over your machine.  
🔗 **Webhooks & HTTP API** - Seamless cross-device automation.  
🎤 **Voice & Text Input** - Use speech or type commands effortlessly.  

---

## ⚡ **Complete Feature List**

✅ **Google Assistant API** - Smart searches, calendar access, automation.  
✅ **iOS Shortcuts API** - Send & receive SMS, trigger device actions remotely.  
✅ **Task Execution** - Runs PowerShell scripts, manages processes.  
✅ **Memory & Context Awareness** - Stores and recalls relevant information.  
✅ **Browser & Web Control** - Opens links, performs searches, automates web tasks.  
✅ **Custom Voice Responses** - AI-powered TTS with emotional tones.  
✅ **Optimized Token Usage** - Intelligent context management for efficiency.  
✅ **Cross-Device Connectivity** - Webhooks & API for remote command execution.  
✅ **Discord Bot Integration** - Execute VORTEX commands via Discord.  
✅ **Secure Execution** - Permission-based system for high-risk operations.  

---

## 🌐 **Seamless iPhone Integration with Shortcuts API**

🔹 **Send & Receive SMS Remotely** – VORTEX can trigger iOS Shortcuts via API to send and receive text messages.  
🔹 **Trigger Any Shortcut from VORTEX** – Automate iPhone actions with a simple API request.  
🔹 **Control HomeKit & Smart Devices** – Use Shortcuts to toggle lights, change settings, or launch apps.  
🔹 **Run iOS Automations from Anywhere** – Even when VORTEX is running on a different machine.  

### **💻 Trigger an iOS Shortcut from VORTEX (Example Code)**
```python
import requests
IFTTT_WEBHOOK_URL = "https://maker.ifttt.com/trigger/vortex_shortcut/with/key/YOUR_IFTTT_KEY"
requests.get(IFTTT_WEBHOOK_URL)
```
This allows VORTEX to **send texts, launch apps, and control iPhone settings** without direct access.  

---

## 🎤 **Google Assistant API: Supercharge VORTEX with Smart AI**

With **Google Assistant API**, VORTEX can:
✅ **Fetch Smart Responses** - Get Google-powered answers and search results.  
✅ **Control Calendar & Tasks** - Add, remove, and modify Google Calendar events.  
✅ **Execute Smart Home Commands** - Control Google Home devices remotely.  
✅ **Retrieve Weather, News, & More** - Get real-time updates on demand.  

### **🔹 Example: Sending a Query to Google Assistant**
```python
import requests
headers = {"Authorization": f"Bearer YOUR_ACCESS_TOKEN", "Content-Type": "application/json"}
data = {"input": {"text": "What's the weather today?"}, "device": {"device_id": "my_device", "device_model_id": "my_model"}}
response = requests.post("https://embeddedassistant.googleapis.com/v1alpha2/converse", headers=headers, json=data)
print(response.json())
```
Now, **VORTEX can speak and act like a real assistant** using Google’s knowledge base! 🤖  

---

## 📁 **Project Structure**
```plaintext
VORTEX/
├── VORTEX.py            # Main execution script
├── voice.py             # Handles speech recognition & TTS
├── boring.py            # Manages OpenAI calls & function execution
├── capabilities.py      # Registers and loads function capabilities
├── functions.py         # Custom tools & system commands
├── auth.py              # Handles authentication (Google APIs)
├── display.py           # Audio-responsive visuals (OpenGL-based)
├── systemprompt.txt     # System prompt for AI personality & rules
└── generated_capabilities.py  # Auto-generated functions for runtime expansion
```

---

## 🎤 **Available Commands**

- `read_gmail` - Fetch unread emails from Gmail.
- `send_email` - Send an email using Gmail.
- `modify_email` - Mark an email as read or delete it.
- `store_memory` - Save information to VORTEX's memory.
- `retrieve_memory` - Retrieve stored memories.
- `send_sms_ios` - Send SMS via iOS Shortcuts API.
- `trigger_shortcut_ios` - Run any iOS Shortcut remotely.
- `google_assistant_query` - Ask Google Assistant API for answers.
- `restart_vortex` - Restart the VORTEX system.
- `shutdown_vortex` - Shut down the assistant.

---

## 🛠 **Planned Features & Development Roadmap**

| Feature                                                      |
| ------------------------------------------------------------ |
| 🚀 **Massive Reorganization & Code Restructuring**           |
| 🔗 **Full Google Assistant API Integration**                 |
| 📱 **Enhanced iOS Shortcut Automations (Advanced Workflows)** |
| 🌍 **Web Automation & Browser Control Improvements**          |
| 🤖 **Expanded AI Memory & Smarter Context Awareness**         |

Stay tuned for more updates! 🎉  

---

## 📝 **License**

VORTEX is **not open-source** and is currently for private use only. All rights reserved by **Wizard1**.  

---

🎤 **"Wake up, VORTEX!"** 💡 The future of AI assistants starts now!
