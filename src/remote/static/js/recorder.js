/**
 * AudioRecorder Class
 * Handles audio recording, visualization, and encoding for the VORTEX web interface
 */
class AudioRecorder {
    constructor(options = {}) {
        // Default options
        this.options = {
            audioBitsPerSecond: 256000,
            mimeType: null, // Will be determined automatically
            visualizer: null,
            onAudioProcess: null,
            onRecordingStart: null,
            onRecordingStop: null,
            onDataAvailable: null,
            ...options
        };

        // State
        this.isRecording = false;
        this.isPaused = false;
        this.stream = null;
        this.audioContext = null;
        this.analyser = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.startTime = 0;
        this.visualizerActive = false;
        this.source = null;

        // Bind methods
        this.startRecording = this.startRecording.bind(this);
        this.stopRecording = this.stopRecording.bind(this);
        this.pauseRecording = this.pauseRecording.bind(this);
        this.resumeRecording = this.resumeRecording.bind(this);
        this._handleDataAvailable = this._handleDataAvailable.bind(this);
        this._setupVisualizer = this._setupVisualizer.bind(this);
        this._drawVisualizer = this._drawVisualizer.bind(this);
    }

    /**
     * Get the best supported MIME type for audio recording
     * @returns {string} The supported MIME type
     */
    static getSupportedMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
            'audio/mpeg'
        ];

        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }

        return ''; // Empty string, default format will be used
    }

    /**
     * Initialize audio context and connect to microphone
     * @param {MediaStream} stream - Microphone stream
     * @returns {Promise<void>}
     */
    async init(stream) {
        try {
            this.stream = stream;
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.source = this.audioContext.createMediaStreamSource(stream);
            
            // Set up analyzer for visualization
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.source.connect(this.analyser);
            
            // Set up the visualizer if provided
            if (this.options.visualizer) {
                this._setupVisualizer();
            }
            
            console.log('AudioRecorder initialized successfully');
        } catch (error) {
            console.error('Failed to initialize AudioRecorder:', error);
            throw error;
        }
    }

    /**
     * Start recording audio
     * @returns {Promise<void>}
     */
    async startRecording() {
        if (this.isRecording) return;
        
        this.audioChunks = [];
        
        try {
            // Determine the best MIME type
            const mimeType = this.options.mimeType || AudioRecorder.getSupportedMimeType();
            
            // Create MediaRecorder instance
            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: mimeType,
                audioBitsPerSecond: this.options.audioBitsPerSecond
            });
            
            // Set up event handlers
            this.mediaRecorder.ondataavailable = this._handleDataAvailable;
            
            // Start recording
            this.mediaRecorder.start(100); // Capture data in 100ms chunks
            this.isRecording = true;
            this.isPaused = false;
            this.startTime = Date.now();
            
            console.log(`Recording started (format: ${mimeType})`);
            
            // Start visualizer animation
            if (this.options.visualizer && !this.visualizerActive) {
                this.visualizerActive = true;
                this._drawVisualizer();
            }
            
            // Trigger onRecordingStart callback
            if (typeof this.options.onRecordingStart === 'function') {
                this.options.onRecordingStart();
            }
        } catch (error) {
            console.error('Failed to start recording:', error);
            this.isRecording = false;
            throw error;
        }
    }

    /**
     * Stop recording audio
     * @returns {Promise<Blob>} The recorded audio blob
     */
    async stopRecording() {
        if (!this.isRecording) {
            return null;
        }
        
        return new Promise((resolve, reject) => {
            try {
                this.mediaRecorder.onstop = () => {
                    this.isRecording = false;
                    this.isPaused = false;
                    this.visualizerActive = false;
                    
                    // Create audio blob from chunks
                    const audioBlob = new Blob(this.audioChunks, { 
                        type: this.mediaRecorder.mimeType 
                    });
                    
                    console.log(`Recording stopped (duration: ${(Date.now() - this.startTime) / 1000}s, size: ${audioBlob.size} bytes)`);
                    
                    // Trigger onRecordingStop callback
                    if (typeof this.options.onRecordingStop === 'function') {
                        this.options.onRecordingStop(audioBlob);
                    }
                    
                    resolve(audioBlob);
                };
                
                this.mediaRecorder.stop();
            } catch (error) {
                console.error('Failed to stop recording:', error);
                this.isRecording = false;
                this.isPaused = false;
                reject(error);
            }
        });
    }

    /**
     * Pause recording
     */
    pauseRecording() {
        if (this.isRecording && !this.isPaused && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.pause();
            this.isPaused = true;
            this.visualizerActive = false;
            console.log('Recording paused');
        }
    }

    /**
     * Resume recording
     */
    resumeRecording() {
        if (this.isRecording && this.isPaused && this.mediaRecorder.state === 'paused') {
            this.mediaRecorder.resume();
            this.isPaused = false;
            
            if (this.options.visualizer) {
                this.visualizerActive = true;
                this._drawVisualizer();
            }
            
            console.log('Recording resumed');
        }
    }

    /**
     * Handle data chunks from the MediaRecorder
     * @param {BlobEvent} event - Event containing a data chunk
     * @private
     */
    _handleDataAvailable(event) {
        if (event.data && event.data.size > 0) {
            this.audioChunks.push(event.data);
            
            // Trigger onDataAvailable callback
            if (typeof this.options.onDataAvailable === 'function') {
                this.options.onDataAvailable(event.data);
            }
        }
    }

    /**
     * Set up the audio visualizer
     * @private
     */
    _setupVisualizer() {
        const canvas = this.options.visualizer;
        if (!canvas || !canvas.getContext) {
            console.warn('Invalid canvas element for visualizer');
            this.options.visualizer = null; // Disable visualizer if canvas is invalid
            return;
        }
        
        this.visualizerContext = canvas.getContext('2d');
        this.bufferLength = this.analyser.frequencyBinCount;
        this.dataArray = new Uint8Array(this.bufferLength);
        
        // Get theme colors from CSS variables
        try {
            const styles = getComputedStyle(document.documentElement);
            this.vizColorCyan = styles.getPropertyValue('--accent-cyan').trim() || '#00FFFF';
            this.vizColorMagenta = styles.getPropertyValue('--accent-magenta').trim() || '#FF00FF';
            this.vizBgColor = styles.getPropertyValue('--bg-accent').trim() || '#1C202E';
        } catch (e) {
            console.warn("Could not read CSS variables for visualizer, using defaults.");
            this.vizColorCyan = '#00FFFF';
            this.vizColorMagenta = '#FF00FF';
            this.vizBgColor = '#1C202E';
        }

        // Ensure canvas is not hidden by parent
        canvas.style.display = 'block';

        const resizeCanvas = () => {
            if (!this.options.visualizer) return;
            // Make canvas sharp on HiDPI displays
            const dpr = window.devicePixelRatio || 1;
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            this.visualizerContext.scale(dpr, dpr); // Scale context to match
        };
        
        // Use ResizeObserver if available for more robust resizing
        if (typeof ResizeObserver !== 'undefined') {
            const resizeObserver = new ResizeObserver(resizeCanvas);
            resizeObserver.observe(canvas.parentElement); // Observe parent container
        } else {
            window.addEventListener('resize', resizeCanvas);
        }
        resizeCanvas(); // Initial call
    }

    /**
     * Draw the audio visualizer - Cyberpunk Style
     * @private
     */
    _drawVisualizer() {
        if (!this.visualizerActive || !this.options.visualizer || !this.visualizerContext) {
            return;
        }

        requestAnimationFrame(this._drawVisualizer); // Loop the drawing

        this.analyser.getByteFrequencyData(this.dataArray); // Get frequency data

        const ctx = this.visualizerContext;
        const canvas = this.options.visualizer;
        // Use logical canvas dimensions for drawing calculations (before DPR scaling)
        const logicalWidth = canvas.width / (window.devicePixelRatio || 1);
        const logicalHeight = canvas.height / (window.devicePixelRatio || 1);

        // Clear canvas with a semi-transparent effect for trails
        ctx.fillStyle = 'rgba(10, 10, 16, 0.3)'; // Darker, more transparent from new theme
        ctx.fillRect(0, 0, logicalWidth, logicalHeight);

        const barCount = this.bufferLength / 2; // Use about half of the bins for visual clarity
        const barWidth = (logicalWidth / barCount) * 1.5; // Slightly wider bars
        let x = 0;

        for (let i = 0; i < barCount; i++) {
            const barHeightScale = this.dataArray[i] / 255.0;
            let barHeight = barHeightScale * logicalHeight * 0.8; // Max 80% of height

            // Color based on amplitude (simple gradient)
            const hue = 180 + (barHeightScale * 60); // Cyan to Greenish-blue range
            ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
            // Glow effect for bars
            ctx.shadowColor = `hsl(${hue}, 100%, 60%)`;
            ctx.shadowBlur = 8;

            // Draw mirrored bars from center for a more symmetrical/cyberpunk look
            // Top half
            ctx.fillRect(x, (logicalHeight / 2) - barHeight, barWidth, barHeight);
            // Bottom half (mirrored)
            ctx.fillRect(x, logicalHeight / 2, barWidth, barHeight);

            x += barWidth + 2; // Add spacing between bars
        }
        ctx.shadowBlur = 0; // Reset shadow for other drawings if any
    }

    /**
     * Release resources and disconnect
     */
    destroy() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
        
        if (this.source) {
            this.source.disconnect();
        }
        
        if (this.audioContext) {
            this.audioContext.close();
        }
        
        this.isRecording = false;
        this.isPaused = false;
        this.visualizerActive = false;
        this.stream = null;
        this.audioContext = null;
        this.mediaRecorder = null;
        this.analyser = null;
        this.source = null;
        
        console.log('AudioRecorder resources released');
    }

    /**
     * Get the current recording duration in seconds
     * @returns {number} Duration in seconds
     */
    getRecordingDuration() {
        if (!this.isRecording || !this.startTime) {
            return 0;
        }
        
        return (Date.now() - this.startTime) / 1000;
    }
} 