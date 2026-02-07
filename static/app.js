// STRATEGOS Web UI - Client-side JavaScript

class StrategosUI {
    constructor() {
        this.ws = null;
        this.autoScroll = true;
        this.statusInterval = null;
        this.apiBase = `http://${window.location.host}`;
        this.wsUrl = `ws://${window.location.host}/ws/events`;
        this.timeScalePendingApply = false; // Track if user changed slider but hasn't applied

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.startStatusPolling();
    }

    // WebSocket Connection
    connectWebSocket() {
        console.log('Connecting to WebSocket:', this.wsUrl);

        this.ws = new WebSocket(this.wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);

            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleEvent(data);
        };
    }

    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        statusEl.textContent = connected ? 'Connected' : 'Disconnected';
        statusEl.className = `status-value ${connected ? 'connected' : 'disconnected'}`;
    }

    // Event Handlers
    handleEvent(event) {
        const streamEl = document.getElementById('event-stream');

        const eventEl = document.createElement('div');
        eventEl.className = 'event-item';

        const timeStr = parseFloat(event.simulation_time).toFixed(2);
        const eventType = event.event_type;
        const dataStr = JSON.stringify(event.data, null, 2);

        eventEl.innerHTML = `
            <div>
                <span class="event-time">[${timeStr}s]</span>
                <span class="event-type">${eventType}</span>
            </div>
            <div class="event-data">${dataStr}</div>
        `;

        streamEl.appendChild(eventEl);

        // Auto-scroll if enabled
        if (this.autoScroll) {
            streamEl.scrollTop = streamEl.scrollHeight;
        }

        // Keep only last 100 events
        while (streamEl.children.length > 100) {
            streamEl.removeChild(streamEl.firstChild);
        }
    }

    // API Calls
    async apiCall(endpoint, method = 'GET', body = null) {
        try {
            const options = {
                method,
                headers: {
                    'Content-Type': 'application/json',
                },
            };

            if (body) {
                options.body = JSON.stringify(body);
            }

            const response = await fetch(`${this.apiBase}${endpoint}`, options);

            if (!response.ok) {
                throw new Error(`API error: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            this.showError(error.message);
            throw error;
        }
    }

    async fetchStatus() {
        try {
            const status = await this.apiCall('/status');
            this.updateStatus(status);
        } catch (error) {
            console.error('Failed to fetch status:', error);
        }
    }

    updateStatus(status) {
        document.getElementById('sim-id').textContent = status.simulation_id.substring(0, 8) + '...';
        document.getElementById('sim-time').textContent = `${parseFloat(status.current_time).toFixed(2)}s`;
        document.getElementById('sim-scale').textContent = `${status.time_scale}x`;
        document.getElementById('sim-state').textContent = status.clock_state;
        document.getElementById('sim-running').textContent = status.is_running ? 'Yes' : 'No';
        document.getElementById('sim-events').textContent = status.event_count;

        // Update time scale slider ONLY if user hasn't made unapplied changes
        // This prevents resetting user's selection before they click Apply
        const slider = document.getElementById('time-scale');
        const sliderValue = document.getElementById('time-scale-value');

        if (!this.timeScalePendingApply) {
            slider.value = status.time_scale;
            sliderValue.textContent = `${status.time_scale}x`;
        } else {
            // Show pending indicator when there are unapplied changes
            document.getElementById('pending-indicator').style.display = 'inline-block';
        }
    }

    startStatusPolling() {
        this.fetchStatus();
        this.statusInterval = setInterval(() => this.fetchStatus(), 1000);
    }

    // Control Actions
    async start() {
        await this.apiCall('/start', 'POST');
        this.showSuccess('Simulation started');
    }

    async stop() {
        await this.apiCall('/stop', 'POST');
        this.showSuccess('Simulation stopped');
    }

    async pause() {
        await this.apiCall('/pause', 'POST');
        this.showSuccess('Simulation paused');
    }

    async resume() {
        await this.apiCall('/resume', 'POST');
        this.showSuccess('Simulation resumed');
    }

    async setTimeScale() {
        const scale = parseFloat(document.getElementById('time-scale').value);
        await this.apiCall('/time-scale', 'POST', { scale });
        this.showSuccess(`Time scale set to ${scale}x`);

        // Clear the pending flag - changes have been applied
        this.timeScalePendingApply = false;

        // Hide the pending indicator
        document.getElementById('pending-indicator').style.display = 'none';

        // Immediately update the display to show the new scale
        document.getElementById('sim-scale').textContent = `${scale}x`;
    }

    async createMarker() {
        const label = document.getElementById('marker-label').value.trim();

        if (!label) {
            this.showError('Please enter a marker label');
            return;
        }

        await this.apiCall('/marker', 'POST', { label });
        this.showSuccess(`Marker "${label}" created`);

        // Clear input
        document.getElementById('marker-label').value = '';
    }

    clearEvents() {
        document.getElementById('event-stream').innerHTML = '';
    }

    // UI Helpers
    showSuccess(message) {
        console.log('✓', message);
        // Could add a toast notification here
    }

    showError(message) {
        console.error('✗', message);
        alert(`Error: ${message}`);
    }

    // Event Listeners Setup
    setupEventListeners() {
        // Control buttons
        document.getElementById('btn-start').addEventListener('click', () => this.start());
        document.getElementById('btn-stop').addEventListener('click', () => this.stop());
        document.getElementById('btn-pause').addEventListener('click', () => this.pause());
        document.getElementById('btn-resume').addEventListener('click', () => this.resume());
        document.getElementById('btn-apply-scale').addEventListener('click', () => this.setTimeScale());
        document.getElementById('btn-create-marker').addEventListener('click', () => this.createMarker());
        document.getElementById('btn-clear-events').addEventListener('click', () => this.clearEvents());

        // Time scale slider
        document.getElementById('time-scale').addEventListener('input', (e) => {
            document.getElementById('time-scale-value').textContent = `${e.target.value}x`;
            // Mark that user has changed the slider - prevent status updates from overwriting
            this.timeScalePendingApply = true;
        });

        // Auto-scroll checkbox
        document.getElementById('auto-scroll').addEventListener('change', (e) => {
            this.autoScroll = e.target.checked;
        });

        // Marker input - submit on Enter
        document.getElementById('marker-label').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.createMarker();
            }
        });
    }
}

// Initialize the UI when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.strategosUI = new StrategosUI();
});
