"""
Advisory File Locking for Logist Jobs

This module provides advisory file locking to prevent concurrent access to job directories
and resources. It uses fcntl-based locking on Unix systems for cross-process coordination.
"""

import os
import fcntl
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from pathlib import Path

from ..job_state import JobStateError


class LockError(JobStateError):
    """Custom exception for locking-related errors."""
    pass


class FileLock:
    """
    Advisory file lock using fcntl for cross-process coordination.

    This provides cooperative locking - processes must explicitly acquire and release locks.
    """

    def __init__(self, lock_file_path: str, timeout: float = 30.0):
        """
        Initialize a file lock.

        Args:
            lock_file_path: Path to the lock file
            timeout: Maximum time to wait for lock acquisition (seconds)
        """
        self.lock_file_path = Path(lock_file_path)
        self.timeout = timeout
        self._lock_fd: Optional[int] = None
        self._locked = False

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the file lock.

        Args:
            blocking: If True, block until lock is acquired or timeout
                     If False, return immediately

        Returns:
            True if lock was acquired, False if not (non-blocking mode)

        Raises:
            LockError: If lock acquisition fails
        """
        if self._locked:
            return True

        # Ensure lock file exists
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file_path.touch(exist_ok=True)

        try:
            self._lock_fd = os.open(str(self.lock_file_path), os.O_RDWR)

            start_time = time.time()
            while True:
                try:
                    # Try to acquire exclusive lock
                    fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._locked = True
                    return True
                except BlockingIOError:
                    if not blocking:
                        os.close(self._lock_fd)
                        self._lock_fd = None
                        return False

                    # Check timeout
                    if time.time() - start_time > self.timeout:
                        os.close(self._lock_fd)
                        self._lock_fd = None
                        raise LockError(f"Lock acquisition timeout after {self.timeout}s: {self.lock_file_path}")

                    # Wait a bit before retrying
                    time.sleep(0.1)

        except OSError as e:
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            raise LockError(f"Failed to acquire lock {self.lock_file_path}: {e}")

    def release(self) -> None:
        """
        Release the file lock.

        Raises:
            LockError: If lock release fails
        """
        if not self._locked or self._lock_fd is None:
            return

        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None
            self._locked = False
        except OSError as e:
            raise LockError(f"Failed to release lock {self.lock_file_path}: {e}")

    def is_locked(self) -> bool:
        """
        Check if this lock instance currently holds the lock.

        Returns:
            True if this instance holds the lock
        """
        return self._locked

    def __enter__(self):
        self.acquire(blocking=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def __del__(self):
        if self._lock_fd is not None:
            try:
                os.close(self._lock_fd)
            except OSError:
                pass  # Ignore errors in destructor


class JobLockManager:
    """
    Manages file locks for job directories and resources.

    Provides convenient methods for locking job directories and related resources
    to prevent concurrent access issues.
    """

    def __init__(self, base_jobs_dir: str):
        """
        Initialize the job lock manager.

        Args:
            base_jobs_dir: Base directory containing job directories
        """
        self.base_jobs_dir = Path(base_jobs_dir)
        self._active_locks: Dict[str, FileLock] = {}

    def lock_job_directory(self, job_id: str, timeout: float = 30.0) -> FileLock:
        """
        Acquire a lock for a job directory.

        Args:
            job_id: Job identifier
            timeout: Lock acquisition timeout

        Returns:
            FileLock instance (already acquired)

        Raises:
            LockError: If lock acquisition fails
        """
        lock_file = self.base_jobs_dir / job_id / ".lock"
        lock = FileLock(str(lock_file), timeout)

        if not lock.acquire(blocking=True):
            raise LockError(f"Failed to acquire lock for job {job_id}")

        self._active_locks[job_id] = lock
        return lock

    def unlock_job_directory(self, job_id: str) -> None:
        """
        Release the lock for a job directory.

        Args:
            job_id: Job identifier
        """
        if job_id in self._active_locks:
            self._active_locks[job_id].release()
            del self._active_locks[job_id]

    def is_job_locked(self, job_id: str) -> bool:
        """
        Check if a job directory is currently locked by this manager.

        Args:
            job_id: Job identifier

        Returns:
            True if job is locked by this manager
        """
        return job_id in self._active_locks and self._active_locks[job_id].is_locked()

    @contextmanager
    def job_lock(self, job_id: str, timeout: float = 30.0):
        """
        Context manager for job directory locking.

        Args:
            job_id: Job identifier
            timeout: Lock acquisition timeout

        Yields:
            FileLock instance

        Example:
            with lock_manager.job_lock("job_123"):
                # Job directory is locked here
                pass
            # Lock is automatically released
        """
        lock = self.lock_job_directory(job_id, timeout)
        try:
            yield lock
        finally:
            self.unlock_job_directory(job_id)

    def lock_jobs_index(self, timeout: float = 30.0) -> FileLock:
        """
        Acquire a lock for the jobs index file.

        Returns:
            FileLock instance for the jobs index

        Raises:
            LockError: If lock acquisition fails
        """
        index_lock_file = self.base_jobs_dir / ".jobs_index.lock"
        lock = FileLock(str(index_lock_file), timeout)

        if not lock.acquire(blocking=True):
            raise LockError("Failed to acquire jobs index lock")

        return lock

    @contextmanager
    def jobs_index_lock(self, timeout: float = 30.0):
        """
        Context manager for jobs index locking.

        Args:
            timeout: Lock acquisition timeout

        Yields:
            FileLock instance
        """
        lock = self.lock_jobs_index(timeout)
        try:
            yield lock
        finally:
            lock.release()

    def cleanup_stale_locks(self, max_age_seconds: int = 3600) -> List[str]:
        """
        Clean up stale lock files that may be left behind by crashed processes.

        Args:
            max_age_seconds: Maximum age of lock files to consider stale

        Returns:
            List of cleaned up job IDs
        """
        cleaned_jobs = []
        current_time = time.time()

        # Check all job directories for stale locks
        if self.base_jobs_dir.exists():
            for job_dir in self.base_jobs_dir.iterdir():
                if job_dir.is_dir() and not job_dir.name.startswith('.'):
                    lock_file = job_dir / ".lock"
                    if lock_file.exists():
                        try:
                            stat = lock_file.stat()
                            age = current_time - stat.st_mtime

                            # If lock file is older than max_age, consider it stale
                            if age > max_age_seconds:
                                lock_file.unlink()
                                cleaned_jobs.append(job_dir.name)
                        except OSError:
                            # If we can't stat or unlink, skip it
                            continue

        # Check jobs index lock
        index_lock_file = self.base_jobs_dir / ".jobs_index.lock"
        if index_lock_file.exists():
            try:
                stat = index_lock_file.stat()
                age = current_time - stat.st_mtime

                if age > max_age_seconds:
                    index_lock_file.unlink()
            except OSError:
                pass

        return cleaned_jobs

    def get_lock_status(self) -> Dict[str, Any]:
        """
        Get status of all locks managed by this instance.

        Returns:
            Dictionary with lock status information
        """
        return {
            "active_locks": list(self._active_locks.keys()),
            "lock_count": len(self._active_locks)
        }


@contextmanager
def job_directory_lock(job_id: str, base_jobs_dir: str, timeout: float = 30.0):
    """
    Convenience context manager for locking a job directory.

    Args:
        job_id: Job identifier
        base_jobs_dir: Base jobs directory path
        timeout: Lock acquisition timeout

    Yields:
        FileLock instance

    Example:
        with job_directory_lock("job_123", "/path/to/jobs"):
            # Job directory is locked
            pass
    """
    lock_manager = JobLockManager(base_jobs_dir)
    with lock_manager.job_lock(job_id, timeout) as lock:
        yield lock


def try_lock_job_directory(job_id: str, base_jobs_dir: str, timeout: float = 5.0) -> Optional[FileLock]:
    """
    Try to acquire a lock for a job directory without blocking indefinitely.

    Args:
        job_id: Job identifier
        base_jobs_dir: Base jobs directory path
        timeout: Maximum time to wait for lock

    Returns:
        FileLock instance if acquired, None if already locked
    """
    lock_manager = JobLockManager(base_jobs_dir)
    try:
        return lock_manager.lock_job_directory(job_id, timeout)
    except LockError:
        return None