"""
Base Runner Interface for Logist

This module defines the abstract base class for all Runner implementations in Logist.
Runners are responsible for executing agent commands in various environments
(Docker containers, host processes, remote systems, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any
import subprocess


class Runner(ABC):
    """
    Abstract base class for all Logist runner environments.

    Runners handle the execution of agent commands, providing isolation,
    monitoring, and resource management capabilities.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the runner.

        Args:
            working_dir: Optional working directory for process execution
        """
        self.working_dir = working_dir

    @abstractmethod
    def spawn(self, cmd: List[str], env: Dict[str, str], labels: Optional[Dict[str, str]] = None) -> str:
        """
        Start a new process or container with the given command and environment.

        Args:
            cmd: List of command arguments to execute
            env: Environment variables to set for the process
            labels: Optional metadata labels for tracking/management

        Returns:
            Unique identifier for the spawned process/container

        Raises:
            RuntimeError: If spawning fails
        """
        pass

    @abstractmethod
    def is_alive(self, process_id: str) -> bool:
        """
        Check if a process/container is still running.

        Args:
            process_id: The identifier returned by spawn()

        Returns:
            True if the process/container is alive, False otherwise
        """
        pass

    @abstractmethod
    def get_logs(self, process_id: str, tail: Optional[int] = None) -> str:
        """
        Get the current logs (stdout/stderr) from a running process.

        Args:
            process_id: The identifier returned by spawn()
            tail: Optional number of lines to return from the end

        Returns:
            Log output as a string

        Raises:
            RuntimeError: If process_id is invalid or logs cannot be retrieved
        """
        pass

    @abstractmethod
    def terminate(self, process_id: str, force: bool = False) -> bool:
        """
        Terminate a running process/container.

        Args:
            process_id: The identifier returned by spawn()
            force: If True, use SIGKILL instead of SIGTERM

        Returns:
            True if termination was successful, False otherwise
        """
        pass

    @abstractmethod
    def wait(self, process_id: str, timeout: Optional[float] = None) -> Tuple[int, str]:
        """
        Wait for a process to complete and return its exit code and final logs.

        Args:
            process_id: The identifier returned by spawn()
            timeout: Optional timeout in seconds to wait

        Returns:
            Tuple of (exit_code, final_logs)

        Raises:
            TimeoutError: If timeout is exceeded
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the human-readable name of this runner.

        Returns:
            String identifier for the runner type
        """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """
        Get the version of this runner implementation.

        Returns:
            Version string (e.g., "1.0.0")
        """
        pass

    def provision(self, job_dir: str, workspace_dir: str) -> Dict[str, Any]:
        """
        Provision workspace for job execution.

        This includes setting up git repositories, copying attachments,
        and preparing the workspace environment.

        Args:
            job_dir: Job directory path
            workspace_dir: Workspace directory path

        Returns:
            Dict with provisioning results
        """
        raise NotImplementedError("provision() must be implemented by subclasses")

    def harvest(self, job_dir: str, workspace_dir: str, evidence_files: List[str], summary: str) -> Dict[str, Any]:
        """
        Harvest results from completed job execution.

        This includes committing changes, collecting artifacts,
        and preparing results for the next phase.

        Args:
            job_dir: Job directory path
            workspace_dir: Workspace directory path
            evidence_files: List of evidence files to commit
            summary: Summary of the execution for commit message

        Returns:
            Dict with harvest results
        """
        raise NotImplementedError("harvest() must be implemented by subclasses")

    def cleanup(self, process_id: str) -> None:
        """
        Clean up any resources associated with a process.

        This is called automatically after termination and can be
        overridden by subclasses for custom cleanup logic.

        Args:
            process_id: The identifier returned by spawn()
        """
        pass
