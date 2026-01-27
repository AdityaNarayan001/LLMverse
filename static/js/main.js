// Global variables
let socket;
let connectionStatus = 'disconnected';

// ===========================================
// Frontend Logging Service
// ===========================================
const Logger = {
    logs: [],
    maxLogs: 500,
    listeners: [],
    
    levels: {
        DEBUG: { value: 0, icon: '🔍', color: '#6c757d' },
        INFO: { value: 1, icon: '📋', color: '#0d6efd' },
        WARNING: { value: 2, icon: '⚠️', color: '#ffc107' },
        ERROR: { value: 3, icon: '❌', color: '#dc3545' },
        CRITICAL: { value: 4, icon: '🚨', color: '#6f42c1' }
    },
    
    currentLevel: 'INFO',
    
    _log(level, message, context = {}) {
        const entry = {
            timestamp: new Date().toISOString(),
            level: level,
            message: message,
            context: context,
            module: 'frontend'
        };
        
        this.logs.push(entry);
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }
        
        // Console output with styling
        const levelInfo = this.levels[level];
        const contextStr = Object.keys(context).length > 0 
            ? ' | ' + Object.entries(context).map(([k, v]) => `${k}=${v}`).join(' ')
            : '';
        
        const style = `color: ${levelInfo.color}; font-weight: bold;`;
        console.log(`%c${levelInfo.icon} [${level}] ${message}${contextStr}`, style);
        
        // Notify listeners
        this.listeners.forEach(listener => listener(entry));
    },
    
    debug(message, context = {}) { this._log('DEBUG', message, context); },
    info(message, context = {}) { this._log('INFO', message, context); },
    warning(message, context = {}) { this._log('WARNING', message, context); },
    error(message, context = {}) { this._log('ERROR', message, context); },
    
    onLog(callback) {
        this.listeners.push(callback);
    },
    
    getLogs(count = 100, minLevel = 'DEBUG') {
        const minValue = this.levels[minLevel].value;
        return this.logs
            .filter(log => this.levels[log.level].value >= minValue)
            .slice(-count);
    }
};

// ===========================================
// Socket Connection
// ===========================================

// Initialize socket connection
document.addEventListener('DOMContentLoaded', function () {
    initializeSocket();
    updateConnectionStatus();
});

function initializeSocket() {
    socket = io();

    socket.on('connect', function () {
        connectionStatus = 'connected';
        updateConnectionStatus();
        Logger.info('Connected to LLMverse server');
    });

    socket.on('disconnect', function () {
        connectionStatus = 'disconnected';
        updateConnectionStatus();
        Logger.warning('Disconnected from LLMverse server');
    });

    socket.on('agent_created', function (data) {
        Logger.info('Agent created', { name: data.name });
        showToast(`Agent "${data.name}" created successfully`, 'success');
    });

    socket.on('agent_updated', function (data) {
        Logger.info('Agent updated', { name: data.name });
        showToast(`Agent "${data.name}" updated successfully`, 'success');
    });

    socket.on('agent_deleted', function (data) {
        Logger.info('Agent deleted');
        showToast('Agent deleted successfully', 'success');
    });

    socket.on('simulation_started', function (data) {
        Logger.info('Simulation started', { agents: data.active_agents });
        showToast('Simulation started', 'success');
    });

    socket.on('simulation_stopped', function (data) {
        Logger.info('Simulation stopped');
        showToast('Simulation stopped', 'info');
    });

    socket.on('environment_reset', function (data) {
        Logger.info('Environment reset');
        showToast('Environment reset successfully', 'success');
    });

    socket.on('environment_switched', function (data) {
        Logger.info('Environment switched', { name: data.environment.name });
        showToast(`Switched to environment: ${data.environment.name}`, 'info');
    });

    socket.on('agent_interaction', function (data) {
        Logger.debug('Agent interaction', { agent: data.agent_name, action: data.action });
        // Handle real-time agent interactions
        showToast(`${data.agent_name}: ${data.action}`, 'info');

        // Update interactions list if we're on the main page
        if (typeof loadRecentInteractions === 'function') {
            loadRecentInteractions();
        }
    });

    socket.on('agent_action', function (data) {
        Logger.debug('Agent action', { agent: data.agent_name });
        // Handle real-time agent actions
        showToast(`${data.agent_name} performed an action`, 'info');

        // Update interactions list if we're on the main page
        if (typeof loadRecentInteractions === 'function') {
            loadRecentInteractions();
        }
    });

    socket.on('broadcast_sent', function (data) {
        Logger.info('Broadcast sent', { message: data.message?.substring(0, 50) });
        showToast('Broadcast message sent to all agents', 'success');
    });
    
    // Listen for backend logs
    socket.on('new_log', function (data) {
        Logger.logs.push({
            ...data,
            module: data.module || 'backend'
        });
        if (Logger.logs.length > Logger.maxLogs) {
            Logger.logs.shift();
        }
        Logger.listeners.forEach(listener => listener(data));
    });
}

function updateConnectionStatus() {
    const statusElement = document.getElementById('connection-status');
    if (statusElement) {
        const icon = statusElement.querySelector('i');

        if (connectionStatus === 'connected') {
            icon.className = 'fas fa-circle text-success';
            statusElement.innerHTML = '<i class="fas fa-circle text-success"></i> Connected';
        } else {
            icon.className = 'fas fa-circle text-danger';
            statusElement.innerHTML = '<i class="fas fa-circle text-danger"></i> Disconnected';
        }
    }
}

function showToast(message, type = 'info') {
    const toastElement = document.getElementById('liveToast');
    const toastBody = toastElement.querySelector('.toast-body');
    const toastHeader = toastElement.querySelector('.toast-header');

    // Set message
    toastBody.textContent = message;

    // Set color based on type
    toastElement.className = 'toast';
    switch (type) {
        case 'success':
            toastElement.classList.add('text-bg-success');
            break;
        case 'error':
        case 'danger':
            toastElement.classList.add('text-bg-danger');
            break;
        case 'warning':
            toastElement.classList.add('text-bg-warning');
            break;
        case 'info':
        default:
            toastElement.classList.add('text-bg-info');
            break;
    }

    // Show toast
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
}

function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString();
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function () {
        showToast('Copied to clipboard', 'success');
    }, function (err) {
        showToast('Failed to copy to clipboard', 'error');
    });
}

// Utility functions for API calls
function apiCall(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const mergedOptions = { ...defaultOptions, ...options };

    return fetch(url, mergedOptions)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        });
}

function getApiCall(url) {
    return apiCall(url, { method: 'GET' });
}

function postApiCall(url, data) {
    return apiCall(url, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

function putApiCall(url, data) {
    return apiCall(url, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
}

function deleteApiCall(url) {
    return apiCall(url, { method: 'DELETE' });
}

// Auto-refresh functionality
let autoRefreshInterval;

function startAutoRefresh(callback, interval = 5000) {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }

    autoRefreshInterval = setInterval(callback, interval);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Page visibility API to pause/resume auto-refresh
document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        // Resume auto-refresh if it was previously active
        if (typeof window.resumeAutoRefresh === 'function') {
            window.resumeAutoRefresh();
        }
    }
});

// Loading state management
function showLoading(element) {
    if (typeof element === 'string') {
        element = document.getElementById(element);
    }

    if (element) {
        element.innerHTML = '<div class="text-center"><div class="loading-spinner"></div> Loading...</div>';
    }
}

function hideLoading(element, content = '') {
    if (typeof element === 'string') {
        element = document.getElementById(element);
    }

    if (element) {
        element.innerHTML = content;
    }
}

// Form validation helpers
function validateForm(formElement) {
    const inputs = formElement.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });

    return isValid;
}

function clearFormValidation(formElement) {
    const inputs = formElement.querySelectorAll('.is-invalid');
    inputs.forEach(input => {
        input.classList.remove('is-invalid');
    });
}

// Export functions for use in other scripts
window.LLMverse = {
    showToast,
    formatTime,
    formatDate,
    escapeHtml,
    debounce,
    copyToClipboard,
    apiCall,
    getApiCall,
    postApiCall,
    putApiCall,
    deleteApiCall,
    startAutoRefresh,
    stopAutoRefresh,
    showLoading,
    hideLoading,
    validateForm,
    clearFormValidation
};