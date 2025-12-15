/**
 * Availability Timeline Component
 * 
 * Visualizes node availability over time with:
 * - Canvas-based timeline chart
 * - Draggable time window selection
 * - Time picker controls (start, end, duration)
 */

class AvailabilityTimeline {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Timeline container not found:', containerId);
            return;
        }

        // Configuration
        this.options = {
            defaultRangeDays: 7,
            defaultWindowHours: 24,
            height: 200,
            margin: { top: 20, right: 40, bottom: 40, left: 60 },
            ...options
        };

        // State
        this.availabilityData = [];
        this.nodeAvailability = new Map(); // Map of nodeId -> availability windows
        this.matchingNodeIds = [];
        this.allNodes = []; // Store reference to all nodes for filtering
        this.timeRange = this.getDefaultTimeRange();
        this.selectedWindow = this.getDefaultWindow();
        this.dragState = null;
        this.onWindowChangeCallback = null; // Callback when time window changes

        // Canvas setup
        this.setupCanvas();
        this.setupControls();
        this.attachEventHandlers();
    }

    getDefaultTimeRange() {
        const now = new Date();
        const start = new Date(now);
        const end = new Date(now);
        end.setDate(end.getDate() + this.options.defaultRangeDays);
        return { start, end };
    }

    getDefaultWindow() {
        const now = new Date();
        const start = new Date(now);
        start.setHours(start.getHours() + 1, 0, 0, 0); // Next hour
        const end = new Date(start);
        end.setHours(end.getHours() + this.options.defaultWindowHours);
        return { start, end };
    }

    setupCanvas() {
        const canvas = this.container.querySelector('#availability-canvas');
        if (!canvas) return;

        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');

        // Set canvas size (account for device pixel ratio)
        const dpr = window.devicePixelRatio || 1;
        const rect = this.container.getBoundingClientRect();
        const width = rect.width - 40; // Account for padding

        this.canvas.width = width * dpr;
        this.canvas.height = this.options.height * dpr;
        this.canvas.style.width = `${width}px`;
        this.canvas.style.height = `${this.options.height}px`;
        
        this.ctx.scale(dpr, dpr);

        this.width = width;
        this.height = this.options.height;
    }

    setupControls() {
        const startInput = document.getElementById('timeline-start');
        const endInput = document.getElementById('timeline-end');
        const durationInput = document.getElementById('timeline-duration');

        if (startInput && endInput && durationInput) {
            // Initialize with default values
            startInput.value = this.formatDateTimeLocal(this.selectedWindow.start);
            endInput.value = this.formatDateTimeLocal(this.selectedWindow.end);
            this.updateDuration();

            // Event listeners
            startInput.addEventListener('change', () => this.onStartChange());
            endInput.addEventListener('change', () => this.onEndChange());
            durationInput.addEventListener('change', () => this.onDurationChange());
        }
    }

    attachEventHandlers() {
        if (!this.canvas) return;

        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.onMouseUp());
        this.canvas.addEventListener('mouseleave', () => this.onMouseUp());

        // Resize handler
        window.addEventListener('resize', () => {
            this.setupCanvas();
            this.render();
        });
    }

    // Time picker event handlers
    onStartChange() {
        const startInput = document.getElementById('timeline-start');
        const newStart = new Date(startInput.value);
        if (isNaN(newStart)) return;

        this.selectedWindow.start = newStart;
        
        // Ensure end is after start
        if (this.selectedWindow.end <= this.selectedWindow.start) {
            this.selectedWindow.end = new Date(this.selectedWindow.start);
            this.selectedWindow.end.setHours(this.selectedWindow.end.getHours() + 1);
            document.getElementById('timeline-end').value = this.formatDateTimeLocal(this.selectedWindow.end);
        }

        this.updateDuration();
        this.render();
        this.notifyWindowChange();
    }

    onEndChange() {
        const endInput = document.getElementById('timeline-end');
        const newEnd = new Date(endInput.value);
        if (isNaN(newEnd)) return;

        this.selectedWindow.end = newEnd;

        // Ensure start is before end
        if (this.selectedWindow.start >= this.selectedWindow.end) {
            this.selectedWindow.start = new Date(this.selectedWindow.end);
            this.selectedWindow.start.setHours(this.selectedWindow.start.getHours() - 1);
            document.getElementById('timeline-start').value = this.formatDateTimeLocal(this.selectedWindow.start);
        }

        this.updateDuration();
        this.render();
        this.notifyWindowChange();
    }

    onDurationChange() {
        const durationInput = document.getElementById('timeline-duration');
        const hours = parseFloat(durationInput.value);
        if (isNaN(hours) || hours <= 0) return;

        this.selectedWindow.end = new Date(this.selectedWindow.start);
        this.selectedWindow.end.setHours(this.selectedWindow.end.getHours() + hours);

        document.getElementById('timeline-end').value = this.formatDateTimeLocal(this.selectedWindow.end);
        this.render();
        this.notifyWindowChange();
    }

    updateDuration() {
        const durationInput = document.getElementById('timeline-duration');
        if (!durationInput) return;

        const hours = (this.selectedWindow.end - this.selectedWindow.start) / (1000 * 60 * 60);
        durationInput.value = hours.toFixed(1);
    }

    // Mouse interaction handlers
    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const time = this.xToTime(x);

        // Check if clicking near start or end handle
        const startX = this.timeToX(this.selectedWindow.start);
        const endX = this.timeToX(this.selectedWindow.end);
        const threshold = 10;

        if (Math.abs(x - startX) < threshold) {
            this.dragState = { type: 'start', initialX: x, initialTime: this.selectedWindow.start };
        } else if (Math.abs(x - endX) < threshold) {
            this.dragState = { type: 'end', initialX: x, initialTime: this.selectedWindow.end };
        } else if (x > startX && x < endX) {
            // Drag entire window
            this.dragState = { 
                type: 'window', 
                initialX: x, 
                initialStart: this.selectedWindow.start,
                initialEnd: this.selectedWindow.end
            };
        }

        this.canvas.style.cursor = this.dragState ? 'grabbing' : 'default';
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;

        if (this.dragState) {
            const time = this.xToTime(x);
            const deltaX = x - this.dragState.initialX;
            const deltaTime = deltaX * (this.timeRange.end - this.timeRange.start) / this.getChartWidth();

            if (this.dragState.type === 'start') {
                const newStart = new Date(this.dragState.initialTime.getTime() + deltaTime);
                if (newStart < this.selectedWindow.end && newStart >= this.timeRange.start) {
                    this.selectedWindow.start = newStart;
                    document.getElementById('timeline-start').value = this.formatDateTimeLocal(newStart);
                    this.updateDuration();
                    this.render();
                    this.notifyWindowChange();
                }
            } else if (this.dragState.type === 'end') {
                const newEnd = new Date(this.dragState.initialTime.getTime() + deltaTime);
                if (newEnd > this.selectedWindow.start && newEnd <= this.timeRange.end) {
                    this.selectedWindow.end = newEnd;
                    document.getElementById('timeline-end').value = this.formatDateTimeLocal(newEnd);
                    this.updateDuration();
                    this.render();
                    this.notifyWindowChange();
                }
            } else if (this.dragState.type === 'window') {
                const newStart = new Date(this.dragState.initialStart.getTime() + deltaTime);
                const newEnd = new Date(this.dragState.initialEnd.getTime() + deltaTime);
                
                if (newStart >= this.timeRange.start && newEnd <= this.timeRange.end) {
                    this.selectedWindow.start = newStart;
                    this.selectedWindow.end = newEnd;
                    document.getElementById('timeline-start').value = this.formatDateTimeLocal(newStart);
                    document.getElementById('timeline-end').value = this.formatDateTimeLocal(newEnd);
                    this.render();
                    this.notifyWindowChange();
                }
            }
        } else {
            // Update cursor on hover
            const startX = this.timeToX(this.selectedWindow.start);
            const endX = this.timeToX(this.selectedWindow.end);
            const threshold = 10;

            if (Math.abs(x - startX) < threshold || Math.abs(x - endX) < threshold) {
                this.canvas.style.cursor = 'ew-resize';
            } else if (x > startX && x < endX) {
                this.canvas.style.cursor = 'grab';
            } else {
                this.canvas.style.cursor = 'default';
            }
        }
    }

    onMouseUp() {
        this.dragState = null;
        this.canvas.style.cursor = 'default';
    }

    // Coordinate conversion
    getChartWidth() {
        return this.width - this.options.margin.left - this.options.margin.right;
    }

    getChartHeight() {
        return this.height - this.options.margin.top - this.options.margin.bottom;
    }

    timeToX(time) {
        const chartWidth = this.getChartWidth();
        const ratio = (time - this.timeRange.start) / (this.timeRange.end - this.timeRange.start);
        return this.options.margin.left + ratio * chartWidth;
    }

    xToTime(x) {
        const chartWidth = this.getChartWidth();
        const ratio = (x - this.options.margin.left) / chartWidth;
        return new Date(this.timeRange.start.getTime() + ratio * (this.timeRange.end - this.timeRange.start));
    }

    valueToY(value, maxValue) {
        const chartHeight = this.getChartHeight();
        const ratio = value / maxValue;
        return this.options.margin.top + chartHeight - (ratio * chartHeight);
    }

    // Update data from external sources
    async updateAvailability(nodeIds, allNodes = []) {
        this.matchingNodeIds = nodeIds;
        this.allNodes = allNodes;
        
        // TODO: Replace with actual API call
        // For now, generate realistic mock data per node
        this.generateNodeAvailabilityWindows(allNodes);
        this.availabilityData = this.aggregateAvailabilityData(nodeIds);
        
        this.render();
    }

    // Generate realistic availability windows for each node
    generateNodeAvailabilityWindows(nodes) {
        this.nodeAvailability.clear();
        
        nodes.forEach(node => {
            // Determine availability rate based on node_type
            let availabilityRate = 0.30; // Default 30%
            
            if (node.node_type) {
                if (node.node_type.startsWith('gpu')) {
                    availabilityRate = 0.15 + Math.random() * 0.10; // 15-25% (high demand)
                } else if (node.node_type.startsWith('compute')) {
                    availabilityRate = 0.25 + Math.random() * 0.15; // 25-40%
                } else if (node.node_type.startsWith('storage')) {
                    availabilityRate = 0.50 + Math.random() * 0.30; // 50-80% (low demand)
                } else if (node.node_type.includes('fpga')) {
                    availabilityRate = 0.10 + Math.random() * 0.15; // 10-25% (very high demand)
                } else {
                    availabilityRate = 0.20 + Math.random() * 0.40; // 20-60% (varied)
                }
            }
            
            // Add some outliers (10% chance of being very available or very busy)
            if (Math.random() < 0.05) {
                availabilityRate = 0.75 + Math.random() * 0.10; // 75-85% outlier (very available)
            } else if (Math.random() < 0.05) {
                availabilityRate = 0.05 + Math.random() * 0.05; // 5-10% outlier (very busy)
            }
            
            const windows = [];
            let currentTime = new Date(this.timeRange.start);
            const endTime = new Date(this.timeRange.end);
            
            while (currentTime < endTime) {
                // Decide if this period is available or reserved
                const isAvailable = Math.random() < availabilityRate;
                
                if (isAvailable) {
                    // Generate an available window
                    // Duration: 2 hours to 1 week (with bias toward shorter)
                    const minHours = 2;
                    const maxHours = 7 * 24; // 1 week
                    // Use exponential distribution to bias toward shorter durations
                    const durationHours = minHours + (maxHours - minHours) * Math.pow(Math.random(), 2);
                    
                    const windowEnd = new Date(currentTime.getTime() + durationHours * 60 * 60 * 1000);
                    const actualEnd = windowEnd > endTime ? endTime : windowEnd;
                    
                    windows.push({
                        start: new Date(currentTime),
                        end: actualEnd,
                        state: 'available'
                    });
                    
                    currentTime = actualEnd;
                } else {
                    // Generate a reserved window
                    const minHours = 2;
                    const maxHours = 7 * 24;
                    const durationHours = minHours + (maxHours - minHours) * Math.pow(Math.random(), 1.5);
                    
                    const windowEnd = new Date(currentTime.getTime() + durationHours * 60 * 60 * 1000);
                    currentTime = windowEnd > endTime ? endTime : windowEnd;
                }
            }
            
            this.nodeAvailability.set(node.uid, windows);
        });
    }

    // Aggregate availability counts over time
    aggregateAvailabilityData(nodeIds) {
        const data = [];
        const intervalMinutes = 30;
        
        let current = new Date(this.timeRange.start);
        while (current <= this.timeRange.end) {
            let availableCount = 0;
            
            // Count how many nodes are available at this time
            nodeIds.forEach(nodeId => {
                if (this.isNodeAvailableAt(nodeId, current)) {
                    availableCount++;
                }
            });
            
            data.push({
                time: new Date(current),
                available: availableCount
            });
            
            current = new Date(current.getTime() + intervalMinutes * 60 * 1000);
        }
        
        return data;
    }

    // Check if a node is available at a specific time
    isNodeAvailableAt(nodeId, time) {
        const windows = this.nodeAvailability.get(nodeId);
        if (!windows) return false;
        
        return windows.some(window => 
            time >= window.start && time <= window.end && window.state === 'available'
        );
    }

    // Check if a node has any availability in the selected window
    isNodeAvailableInWindow(nodeId) {
        const windows = this.nodeAvailability.get(nodeId);
        if (!windows) return false;
        
        return windows.some(window => {
            if (window.state !== 'available') return false;
            // Check for overlap with selected window
            return window.start < this.selectedWindow.end && window.end > this.selectedWindow.start;
        });
    }

    // Get list of node IDs that are available in the selected window
    getAvailableNodeIds() {
        return this.matchingNodeIds.filter(nodeId => this.isNodeAvailableInWindow(nodeId));
    }

    // Register callback for when time window changes
    onWindowChange(callback) {
        this.onWindowChangeCallback = callback;
    }

    // Notify that window changed
    notifyWindowChange() {
        if (this.onWindowChangeCallback) {
            this.onWindowChangeCallback(this.selectedWindow);
        }
    }

    // Rendering
    render() {
        if (!this.ctx) return;

        const ctx = this.ctx;
        const { margin } = this.options;
        const chartWidth = this.getChartWidth();
        const chartHeight = this.getChartHeight();

        // Clear canvas
        ctx.clearRect(0, 0, this.width, this.height);

        // Background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, this.width, this.height);

        if (this.availabilityData.length === 0) {
            // Show placeholder message
            ctx.fillStyle = '#999';
            ctx.font = '14px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Select filters to view availability', this.width / 2, this.height / 2);
            return;
        }

        // Find max value for Y scale
        const maxAvailable = Math.max(...this.availabilityData.map(d => d.available), 1);

        // Draw selected window highlight
        this.drawSelectedWindow(maxAvailable);

        // Draw axes
        this.drawAxes(maxAvailable);

        // Draw availability line/area
        this.drawAvailabilityChart(maxAvailable);

        // Draw handles
        this.drawHandles();
    }

    drawSelectedWindow(maxAvailable) {
        const ctx = this.ctx;
        const startX = this.timeToX(this.selectedWindow.start);
        const endX = this.timeToX(this.selectedWindow.end);
        const chartHeight = this.getChartHeight();

        ctx.fillStyle = 'rgba(37, 99, 235, 0.1)';
        ctx.fillRect(
            startX,
            this.options.margin.top,
            endX - startX,
            chartHeight
        );

        // Border
        ctx.strokeStyle = 'rgba(37, 99, 235, 0.3)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(startX, this.options.margin.top);
        ctx.lineTo(startX, this.options.margin.top + chartHeight);
        ctx.moveTo(endX, this.options.margin.top);
        ctx.lineTo(endX, this.options.margin.top + chartHeight);
        ctx.stroke();
        ctx.setLineDash([]);
    }

    drawAxes(maxAvailable) {
        const ctx = this.ctx;
        const { margin } = this.options;
        const chartWidth = this.getChartWidth();
        const chartHeight = this.getChartHeight();

        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;

        // Y axis
        ctx.beginPath();
        ctx.moveTo(margin.left, margin.top);
        ctx.lineTo(margin.left, margin.top + chartHeight);
        ctx.stroke();

        // X axis
        ctx.beginPath();
        ctx.moveTo(margin.left, margin.top + chartHeight);
        ctx.lineTo(margin.left + chartWidth, margin.top + chartHeight);
        ctx.stroke();

        // Y axis labels
        ctx.fillStyle = '#666';
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';

        const ySteps = 4;
        for (let i = 0; i <= ySteps; i++) {
            const value = Math.round((maxAvailable / ySteps) * i);
            const y = this.valueToY(value, maxAvailable);
            ctx.fillText(value.toString(), margin.left - 10, y);

            // Grid line
            ctx.strokeStyle = '#f0f0f0';
            ctx.beginPath();
            ctx.moveTo(margin.left, y);
            ctx.lineTo(margin.left + chartWidth, y);
            ctx.stroke();
        }

        // X axis labels
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const xSteps = 6;
        for (let i = 0; i <= xSteps; i++) {
            const ratio = i / xSteps;
            const time = new Date(this.timeRange.start.getTime() + ratio * (this.timeRange.end - this.timeRange.start));
            const x = this.timeToX(time);
            ctx.fillText(this.formatDateShort(time), x, margin.top + chartHeight + 5);
        }

        // Axis labels
        ctx.save();
        ctx.translate(15, this.height / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.textAlign = 'center';
        ctx.font = '12px Inter, sans-serif';
        ctx.fillStyle = '#333';
        ctx.fillText('Available Nodes', 0, 0);
        ctx.restore();

        ctx.textAlign = 'center';
        ctx.fillText('Time', this.width / 2, this.height - 5);
    }

    drawAvailabilityChart(maxAvailable) {
        const ctx = this.ctx;

        if (this.availabilityData.length === 0) return;

        // Draw area
        ctx.fillStyle = 'rgba(37, 99, 235, 0.2)';
        ctx.beginPath();
        
        const firstPoint = this.availabilityData[0];
        ctx.moveTo(this.timeToX(firstPoint.time), this.valueToY(0, maxAvailable));
        
        this.availabilityData.forEach(d => {
            ctx.lineTo(this.timeToX(d.time), this.valueToY(d.available, maxAvailable));
        });

        const lastPoint = this.availabilityData[this.availabilityData.length - 1];
        ctx.lineTo(this.timeToX(lastPoint.time), this.valueToY(0, maxAvailable));
        ctx.closePath();
        ctx.fill();

        // Draw line
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        this.availabilityData.forEach((d, i) => {
            const x = this.timeToX(d.time);
            const y = this.valueToY(d.available, maxAvailable);
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.stroke();
    }

    drawHandles() {
        const ctx = this.ctx;
        const startX = this.timeToX(this.selectedWindow.start);
        const endX = this.timeToX(this.selectedWindow.end);
        const chartHeight = this.getChartHeight();
        const handleY = this.options.margin.top + chartHeight / 2;

        // Draw handles
        const drawHandle = (x) => {
            ctx.fillStyle = '#2563eb';
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;

            ctx.beginPath();
            ctx.arc(x, handleY, 8, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        };

        drawHandle(startX);
        drawHandle(endX);
    }

    // Formatting helpers
    formatDateTimeLocal(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    formatDateShort(date) {
        const month = date.getMonth() + 1;
        const day = date.getDate();
        const hours = date.getHours();
        const ampm = hours >= 12 ? 'PM' : 'AM';
        const displayHours = hours % 12 || 12;
        return `${month}/${day} ${displayHours}${ampm}`;
    }
}

// Export for use in app.js
window.AvailabilityTimeline = AvailabilityTimeline;
