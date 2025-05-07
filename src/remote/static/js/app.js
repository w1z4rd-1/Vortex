/**
 * VORTEX Web Interface
 * Main application JavaScript file
 */

// Global variables
let audioRecorder = null;
let selectedMicrophone = null;
let wakeWordDetector = null;
let socket = null;
let isListening = false;
let isWakeWordActive = false; // Changed to false by default - wake word disabled
let isSpeechEnabled = true;
let audioContext = null;
let audioQueue = [];
let isProcessingAudio = false;
let recognition = null;
let wakeWordModel = null;

// DOM Elements
const conversationElement = document.getElementById('conversation');
const userInputElement = document.getElementById('userInput');
const sendButtonElement = document.getElementById('sendButton');
const micButtonElement = document.getElementById('micButton');
const debugLogElement = document.getElementById('debugLog');
const wakeWordToggleElement = document.getElementById('wakeWordToggle');
const speechToggleElement = document.getElementById('speechToggle');
const microphoneSelectElement = document.getElementById('microphones');
const visualizerElement = document.getElementById('audioVisualizer');
const enableMicButtonElement = document.getElementById('enableMicButton');
const micInitPromptElement = document.getElementById('mic-init-prompt');
const micStatusElement = document.getElementById('mic-status');
const openaiVoiceSelectorContainerElement = document.getElementById('openaiVoiceSelectorContainer');
const openaiVoiceSelectElement = document.getElementById('openaiVoiceSelect');

// Constants
const WAKE_WORD = 'vortex';
const MAX_RECORDING_TIME = 15000; // 15 seconds
const WAKE_WORD_SENSITIVITY = 0.7; // 0-1 range

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeApplication();
});

/**
 * Initialize the application
 */
async function initializeApplication() {
    try {
        // Setup event listeners (including the new mic button)
        setupEventListeners();
        
        // Initialize Socket.io
        initializeSocketConnection();
        
        // Display welcome message
        addMessageToChatWindow('Welcome to VORTEX Voice Assistant!', 'assistant');
        logDebug('VORTEX Web Interface initialized');
        logDebug('Click "Enable Microphone" to grant permission.');
        
        // Check health of backend server
        await checkServerHealth();
        
        // Disable wake word toggle
        wakeWordToggleElement.checked = false;
        wakeWordToggleElement.disabled = true;
        logDebug('Wake word detection is disabled in this version');
    } catch (error) {
        console.error('Error initializing application:', error);
        logDebug('Error initializing: ' + error.message, true);
    }
}

/**
 * Setup event listeners for UI elements
 */
function setupEventListeners() {
    // Send button
    sendButtonElement.addEventListener('click', handleSendButtonClick);
    
    // User input - send on Enter key (but allow Shift+Enter for newlines)
    userInputElement.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleSendButtonClick();
        }
    });
    
    // Microphone button (for recording)
    micButtonElement.addEventListener('click', toggleRecording);
    
    // Enable Microphone button (for permission)
    enableMicButtonElement.addEventListener('click', requestMicrophoneAccess);

    // Wake word toggle - kept as legacy code but functionally disabled
    wakeWordToggleElement.addEventListener('change', (event) => {
        // Always keep wake word disabled regardless of toggle
        isWakeWordActive = false;
        event.target.checked = false;
        logDebug('Wake word detection is disabled in this version');
    });
    
    // Speech toggle
    speechToggleElement.addEventListener('change', (event) => {
        isSpeechEnabled = event.target.checked;
        logDebug(`Speech output ${isSpeechEnabled ? 'enabled' : 'disabled'}`);
    });
    
    // Handle window close/unload to clean up
    window.addEventListener('beforeunload', () => {
        if (audioRecorder) {
            audioRecorder.destroy();
        }
        if (socket) {
            socket.disconnect();
        }
    });
}

/**
 * Initialize Socket.io connection
 */
function initializeSocketConnection() {
    socket = io();
    
    socket.on('connect', () => {
        logDebug('Connected to server');
    });
    
    socket.on('disconnect', () => {
        logDebug('Disconnected from server');
    });
    
    socket.on('transcription', (data) => {
        addMessageToChatWindow(data.text, 'user');
    });
    
    socket.on('response', (data) => {
        addMessageToChatWindow(data.text, 'assistant');
        if (isSpeechEnabled) {
            speakText(data.text);
        }
    });
    
    socket.on('status', (data) => {
        logDebug(`Status: ${data.status}`);
    });
    
    socket.on('error', (data) => {
        logDebug(`Error: ${data.message}`, true);
    });
}

/**
 * Request microphone access and initialize setup upon user click
 */
async function requestMicrophoneAccess() {
    logDebug('Attempting to enable microphone...');
    micStatusElement.textContent = 'Requesting permission...';
    enableMicButtonElement.disabled = true; // Disable button while attempting

    try {
        // Check if browser supports getUserMedia
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Your browser does not support microphone access');
        }
        
        // Request access to microphone
        const userMediaPromise = new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Microphone access timed out. Please check your browser permissions.'));
            }, 10000); // 10 second timeout
            
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then((stream) => {
                    clearTimeout(timeout);
                    resolve(stream);
                })
                .catch((error) => {
                    clearTimeout(timeout);
                    // Provide more specific error messages
                    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                        reject(new Error('Microphone permission denied. Please allow access in browser settings.'));
                    } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                        reject(new Error('No microphone found. Please ensure a microphone is connected and enabled.'));
                    } else {
                        reject(error);
                    }
                });
        });
        
        const stream = await userMediaPromise;
        logDebug('Microphone access granted.');
        micStatusElement.textContent = 'Access granted!';
        micInitPromptElement.style.display = 'none'; // Hide the prompt button section

        // Get available microphones and populate UI
        await populateMicrophoneList(stream);
        
        return true;
    } catch (error) {
        logDebug(`Microphone access error: ${error.message}`, true);
        micStatusElement.textContent = `Error: ${error.message}`; 
        micStatusElement.style.color = 'var(--error-color)';
        enableMicButtonElement.disabled = false; // Re-enable button on error
        // No need for the retry button logic here anymore, the main button serves that purpose
        return false;
    }
}

/**
 * Populate microphone list and setup the default recorder
 * @param {MediaStream} stream - The initial media stream from getUserMedia
 */
async function populateMicrophoneList(stream) {
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const microphones = devices.filter(device => device.kind === 'audioinput');
        
        if (microphones.length === 0) {
            throw new Error('No microphones found after permission grant.');
        }
        
        logDebug(`Found ${microphones.length} microphone(s)`);
        
        // Get the container and display it
        const microphoneContainer = document.getElementById('microphones');
        microphoneContainer.innerHTML = ''; // Clear previous content (if any)
        microphoneContainer.style.display = 'flex'; // Show the radio group
        
        microphones.forEach((mic, index) => {
            const micName = mic.label || `Microphone ${index + 1}`;
            const radioId = `mic-${mic.deviceId}`;
            
            const label = document.createElement('label');
            label.className = 'radio-label';
            
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = 'microphone';
            radio.id = radioId;
            radio.value = mic.deviceId;
            radio.checked = index === 0; // Default to first microphone
            
            radio.addEventListener('change', () => {
                if (radio.checked) {
                    selectMicrophone(mic.deviceId);
                }
            });
            
            const textNode = document.createElement('span'); // Wrap text for styling
            textNode.textContent = micName;

            label.appendChild(radio);
            label.appendChild(textNode); // Append the span
            microphoneContainer.appendChild(label);
        });
        
        // Set default microphone
        selectedMicrophone = microphones[0].deviceId;
        
        // Initialize audio recorder with default microphone stream
        await initializeAudioRecorder(stream);
        logDebug(`Initialized recorder with default microphone: ${selectedMicrophone}`);

    } catch(error) {
        logDebug(`Error populating microphone list: ${error.message}`, true);
        micStatusElement.textContent = `Error setting up microphones: ${error.message}`;
        micStatusElement.style.color = 'var(--error-color)';
    }
}

/**
 * Initialize Audio Recorder with the specified stream
 * @param {MediaStream} stream - Microphone media stream
 */
async function initializeAudioRecorder(stream) {
    // Clean up existing recorder if any
    if (audioRecorder) {
        audioRecorder.destroy();
    }
    
    // Create new recorder
    audioRecorder = new AudioRecorder({
        visualizer: visualizerElement,
        onRecordingStart: () => {
            micButtonElement.classList.add('recording');
            logDebug('Recording started');
        },
        onRecordingStop: (blob) => {
            micButtonElement.classList.remove('recording');
            logDebug(`Recording stopped (${Math.round(blob.size / 1024)} KB)`);
        },
        onDataAvailable: (chunk) => {
            // Optional: handle streaming chunks in real-time
        }
    });
    
    await audioRecorder.init(stream);
}

/**
 * Select a different microphone
 * @param {string} deviceId - Device ID of the microphone to use
 */
async function selectMicrophone(deviceId) {
    if (deviceId === selectedMicrophone) return;
    
    try {
        // Stop current recording if active
        if (audioRecorder && audioRecorder.isRecording) {
            await audioRecorder.stopRecording();
        }
        
        // Get stream from selected microphone
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                deviceId: { exact: deviceId }
            }
        });
        
        selectedMicrophone = deviceId;
        
        // Initialize recorder with new stream
        await initializeAudioRecorder(stream);
        
        logDebug(`Switched to microphone: ${deviceId}`);
    } catch (error) {
        logDebug(`Error switching microphone: ${error.message}`, true);
    }
}

/**
 * Start wake word detection - LEGACY CODE, NOT ACTIVE
 */
function startWakeWordDetection() {
    // This function is kept for legacy purposes but is not used
    // Wake word detection is disabled in the web interface
    return;
}

/**
 * Stop wake word detection - LEGACY CODE, NOT ACTIVE
 */
function stopWakeWordDetection() {
    // This function is kept for legacy purposes but is not used
    if (recognition) {
        recognition.stop();
        recognition = null;
    }
}

/**
 * Toggle recording state
 */
async function toggleRecording() {
    if (!audioRecorder) {
        logDebug('Audio recorder not initialized', true);
        return;
    }
    
    try {
        if (audioRecorder.isRecording) {
            // Stop recording
            const audioBlob = await audioRecorder.stopRecording();
            isListening = false;
            
            if (audioBlob) {
                // Create a form for sending the audio
                const formData = new FormData();
                formData.append('audio', audioBlob);
                
                // Show processing state
                addMessageToChatWindow('Processing...', 'system');
                
                // Send audio to server
                const response = await fetch('/api/audio', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to process audio');
                }
                
                const data = await response.json();
                
                // Remove processing message
                removeLastMessage();
                
                // Add transcription and response to chat
                if (data.transcription) {
                    addMessageToChatWindow(data.transcription, 'user');
                }
                
                if (data.response) {
                    addMessageToChatWindow(data.response, 'assistant');
                    
                    if (isSpeechEnabled) {
                        speakText(data.response);
                    }
                }
            }
        } else {
            // Start recording
            await audioRecorder.startRecording();
            isListening = true;
            
            // Stop after MAX_RECORDING_TIME if not stopped manually
            setTimeout(() => {
                if (audioRecorder && audioRecorder.isRecording) {
                    logDebug('Recording timed out after ' + (MAX_RECORDING_TIME / 1000) + ' seconds');
                    toggleRecording();
                }
            }, MAX_RECORDING_TIME);
        }
    } catch (error) {
        logDebug(`Recording error: ${error.message}`, true);
    }
}

/**
 * Handle send button click - process text input
 */
async function handleSendButtonClick() {
    const text = userInputElement.value.trim();
    
    if (!text) return;
    
    // Clear input
    userInputElement.value = '';
    
    // Add user message to chat
    addMessageToChatWindow(text, 'user');
    
    try {
        // Send text to server
        const response = await fetch('/api/text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to process message');
        }
        
        const data = await response.json();
        
        // Add response to chat
        if (data.response) {
            addMessageToChatWindow(data.response, 'assistant');
            
            if (isSpeechEnabled) {
                speakText(data.response);
            }
        }
    } catch (error) {
        logDebug(`Error sending message: ${error.message}`, true);
        addMessageToChatWindow('Error: ' + error.message, 'system');
    }
}

/**
 * Add a message to the chat window
 * @param {string} text - Message text
 * @param {string} role - Message role ('user', 'assistant', or 'system')
 */
function addMessageToChatWindow(text, role) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}-message`;
    
    let formattedText = text;
    
    // Add message timestamp
    const timestamp = document.createElement('div');
    timestamp.className = 'message-timestamp';
    timestamp.textContent = new Date().toLocaleTimeString();
    
    messageElement.innerHTML = formattedText;
    messageElement.appendChild(timestamp);
    
    // Add to conversation
    conversationElement.appendChild(messageElement);
    
    // Scroll to bottom
    conversationElement.scrollTop = conversationElement.scrollHeight;
}

/**
 * Remove the last message from the chat window
 */
function removeLastMessage() {
    const messages = conversationElement.getElementsByClassName('message');
    if (messages.length > 0) {
        messages[messages.length - 1].remove();
    }
}

/**
 * Log a debug message
 * @param {string} message - Debug message
 * @param {boolean} isError - Whether this is an error message
 */
function logDebug(message, isError = false) {
    const logItem = document.createElement('div');
    logItem.className = isError ? 'log-error' : 'log-info';
    
    const timestamp = new Date().toLocaleTimeString();
    logItem.textContent = `[${timestamp}] ${message}`;
    
    // Add to debug log
    debugLogElement.appendChild(logItem);
    
    // Scroll to bottom
    debugLogElement.scrollTop = debugLogElement.scrollHeight;
    
    // Also log to console
    if (isError) {
        console.error(message);
    } else {
        console.log(message);
    }
}

/**
 * Check the health of the backend server
 */
async function checkServerHealth() {
    try {
        const response = await fetch('/health');
        if (!response.ok) {
            throw new Error(`Server health check failed: ${response.status}`);
        }
        
        const data = await response.json();
        
        logDebug(`Server health: ${data.status}, AI Provider: ${data.ai_provider}`);

        // Show/hide OpenAI voice selector based on provider
        if (data.ai_provider === 'openai') {
            openaiVoiceSelectorContainerElement.style.display = 'flex'; // Or 'block' depending on desired layout
        } else {
            openaiVoiceSelectorContainerElement.style.display = 'none';
        }
        
        if (!data.ffmpeg_available) {
            logDebug('Warning: FFmpeg not available on server. Audio conversion may be limited.', true);
        }
        
        if (!data.vortex_imports_ok) {
            logDebug('Warning: VORTEX modules not available. Limited functionality.', true);
        }
        
        return data;
    } catch (error) {
        logDebug(`Server health check error: ${error.message}`, true);
        return null;
    }
}

/**
 * Use the Web Speech API to speak text
 * @param {string} text - Text to speak
 */
async function speakText(text) {
    if (!isSpeechEnabled || !text) return;

    // Try to use OpenAI TTS via backend first
    try {
        const payload = { text };
        if (openaiVoiceSelectorContainerElement.style.display !== 'none') {
            payload.voice = openaiVoiceSelectElement.value;
        }

        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload) // Send payload with conditional voice
        });

        if (response.ok && response.headers.get("content-type")?.includes("audio/mpeg")) {
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.play();
            audio.onended = () => {
                URL.revokeObjectURL(audioUrl); // Clean up blob URL
            };
            logDebug('Playing audio via OpenAI TTS from backend.');
            return; // Successfully played OpenAI TTS
        } else if (response.status === 202) {
            logDebug('OpenAI TTS not configured on backend, falling back to browser speech synthesis.');
            // Fall through to browser synthesis
        } else {
            const errorData = await response.json().catch(() => null); // Try to get error details
            logDebug(`Backend TTS API error: ${response.status} ${response.statusText}. Details: ${errorData ? JSON.stringify(errorData) : 'N/A'}. Falling back to browser speech synthesis.`, true);
            // Fall through to browser synthesis
        }
    } catch (error) {
        logDebug(`Error fetching from /api/tts: ${error.message}. Falling back to browser speech synthesis.`, true);
        // Fall through to browser synthesis
    }

    // Fallback to browser's SpeechSynthesis API
    if (!window.speechSynthesis) {
        logDebug('Speech synthesis not supported by this browser', true);
        return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    let voices = speechSynthesis.getVoices();

    if (voices.length === 0) {
        speechSynthesis.onvoiceschanged = () => { // Use onvoiceschanged for broader compatibility
            voices = speechSynthesis.getVoices();
            setVoice(utterance, voices);
            speechSynthesis.speak(utterance); // Speak after voices are loaded and set
        };
    } else {
        setVoice(utterance, voices);
        speechSynthesis.speak(utterance);
    }
}

/**
 * Set the best available voice for text-to-speech
 * @param {SpeechSynthesisUtterance} utterance - The utterance to set voice for
 * @param {SpeechSynthesisVoice[]} voices - Available voices
 */
function setVoice(utterance, voices) {
    // Preferred voice names (in order of preference)
    const preferredVoices = [
        'Google US English',
        'Microsoft David',
        'Microsoft Zira',
        'Alex',  // macOS
        'Daniel' // British English
    ];
    
    // Try to find one of our preferred voices
    for (const name of preferredVoices) {
        const voice = voices.find(v => v.name.includes(name));
        if (voice) {
            utterance.voice = voice;
            return;
        }
    }
    
    // Fall back to the first English voice
    const englishVoice = voices.find(v => v.lang.startsWith('en'));
    if (englishVoice) {
        utterance.voice = englishVoice;
    }
} 