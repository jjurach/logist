"""
Advanced Job Recovery Logic for Logist

This module provides comprehensive job recovery capabilities including:
- Job reattachment and crash recovery
- State consistency validation
- Automatic recovery workflows
- Integration with directory management and locking
"""

import os
import json
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from pathlib import Path

from .job_directory import JobDirectoryManager
from .locking import JobLockManager, LockError
from ..job_state import JobStateError, load_job_manifest, JobStates
from ..recovery import RecoveryError, detect_hung_process, perform_automatic_recovery


class JobRecoveryManager:
    """
    Manages advanced job recovery operations including crash recovery,
    job reattachment, and state consistency validation.
    """

    def __init__(self, base_jobs_dir: str):
        """
        Initialize the job recovery manager.

        Args:
            base_jobs_dir: Base directory containing all job directories
        """
        self.base_jobs_dir = Path(base_jobs_dir)
        self.dir_manager = JobDirectoryManager(str(base_jobs_dir))
        self.lock_manager = JobLockManager(str(base_jobs_dir))

    def detect_crashed_jobs(self) -> List[Dict[str, Any]]:
        """
        Detect jobs that appear to have crashed or been interrupted.

        Returns:
            List of crashed job information dictionaries
        """
        crashed_jobs = []

        try:
            jobs = self.dir_manager.list_jobs()

            for job_info in jobs:
                job_id = job_info["job_id"]
                status = job_info["status"]

                # Only check jobs in execution states
                execution_states = {JobStates.RUNNING, JobStates.REVIEWING, JobStates.PENDING}
                if status not in execution_states:
                    continue

                try:
                    # Try to acquire lock - if we can get it, job might be crashed
                    lock = self.lock_manager.lock_job_directory(job_id, timeout=5.0)

                    # If we got the lock, check if the job should still be locked
                    if self._should_job_be_locked(job_id):
                        crashed_jobs.append({
                            "job_id": job_id,
                            "status": status,
                            "reason": "lock_available_but_should_be_locked",
                            "directory": job_info["directory"]
                        })

                    self.lock_manager.unlock_job_directory(job_id)

                except LockError:
                    # Lock is held by another process - job is likely still running
                    continue
                except Exception as e:
                    crashed_jobs.append({
                        "job_id": job_id,
                        "status": status,
                        "reason": f"error_checking_lock: {e}",
                        "directory": job_info["directory"]
                    })

        except Exception as e:
            # Log error but don't fail completely
            print(f"Warning: Error detecting crashed jobs: {e}")

        return crashed_jobs

    def _should_job_be_locked(self, job_id: str) -> bool:
        """
        Determine if a job should currently be locked based on its state.

        Args:
            job_id: Job identifier

        Returns:
            True if job should be locked by a running process
        """
        try:
            job_dir = self.dir_manager.get_job_directory(job_id)
            manifest = load_job_manifest(job_dir)
            status = manifest.get("status", "")

            # Jobs in these states should be locked by active processes
            active_states = {JobStates.RUNNING, JobStates.REVIEWING}
            return status in active_states

        except (JobStateError, KeyError):
            return False

    def recover_crashed_job(self, job_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Attempt to recover a crashed job.

        Args:
            job_id: Job identifier
            force: Force recovery even if job appears to be running

        Returns:
            Recovery result dictionary

        Raises:
            RecoveryError: If recovery fails
        """
        result = {
            "job_id": job_id,
            "recovered": False,
            "actions_taken": [],
            "errors": []
        }

        try:
            job_dir = self.dir_manager.get_job_directory(job_id)

            # Validate job directory first
            validation = self.dir_manager.validate_job_directory(job_id)
            if not validation["valid"]:
                result["errors"].extend(validation["issues"])
                if not force:
                    return result

            # Try to acquire lock
            try:
                lock = self.lock_manager.lock_job_directory(job_id, timeout=10.0)
                result["actions_taken"].append("acquired_lock")
            except LockError:
                if not force:
                    result["errors"].append("could_not_acquire_lock")
                    return result
                result["actions_taken"].append("forced_lock_acquisition")

            try:
                # Load and validate manifest
                manifest = load_job_manifest(job_dir)
                original_status = manifest.get("status", "UNKNOWN")

                # Check for hung process
                recovery_action = detect_hung_process(manifest)
                if recovery_action:
                    perform_automatic_recovery(job_dir, recovery_action)
                    result["actions_taken"].append(f"performed_{recovery_action}")
                    result["recovered"] = True
                else:
                    # Job doesn't appear hung, but was crashed - reset to safe state
                    if original_status in {JobStates.RUNNING, JobStates.REVIEWING}:
                        safe_status = JobStates.PENDING if original_status == JobStates.RUNNING else JobStates.REVIEW_REQUIRED

                        from ..job_state import update_job_manifest
                        recovery_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "event": "CRASH_RECOVERY",
                            "previous_status": original_status,
                            "new_status": safe_status,
                            "reason": "Job recovered from crash"
                        }

                        update_job_manifest(
                            job_dir=job_dir,
                            new_status=safe_status,
                            history_entry=recovery_entry
                        )

                        result["actions_taken"].append(f"reset_status_{original_status}_to_{safe_status}")
                        result["recovered"] = True

                # Clean up any stale lock files
                self.lock_manager.cleanup_stale_locks(max_age_seconds=300)  # 5 minutes

            finally:
                # Always release lock
                try:
                    self.lock_manager.unlock_job_directory(job_id)
                except LockError:
                    pass  # Ignore release errors

        except Exception as e:
            result["errors"].append(f"recovery_failed: {e}")
            raise RecoveryError(f"Failed to recover job {job_id}: {e}")

        return result

    def reattach_to_running_job(self, job_id: str, process_check: bool = True) -> Dict[str, Any]:
        """
        Attempt to reattach to a job that may still be running.

        Args:
            job_id: Job identifier
            process_check: Whether to check for running processes

        Returns:
            Reattachment result dictionary
        """
        result = {
            "job_id": job_id,
            "reattached": False,
            "status": "unknown",
            "process_running": False,
            "errors": []
        }

        try:
            job_dir = self.dir_manager.get_job_directory(job_id)
            manifest = load_job_manifest(job_dir)
            result["status"] = manifest.get("status", "UNKNOWN")

            # Check if there's a running process for this job
            if process_check:
                result["process_running"] = self._check_job_process_running(job_id, manifest)

            # Try non-blocking lock acquisition
            try:
                lock = self.lock_manager.lock_job_directory(job_id, timeout=1.0)
                # If we got the lock, no active process is holding it
                self.lock_manager.unlock_job_directory(job_id)

                if result["process_running"]:
                    result["errors"].append("process_running_but_lock_available")
                    return result
                else:
                    # Safe to reattach
                    result["reattached"] = True

            except LockError:
                # Lock is held - there might be an active process
                if result["process_running"]:
                    result["reattached"] = True  # Process is running and holds lock
                else:
                    result["errors"].append("lock_held_but_no_process_found")

        except Exception as e:
            result["errors"].append(f"reattachment_check_failed: {e}")

        return result

    def _check_job_process_running(self, job_id: str, manifest: Dict[str, Any]) -> bool:
        """
        Check if there's a running process associated with the job.

        Args:
            job_id: Job identifier
            manifest: Job manifest

        Returns:
            True if a process appears to be running
        """
        try:
            # Look for process ID in manifest or job metadata
            pid = manifest.get("process_id") or manifest.get("metadata", {}).get("pid")

            if pid:
                return psutil.pid_exists(pid)

            # Alternative: check for recent activity in log files
            job_dir = self.dir_manager.get_job_directory(job_id)
            logs_dir = Path(job_dir) / "logs"

            if logs_dir.exists():
                # Check if any log file has been modified recently (last 5 minutes)
                recent_activity = False
                for log_file in logs_dir.glob("*.log"):
                    try:
                        mtime = log_file.stat().st_mtime
                        if time.time() - mtime < 300:  # 5 minutes
                            recent_activity = True
                            break
                    except OSError:
                        continue

                if recent_activity:
                    return True

        except Exception:
            pass  # Don't fail on process checking

        return False

    def validate_job_consistency(self, job_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive consistency validation for a job.

        Args:
            job_id: Job identifier

        Returns:
            Validation result dictionary
        """
        result = {
            "job_id": job_id,
            "consistent": True,
            "issues": [],
            "recommendations": []
        }

        try:
            job_dir = self.dir_manager.get_job_directory(job_id)
            manifest = load_job_manifest(job_dir)

            # Check directory structure
            dir_validation = self.dir_manager.validate_job_directory(job_id)
            if not dir_validation["valid"]:
                result["consistent"] = False
                result["issues"].extend(dir_validation["issues"])

            # Check manifest consistency
            manifest_issues = self._validate_manifest_consistency(manifest)
            if manifest_issues:
                result["consistent"] = False
                result["issues"].extend(manifest_issues)

            # Check for orphaned resources
            resource_issues = self._check_orphaned_resources(job_id, manifest)
            if resource_issues:
                result["issues"].extend(resource_issues)

            # Generate recommendations
            if result["issues"]:
                result["recommendations"] = self._generate_consistency_recommendations(result["issues"])

        except Exception as e:
            result["consistent"] = False
            result["issues"].append(f"validation_error: {e}")

        return result

    def _validate_manifest_consistency(self, manifest: Dict[str, Any]) -> List[str]:
        """Validate internal consistency of job manifest."""
        issues = []

        # Check required fields
        required_fields = ["job_id", "status", "created_at", "metrics"]
        for field in required_fields:
            if field not in manifest:
                issues.append(f"missing_required_field: {field}")

        # Check status validity
        valid_states = {state for state in dir(JobStates) if not state.startswith('_')}
        if manifest.get("status") not in valid_states:
            issues.append(f"invalid_status: {manifest.get('status')}")

        # Check metrics structure
        metrics = manifest.get("metrics", {})
        required_metrics = ["cumulative_cost", "cumulative_time_seconds"]
        for metric in required_metrics:
            if metric not in metrics:
                issues.append(f"missing_metric: {metric}")

        return issues

    def _check_orphaned_resources(self, job_id: str, manifest: Dict[str, Any]) -> List[str]:
        """Check for orphaned or inconsistent resources."""
        issues = []
        job_dir = Path(self.dir_manager.get_job_directory(job_id))

        # Check for temp files that should have been cleaned up
        temp_dir = job_dir / "temp"
        if temp_dir.exists():
            try:
                temp_files = list(temp_dir.glob("*"))
                if temp_files:
                    # Check if any temp files are older than expected
                    max_temp_age = timedelta(hours=1)
                    old_temp_files = []

                    for temp_file in temp_files:
                        try:
                            mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                            if datetime.now() - mtime > max_temp_age:
                                old_temp_files.append(str(temp_file.name))
                        except OSError:
                            continue

                    if old_temp_files:
                        issues.append(f"old_temp_files: {len(old_temp_files)} files older than 1 hour")
            except OSError:
                issues.append("cannot_check_temp_files")

        return issues

    def _generate_consistency_recommendations(self, issues: List[str]) -> List[str]:
        """Generate recommendations based on consistency issues."""
        recommendations = []

        for issue in issues:
            if "missing_required_field" in issue:
                recommendations.append("run_job_validation_and_repair")
            elif "invalid_status" in issue:
                recommendations.append("reset_job_to_safe_state")
            elif "old_temp_files" in issue:
                recommendations.append("cleanup_temporary_files")
            elif "orphaned" in issue:
                recommendations.append("check_for_data_integrity_issues")

        if not recommendations:
            recommendations.append("run_full_job_recovery")

        return recommendations

    def perform_bulk_recovery(self, job_ids: Optional[List[str]] = None,
                            force: bool = False) -> Dict[str, Any]:
        """
        Perform recovery operations on multiple jobs.

        Args:
            job_ids: List of job IDs to recover, or None for all crashed jobs
            force: Force recovery operations

        Returns:
            Bulk recovery results
        """
        result = {
            "total_jobs_processed": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "job_results": []
        }

        if job_ids is None:
            # Auto-detect crashed jobs
            crashed_jobs = self.detect_crashed_jobs()
            job_ids = [job["job_id"] for job in crashed_jobs]

        for job_id in job_ids:
            try:
                recovery_result = self.recover_crashed_job(job_id, force)
                result["job_results"].append(recovery_result)

                if recovery_result["recovered"]:
                    result["successful_recoveries"] += 1
                else:
                    result["failed_recoveries"] += 1

            except Exception as e:
                result["job_results"].append({
                    "job_id": job_id,
                    "recovered": False,
                    "errors": [str(e)]
                })
                result["failed_recoveries"] += 1

            result["total_jobs_processed"] += 1

        return result

    def get_recovery_status_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive recovery status report.

        Returns:
            Status report dictionary
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "crashed_jobs": [],
            "inconsistent_jobs": [],
            "recovery_needed": [],
            "system_health": "healthy"
        }

        try:
            # Check for crashed jobs
            crashed = self.detect_crashed_jobs()
            report["crashed_jobs"] = crashed

            # Check all jobs for consistency
            all_jobs = self.dir_manager.list_jobs()
            for job_info in all_jobs:
                job_id = job_info["job_id"]
                consistency = self.validate_job_consistency(job_id)

                if not consistency["consistent"]:
                    report["inconsistent_jobs"].append({
                        "job_id": job_id,
                        "issues": consistency["issues"]
                    })

                if consistency["issues"] or job_id in [c["job_id"] for c in crashed]:
                    report["recovery_needed"].append(job_id)

            # Determine overall system health
            if report["crashed_jobs"] or report["inconsistent_jobs"]:
                report["system_health"] = "needs_attention"
            if len(report["recovery_needed"]) > len(all_jobs) * 0.5:
                report["system_health"] = "critical"

        except Exception as e:
            report["system_health"] = "error"
            report["error"] = str(e)

        return report


def create_recovery_manager(base_jobs_dir: str) -> JobRecoveryManager:
    """
    Factory function to create a JobRecoveryManager instance.

    Args:
        base_jobs_dir: Base directory for jobs

    Returns:
        Configured JobRecoveryManager instance
    """
    return JobRecoveryManager(base_jobs_dir)


def auto_recover_system(base_jobs_dir: str, max_jobs: int = 10) -> Dict[str, Any]:
    """
    Perform automatic system-wide recovery.

    Args:
        base_jobs_dir: Base directory for jobs
        max_jobs: Maximum number of jobs to recover in one operation

    Returns:
        Recovery operation results
    """
    manager = create_recovery_manager(base_jobs_dir)

    # Get recovery status
    status = manager.get_recovery_status_report()

    # Limit recovery to avoid overwhelming the system
    jobs_to_recover = status["recovery_needed"][:max_jobs]

    if jobs_to_recover:
        result = manager.perform_bulk_recovery(jobs_to_recover, force=False)
        result["status_report"] = status
        return result
    else:
        return {
            "message": "No recovery needed",
            "status_report": status
        }