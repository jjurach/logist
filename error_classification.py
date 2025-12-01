"""
Error classification and handling system for Logist jobs.

This module provides sophisticated error classification, recovery strategies,
and escalation logic to ensure robust job execution with appropriate human intervention.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import time


class ErrorSeverity(Enum):
    """Error severity levels determining escalation and recovery behavior."""
    TRANSIENT = "transient"      # Auto-retry, no intervention needed
    RECOVERABLE = "recoverable"  # Human intervention can fix
    FATAL = "fatal"             # Job cancellation required


class ErrorCategory(Enum):
    """Categorization of error types for targeted handling."""
    NETWORK = "network"              # API connectivity, timeouts
    VALIDATION = "validation"        # JSON parsing, schema validation
    RESOURCE = "resource"            # Quotas, limits exceeded
    EXECUTION = "execution"          # CLINE execution failures
    CONFIGURATION = "configuration"  # Invalid job setup
    SYSTEM = "system"               # File system, permissions


@dataclass
class ErrorClassification:
    """Complete error classification with handling instructions."""
    severity: ErrorSeverity
    category: ErrorCategory
    description: str
    user_message: str
    can_retry: bool
    max_retries: int
    intervention_required: bool
    suggested_action: str
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "description": self.description,
            "user_message": self.user_message,
            "can_retry": self.can_retry,
            "max_retries": self.max_retries,
            "intervention_required": self.intervention_required,
            "suggested_action": self.suggested_action,
            "correlation_id": self.correlation_id
        }


class ErrorClassifier:
    """Classifies errors and provides recovery strategies."""

    def __init__(self):
        self.correlation_counter = 0

    def _generate_correlation_id(self) -> str:
        """Generate unique correlation ID for error tracking."""
        import uuid
        return f"error_{uuid.uuid4().hex[:8]}"

    def classify_subprocess_error(self, returncode: int, stderr: str, stdout: str) -> ErrorClassification:
        """
        Classify errors from subprocess execution (CLINE, git, etc.).

        Args:
            returncode: Process exit code
            stderr: Standard error output
            stdout: Standard output

        Returns:
            ErrorClassification with handling instructions
        """
        correlation_id = self._generate_correlation_id()
        combined_output = (stdout + stderr).lower()

        # CLINE-specific exit codes and error patterns
        if returncode == 124:  # timeout
            return ErrorClassification(
                severity=ErrorSeverity.TRANSIENT,
                category=ErrorCategory.EXECUTION,
                description="CLINE execution timed out",
                user_message="LLM execution timed out. This is usually temporary.",
                can_retry=True,
                max_retries=2,
                intervention_required=False,
                suggested_action="Automatic retry with increased timeout",
                correlation_id=correlation_id
            )

        if returncode == 1:  # General error
            # Check for specific CLINE error patterns
            if "api key" in combined_output or "authentication" in combined_output:
                return ErrorClassification(
                    severity=ErrorSeverity.FATAL,
                    category=ErrorCategory.CONFIGURATION,
                    description="API authentication failed",
                    user_message="API key or authentication configuration error.",
                    can_retry=False,
                    max_retries=0,
                    intervention_required=True,
                    suggested_action="Check API keys and authentication setup",
                    correlation_id=correlation_id
                )

            if "quota exceeded" in combined_output or "rate limit" in combined_output:
                return ErrorClassification(
                    severity=ErrorSeverity.RECOVERABLE,
                    category=ErrorCategory.RESOURCE,
                    description="API quota or rate limit exceeded",
                    user_message="API quota exceeded. Please wait or check billing.",
                    can_retry=True,
                    max_retries=1,
                    intervention_required=True,
                    suggested_action="Wait for quota reset or upgrade plan",
                    correlation_id=correlation_id
                )

            if "network" in combined_output or "connection" in combined_output:
                return ErrorClassification(
                    severity=ErrorSeverity.TRANSIENT,
                    category=ErrorCategory.NETWORK,
                    description="Network connectivity issue",
                    user_message="Network connection failed. This is usually temporary.",
                    can_retry=True,
                    max_retries=3,
                    intervention_required=False,
                    suggested_action="Automatic retry with exponential backoff",
                    correlation_id=correlation_id
                )

            # Default CLINE error
            return ErrorClassification(
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.EXECUTION,
                description=f"CLINE execution failed with code {returncode}",
                user_message=f"LLM execution failed. Please check the error details.",
                can_retry=True,
                max_retries=1,
                intervention_required=True,
                suggested_action="Review error output and job configuration",
                correlation_id=correlation_id
            )

        if returncode == 2:  # File/directory errors
            return ErrorClassification(
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.SYSTEM,
                description="File system error in CLINE execution",
                user_message="File system error occurred during execution.",
                can_retry=False,
                max_retries=0,
                intervention_required=True,
                suggested_action="Check file permissions and workspace setup",
                correlation_id=correlation_id
            )

        # Success case
        if returncode == 0:
            return ErrorClassification(
                severity=ErrorSeverity.TRANSIENT,
                category=ErrorCategory.EXECUTION,
                description="Successful execution",
                user_message="No error occurred",
                can_retry=False,
                max_retries=0,
                intervention_required=False,
                suggested_action="Continue normal operation",
                correlation_id=correlation_id
            )

        # Unknown exit code
        return ErrorClassification(
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.EXECUTION,
            description=f"Unknown subprocess exit code: {returncode}",
            user_message=f"Unexpected error occurred (exit code {returncode}).",
            can_retry=True,
            max_retries=1,
            intervention_required=True,
            suggested_action="Review error output and contact support if needed",
            correlation_id=correlation_id
        )

    def classify_json_error(self, error: Exception, raw_content: str) -> ErrorClassification:
        """
        Classify JSON parsing and validation errors.

        Args:
            error: The parsing/validation exception
            raw_content: Raw content that failed to parse

        Returns:
            ErrorClassification with handling instructions
        """
        correlation_id = self._generate_correlation_id()
        error_str = str(error).lower()
        content_preview = raw_content[:200] if raw_content else ""

        if "json" in error_str and ("decode" in error_str or "parse" in error_str):
            # JSON parsing error from LLM
            return ErrorClassification(
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.VALIDATION,
                description="LLM returned malformed JSON",
                user_message="The LLM response contained invalid JSON format.",
                can_retry=True,
                max_retries=2,
                intervention_required=True,
                suggested_action="LLM may need better JSON formatting instructions",
                correlation_id=correlation_id
            )

        if "schema" in error_str or "validation" in error_str:
            # Schema validation error
            return ErrorClassification(
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.VALIDATION,
                description="LLM response failed schema validation",
                user_message="The LLM response didn't match expected format.",
                can_retry=True,
                max_retries=1,
                intervention_required=True,
                suggested_action="Review response format requirements with LLM",
                correlation_id=correlation_id
            )

        # Generic JSON error
        return ErrorClassification(
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.VALIDATION,
            description=f"JSON processing error: {str(error)}",
            user_message="Error processing structured data from LLM response.",
            can_retry=True,
            max_retries=1,
            intervention_required=True,
            suggested_action="Check LLM response format and schema requirements",
            correlation_id=correlation_id
        )

    def classify_timeout_error(self, timeout_seconds: int, operation: str) -> ErrorClassification:
        """
        Classify timeout errors.

        Args:
            timeout_seconds: Timeout duration that was exceeded
            operation: Description of the operation that timed out

        Returns:
            ErrorClassification with handling instructions
        """
        correlation_id = self._generate_correlation_id()

        return ErrorClassification(
            severity=ErrorSeverity.TRANSIENT,
            category=ErrorCategory.EXECUTION,
            description=f"{operation} timed out after {timeout_seconds} seconds",
            user_message=f"Operation timed out. This is usually temporary.",
            can_retry=True,
            max_retries=2,
            intervention_required=False,
            suggested_action="Automatic retry with longer timeout",
            correlation_id=correlation_id
        )

    def classify_system_error(self, error: Exception, operation: str) -> ErrorClassification:
        """
        Classify system-level errors (file system, permissions, etc.).

        Args:
            error: The system exception
            operation: Description of the operation that failed

        Returns:
            ErrorClassification with handling instructions
        """
        correlation_id = self._generate_correlation_id()
        error_str = str(error).lower()

        if "permission denied" in error_str or "access denied" in error_str:
            return ErrorClassification(
                severity=ErrorSeverity.FATAL,
                category=ErrorCategory.SYSTEM,
                description=f"Permission denied during {operation}",
                user_message="File system permissions prevent operation.",
                can_retry=False,
                max_retries=0,
                intervention_required=True,
                suggested_action="Check file permissions and user access rights",
                correlation_id=correlation_id
            )

        if "no such file" in error_str or "file not found" in error_str:
            return ErrorClassification(
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.SYSTEM,
                description=f"Required file missing during {operation}",
                user_message="Required file or directory is missing.",
                can_retry=False,
                max_retries=0,
                intervention_required=True,
                suggested_action="Verify file paths and recreate missing files",
                correlation_id=correlation_id
            )

        if "disk" in error_str and ("full" in error_str or "space" in error_str):
            return ErrorClassification(
                severity=ErrorSeverity.FATAL,
                category=ErrorCategory.RESOURCE,
                description="Disk space exhausted",
                user_message="No disk space available for operation.",
                can_retry=False,
                max_retries=0,
                intervention_required=True,
                suggested_action="Free up disk space and retry",
                correlation_id=correlation_id
            )

        # Generic system error
        return ErrorClassification(
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.SYSTEM,
            description=f"System error during {operation}: {str(error)}",
            user_message="System-level error occurred during operation.",
            can_retry=True,
            max_retries=1,
            intervention_required=True,
            suggested_action="Check system resources and configuration",
            correlation_id=correlation_id
        )


# Global error classifier instance
error_classifier = ErrorClassifier()


def classify_error(error: Exception, context: Dict[str, Any]) -> ErrorClassification:
    """
    Main entry point for error classification.

    Args:
        error: The exception that occurred
        context: Context information about the error

    Returns:
        ErrorClassification with handling instructions
    """
    error_type = context.get("error_type", "unknown")
    operation = context.get("operation", "unknown operation")

    if error_type == "subprocess":
        returncode = context.get("returncode", -1)
        stderr = context.get("stderr", "")
        stdout = context.get("stdout", "")
        return error_classifier.classify_subprocess_error(returncode, stderr, stdout)

    elif error_type == "json":
        raw_content = context.get("raw_content", "")
        return error_classifier.classify_json_error(error, raw_content)

    elif error_type == "timeout":
        timeout_seconds = context.get("timeout_seconds", 0)
        return error_classifier.classify_timeout_error(timeout_seconds, operation)

    elif error_type == "system":
        return error_classifier.classify_system_error(error, operation)

    else:
        # Generic error classification
        correlation_id = error_classifier._generate_correlation_id()
        return ErrorClassification(
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.EXECUTION,
            description=f"Unhandled error: {str(error)}",
            user_message="An unexpected error occurred.",
            can_retry=True,
            max_retries=1,
            intervention_required=True,
            suggested_action="Review error details and retry operation",
            correlation_id=correlation_id
        )


def should_retry_error(classification: ErrorClassification, attempt_count: int) -> bool:
    """
    Determine if an error should trigger a retry based on classification and attempt history.

    Args:
        classification: The error classification
        attempt_count: Number of previous attempts (0-based)

    Returns:
        True if retry should be attempted
    """
    if not classification.can_retry:
        return False

    return attempt_count < classification.max_retries


def get_retry_delay(classification: ErrorClassification, attempt_count: int) -> float:
    """
    Calculate delay before retry based on error classification and attempt count.

    Args:
        classification: The error classification
        attempt_count: Number of previous attempts (0-based)

    Returns:
        Delay in seconds before retry
    """
    if classification.category == ErrorCategory.NETWORK:
        # Exponential backoff for network errors
        base_delay = 1.0
        return base_delay * (2 ** attempt_count)

    elif classification.category == ErrorCategory.RESOURCE:
        # Longer delay for resource/quota issues
        return 30.0 * (attempt_count + 1)

    else:
        # Default short delay
        return 1.0


def get_new_job_status(classification: ErrorClassification) -> str:
    """
    Determine appropriate job status based on error classification.

    Args:
        classification: The error classification

    Returns:
        New job status string
    """
    if classification.severity == ErrorSeverity.TRANSIENT:
        # Transient errors don't change job status - just retry
        return None

    elif classification.severity == ErrorSeverity.RECOVERABLE:
        # Recoverable errors require intervention
        return "INTERVENTION_REQUIRED"

    elif classification.severity == ErrorSeverity.FATAL:
        # Fatal errors cancel the job
        return "CANCELED"

    return "INTERVENTION_REQUIRED"  # Default fallback