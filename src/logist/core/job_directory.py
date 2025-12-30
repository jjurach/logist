"""
Job Directory Structure Management

This module provides comprehensive job directory management including:
- Directory structure creation and validation
- Job discovery and enumeration
- Directory cleanup and maintenance
- Path resolution utilities
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from ..job_state import JobStateError
from .locking import JobLockManager


class JobDirectoryManager:
    """
    Manages the filesystem structure for Logist jobs.

    Provides methods for creating, validating, and managing job directories
    with proper structure and metadata tracking.
    """

    def __init__(self, base_jobs_dir: str):
        """
        Initialize the job directory manager.

        Args:
            base_jobs_dir: Base directory containing all job directories
        """
        self.base_jobs_dir = Path(base_jobs_dir).resolve()
        self.jobs_index_path = self.base_jobs_dir / "jobs_index.json"
        self._lock_manager = JobLockManager(str(self.base_jobs_dir))

    def ensure_base_structure(self) -> None:
        """
        Ensure the base jobs directory structure exists.

        Creates the base directory and jobs index file if they don't exist.
        """
        # Create base directory
        self.base_jobs_dir.mkdir(parents=True, exist_ok=True)

        # Create jobs index if it doesn't exist
        if not self.jobs_index_path.exists():
            self._create_jobs_index()

    def _create_jobs_index(self) -> None:
        """Create the initial jobs index file."""
        index_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "jobs": {},
            "queue": [],
            "archived_jobs": []
        }

        with open(self.jobs_index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

    def create_job_directory(self, job_id: str, job_config: Dict[str, Any]) -> str:
        """
        Create a new job directory with standard structure.

        Args:
            job_id: Unique identifier for the job
            job_config: Job configuration dictionary

        Returns:
            Path to the created job directory

        Raises:
            JobStateError: If directory creation fails
        """
        job_dir = self.base_jobs_dir / job_id
        job_dir_str = str(job_dir)

        if job_dir.exists():
            raise JobStateError(f"Job directory already exists: {job_dir_str}")

        try:
            # Create main job directory
            job_dir.mkdir(parents=True)

            # Create initial job manifest
            manifest_path = job_dir / "job_manifest.json"
            manifest = self._create_initial_manifest(job_id, job_config)

            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

            # Update jobs index (thread-safe)
            self._add_job_to_index(job_id, manifest)

            return job_dir_str

        except OSError as e:
            # Cleanup on failure
            if job_dir.exists():
                shutil.rmtree(job_dir)
            raise JobStateError(f"Failed to create job directory {job_dir_str}: {e}")
        except Exception as e:
            # Cleanup on any failure
            if job_dir.exists():
                shutil.rmtree(job_dir)
            raise JobStateError(f"Unexpected error creating job directory {job_dir_str}: {e}")

    def _create_initial_manifest(self, job_id: str, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create the initial job manifest."""
        now = datetime.now().isoformat()

        return {
            "job_id": job_id,
            "status": "DRAFT",
            "current_phase": None,
            "created_at": now,
            "updated_at": now,
            "config": job_config,
            "phases": [],
            "metrics": {
                "cumulative_cost": 0.0,
                "cumulative_time_seconds": 0.0,
                "step_count": 0
            },
            "history": [{
                "timestamp": now,
                "event": "JOB_CREATED",
                "message": f"Job directory created for {job_id}"
            }]
        }

    def _add_job_to_index(self, job_id: str, manifest: Dict[str, Any]) -> None:
        """Add job to the jobs index."""
        with self._lock_manager.jobs_index_lock():
            index_data = self._load_jobs_index()

            # Store just the directory path for compatibility with JobManagerService
            index_data["jobs"][job_id] = str(self.base_jobs_dir / job_id)

            self._save_jobs_index(index_data)

    def get_job_directory(self, job_id: str) -> str:
        """
        Get the absolute path to a job's directory.

        Args:
            job_id: Job identifier

        Returns:
            Absolute path to job directory

        Raises:
            JobStateError: If job directory doesn't exist
        """
        job_dir = self.base_jobs_dir / job_id

        if not job_dir.exists():
            raise JobStateError(f"Job directory not found: {job_id}")

        return str(job_dir)

    def list_jobs(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all jobs with optional status filtering.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of job information dictionaries
        """
        index_data = self._load_jobs_index()
        jobs = []

        for job_id, job_dir_path in index_data["jobs"].items():
            # Load manifest to get status
            manifest_path = Path(job_dir_path) / "job_manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    status = manifest.get("status", "UNKNOWN")
                except json.JSONDecodeError:
                    status = "CORRUPTED"
            else:
                status = "MISSING_MANIFEST"

            if status_filter and status != status_filter:
                continue

            # Verify directory still exists
            job_dir = Path(job_dir_path)
            if job_dir.exists():
                jobs.append({
                    "job_id": job_id,
                    "directory": job_dir_path,
                    "status": status
                })

        return jobs

    def validate_job_directory(self, job_id: str) -> Dict[str, Any]:
        """
        Validate that a job directory has the required structure and files.

        Args:
            job_id: Job identifier

        Returns:
            Validation result with status and any issues found

        Raises:
            JobStateError: If job directory doesn't exist
        """
        job_dir = Path(self.get_job_directory(job_id))

        validation_result = {
            "job_id": job_id,
            "valid": True,
            "issues": [],
            "missing_files": [],
            "missing_dirs": []
        }

        # Check required files
        required_files = ["job_manifest.json"]
        for filename in required_files:
            file_path = job_dir / filename
            if not file_path.exists():
                validation_result["valid"] = False
                validation_result["missing_files"].append(filename)

        # Check manifest validity
        manifest_path = job_dir / "job_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

                required_fields = ["job_id", "status", "created_at", "config", "metrics"]
                for field in required_fields:
                    if field not in manifest:
                        validation_result["issues"].append(f"Missing required field: {field}")

            except json.JSONDecodeError as e:
                validation_result["valid"] = False
                validation_result["issues"].append(f"Invalid manifest JSON: {e}")

        if not validation_result["valid"]:
            validation_result["issues"].extend(
                [f"Missing directory: {d}" for d in validation_result["missing_dirs"]] +
                [f"Missing file: {f}" for f in validation_result["missing_files"]]
            )

        return validation_result

    def cleanup_job_directory(self, job_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Clean up a job directory.

        Args:
            job_id: Job identifier
            force: If True, remove directory even if job is not in terminal state

        Returns:
            Cleanup result with status and details

        Raises:
            JobStateError: If cleanup is not allowed or fails
        """
        job_dir = Path(self.get_job_directory(job_id))

        # Load manifest to check status
        manifest_path = job_dir / "job_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            status = manifest.get("status", "UNKNOWN")
        else:
            status = "UNKNOWN"

        # Check if cleanup is allowed
        terminal_states = {"SUCCESS", "CANCELED", "FAILED"}
        if not force and status not in terminal_states:
            raise JobStateError(f"Cannot cleanup job {job_id} in non-terminal state: {status}")

        try:
            # Create backup before cleanup if directory has content
            if any(job_dir.iterdir()):
                backup_name = f"{job_id}_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_path = self.base_jobs_dir / "backups" / backup_name
                backup_path.parent.mkdir(exist_ok=True)

                shutil.make_archive(str(backup_path), 'zip', job_dir)
                backup_created = str(backup_path) + ".zip"
            else:
                backup_created = None

            # Remove directory
            shutil.rmtree(job_dir)

            # Update jobs index
            self._remove_job_from_index(job_id)

            return {
                "success": True,
                "job_id": job_id,
                "backup_created": backup_created,
                "message": f"Job directory cleaned up successfully"
            }

        except Exception as e:
            raise JobStateError(f"Failed to cleanup job directory {job_id}: {e}")

    def _remove_job_from_index(self, job_id: str) -> None:
        """Remove job from the jobs index."""
        with self._lock_manager.jobs_index_lock():
            index_data = self._load_jobs_index()

            if job_id in index_data["jobs"]:
                del index_data["jobs"][job_id]

            # Also remove from queue if present
            if job_id in index_data["queue"]:
                index_data["queue"].remove(job_id)

            # Add to archived jobs
            index_data["archived_jobs"].append({
                "job_id": job_id,
                "archived_at": datetime.now().isoformat(),
                "reason": "cleanup"
            })

            self._save_jobs_index(index_data)

    def _load_jobs_index(self) -> Dict[str, Any]:
        """Load the jobs index file."""
        try:
            with open(self.jobs_index_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Recreate index if corrupted or missing
            self._create_jobs_index()
            return self._load_jobs_index()

    def _save_jobs_index(self, index_data: Dict[str, Any]) -> None:
        """Save the jobs index file."""
        with open(self.jobs_index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

    def get_job_stats(self) -> Dict[str, Any]:
        """
        Get statistics about jobs in the system.

        Returns:
            Dictionary with job statistics
        """
        index_data = self._load_jobs_index()
        jobs = index_data["jobs"]

        stats = {
            "total_jobs": len(jobs),
            "status_counts": {},
            "queue_length": len(index_data["queue"]),
            "archived_jobs": len(index_data["archived_jobs"])
        }

        # Count status for each job by loading manifests
        for job_id, job_dir_path in jobs.items():
            manifest_path = Path(job_dir_path) / "job_manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    status = manifest.get("status", "UNKNOWN")
                except json.JSONDecodeError:
                    status = "CORRUPTED"
            else:
                status = "MISSING_MANIFEST"

            stats["status_counts"][status] = stats["status_counts"].get(status, 0) + 1

        return stats


def find_jobs_directory(start_path: str = ".") -> Optional[str]:
    """
    Find the jobs directory by searching upwards from start_path.

    Args:
        start_path: Starting path for search (default: current directory)

    Returns:
        Path to jobs directory, or None if not found
    """
    current = Path(start_path).resolve()

    # Search up to 5 levels up
    for _ in range(5):
        jobs_dir = current / "jobs"
        if jobs_dir.exists() and jobs_dir.is_dir():
            return str(jobs_dir)

        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent

    return None


def ensure_jobs_directory(base_dir: str) -> str:
    """
    Ensure a jobs directory exists and return its path.

    Args:
        base_dir: Base directory where jobs directory should be created

    Returns:
        Path to jobs directory
    """
    jobs_dir = Path(base_dir) / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return str(jobs_dir)