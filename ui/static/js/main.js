/**
 * AI Safety System - Main JavaScript
 * ==================================
 * Handles interactions, real-time updates, and UI state
 */

// Global state
const state = {
    isConnected: false,
    lastUpdate: null,
    activeModal: null
};

// ===== UTILITY FUNCTIONS =====

function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const iconMap = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle',
        warning: 'fa-exclamation-triangle'
    };

    toast.innerHTML = `
        <i class="fas ${iconMap[type]}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s reverse';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function formatTimestamp(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;

    // Less than 1 minute
    if (diff < 60000) {
        return 'Just now';
    }
    // Less than 1 hour
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    }
    // Less than 1 day
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }
    // More than 1 day
    return date.toLocaleDateString();
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// ===== MODAL FUNCTIONS =====

function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        state.activeModal = modalId;
        document.body.style.overflow = 'hidden';
    }
}

function closeModal() {
    if (state.activeModal) {
        const modal = document.getElementById(state.activeModal);
        if (modal) {
            modal.classList.remove('active');
            state.activeModal = null;
            document.body.style.overflow = '';
        }
    }
}

// Close modal on background click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        closeModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.activeModal) {
        closeModal();
    }
});

// ===== EMERGENCY FUNCTIONS =====

function emergencyHalt() {
    showModal('emergencyModal');
}

async function confirmEmergencyHalt() {
    try {
        showToast('Initiating emergency halt...', 'warning');
        closeModal();

        const response = await fetch('/api/emergency/halt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Emergency halt successful', 'success');
            // Update UI to reflect halted state
            updateSystemStatus('halted');
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Emergency halt error:', error);
        showToast('Failed to execute emergency halt', 'error');
    }
}

function updateSystemStatus(status) {
    const statusIndicator = document.getElementById('systemStatus');
    if (!statusIndicator) return;

    const statusMap = {
        operational: { text: 'Operational', class: 'success' },
        degraded: { text: 'Degraded', class: 'warning' },
        halted: { text: 'Halted', class: 'danger' }
    };

    const info = statusMap[status] || statusMap.operational;

    statusIndicator.innerHTML = `
        <span class="status-dot ${info.class}"></span>
        <span class="status-text">${info.text}</span>
    `;
}

// ===== GLOBAL BANNER =====
function showBanner(message, type = 'info', duration = 0){
    const el = document.getElementById('globalBanner');
    const text = document.getElementById('globalBannerText');
    if(!el || !text) return;
    el.className = `alert-banner ${type}`;
    text.textContent = message;
    el.style.display = 'block';
    if(duration && duration > 0){
        setTimeout(()=> hideBanner(), duration);
    }
}
function hideBanner(){
    const el = document.getElementById('globalBanner');
    if(el) el.style.display = 'none';
}

// ===== API HELPERS =====

// API request configuration
const API_CONFIG = {
    maxRetries: 3,
    retryDelay: 1000,
    timeout: 30000
};

async function fetchJSON(url, options = {}) {
    const maxRetries = options.maxRetries || API_CONFIG.maxRetries;
    const retryDelay = options.retryDelay || API_CONFIG.retryDelay;
    
    let lastError;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            const opts = Object.assign({}, options);
            opts.headers = Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, (options.headers || {}));
            
            // Create abort controller for timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.timeout);
            opts.signal = controller.signal;
            
            const response = await fetch(url, opts);
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                if (response.status === 401) showBanner('Unauthorized: check admin token.', 'danger');
                else if (response.status === 403) showBanner('Forbidden: insufficient role for this action.', 'warning');
                else if (response.status === 429) showBanner('Rate limited: please slow down.', 'warning');
                
                const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
                error.status = response.status;
                
                // Don't retry for client errors (4xx)
                if (response.status >= 400 && response.status < 500) {
                    throw error;
                }
                
                throw error;
            }
            
            return await response.json();
            
        } catch (error) {
            lastError = error;
            
            // Handle timeout
            if (error.name === 'AbortError') {
                console.warn(`Request timeout (${url})`);
                error.message = 'Request timed out';
                showToast('Request timed out - please try again', 'warning');
            }
            
            // Don't retry for client errors (4xx)
            if (error.status && error.status >= 400 && error.status < 500) {
                throw error;
            }
            
            // Log retry attempt
            if (attempt < maxRetries) {
                console.warn(`API retry ${attempt}/${maxRetries} for ${url}: ${error.message}`);
                await sleep(retryDelay * attempt);  // Exponential backoff
            }
        }
    }
    
    console.error(`API Error (${url}) after ${maxRetries} attempts:`, lastError);
    throw lastError;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Global error handler for unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    
    // Show user-friendly error for network errors
    if (event.reason && event.reason.message) {
        const message = event.reason.message;
        if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
            showToast('Network error - please check your connection', 'error');
        }
    }
});

// Global error handler for uncaught errors
window.addEventListener('error', (event) => {
    console.error('Uncaught error:', event.error);
});

// ===== REAL-TIME UPDATES =====

// Socket.IO connection instance
let socket = null;

function setupRealTimeUpdates() {
    // Update timestamps every minute
    setInterval(() => {
        document.querySelectorAll('[data-timestamp]').forEach(el => {
            const timestamp = el.getAttribute('data-timestamp');
            el.textContent = formatTimestamp(timestamp);
        });
    }, 60000);

    // Fetch fresh data periodically
    setInterval(async () => {
        try {
            const status = await fetchJSON('/api/status');
            state.lastUpdate = new Date();

            // Update connection indicator
            if (!state.isConnected) {
                state.isConnected = true;
                // Connection toast removed - only show warnings/errors
            }
        } catch (error) {
            if (state.isConnected) {
                state.isConnected = false;
                showToast('Connection lost', 'error');
            }
        }
    }, 5000);
    
    // Setup Socket.IO connection
    setupSocketIO();
}

function setupSocketIO() {
    // Check if Socket.IO is available
    if (typeof io === 'undefined') {
        console.warn('Socket.IO not available');
        return;
    }
    
    socket = io();
    
    // Connection events
    socket.on('connect', () => {
        console.log('Socket.IO connected');
        state.isConnected = true;
        
        // Subscribe to relevant channels
        socket.emit('subscribe', { channel: 'proposals' });
        socket.emit('subscribe', { channel: 'notifications' });
        socket.emit('subscribe', { channel: 'orka' });
    });
    
    socket.on('disconnect', () => {
        console.log('Socket.IO disconnected');
        state.isConnected = false;
    });
    
    socket.on('status', (data) => {
        console.log('Server status:', data.message);
    });
    
    // Proposal events
    socket.on('proposals:new', (data) => {
        console.log('New proposal:', data);
        showToast(`New proposal submitted: ${data.title}`, 'info');
        updateProposalBadge(1);
        // Refresh proposals list if on proposals page
        if (typeof loadAllProposals === 'function') {
            loadAllProposals();
        }
    });
    
    socket.on('proposals:update', (data) => {
        console.log('Proposal updated:', data);
        showToast(`Proposal ${data.proposal_id} status: ${data.status}`, 'info');
        // Refresh if viewing this proposal
        if (typeof refreshCurrentProposal === 'function') {
            refreshCurrentProposal(data.proposal_id);
        }
    });
    
    socket.on('proposals:phase_transition', (data) => {
        console.log('Phase transition:', data);
        showToast(`Proposal ${data.proposal_id}: ${data.from_phase} → ${data.to_phase}`, 'info');
        // Update workflow visualization if visible
        if (typeof updateWorkflowVisualization === 'function') {
            updateWorkflowVisualization(data.proposal_id, data.to_phase);
        }
    });
    
    // ORKA events
    socket.on('orka:challenge', (data) => {
        console.log('ORKA challenge:', data);
        showToast(`ORKA Challenge for ${data.proposal_id}: ${data.summary}`, 'warning');
    });
    
    // VAL events
    socket.on('val:validation', (data) => {
        console.log('VAL validation:', data);
        const resultIcon = data.result === 'approved' ? '✓' : data.result === 'rejected' ? '✗' : '⏳';
        showToast(`VAL Validation ${resultIcon}: ${data.proposal_id} - ${data.result}`, 
            data.result === 'approved' ? 'success' : data.result === 'rejected' ? 'error' : 'warning');
    });
    
    // Deployment events
    socket.on('deployment:complete', (data) => {
        console.log('Deployment complete:', data);
        showToast(`Deployment ${data.success ? 'successful' : 'failed'}: ${data.proposal_id}`, 
            data.success ? 'success' : 'error');
    });
    
    // Deception alerts
    socket.on('deception:alert', (data) => {
        console.log('Deception alert:', data);
        showToast(`⚠️ Deception detected: Agent ${data.agent_id} - ${data.severity} severity`, 'error', 8000);
        updateDeceptionAlertBadge(1);
    });
    
    // Collusion attempts
    socket.on('collusion:attempt', (data) => {
        console.log('Collusion attempt:', data);
        showToast(`🚨 Collusion detected between agents: ${data.agents.join(', ')}`, 'error', 10000);
    });
    
    // Notifications
    socket.on('notifications:new', (data) => {
        console.log('New notification:', data);
        addNotificationToPanel(data);
        updateNotificationBadge(1);
        
        // Show toast for important notifications
        if (data.severity === 'error' || data.severity === 'warning') {
            showToast(`${data.title}: ${data.message}`, data.severity);
        }
    });
    
    // General updates
    socket.on('update', (data) => {
        // Update dashboard metrics if visible
        updateDashboardMetrics(data);
    });
    
    // Trajectory updates
    socket.on('trajectories:update', (data) => {
        console.log('Trajectory update:', data);
        if (typeof loadTrajectories === 'function') {
            loadTrajectories();
        }
    });
    
    // Workflow updates
    socket.on('workflows:update', (data) => {
        console.log('Workflow update:', data);
        if (typeof loadWorkflows === 'function') {
            loadWorkflows();
        }
    });
    
    // Training updates
    socket.on('training:update', (data) => {
        console.log('Training update:', data);
        if (typeof loadTrainingMetrics === 'function') {
            loadTrainingMetrics();
        }
    });
}

function updateProposalBadge(increment) {
    const badge = document.getElementById('proposalBadge');
    if (badge) {
        const current = parseInt(badge.textContent) || 0;
        badge.textContent = current + increment;
        badge.style.display = 'inline-block';
    }
}

function updateDeceptionAlertBadge(increment) {
    const badge = document.getElementById('deceptionBadge');
    if (badge) {
        const current = parseInt(badge.textContent) || 0;
        badge.textContent = current + increment;
        badge.style.display = 'inline-block';
    }
}

function updateNotificationBadge(increment) {
    const badge = document.getElementById('notificationBadge');
    if (badge) {
        const current = parseInt(badge.textContent) || 0;
        const newCount = current + increment;
        badge.textContent = newCount;
        badge.style.display = newCount > 0 ? 'inline-block' : 'none';
    }
}

function addNotificationToPanel(notification) {
    const panel = document.getElementById('notificationList');
    if (!panel) return;
    
    const item = document.createElement('div');
    item.className = `notification-item ${notification.severity} unread`;
    item.innerHTML = `
        <div class="notification-icon">
            <i class="fas ${getNotificationIcon(notification.type)}"></i>
        </div>
        <div class="notification-content">
            <div class="notification-title">${escapeHtml(notification.title)}</div>
            <div class="notification-message">${escapeHtml(notification.message)}</div>
            <div class="notification-time">${formatTimestamp(notification.timestamp)}</div>
        </div>
    `;
    panel.insertBefore(item, panel.firstChild);
}

function getNotificationIcon(type) {
    const icons = {
        'proposal': 'fa-file-alt',
        'deception': 'fa-exclamation-triangle',
        'penalty': 'fa-gavel',
        'system': 'fa-cog',
        'deployment': 'fa-rocket',
        'val': 'fa-shield-alt'
    };
    return icons[type] || 'fa-bell';
}

function updateDashboardMetrics(data) {
    // Accept either socket update or /api/status payload
    const metrics = data.metrics || data;

    const activeProposalsEl = document.getElementById('activeProposals');
    if (activeProposalsEl && metrics.proposals_processed !== undefined) {
        activeProposalsEl.textContent = metrics.proposals_processed;
    }

    const detectionAlertsEl = document.getElementById('deceptionAlerts');
    if (detectionAlertsEl && metrics.deception_detected !== undefined) {
        detectionAlertsEl.textContent = metrics.deception_detected;
    }

    const detectionAccuracyEl = document.getElementById('detectionAccuracy');
    if (detectionAccuracyEl && metrics.detection_accuracy !== undefined) {
        detectionAccuracyEl.textContent = `${(metrics.detection_accuracy * 100).toFixed(1)}%`;
    }

    const nodesOnlineEl = document.getElementById('nodesOnline');
    if (nodesOnlineEl && metrics.cluster_online !== undefined && metrics.cluster_total !== undefined) {
        nodesOnlineEl.textContent = `${metrics.cluster_online}/${metrics.cluster_total}`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== CHART HELPERS =====

function createChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        console.warn(`Canvas ${canvasId} not found`);
        return null;
    }

    const ctx = canvas.getContext('2d');
    return new Chart(ctx, config);
}

// ===== KEYBOARD SHORTCUTS =====

document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K: Focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('input[type="search"]');
        if (searchInput) searchInput.focus();
    }

    // Ctrl/Cmd + /: Show shortcuts help
    if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        showToast('Keyboard shortcuts: Ctrl+K (Search), Ctrl+/ (Help), Esc (Close)', 'info', 5000);
    }
});

// ===== TOP BAR BUTTON FUNCTIONS =====

function showNotifications() {
    showModal('notificationsModal');
}

function showSettings() {
    // Load saved settings from localStorage
    loadSettings();
    showModal('settingsModal');
}

function toggleUserMenu() {
    const dropdown = document.getElementById('userMenuDropdown');
    const isVisible = dropdown.classList.contains('active');

    if (isVisible) {
        dropdown.classList.remove('active');
    } else {
        dropdown.classList.add('active');
    }
}

// Close user menu when clicking outside
document.addEventListener('click', (e) => {
    const userMenu = document.querySelector('.user-menu');
    const dropdown = document.getElementById('userMenuDropdown');

    if (dropdown && !userMenu.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove('active');
    }
});

// ===== NOTIFICATION FUNCTIONS =====

function markAllRead() {
    const notifications = document.querySelectorAll('.notification-item.unread');
    notifications.forEach(notif => {
        notif.classList.remove('unread');
    });

    updateNotificationCount();
    showToast('All notifications marked as read', 'success');
}

function clearNotifications() {
    const notifList = document.getElementById('notificationList');
    if (notifList) {
        notifList.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>No notifications</p></div>';
        updateNotificationCount();
        showToast('All notifications cleared', 'success');
    }
}

function updateNotificationCount() {
    const unreadCount = document.querySelectorAll('.notification-item.unread').length;
    const badge = document.getElementById('notificationCount');

    if (badge) {
        if (unreadCount > 0) {
            badge.textContent = unreadCount;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }
}

// ===== SETTINGS FUNCTIONS =====

const SETTINGS_KEY = 'ai_safety_settings';

function loadSettings() {
    const settings = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');

    // Apply settings to UI
    if (document.getElementById('darkModeToggle')) {
        document.getElementById('darkModeToggle').checked = settings.darkMode !== false;
    }
    if (document.getElementById('autoRefreshToggle')) {
        document.getElementById('autoRefreshToggle').checked = settings.autoRefresh !== false;
    }
    if (document.getElementById('soundToggle')) {
        document.getElementById('soundToggle').checked = settings.sound === true;
    }
    if (document.getElementById('desktopToggle')) {
        document.getElementById('desktopToggle').checked = settings.desktopNotifications === true;
    }
    if (document.getElementById('refreshInterval')) {
        document.getElementById('refreshInterval').value = settings.refreshInterval || 5;
    }
}

function saveSettings() {
    const settings = {
        darkMode: document.getElementById('darkModeToggle')?.checked ?? true,
        autoRefresh: document.getElementById('autoRefreshToggle')?.checked ?? true,
        sound: document.getElementById('soundToggle')?.checked ?? false,
        desktopNotifications: document.getElementById('desktopToggle')?.checked ?? false,
        refreshInterval: parseInt(document.getElementById('refreshInterval')?.value || '5')
    };

    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    showToast('Settings saved successfully', 'success');
    closeModal();
}

function toggleDarkMode() {
    const isDark = document.getElementById('darkModeToggle').checked;
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    showToast(`${isDark ? 'Dark' : 'Light'} mode enabled`, 'info', 2000);
}

function toggleAutoRefresh() {
    const isEnabled = document.getElementById('autoRefreshToggle').checked;
    state.autoRefresh = isEnabled;
    showToast(`Auto-refresh ${isEnabled ? 'enabled' : 'disabled'}`, 'info', 2000);
}

function toggleSound() {
    const isEnabled = document.getElementById('soundToggle').checked;
    showToast(`Sound alerts ${isEnabled ? 'enabled' : 'disabled'}`, 'info', 2000);
}

function toggleDesktopNotifications() {
    const isEnabled = document.getElementById('desktopToggle').checked;

    if (isEnabled && 'Notification' in window) {
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                showToast('Desktop notifications enabled', 'success', 2000);
            } else {
                document.getElementById('desktopToggle').checked = false;
                showToast('Desktop notifications permission denied', 'error');
            }
        });
    } else {
        showToast('Desktop notifications disabled', 'info', 2000);
    }
}

function updateRefreshInterval() {
    const interval = parseInt(document.getElementById('refreshInterval').value);
    if (interval >= 1 && interval <= 60) {
        showToast(`Refresh interval set to ${interval}s`, 'info', 2000);
    }
}

// ===== USER MENU FUNCTIONS =====

function showActivityLog() {
    closeUserMenu();
    showToast('Opening activity log...', 'info');
    // TODO: Implement activity log modal
    setTimeout(() => {
        showToast('Activity log feature coming soon', 'info');
    }, 500);
}

function showAbout() {
    closeUserMenu();
    showToast('AI Safety System v0.4.1-dev', 'info', 4000);
}

function logout() {
    closeUserMenu();
    if (confirm('Are you sure you want to logout?')) {
        showToast('Logging out...', 'info');
        setTimeout(() => {
            window.location.href = '/logout';
        }, 1000);
    }
}

function closeUserMenu() {
    const dropdown = document.getElementById('userMenuDropdown');
    if (dropdown) {
        dropdown.classList.remove('active');
    }
}

// ===== INITIALIZATION =====

document.addEventListener('DOMContentLoaded', () => {
    console.log('🛡️  AI Safety System UI Loaded');

    // Setup real-time updates
    setupRealTimeUpdates();

    // Add smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Add loading states to forms
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            }
        });
    });

    // Initialize tooltips
    document.querySelectorAll('[title]').forEach(el => {
        el.setAttribute('data-tooltip', el.getAttribute('title'));
    });

    // Welcome toast removed - only show warnings/errors

    // Initialize WORM badge if present on the page
    initWormBadgeSafe();

    // Poll for HALT status and show banner
    initHaltBannerPolling();
});

// ===== EXPORT FUNCTIONS =====

async function exportDetectionData() {
    try {
        showToast('Preparing detection data export...', 'info');

        const response = await fetch('/api/detection/export');

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `detection_data_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('Detection data exported successfully', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Failed to export detection data', 'error');
    }
}

async function exportAgentData() {
    try {
        showToast('Preparing agent data export...', 'info');

        const response = await fetch('/api/penalties/export');

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `agent_penalties_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('Agent data exported successfully', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Failed to export agent data', 'error');
    }
}

async function exportProposals() {
    try {
        showToast('Preparing proposals export...', 'info');

        // Get current filters
        const statusFilter = document.getElementById('statusFilter')?.value || 'all';
        const componentFilter = document.getElementById('componentFilter')?.value || 'all';
        const agentFilter = document.getElementById('agentFilter')?.value || 'all';

        let url = '/api/proposals/export?';
        if (statusFilter !== 'all') url += `status=${statusFilter}&`;
        if (componentFilter !== 'all') url += `component=${componentFilter}&`;
        if (agentFilter !== 'all') url += `agent=${agentFilter}&`;

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `proposals_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);

        showToast('Proposals exported successfully', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Failed to export proposals', 'error');
    }
}

async function valExport() {
    try {
        showToast('Preparing VAL export...', 'info');

        const response = await fetch('/api/admin/val/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `val_audit_log_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('VAL data exported successfully', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Failed to export VAL data', 'error');
    }
}

async function exportOrkaReport() {
    try {
        showToast('Generating ORKA full report...', 'info');

        const response = await fetch('/api/orka/export-report');

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `orka_full_report_${new Date().toISOString().split('T')[0]}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('ORKA report exported successfully', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Failed to export ORKA report', 'error');
    }
}

// Refresh functions for various pages
function refreshDetection() {
    showToast('Refreshing detection data...', 'info');
    window.location.reload();
}

function refreshAgentData() {
    showToast('Refreshing agent data...', 'info');
    window.location.reload();
}

function refreshProposals() {
    showToast('Refreshing proposals...', 'info');
    window.location.reload();
}

function filterProposals() {
    // This would typically filter without a full reload
    // For now, just reload to apply filters
    window.location.reload();
}

// ===== EXPORT FOR GLOBAL USE =====

window.AISystem = {
    showToast,
    showBanner,
    showModal,
    closeModal,
    emergencyHalt,
    confirmEmergencyHalt,
    fetchJSON,
    formatTimestamp,
    formatBytes,
    createChart,
    exportDetectionData,
    exportAgentData,
    exportProposals,
    valExport,
    exportOrkaReport,
    refreshDetection,
    refreshAgentData,
    refreshProposals,
    filterProposals
};

// ===== WORM BADGE (global, safe init) =====
function initWormBadgeSafe(){
  const badge = document.getElementById('wormBadge');
  const panel = document.getElementById('wormBadgePanel');
  if(!badge) return; // Not on this page/template

  let __wormLast = null;
  async function refresh(){
    try{
      const res = await fetch('/api/worm/status');
      const d = await res.json();
      const text = document.getElementById('wormBadgeText');
      let cls = 'worm-unknown';
      if(!d.exists || d.verified === false){ cls = 'worm-err'; }
      else if(d.exists && d.verified === true && (d.read_only === true || d.read_only == null)){ cls = 'worm-ok'; }
      else if(d.exists && d.read_only === false){ cls = 'worm-warn'; }
      badge.className = 'worm-badge ' + cls;
      if(text){ text.textContent = (cls==='worm-ok'?'WORM OK':(cls==='worm-warn'?'WORM WARN':'WORM ERR')); }
      __wormLast = { d, ts: new Date() };
      if(panel){
        const rows = [
          ['Path', d.path || ''],
          ['Exists', d.exists ? 'Yes' : 'No'],
          ['Verified', d.verified === true ? 'Yes' : (d.verified === false ? 'No' : 'Unknown')],
          ['Read-only', d.read_only === true ? 'Yes' : (d.read_only === false ? 'No' : 'Unknown')],
          ['Fail-closed', d.fail_closed ? 'ENABLED' : 'off'],
          ['Last check', new Date().toLocaleString()],
        ];
        panel.innerHTML = '<h4><i class="fas fa-usb"></i> WORM Details</h4>'
          + rows.map(r=>`<div class="row"><span>${r[0]}</span><span>${r[1]}</span></div>`).join('');
      }
    }catch(e){ /* leave unknown */ }
  }
  refresh();
  setInterval(refresh, 15000);

  if(panel){
    let over=false, overPanel=false, hideTimer=null;
    const scheduleHide=()=>{ clearTimeout(hideTimer); hideTimer=setTimeout(()=>{ if(!over && !overPanel) panel.style.display='none'; }, 200); };
    badge.addEventListener('mouseenter', ()=>{ over=true; panel.style.display='block'; });
    badge.addEventListener('mouseleave', ()=>{ over=false; scheduleHide(); });
    panel.addEventListener('mouseenter', ()=>{ overPanel=true; });
    panel.addEventListener('mouseleave', ()=>{ overPanel=false; scheduleHide(); });
  }
}

// ===== HALT BANNER =====
function initHaltBannerPolling(){
  const banner = document.getElementById('haltBanner');
  if(!banner) return;
  async function refresh(){
    try{
      const res = await fetch('/api/system/halted');
      const j = await res.json();
      if(j.halted){
        banner.style.display = 'block';
        updateSystemStatus('halted');
      } else {
        banner.style.display = 'none';
      }
    }catch(e){ /* ignore */ }
  }
  refresh();
  setInterval(refresh, 10000);
}
