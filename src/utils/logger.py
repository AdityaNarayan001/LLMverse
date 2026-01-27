"""
Centralized logging utility for LLMverse.

Provides structured logging with context, WebSocket emission, and file output.
All modules should use get_logger(__name__) to obtain a logger instance.
"""

import logging
import os
import sys
import time
from datetime import datetime
from collections import deque
from functools import wraps
from typing import Any, Optional, Dict
from contextlib import contextmanager

# Global configuration
LOG_DIR = 'logs'
LOG_FILE = 'llmverse.log'
MAX_LOG_ENTRIES = 1000
DEFAULT_LEVEL = logging.INFO

# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


class StructuredFormatter(logging.Formatter):
    """Custom formatter that adds structured context to log messages."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }
    
    ICONS = {
        'DEBUG': '🔍',
        'INFO': '📋',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        # Add context if available
        context = getattr(record, 'context', {})
        context_str = ''
        if context:
            context_str = ' | ' + ' '.join(f'{k}={v}' for k, v in context.items())
        
        # Build the message
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        level = record.levelname
        icon = self.ICONS.get(level, '')
        
        if self.use_colors:
            color = self.COLORS.get(level, '')
            reset = self.COLORS['RESET']
            formatted = f"{timestamp} {color}{icon} [{level:8}]{reset} {record.name}: {record.getMessage()}{context_str}"
        else:
            formatted = f"{timestamp} {icon} [{level:8}] {record.name}: {record.getMessage()}{context_str}"
        
        # Add exception info if present
        if record.exc_info:
            formatted += '\n' + self.formatException(record.exc_info)
        
        return formatted


class WebSocketHandler(logging.Handler):
    """Handler that emits logs to connected WebSocket clients."""
    
    _instance = None
    _socketio = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logs = deque(maxlen=MAX_LOG_ENTRIES)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
    
    @classmethod
    def set_socketio(cls, socketio):
        """Set the SocketIO instance for real-time log emission."""
        cls._socketio = socketio
    
    def emit(self, record: logging.LogRecord):
        try:
            context = getattr(record, 'context', {})
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
                'name': record.name,
                'line': record.lineno,
                'context': context
            }
            self.logs.append(log_entry)
            
            # Emit to WebSocket if available
            if self._socketio:
                self._socketio.emit('new_log', log_entry)
        except Exception:
            self.handleError(record)
    
    def get_recent_logs(self, count: int = 100) -> list:
        """Get recent log entries."""
        return list(self.logs)[-count:]


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that supports structured context."""
    
    def __init__(self, logger: logging.Logger, extra: Optional[Dict] = None):
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: Dict) -> tuple:
        # Merge extra context with any provided in the call
        context = {**self.extra}
        if 'extra' in kwargs:
            if 'context' in kwargs['extra']:
                context.update(kwargs['extra']['context'])
            kwargs['extra']['context'] = context
        else:
            kwargs['extra'] = {'context': context}
        return msg, kwargs
    
    def with_context(self, **context) -> 'ContextAdapter':
        """Create a new adapter with additional context."""
        new_context = {**self.extra, **context}
        return ContextAdapter(self.logger, new_context)


# Global handlers (singletons)
_ws_handler = WebSocketHandler()
_ws_handler.setLevel(DEFAULT_LEVEL)
_ws_handler.setFormatter(StructuredFormatter(use_colors=False))

_file_handler = logging.FileHandler(os.path.join(LOG_DIR, LOG_FILE))
_file_handler.setLevel(DEFAULT_LEVEL)
_file_handler.setFormatter(StructuredFormatter(use_colors=False))

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(DEFAULT_LEVEL)
_console_handler.setFormatter(StructuredFormatter(use_colors=True))

# Track configured loggers
_configured_loggers = set()


def get_logger(name: str, **context) -> ContextAdapter:
    """
    Get a logger instance with optional context.
    
    Args:
        name: Logger name (typically __name__)
        **context: Optional key-value pairs to include in all log messages
    
    Returns:
        ContextAdapter with structured logging support
    
    Example:
        logger = get_logger(__name__, agent_id=1, provider='ollama')
        logger.info("Processing request")
        # Output: 2024-01-27 10:30:00 📋 [INFO    ] module: Processing request | agent_id=1 provider=ollama
    """
    logger = logging.getLogger(name)
    
    # Configure logger only once
    if name not in _configured_loggers:
        logger.setLevel(DEFAULT_LEVEL)
        logger.addHandler(_ws_handler)
        logger.addHandler(_file_handler)
        logger.addHandler(_console_handler)
        logger.propagate = False
        _configured_loggers.add(name)
    
    return ContextAdapter(logger, context)


@contextmanager
def LogContext(**context):
    """
    Context manager for temporary logging context.
    
    Example:
        with LogContext(request_id='abc123'):
            logger.info("Processing")  # Includes request_id in context
    """
    # This is a placeholder - actual implementation would need thread-local storage
    yield


def log_timing(logger: ContextAdapter, operation: str):
    """
    Decorator to log timing of operations.
    
    Example:
        @log_timing(logger, "LLM generation")
        def generate_response(prompt):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info(f"{operation} completed", extra={'context': {'elapsed_ms': f'{elapsed*1000:.2f}'}})
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error(f"{operation} failed: {e}", extra={'context': {'elapsed_ms': f'{elapsed*1000:.2f}'}})
                raise
        return wrapper
    return decorator


def get_websocket_handler() -> WebSocketHandler:
    """Get the global WebSocket handler instance."""
    return _ws_handler
