// Global variables
let socket;
let connectionStatus = 'disconnected';

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
        console.log('Connected to LLMverse server');
    });

    socket.on('disconnect', function () {
        connectionStatus = 'disconnected';
        updateConnectionStatus();
        console.log('Disconnected from LLMverse server');
    });

    socket.on('agent_created', function (data) {
        showToast(`Agent "${data.name}" created successfully`, 'success');
    });

    socket.on('agent_updated', function (data) {
        showToast(`Agent "${data.name}" updated successfully`, 'success');
    });

    socket.on('agent_deleted', function (data) {
        showToast('Agent deleted successfully', 'success');
    });

    socket.on('simulation_started', function (data) {
        showToast('Simulation started', 'success');
    });

    socket.on('simulation_stopped', function (data) {
        showToast('Simulation stopped', 'info');
    });

    socket.on('environment_reset', function (data) {
        showToast('Environment reset successfully', 'success');
    });

    socket.on('environment_switched', function (data) {
        showToast(`Switched to environment: ${data.environment.name}`, 'info');
    });

    socket.on('agent_interaction', function (data) {
        console.log('Agent interaction:', data);
        // Handle real-time agent interactions
        showToast(`${data.agent_name}: ${data.action}`, 'info');

        // Update interactions list if we're on the main page
        if (typeof loadRecentInteractions === 'function') {
            loadRecentInteractions();
        }
    });

    socket.on('agent_action', function (data) {
        console.log('Agent action:', data);
        // Handle real-time agent actions
        showToast(`${data.agent_name} performed an action`, 'info');

        // Update interactions list if we're on the main page
        if (typeof loadRecentInteractions === 'function') {
            loadRecentInteractions();
        }
    });

    socket.on('broadcast_sent', function (data) {
        showToast('Broadcast message sent to all agents', 'success');
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