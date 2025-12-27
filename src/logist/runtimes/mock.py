"""
Mock Runtime Implementation for Logist

This module provides a MockRuntime that simulates Runtime behavior for testing
purposes without requiring actual process execution or external dependencies.
"""

import time
import threading
import random
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .base import Runtime


class MockRuntime(Runtime):
    """
    Mock runtime that simulates process execution for testing.

    This runtime provides realistic simulation of process lifecycles,
    log streaming, and termination behaviors without spawning actual processes.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the MockRuntime.

        Args:
            working_dir: Optional working directory (ignored for mock)
        """
        super().__init__(working_dir)
        self._processes: Dict[str, Dict] = {}
        self._process_counter = 0
        self._lock = threading.Lock()

    def spawn(self, cmd: List[str], env: Dict[str, str], labels: Optional[Dict[str, str]] = None) -> str:
        """
        Simulate spawning a process.

        Args:
            cmd: Command that would be executed (used to determine mock behavior)
            env: Environment variables (used for mode detection)
            labels: Optional metadata labels (ignored for mock)

        Returns:
            Unique process identifier

        Raises:
            RuntimeError: If spawning simulation fails
        """
        # Basic command validation - check if command exists (for testing invalid commands)
        if cmd and len(cmd) > 0:
            import shutil
            if not shutil.which(cmd[0]):
                # Command doesn't exist
                raise RuntimeError(f"Failed to spawn process: command not found: {cmd[0]}")

        # Generate unique process ID
        process_id = f"mock_{int(time.time() * 1000000)}_{self._process_counter}"
        self._process_counter += 1

        # Determine mode from environment
        mode = env.get('MOCK_AGENT_MODE', 'success')

        # Initialize process state
        process_state = {
            'process_id': process_id,
            'mode': mode,
            'status': 'running',
            'start_time': time.time(),
            'logs': [],
            'exit_code': None,
            'thread': None,
            'terminated': False,
            'force_terminated': False
        }

        # Start background thread to simulate execution
        thread = threading.Thread(
            target=self._simulate_execution,
            args=(process_state,),
            daemon=True
        )

        process_state['thread'] = thread

        with self._lock:
            self._processes[process_id] = process_state

        thread.start()

        return process_id

    def _simulate_execution(self, process_state: Dict) -> None:
        """
        Simulate the execution of a mock agent process.

        Args:
            process_state: The process state dictionary to update
        """
        mode = process_state['mode']

        try:
            if mode == 'success':
                self._simulate_success(process_state)
            elif mode == 'hang':
                self._simulate_hang(process_state)
            elif mode == 'api_error':
                self._simulate_api_error(process_state)
            elif mode == 'context_full':
                self._simulate_context_full(process_state)
            elif mode == 'auth_error':
                self._simulate_auth_error(process_state)
            elif mode == 'interactive':
                self._simulate_interactive(process_state)
            else:
                # Default to success
                self._simulate_success(process_state)

        except Exception as e:
            # Handle any unexpected errors in simulation
            process_state['logs'].append(f"Unexpected error in mock agent: {e}")
            process_state['exit_code'] = 1
            process_state['status'] = 'completed'

    def _simulate_success(self, process_state: Dict) -> None:
        """Simulate successful execution."""
        self._add_log(process_state, "Thinking...")
        time.sleep(random.uniform(0.1, 0.5))  # Fast for testing

        self._add_log(process_state, "Analyzing requirements...")
        time.sleep(random.uniform(0.2, 0.8))

        self._add_log(process_state, "Planning implementation...")
        time.sleep(random.uniform(0.1, 0.4))

        self._add_log(process_state, "Applying changes...")
        time.sleep(random.uniform(0.5, 1.5))

        self._add_log(process_state, "Running tests...")
        time.sleep(random.uniform(0.3, 0.8))

        self._add_log(process_state, "Task completed successfully.")

        process_state['exit_code'] = 0
        process_state['status'] = 'completed'

    def _simulate_hang(self, process_state: Dict) -> None:
        """Simulate hanging execution."""
        self._add_log(process_state, "Thinking...")
        time.sleep(random.uniform(0.1, 0.5))

        self._add_log(process_state, "Processing request...")
        time.sleep(random.uniform(0.2, 0.8))

        self._add_log(process_state, "Working on complex analysis...")

        # Simulate hanging - sleep for a long time or until terminated
        end_time = time.time() + 300  # 5 minutes should be enough for testing
        while time.time() < end_time and not process_state.get('terminated', False):
            time.sleep(0.1)

        if not process_state.get('terminated', False):
            # If not terminated, complete normally (shouldn't happen in tests)
            self._add_log(process_state, "Task completed successfully.")
            process_state['exit_code'] = 0
            process_state['status'] = 'completed'

    def _simulate_api_error(self, process_state: Dict) -> None:
        """Simulate API error."""
        self._add_log(process_state, "Thinking...")
        time.sleep(random.uniform(0.1, 0.5))

        self._add_log(process_state, "Preparing API request...")
        time.sleep(random.uniform(0.2, 0.8))

        self._add_log(process_state, "API Error: Rate limit reached (429)")
        self._add_log(process_state, "Too Many Requests - please try again later.")

        process_state['exit_code'] = 1
        process_state['status'] = 'completed'

    def _simulate_context_full(self, process_state: Dict) -> None:
        """Simulate context full error."""
        self._add_log(process_state, "Thinking...")
        time.sleep(random.uniform(0.1, 0.5))

        self._add_log(process_state, "Processing large codebase...")
        time.sleep(random.uniform(0.2, 0.8))

        self._add_log(process_state, "Token limit exceeded.")
        self._add_log(process_state, "Context length is too large for this model.")

        process_state['exit_code'] = 1
        process_state['status'] = 'completed'

    def _simulate_auth_error(self, process_state: Dict) -> None:
        """Simulate auth error."""
        self._add_log(process_state, "Initializing...")
        time.sleep(random.uniform(0.1, 0.4))

        self._add_log(process_state, "Authentication failed.")
        self._add_log(process_state, "Invalid API key provided.")

        process_state['exit_code'] = 1
        process_state['status'] = 'completed'

    def _simulate_interactive(self, process_state: Dict) -> None:
        """Simulate interactive execution."""
        self._add_log(process_state, "Thinking...")
        time.sleep(random.uniform(0.1, 0.5))

        self._add_log(process_state, "Analyzing changes...")
        time.sleep(random.uniform(0.2, 0.8))

        self._add_log(process_state, "Found potential issues that need confirmation.")
        time.sleep(random.uniform(0.1, 0.4))

        self._add_log(process_state, "Confirm changes? [y/N]: ")

        # Simulate waiting for input indefinitely
        end_time = time.time() + 300  # 5 minutes
        while time.time() < end_time and not process_state.get('terminated', False):
            time.sleep(0.1)

        if not process_state.get('terminated', False):
            # If not terminated, assume user cancelled
            self._add_log(process_state, "Operation cancelled.")
            process_state['exit_code'] = 1
            process_state['status'] = 'completed'

    def _add_log(self, process_state: Dict, message: str) -> None:
        """
        Add a log message to the process state.

        Args:
            process_state: The process state dictionary
            message: The log message to add
        """
        process_state['logs'].append(message)

    def is_alive(self, process_id: str) -> bool:
        """
        Check if a mock process is still running.

        Args:
            process_id: The process identifier

        Returns:
            True if the process is alive, False otherwise

        Raises:
            RuntimeError: If process_id is invalid
        """
        with self._lock:
            if process_id not in self._processes:
                raise RuntimeError(f"Invalid process ID: {process_id}")

            process_state = self._processes[process_id]
            return process_state['status'] == 'running' and not process_state.get('terminated', False)

    def get_logs(self, process_id: str, tail: Optional[int] = None) -> str:
        """
        Get the current logs from a mock process.

        Args:
            process_id: The process identifier
            tail: Optional number of lines to return from the end

        Returns:
            Log output as a string

        Raises:
            RuntimeError: If process_id is invalid
        """
        with self._lock:
            if process_id not in self._processes:
                raise RuntimeError(f"Invalid process ID: {process_id}")

            logs = self._processes[process_id]['logs']
            if tail is not None and tail > 0:
                logs = logs[-tail:]

            return '\n'.join(logs)

    def terminate(self, process_id: str, force: bool = False) -> bool:
        """
        Terminate a mock process.

        Args:
            process_id: The process identifier
            force: If True, use force termination (same behavior for mock)

        Returns:
            True if termination was successful, False otherwise

        Raises:
            RuntimeError: If process_id is invalid
        """
        with self._lock:
            if process_id not in self._processes:
                raise RuntimeError(f"Invalid process ID: {process_id}")

            process_state = self._processes[process_id]

            if process_state['status'] != 'running':
                return False

            # Mark as terminated
            process_state['terminated'] = True
            process_state['force_terminated'] = force
            process_state['status'] = 'terminated'

            # Set exit code based on termination type
            if force:
                process_state['exit_code'] = 137  # SIGKILL
            else:
                process_state['exit_code'] = 143  # SIGTERM

            return True

    def wait(self, process_id: str, timeout: Optional[float] = None) -> Tuple[int, str]:
        """
        Wait for a mock process to complete.

        Args:
            process_id: The process identifier
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (exit_code, final_logs)

        Raises:
            TimeoutError: If timeout is exceeded
            RuntimeError: If process_id is invalid
        """
        with self._lock:
            if process_id not in self._processes:
                raise RuntimeError(f"Invalid process ID: {process_id}")

            process_state = self._processes[process_id]

        start_wait = time.time()
        while process_state['status'] == 'running':
            if timeout is not None and (time.time() - start_wait) > timeout:
                raise TimeoutError(f"Process {process_id} did not complete within {timeout} seconds")

            time.sleep(0.05)  # Small sleep to avoid busy waiting

        # Return final results
        return process_state['exit_code'], self.get_logs(process_id)

    def cleanup(self, process_id: str) -> None:
        """
        Clean up resources associated with a mock process.

        Args:
            process_id: The process identifier
        """
        with self._lock:
            self._processes.pop(process_id, None)

    @property
    def name(self) -> str:
        """Get the runtime name."""
        return "Mock Runtime"

    def provision(self, job_dir: str, workspace_dir: str) -> Dict[str, Any]:
        """
        Provision workspace for mock job execution.

        For mock runtime, this is a no-op that always succeeds.

        Args:
            job_dir: Job directory path
            workspace_dir: Workspace directory path

        Returns:
            Dict with provisioning results
        """
        return {
            "success": True,
            "attachments_copied": [],
            "discovered_files": [],
            "file_arguments": [],
            "error": None
        }

    def harvest(self, job_dir: str, workspace_dir: str, evidence_files: List[str], summary: str) -> Dict[str, Any]:
        """
        Harvest results from mock job execution.

        For mock runtime, this is a no-op that always succeeds.

        Args:
            job_dir: Job directory path
            workspace_dir: Workspace directory path
            evidence_files: List of evidence files to commit
            summary: Summary of the execution for commit message

        Returns:
            Dict with harvest results
        """
        return {
            "success": True,
            "commit_hash": f"mock_{int(time.time())}_{random.randint(1000, 9999)}",
            "timestamp": time.time(),
            "files_committed": evidence_files,
            "error": None
        }

    @property
    def version(self) -> str:
        """Get the runtime version."""
        return "1.0.0"