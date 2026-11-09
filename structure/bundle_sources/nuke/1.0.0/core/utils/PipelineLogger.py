"""
Pipeline Logger - Centralized Logging System

A comprehensive logging utility for the Nuke pipeline that provides consistent
logging across all modules with proper formatting, file output, and debug levels.

It is built on the shared studio logging in tls_common: every logger lives under "tls.nuke", the
console and file handlers sit on the "tls" logger, and the root logger (which AYON and Nuke also use)
is never touched. The API used by the rest of the pipeline (get_logger, set_log_level, log_performance,
log_function_call, get_log_stats, log_calls) is unchanged.

Author: Pipeline Team
Date: July 2025
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from tls_common import NukeLogger, get_logger as _tls_get_logger
from tls_common.log import ROOT_NAME


class PipelineLogger:
    """
    Centralized logging system for the pipeline.
    
    Provides consistent logging across all pipeline modules with configurable
    output levels, file logging, and formatted output.
    """
    
    _instance = None
    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super(PipelineLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the pipeline logger."""
        if not self._initialized:
            self.log_dir = self._get_log_directory()
            self.log_level = logging.INFO
            self.console_level = logging.INFO
            self.file_level = logging.DEBUG
            self.max_log_files = 10
            self._setup_logging()
            PipelineLogger._initialized = True
    
    def _get_log_directory(self) -> Path:
        """
        Get the logging directory for the pipeline.
        
        Returns:
            Path: Path to the logging directory
        """
        # Logs belong outside the release: TLS_LOG_DIR is set by the bundle entry to the localiser's logs folder
        configured = os.environ.get("TLS_LOG_DIR")
        log_dir = Path(configured) if configured else Path(__file__).parent.parent / "logs"
        
        # Create logs directory if it doesn't exist
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
        except (PermissionError, OSError):
            # Fallback to temp directory if we can't write to pipeline directory
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "nuke_pipeline_logs"
            temp_dir.mkdir(exist_ok=True)
            return temp_dir
    
    def _setup_logging(self) -> None:
        """Attach the console and file handlers to the studio "tls" logger."""
        NukeLogger.logger_obj()  # makes tls_common create the "tls" logger and its console handler
        root = logging.getLogger(ROOT_NAME)

        # TLS_LOG_LEVEL (read by tls_common) decides the console level when it is set
        self.console_level = root.level or self.console_level
        for handler in self._console_handlers():
            handler.setLevel(self.console_level)

        # File handler: one file per day, named like the old pipeline logs
        log_file = self.log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            NukeLogger.write_to_file(log_file, self.file_level)
            self._cleanup_old_logs()
        except (PermissionError, OSError) as e:
            # If we can't write to file, just use console logging
            for handler in self._console_handlers():
                handler.setLevel(logging.DEBUG)
            self.console_level = logging.DEBUG
            NukeLogger.warning("Could not set up file logging: %s", e)

        # The logger passes on whatever the most verbose handler wants
        root.setLevel(min(self.console_level, self.file_level))

    @staticmethod
    def _console_handlers():
        root = logging.getLogger(ROOT_NAME)
        return [h for h in root.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
    
    def _cleanup_old_logs(self) -> None:
        """Clean up old log files to prevent disk space issues."""
        try:
            log_files = sorted(
                [f for f in self.log_dir.glob("pipeline_*.log")],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Keep only the most recent files
            for old_file in log_files[self.max_log_files:]:
                try:
                    old_file.unlink()
                except OSError:
                    pass  # Ignore errors when deleting old files
                    
        except (OSError, PermissionError):
            pass  # Ignore errors during cleanup
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.
        
        Args:
            name (str): Name of the logger (usually module name)
            
        Returns:
            logging.Logger: Configured logger instance
        """
        if name not in self._loggers:
            self._loggers[name] = _tls_get_logger("nuke." + name)
        
        return self._loggers[name]
    
    def set_level(self, level: int, handler_type: str = "all") -> None:
        """
        Set logging level for console, file, or both.
        
        Args:
            level (int): Logging level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
            handler_type (str): "console", "file", or "all"
        """
        root = logging.getLogger(ROOT_NAME)
        
        if handler_type in ("console", "all"):
            for handler in self._console_handlers():
                handler.setLevel(level)
            self.console_level = level
        
        if handler_type in ("file", "all"):
            for handler in root.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.setLevel(level)
            self.file_level = level
        
        root.setLevel(min(self.console_level, self.file_level))
    
    def log_function_call(self, func_name: str, args: tuple = (), kwargs: dict = None) -> None:
        """
        Log a function call with its arguments (useful for debugging).
        
        Args:
            func_name (str): Name of the function being called
            args (tuple): Positional arguments
            kwargs (dict): Keyword arguments
        """
        logger = self.get_logger("FunctionCalls")
        kwargs = kwargs or {}
        
        args_str = ", ".join([repr(arg) for arg in args])
        kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in kwargs.items()])
        
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        logger.debug(f"Calling {func_name}({all_args})")
    
    def log_performance(self, operation: str, duration: float, details: dict = None) -> None:
        """
        Log performance metrics for operations.
        
        Args:
            operation (str): Name of the operation
            duration (float): Duration in seconds
            details (dict): Additional details about the operation
        """
        logger = self.get_logger("Performance")
        details = details or {}
        
        details_str = ", ".join([f"{k}={v}" for k, v in details.items()])
        logger.info(f"Performance: {operation} took {duration:.3f}s ({details_str})")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get logging statistics.
        
        Returns:
            Dict[str, Any]: Dictionary with logging statistics
        """
        stats = {
            'log_directory': str(self.log_dir),
            'console_level': logging.getLevelName(self.console_level),
            'file_level': logging.getLevelName(self.file_level),
            'active_loggers': list(self._loggers.keys()),
            'log_files': []
        }
        
        try:
            log_files = list(self.log_dir.glob("pipeline_*.log"))
            stats['log_files'] = [
                {
                    'name': f.name,
                    'size': f.stat().st_size,
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                }
                for f in log_files
            ]
        except (OSError, PermissionError):
            pass
        
        return stats


# Global instance
pipeline_logger = PipelineLogger()


# Convenience functions for easy access
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return pipeline_logger.get_logger(name)


def set_log_level(level: int, handler_type: str = "all") -> None:
    """Set logging level."""
    pipeline_logger.set_level(level, handler_type)


def log_function_call(func_name: str, args: tuple = (), kwargs: dict = None) -> None:
    """Log a function call."""
    pipeline_logger.log_function_call(func_name, args, kwargs)


def log_performance(operation: str, duration: float, details: dict = None) -> None:
    """Log performance metrics."""
    pipeline_logger.log_performance(operation, duration, details)


def get_log_stats() -> Dict[str, Any]:
    """Get logging statistics."""
    return pipeline_logger.get_log_stats()


# Decorator for automatic function call logging
def log_calls(logger_name: str = None):
    """
    Decorator to automatically log function calls.
    
    Args:
        logger_name (str): Optional logger name, defaults to module name
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = logger_name or func.__module__
            logger = get_logger(name)
            
            # Log the call
            args_str = ", ".join([repr(arg) for arg in args])
            kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in kwargs.items()])
            all_args = ", ".join(filter(None, [args_str, kwargs_str]))
            
            logger.debug(f"Calling {func.__name__}({all_args})")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} failed: {e}")
                raise
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # Example usage
    logger = get_logger("TestModule")
    logger.info("Pipeline logger initialized")
    logger.debug("This is a debug message")
    logger.warning("This is a warning")
    
    # Test performance logging
    import time
    start = time.time()
    time.sleep(0.1)
    log_performance("test_operation", time.time() - start, {"items": 10})
    
    # Print stats
    import json
    print(json.dumps(get_log_stats(), indent=2))
