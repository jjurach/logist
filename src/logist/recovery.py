"""
Recovery module for Logist job state persistence and crash recovery.

This module provides functionality for:
- Job state backups and recovery
- Detection of hung processes
- Automatic recovery from stuck states
- Validation of job state survival across restarts
"""

import json
import os
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from logist.job_state import JobStateError, load_job_manifest


class RecoveryError(Exception):
    """Custom exception for recovery-related errors."""
    pass


def create_job_manifest_backup(job_dir: str) -> str:
    """
    Creates a timestamped backup of the current job manifest.

    Args:
        job_dir: Path to the job directory.

    Returns:
        Path to the backup file created.

    Raises:
        RecoveryError: If backup creation fails.
    """
    try:
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        if not os.path.exists(manifest_path):
            raise RecoveryError(f"No manifest to backup at {manifest_path}")

        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(job_dir, ".backups")
        os.makedirs(backup_dir, exist_ok=True)

        # Create timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"job_manifest_{timestamp}.json.backup"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Copy current manifest to backup
        with open(manifest_path, 'r') as src:
            with open(backup_path, 'w') as dst:
                dst.write(src.read())

        # Clean up old backups (keep last 5)
        _cleanup_old_backups(backup_dir, max_backups=5)

        return backup_path

    except (OSError, IOError) as e:
        raise RecoveryError(f"Failed to create backup: {e}")


def _cleanup_old_backups(backup_dir: str, max_backups: int = 5) -> None:
    """Clean up old backup files, keeping only the most recent ones."""
    try:
        backup_files = [
            f for f in os.listdir(backup_dir)
            if f.endswith('.backup') and f.startswith('job_manifest_')
        ]

        if len(backup_files) <= max_backups:
            return

        # Sort by modification time, newest first
        backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)

        # Remove older backups
        for old_backup in backup_files[max_backups:]:
            try:
                os.remove(os.path.join(backup_dir, old_backup))
            except OSError:
                pass  # Ignore cleanup errors

    except OSError:
        pass  # Ignore cleanup errors


def recover_from_backup(job_dir: str) -> Optional[str]:
    """
    Attempts to recover the job manifest from the most recent backup.

    Args:
        job_dir: Path to the job directory.

    Returns:
        Path to the backup file used for recovery, or None if no recovery needed/was performed.

    Raises:
        RecoveryError: If recovery fails.
    """
    manifest_path = os.path.join(job_dir, "job_manifest.json")
    backup_dir = os.path.join(job_dir, ".backups")

    # Check if recovery is needed
    if os.path.exists(manifest_path):
        try:
            # Try to load current manifest to see if it's valid
            load_job_manifest(job_dir)
            return None  # No recovery needed
        except JobStateError:
            pass  # Manifest is corrupted, try recovery

    if not os.path.exists(backup_dir):
        raise RecoveryError("No backups available for recovery")

    # Find the most recent backup
    try:
        backup_files = [
            f for f in os.listdir(backup_dir)
            if f.endswith('.backup') and f.startswith('job_manifest_')
        ]

        if not backup_files:
            raise RecoveryError("No backup files found")

        # Sort by modification time, newest first
        backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)
        latest_backup = os.path.join(backup_dir, backup_files[0])

        # Copy backup to main manifest
        with open(latest_backup, 'r') as src:
            with open(manifest_path, 'w') as dst:
                dst.write(src.read())

        # Verify recovery worked
        load_job_manifest(job_dir)

        return latest_backup

    except (OSError, IOError) as e:
        raise RecoveryError(f"Failed to recover from backup: {e}")


def detect_hung_process(manifest: Dict[str, Any], timeout_minutes: int = 30) -> Optional[str]:
    """
    Detects if a job is in a hung state that requires recovery.

    Args:
        manifest: Job manifest dictionary.
        timeout_minutes: How long before considering a process hung (default 30 minutes).

    Returns:
        Recovery action string if hung, None if not hung.

    Possible recovery actions:
        - "worker_recovery": Job stuck in RUNNING, reset to PENDING
        - "supervisor_recovery": Job stuck in REVIEWING, reset to REVIEW_REQUIRED
    """
    status = manifest.get("status")
    history = manifest.get("history", [])

    # Only check for hung processes in active execution states
    if status not in ["RUNNING", "REVIEWING"]:
        return None

    # Check if there's been recent activity
    if not history:
        # No history means job just started, not hung yet
        return None

    # Get the most recent history entry with a timestamp
    recent_entry = None
    for entry in reversed(history):
        if "timestamp" in entry:
            recent_entry = entry
            break

    if not recent_entry:
        return None

    try:
        # Parse the timestamp
        last_activity = datetime.fromisoformat(recent_entry["timestamp"])
        now = datetime.now()

        # Check if timeout has been exceeded
        if now - last_activity > timedelta(minutes=timeout_minutes):
            if status == "RUNNING":
                return "worker_recovery"
            elif status == "REVIEWING":
                return "supervisor_recovery"

    except (ValueError, KeyError):
        # Invalid timestamp or missing data, assume not hung
        pass

    return None


def perform_automatic_recovery(job_dir: str, recovery_action: str) -> Dict[str, Any]:
    """
    Performs automatic recovery for a hung process.

    Args:
        job_dir: Path to the job directory.
        recovery_action: Type of recovery to perform.

    Returns:
        Updated manifest dictionary.

    Raises:
        RecoveryError: If recovery fails.
    """
    try:
        manifest = load_job_manifest(job_dir)

        from logist.job_state import update_job_manifest
        from datetime import datetime

        # Create recovery history entry
        recovery_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "AUTOMATIC_RECOVERY",
            "recovery_action": recovery_action,
            "previous_status": manifest.get("status"),
            "reason": "Process detected as hung based on timeout"
        }

        if recovery_action == "worker_recovery":
            # RUNNING (stuck) → PENDING (retry Worker)
            new_status = "PENDING"
            recovery_entry["description"] = "Recovered hung Worker execution"

        elif recovery_action == "supervisor_recovery":
            # REVIEWING (stuck) → REVIEW_REQUIRED (retry Supervisor)
            new_status = "REVIEW_REQUIRED"
            recovery_entry["description"] = "Recovered hung Supervisor review"

        else:
            raise RecoveryError(f"Unknown recovery action: {recovery_action}")

        # Update manifest with recovery information
        updated_manifest = update_job_manifest(
            job_dir=job_dir,
            new_status=new_status,
            history_entry=recovery_entry
        )

        return updated_manifest

    except Exception as e:
        raise RecoveryError(f"Automatic recovery failed: {e}")


def validate_state_persistence(job_dir: str) -> Dict[str, Any]:
    """
    Validates that job state persists correctly and performs recovery if needed.

    This function should be called at the beginning of job operations to ensure
    the job is in a consistent state.

    Args:
        job_dir: Path to the job directory.

    Returns:
        Dictionary with validation results.

    Keys:
        - "recovered": bool - True if recovery was performed
        - "recovery_from": str or None - What type of recovery was done
        - "valid": bool - True if state is now valid
        - "errors": list - Any errors encountered
    """
    result = {
        "recovered": False,
        "recovery_from": None,
        "valid": False,
        "errors": []
    }

    try:
        # Try to load manifest
        manifest = load_job_manifest(job_dir)

        # Check for hung processes
        recovery_action = detect_hung_process(manifest)
        if recovery_action:
            perform_automatic_recovery(job_dir, recovery_action)
            result["recovered"] = True
            result["recovery_from"] = recovery_action

            # Reload manifest after recovery
            manifest = load_job_manifest(job_dir)

        result["valid"] = True

    except JobStateError as e:
        # Try recovery from backup
        try:
            backup_used = recover_from_backup(job_dir)
            result["recovered"] = True
            result["recovery_from"] = "backup_recovery"
            result["valid"] = True
        except RecoveryError as recovery_error:
            result["errors"].append(f"Backup recovery failed: {recovery_error}")

    except RecoveryError as e:
        result["errors"].append(f"Recovery validation error: {e}")

    except Exception as e:
        result["errors"].append(f"Unexpected error during validation: {e}")

    return result


def get_recovery_status(job_dir: str) -> Dict[str, Any]:
    """
    Gets the current recovery status for a job, including backup information.

    Args:
        job_dir: Path to the job directory.

    Returns:
        Dictionary with recovery status information.
    """
    status = {
        "backups_available": 0,
        "last_backup": None,
        "hung_process_detected": False,
        "recovery_needed": False,
        "state_consistent": True
    }

    backup_dir = os.path.join(job_dir, ".backups")
    if os.path.exists(backup_dir):
        try:
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.backup')]
            status["backups_available"] = len(backup_files)

            if backup_files:
                # Find most recent
                backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)
                status["last_backup"] = backup_files[0]

        except OSError:
            pass

    try:
        manifest = load_job_manifest(job_dir)
        recovery_action = detect_hung_process(manifest)
        if recovery_action:
            status["hung_process_detected"] = True
            status["recovery_needed"] = True

    except (JobStateError, RecoveryError):
        status["state_consistent"] = False
        status["recovery_needed"] = True

    return status