"""
Execution Sentinel for Logist Job Monitoring

This module provides automated hang detection and process monitoring capabilities
for the Logist system. It implements intelligent timeout detection, resource monitoring,
and automatic cleanup of unresponsive processes.
"""

import os
import time
import signal
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from .job_directory import JobDirectoryManager
from .locking import JobLockManager, LockError
from ..job_state import JobStateError, load_job_manifest, JobStates


class SentinelState(Enum):
    """States for the execution sentinel."""
    INACTIVE = "inactive"
    MONITORING = "monitoring"
    ALERTING = "alerting"
    INTERVENING = "intervening"
    CLEANUP = "cleanup"


class HangSeverity(Enum):
    """Severity levels for detected hangs."""
    LOW = "low"          # Minor delay, likely transient
    MEDIUM = "medium"    # Moderate delay, needs attention
    HIGH = "high"        # Significant delay, requires intervention
    CRITICAL = "critical"  # Severe hang, immediate action needed


@dataclass
class HangDetection:
    """Represents a detected hang condition."""
    job_id: str
    severity: HangSeverity
    detected_at: datetime
    timeout_duration: float
    last_activity: datetime
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SentinelConfig:
    """Configuration for the execution sentinel."""
    # Timeout thresholds (seconds)
    worker_timeout: float = 1800.0  # 30 minutes
    supervisor_timeout: float = 900.0  # 15 minutes
    critical_timeout: float = 3600.0  # 1 hour

    # Check intervals (seconds)
    check_interval: float = 60.0  # Check every minute
    activity_check_interval: float = 30.0  # Check activity every 30 seconds

    # Intervention settings
    auto_intervene: bool = True
    max_interventions_per_hour: int = 5

    # Resource monitoring
    enable_resource_monitoring: bool = True
    memory_threshold_mb: int = 1024  # 1GB
    cpu_threshold_percent: float = 95.0

    # Notification settings
    enable_notifications: bool = False
    notification_callback: Optional[Callable] = None


class ExecutionSentinel:
    """
    Monitors job execution for hangs and provides automatic intervention.

    The sentinel provides comprehensive monitoring including:
    - Timeout detection based on job state and activity
    - Resource usage monitoring (memory, CPU)
    - Automatic intervention for critical hangs
    - Process health checking
    """

    def __init__(self, base_jobs_dir: str, config: Optional[SentinelConfig] = None):
        """
        Initialize the execution sentinel.

        Args:
            base_jobs_dir: Base directory containing job directories
            config: Sentinel configuration (uses defaults if None)
        """
        self.base_jobs_dir = base_jobs_dir
        self.config = config or SentinelConfig()

        self.dir_manager = JobDirectoryManager(base_jobs_dir)
        self.lock_manager = JobLockManager(base_jobs_dir)

        # Monitoring state
        self.state = SentinelState.INACTIVE
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Tracking
        self.active_jobs: Set[str] = set()
        self.last_activity: Dict[str, datetime] = {}
        self.hang_detections: List[HangDetection] = []
        self.intervention_count = 0
        self.last_intervention_time = datetime.min

        # Resource monitoring
        self.process_cache: Dict[str, psutil.Process] = {}

    def start_monitoring(self) -> None:
        """Start the monitoring thread."""
        if self.state != SentinelState.INACTIVE:
            return

        self.state = SentinelState.MONITORING
        self.stop_event.clear()
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

    def stop_monitoring(self) -> None:
        """Stop the monitoring thread."""
        if self.state == SentinelState.INACTIVE:
            return

        self.state = SentinelState.INACTIVE
        self.stop_event.set()

        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5.0)

    def add_job(self, job_id: str) -> None:
        """
        Add a job to monitoring.

        Args:
            job_id: Job identifier
        """
        self.active_jobs.add(job_id)
        self.last_activity[job_id] = datetime.now()

    def remove_job(self, job_id: str) -> None:
        """
        Remove a job from monitoring.

        Args:
            job_id: Job identifier
        """
        self.active_jobs.discard(job_id)
        self.last_activity.pop(job_id, None)
        self.process_cache.pop(job_id, None)

    def update_activity(self, job_id: str) -> None:
        """
        Update the last activity timestamp for a job.

        Args:
            job_id: Job identifier
        """
        if job_id in self.active_jobs:
            self.last_activity[job_id] = datetime.now()

    def check_job_timeout(self, job_id: str) -> Optional[HangDetection]:
        """
        Check if a job has exceeded its timeout threshold.

        Args:
            job_id: Job identifier

        Returns:
            HangDetection if job is hung, None otherwise
        """
        if job_id not in self.active_jobs:
            return None

        try:
            job_dir = self.dir_manager.get_job_directory(job_id)
            manifest = load_job_manifest(job_dir)
            status = manifest.get("status", "UNKNOWN")
            last_activity = self.last_activity.get(job_id, datetime.min)

            # Determine timeout threshold based on job state
            timeout_threshold = self._get_timeout_threshold(status)
            if timeout_threshold is None:
                return None  # No timeout for this state

            time_since_activity = datetime.now() - last_activity

            if time_since_activity.total_seconds() > timeout_threshold:
                severity = self._calculate_hang_severity(time_since_activity.total_seconds(), timeout_threshold)

                evidence = [
                    f"Last activity: {last_activity.isoformat()}",
                    f"Time since activity: {time_since_activity.total_seconds():.1f}s",
                    f"Timeout threshold: {timeout_threshold}s",
                    f"Job status: {status}"
                ]

                # Check resource usage if enabled
                if self.config.enable_resource_monitoring:
                    resource_evidence = self._check_resource_usage(job_id)
                    evidence.extend(resource_evidence)

                return HangDetection(
                    job_id=job_id,
                    severity=severity,
                    detected_at=datetime.now(),
                    timeout_duration=time_since_activity.total_seconds(),
                    last_activity=last_activity,
                    evidence=evidence,
                    metadata={
                        "job_status": status,
                        "timeout_threshold": timeout_threshold,
                        "manifest": manifest
                    }
                )

        except (JobStateError, OSError) as e:
            # Log error but don't fail - job might be in inconsistent state
            print(f"Warning: Error checking timeout for job {job_id}: {e}")

        return None

    def _get_timeout_threshold(self, status: str) -> Optional[float]:
        """Get timeout threshold for a job status."""
        thresholds = {
            JobStates.RUNNING: self.config.worker_timeout,
            JobStates.REVIEWING: self.config.supervisor_timeout,
        }

        # Critical timeout for any executing state
        if status in {JobStates.RUNNING, JobStates.REVIEWING, JobStates.PENDING}:
            return min(thresholds.get(status, self.config.worker_timeout), self.config.critical_timeout)

        return None  # No timeout for terminal states

    def _calculate_hang_severity(self, actual_timeout: float, threshold: float) -> HangSeverity:
        """Calculate the severity of a hang based on timeout duration."""
        ratio = actual_timeout / threshold

        if ratio < 1.5:
            return HangSeverity.LOW
        elif ratio < 2.0:
            return HangSeverity.MEDIUM
        elif ratio < 3.0:
            return HangSeverity.HIGH
        else:
            return HangSeverity.CRITICAL

    def intervene_in_hung_job(self, hang_detection: HangDetection) -> Dict[str, Any]:
        """
        Intervene in a hung job based on detection severity.

        Args:
            hang_detection: The hang detection information

        Returns:
            Intervention result
        """
        result = {
            "job_id": hang_detection.job_id,
            "intervention_performed": False,
            "actions_taken": [],
            "errors": []
        }

        # Check intervention limits
        if not self._can_intervene():
            result["errors"].append("Intervention limit exceeded")
            return result

        try:
            # Acquire job lock for safe intervention
            lock = self.lock_manager.lock_job_directory(hang_detection.job_id, timeout=30.0)

            try:
                intervention_actions = self._perform_intervention(hang_detection)
                result["actions_taken"].extend(intervention_actions)
                result["intervention_performed"] = True

                # Update intervention tracking
                self.intervention_count += 1
                self.last_intervention_time = datetime.now()

            finally:
                self.lock_manager.unlock_job_directory(hang_detection.job_id)

        except LockError as e:
            result["errors"].append(f"Could not acquire lock: {e}")
        except Exception as e:
            result["errors"].append(f"Intervention failed: {e}")

        return result

    def _can_intervene(self) -> bool:
        """Check if intervention is allowed based on limits."""
        if not self.config.auto_intervene:
            return False

        # Check hourly limit
        hour_ago = datetime.now() - timedelta(hours=1)
        if self.last_intervention_time > hour_ago and self.intervention_count >= self.config.max_interventions_per_hour:
            return False

        return True

    def _perform_intervention(self, hang_detection: HangDetection) -> List[str]:
        """
        Perform the actual intervention based on hang severity.

        Returns:
            List of actions taken
        """
        actions = []
        job_id = hang_detection.job_id

        if hang_detection.severity == HangSeverity.CRITICAL:
            # For critical hangs, force recovery
            from .recovery import JobRecoveryManager
            recovery_manager = JobRecoveryManager(self.base_jobs_dir)

            recovery_result = recovery_manager.recover_crashed_job(job_id, force=True)
            if recovery_result["recovered"]:
                actions.append("forced_job_recovery")
                actions.append(f"recovery_actions: {', '.join(recovery_result['actions_taken'])}")

        elif hang_detection.severity in {HangSeverity.HIGH, HangSeverity.MEDIUM}:
            # For high/medium hangs, attempt graceful recovery first
            from .recovery import JobRecoveryManager
            recovery_manager = JobRecoveryManager(self.base_jobs_dir)

            recovery_result = recovery_manager.recover_crashed_job(job_id, force=False)
            if recovery_result["recovered"]:
                actions.append("graceful_job_recovery")
                actions.append(f"recovery_actions: {', '.join(recovery_result['actions_taken'])}")
            else:
                # If graceful recovery fails, try process termination
                terminated = self._terminate_job_process(job_id)
                if terminated:
                    actions.append("process_terminated")

        # Update job status to indicate intervention
        try:
            from ..job_state import update_job_manifest
            update_job_manifest(
                job_dir=self.dir_manager.get_job_directory(job_id),
                new_status=JobStates.INTERVENTION_REQUIRED,
                history_entry={
                    "event": "SENTINEL_INTERVENTION",
                    "severity": hang_detection.severity.value,
                    "timeout_duration": hang_detection.timeout_duration,
                    "actions_taken": actions
                }
            )
            actions.append("status_updated_to_intervention_required")
        except Exception as e:
            actions.append(f"status_update_failed: {e}")

        return actions

    def _terminate_job_process(self, job_id: str) -> bool:
        """Terminate the process associated with a job."""
        try:
            # Get process ID from manifest if available
            job_dir = self.dir_manager.get_job_directory(job_id)
            manifest = load_job_manifest(job_dir)
            pid = manifest.get("process_id")

            if pid and psutil.pid_exists(pid):
                process = psutil.Process(pid)
                process.terminate()

                # Wait for termination
                try:
                    process.wait(timeout=10.0)
                    return True
                except psutil.TimeoutExpired:
                    # Force kill if terminate doesn't work
                    process.kill()
                    process.wait(timeout=5.0)
                    return True

        except Exception as e:
            print(f"Warning: Process termination failed for job {job_id}: {e}")

        return False

    def _check_resource_usage(self, job_id: str) -> List[str]:
        """Check resource usage for a job."""
        evidence = []

        try:
            # Try to get process information
            job_dir = self.dir_manager.get_job_directory(job_id)
            manifest = load_job_manifest(job_dir)
            pid = manifest.get("process_id")

            if pid and psutil.pid_exists(pid):
                process = psutil.Process(pid)

                # Memory usage
                memory_mb = process.memory_info().rss / 1024 / 1024
                if memory_mb > self.config.memory_threshold_mb:
                    evidence.append(f"High memory usage: {memory_mb:.1f}MB (threshold: {self.config.memory_threshold_mb}MB)")

                # CPU usage (over last interval)
                cpu_percent = process.cpu_percent(interval=1.0)
                if cpu_percent > self.config.cpu_threshold_percent:
                    evidence.append(f"High CPU usage: {cpu_percent:.1f}% (threshold: {self.config.cpu_threshold_percent}%)")

                # Process status
                status = process.status()
                if status in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                    evidence.append(f"Process in bad state: {status}")

        except Exception as e:
            evidence.append(f"Resource check error: {e}")

        return evidence

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while not self.stop_event.is_set():
            try:
                self._perform_monitoring_cycle()
            except Exception as e:
                print(f"Warning: Monitoring cycle error: {e}")

            # Wait for next check interval
            self.stop_event.wait(self.config.check_interval)

    def _perform_monitoring_cycle(self) -> None:
        """Perform one complete monitoring cycle."""
        # Update active jobs list
        self._refresh_active_jobs()

        # Check for hangs
        hangs_detected = []
        for job_id in list(self.active_jobs):
            hang = self.check_job_timeout(job_id)
            if hang:
                hangs_detected.append(hang)
                self.hang_detections.append(hang)

        # Process detected hangs
        for hang in hangs_detected:
            if self.config.enable_notifications and self.config.notification_callback:
                self.config.notification_callback(hang)

            if self.config.auto_intervene:
                intervention_result = self.intervene_in_hung_job(hang)
                if intervention_result["intervention_performed"]:
                    print(f"Sentinel intervened in hung job {hang.job_id}: {intervention_result['actions_taken']}")

    def _refresh_active_jobs(self) -> None:
        """Refresh the list of active jobs being monitored."""
        try:
            all_jobs = self.dir_manager.list_jobs()
            current_active = set()

            for job_info in all_jobs:
                job_id = job_info["job_id"]
                status = job_info["status"]

                # Monitor jobs in executing states
                if status in {JobStates.RUNNING, JobStates.REVIEWING, JobStates.PENDING}:
                    current_active.add(job_id)

                    # Add to monitoring if not already there
                    if job_id not in self.active_jobs:
                        self.add_job(job_id)

            # Remove jobs that are no longer active
            inactive_jobs = self.active_jobs - current_active
            for job_id in inactive_jobs:
                self.remove_job(job_id)

        except Exception as e:
            print(f"Warning: Error refreshing active jobs: {e}")

    def get_status_report(self) -> Dict[str, Any]:
        """Get a comprehensive status report."""
        return {
            "state": self.state.value,
            "active_jobs": len(self.active_jobs),
            "hangs_detected": len(self.hang_detections),
            "interventions_performed": self.intervention_count,
            "last_intervention": self.last_intervention_time.isoformat() if self.last_intervention_time != datetime.min else None,
            "recent_hangs": [
                {
                    "job_id": h.job_id,
                    "severity": h.severity.value,
                    "detected_at": h.detected_at.isoformat(),
                    "timeout_duration": h.timeout_duration
                }
                for h in self.hang_detections[-10:]  # Last 10 hangs
            ]
        }


def create_execution_sentinel(base_jobs_dir: str, config: Optional[SentinelConfig] = None) -> ExecutionSentinel:
    """
    Factory function to create an execution sentinel.

    Args:
        base_jobs_dir: Base directory for jobs
        config: Sentinel configuration

    Returns:
        Configured ExecutionSentinel instance
    """
    return ExecutionSentinel(base_jobs_dir, config)


def start_job_monitoring(base_jobs_dir: str, config: Optional[SentinelConfig] = None) -> ExecutionSentinel:
    """
    Start monitoring jobs in the background.

    Args:
        base_jobs_dir: Base directory for jobs
        config: Sentinel configuration

    Returns:
        Started ExecutionSentinel instance
    """
    sentinel = create_execution_sentinel(base_jobs_dir, config)
    sentinel.start_monitoring()
    return sentinel