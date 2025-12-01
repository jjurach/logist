"""
Structured error logging system for Logist jobs.

This module provides comprehensive error logging, correlation tracking,
and debugging support for the error handling system.
"""

import json
import os
import logging
import logging.handlers
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from logist.error_classification import ErrorClassification


class ErrorLogger:
    """Structured error logging system with correlation tracking."""

    def __init__(self, log_directory: str = None):
        """
        Initialize the error logger.

        Args:
            log_directory: Directory to store error logs (default: ~/.logist/logs/errors)
        """
        if log_directory is None:
            home_dir = os.path.expanduser("~")
            log_directory = os.path.join(home_dir, ".logist", "logs", "errors")

        self.log_directory = log_directory
        self._ensure_log_directory()

        # Set up Python logging
        self._setup_logging()

        # Error metrics tracking
        self.error_counts = {}
        self.correlation_tracking = {}

    def _ensure_log_directory(self) -> None:
        """Ensure the log directory exists."""
        os.makedirs(self.log_directory, exist_ok=True)

    def _setup_logging(self) -> None:
        """Set up Python logging with structured format."""
        # Main error log file - rotates daily, keeps 30 days
        error_log_path = os.path.join(self.log_directory, "errors.log")
        error_handler = logging.handlers.TimedRotatingFileHandler(
            error_log_path,
            when='midnight',
            backupCount=30,
            encoding='utf-8'
        )

        # Format for structured JSON logging
        formatter = JsonFormatter()
        error_handler.setFormatter(formatter)

        # Set up logger
        self.logger = logging.getLogger('logist.errors')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(error_handler)

        # Prevent duplicate handlers
        self.logger.propagate = False

    def log_error(self,
                  classification: ErrorClassification,
                  job_id: str,
                  job_dir: str,
                  error: Exception,
                  context: Dict[str, Any] = None) -> str:
        """
        Log an error with full classification and context.

        Args:
            classification: ErrorClassification object
            job_id: ID of the job where error occurred
            job_dir: Directory of the job
            error: The original exception
            context: Additional context information

        Returns:
            Correlation ID for tracking this error
        """
        correlation_id = classification.correlation_id

        # Create comprehensive log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "job_dir": job_dir,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "classification": classification.to_dict(),
            "context": context or {},
            "system_info": self._get_system_info()
        }

        # Log using structured logger
        self.logger.error("Job execution error", extra=log_entry)

        # Store correlation tracking
        self.correlation_tracking[correlation_id] = {
            "job_id": job_id,
            "timestamp": log_entry["timestamp"],
            "classification": classification.to_dict(),
            "resolved": False,
            "retry_count": 0,
            "last_retry": None
        }

        # Update error metrics
        error_key = f"{classification.category.value}:{classification.severity.value}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # Save correlation log separately for tracking
        self._save_correlation_log(correlation_id, log_entry)

        return correlation_id

    def _save_correlation_log(self, correlation_id: str, log_entry: Dict[str, Any]) -> None:
        """Save detailed correlation log for debugging."""
        correlation_dir = os.path.join(self.log_directory, "correlations")
        os.makedirs(correlation_dir, exist_ok=True)

        correlation_file = os.path.join(correlation_dir, f"{correlation_id}.json")

        try:
            with open(correlation_file, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Don't let log file write failures break error handling
            print(f"Warning: Failed to write correlation log {correlation_id}: {e}")

    def log_retry_attempt(self, correlation_id: str, attempt_number: int, delay_seconds: float) -> None:
        """
        Log a retry attempt for an error.

        Args:
            correlation_id: Error correlation ID
            attempt_number: Retry attempt number (0-based)
            delay_seconds: Delay before retry
        """
        if correlation_id in self.correlation_tracking:
            self.correlation_tracking[correlation_id]["retry_count"] = attempt_number + 1
            self.correlation_tracking[correlation_id]["last_retry"] = datetime.now().isoformat()

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "correlation_id": correlation_id,
            "event": "retry_attempt",
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds
        }

        self.logger.info("Error retry attempt", extra=log_entry)

    def log_resolution(self, correlation_id: str, resolution: str, successful: bool = True) -> None:
        """
        Log the resolution of an error.

        Args:
            correlation_id: Error correlation ID
            resolution: Description of how it was resolved
            successful: Whether the resolution was successful
        """
        if correlation_id in self.correlation_tracking:
            self.correlation_tracking[correlation_id]["resolved"] = True
            self.correlation_tracking[correlation_id]["resolution"] = resolution

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "correlation_id": correlation_id,
            "event": "error_resolution",
            "resolution": resolution,
            "successful": successful
        }

        log_level = logging.INFO if successful else logging.WARNING
        self.logger.log(log_level, "Error resolution", extra=log_entry)

    def get_error_metrics(self, since_hours: int = 24) -> Dict[str, Any]:
        """
        Get error metrics for the specified time period.

        Args:
            since_hours: Hours to look back for metrics

        Returns:
            Dictionary with error metrics
        """
        cutoff_time = datetime.now() - timedelta(hours=since_hours)

        metrics = {
            "period_hours": since_hours,
            "total_errors": 0,
            "errors_by_category": {},
            "errors_by_severity": {},
            "top_errors": []
        }

        # Count current error tally
        for error_key, count in self.error_counts.items():
            metrics["total_errors"] += count

            category, severity = error_key.split(':')
            metrics["errors_by_category"][category] = metrics["errors_by_category"].get(category, 0) + count
            metrics["errors_by_severity"][severity] = metrics["errors_by_severity"].get(severity, 0) + count

        # Get most common errors
        sorted_errors = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)
        metrics["top_errors"] = [{"error_type": k, "count": v} for k, v in sorted_errors[:10]]

        return metrics

    def get_correlation_details(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific error by correlation ID.

        Args:
            correlation_id: Error correlation ID

        Returns:
            Dictionary with error details if found
        """
        correlation_file = os.path.join(self.log_directory, "correlations", f"{correlation_id}.json")

        try:
            with open(correlation_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def find_related_errors(self, job_id: str, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Find all errors related to a specific job.

        Args:
            job_id: Job ID to search for
            hours_back: Hours to look back

        Returns:
            List of related error correlation details
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        related_errors = []

        correlation_dir = os.path.join(self.log_directory, "correlations")
        if not os.path.exists(correlation_dir):
            return related_errors

        for file_path in Path(correlation_dir).glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    error_data = json.load(f)

                if error_data.get("job_id") == job_id:
                    error_timestamp = datetime.fromisoformat(error_data["timestamp"])
                    if error_timestamp >= cutoff_time:
                        related_errors.append(error_data)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        # Sort by timestamp, most recent first
        related_errors.sort(key=lambda x: x["timestamp"], reverse=True)
        return related_errors

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for error context."""
        try:
            return {
                "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                "platform": os.sys.platform,
                "pid": os.getpid(),
                "working_directory": os.getcwd()
            }
        except Exception:
            return {"error": "Could not gather system info"}

    def cleanup_old_logs(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """
        Clean up old error logs and correlation files.

        Args:
            days_to_keep: Number of days of logs to keep

        Returns:
            Cleanup summary
        """
        cleanup_summary = {
            "correlation_files_removed": 0,
            "old_backups_cleaned": 0,
            "space_freed_kb": 0
        }

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        # Clean up old correlation files
        correlation_dir = os.path.join(self.log_directory, "correlations")
        if os.path.exists(correlation_dir):
            for file_path in Path(correlation_dir).glob("*.json"):
                try:
                    # Check file modification time
                    stat = file_path.stat()
                    file_time = datetime.fromtimestamp(stat.st_mtime)

                    if file_time < cutoff_date:
                        size_kb = stat.st_size / 1024
                        cleanup_summary["space_freed_kb"] += size_kb
                        file_path.unlink()
                        cleanup_summary["correlation_files_removed"] += 1

                except Exception:
                    continue

        return cleanup_summary


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        # Get the standard log record as dict
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add any extra fields from the record
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno',
                             'pathname', 'filename', 'module', 'exc_info',
                             'exc_text', 'stack_info', 'lineno', 'funcName',
                             'created', 'msecs', 'relativeCreated', 'thread',
                             'threadName', 'processName', 'process']:
                    log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False)


# Global error logger instance
error_logger = ErrorLogger()


def log_job_error(classification: ErrorClassification,
                  job_id: str,
                  job_dir: str,
                  error: Exception,
                  context: Dict[str, Any] = None) -> str:
    """
    Convenience function to log a job error.

    Returns:
        Correlation ID for tracking the error
    """
    return error_logger.log_error(classification, job_id, job_dir, error, context)


def get_error_metrics(hours: int = 24) -> Dict[str, Any]:
    """
    Get error metrics for the specified period.
    """
    return error_logger.get_error_metrics(hours)


def find_job_errors(job_id: str, hours_back: int = 24) -> List[Dict[str, Any]]:
    """
    Find all errors for a specific job.
    """
    return error_logger.find_related_errors(job_id, hours_back)