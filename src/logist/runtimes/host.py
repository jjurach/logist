"""
Host Runtime Implementation for Logist

This module provides a Runtime implementation that executes processes
directly on the host system using Python's subprocess module.
"""

import os
import signal
import subprocess
import threading
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .base import Runtime


class HostRuntime(Runtime):
    """
    Runtime implementation that executes processes on the host system.

    This runtime uses subprocess.Popen to spawn and manage processes,
    providing direct execution without containerization.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the HostRuntime.

        Args:
            working_dir: Optional working directory for process execution.
                        Defaults to current directory.
        """
        super().__init__(working_dir)
        self._processes: Dict[str, subprocess.Popen] = {}
        self._logs: Dict[str, List[str]] = {}
        self._log_threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def spawn(self, cmd: List[str], env: Dict[str, str], labels: Optional[Dict[str, str]] = None) -> str:
        """
        Start a new process on the host system.

        Args:
            cmd: List of command arguments to execute
            env: Environment variables to set for the process
            labels: Optional metadata labels (ignored for host runtime)

        Returns:
            Unique process identifier

        Raises:
            RuntimeError: If process spawning fails
        """
        # Create unique process ID
        process_id = f"host_{int(time.time() * 1000000)}_{os.getpid()}"

        # Merge environment variables
        process_env = os.environ.copy()
        process_env.update(env)

        # Set working directory
        cwd = self.working_dir or os.getcwd()

        try:
            # Start the process
            popen = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stdout and stderr
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            with self._lock:
                self._processes[process_id] = popen
                self._logs[process_id] = []

                # Start log collection thread
                log_thread = threading.Thread(
                    target=self._collect_logs,
                    args=(process_id, popen),
                    daemon=True
                )
                self._log_threads[process_id] = log_thread
                log_thread.start()

            return process_id

        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(f"Failed to spawn process: {e}") from e

    def _collect_logs(self, process_id: str, popen: subprocess.Popen) -> None:
        """
        Collect logs from a running process in a separate thread.

        Args:
            process_id: The process identifier
            popen: The subprocess.Popen object
        """
        try:
            while popen.poll() is None:  # Process is still running
                if popen.stdout:
                    line = popen.stdout.readline()
                    if line:  # Empty string means EOF
                        with self._lock:
                            if process_id in self._logs:
                                self._logs[process_id].append(line.rstrip('\n\r'))
                    else:
                        time.sleep(0.1)  # Small delay to avoid busy waiting
                else:
                    break

            # Collect any remaining output
            if popen.stdout:
                remaining = popen.stdout.read()
                if remaining:
                    with self._lock:
                        if process_id in self._logs:
                            self._logs[process_id].extend(
                                line.rstrip('\n\r') for line in remaining.splitlines() if line
                            )

        except Exception:
            # Log collection errors shouldn't crash the main thread
            pass

    def is_alive(self, process_id: str) -> bool:
        """
        Check if a process is still running.

        Args:
            process_id: The process identifier

        Returns:
            True if the process is alive, False otherwise
        """
        with self._lock:
            popen = self._processes.get(process_id)
            if popen is None:
                return False

            # Check if process has terminated
            return popen.poll() is None

    def get_logs(self, process_id: str, tail: Optional[int] = None) -> str:
        """
        Get the current logs from a running process.

        Args:
            process_id: The process identifier
            tail: Optional number of lines to return from the end

        Returns:
            Log output as a string

        Raises:
            RuntimeError: If process_id is invalid
        """
        with self._lock:
            if process_id not in self._logs:
                raise RuntimeError(f"Invalid process ID: {process_id}")

            logs = self._logs[process_id]
            if tail is not None and tail > 0:
                logs = logs[-tail:]

            return '\n'.join(logs)

    def terminate(self, process_id: str, force: bool = False) -> bool:
        """
        Terminate a running process.

        Args:
            process_id: The process identifier
            force: If True, use SIGKILL instead of SIGTERM

        Returns:
            True if termination was successful, False otherwise
        """
        with self._lock:
            popen = self._processes.get(process_id)
            if popen is None:
                return False

            try:
                if force:
                    popen.kill()  # SIGKILL
                else:
                    popen.terminate()  # SIGTERM

                # Wait a bit for graceful shutdown (unless force=True)
                if not force:
                    try:
                        popen.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        # If SIGTERM didn't work, force kill
                        popen.kill()

                return True

            except (OSError, subprocess.SubprocessError):
                return False

    def wait(self, process_id: str, timeout: Optional[float] = None) -> Tuple[int, str]:
        """
        Wait for a process to complete and return its exit code and final logs.

        Args:
            process_id: The process identifier
            timeout: Optional timeout in seconds to wait

        Returns:
            Tuple of (exit_code, final_logs)

        Raises:
            TimeoutError: If timeout is exceeded
        """
        with self._lock:
            popen = self._processes.get(process_id)
            if popen is None:
                raise RuntimeError(f"Invalid process ID: {process_id}")

        try:
            # Wait for process to complete
            if timeout is not None:
                exit_code = popen.wait(timeout=timeout)
            else:
                exit_code = popen.wait()

            # Get final logs
            final_logs = self.get_logs(process_id)

            # Cleanup resources
            self.cleanup(process_id)

            return exit_code, final_logs

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Process {process_id} did not complete within {timeout} seconds")

    def cleanup(self, process_id: str) -> None:
        """
        Clean up resources associated with a process.

        Args:
            process_id: The process identifier
        """
        with self._lock:
            # Remove from tracking dictionaries
            self._processes.pop(process_id, None)
            self._logs.pop(process_id, None)
            self._log_threads.pop(process_id, None)

    @property
    def name(self) -> str:
        """Get the runtime name."""
        return "Host Runtime"

    @property
    def version(self) -> str:
        """Get the runtime version."""
        return "1.0.0"