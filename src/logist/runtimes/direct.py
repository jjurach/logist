"""
Direct Command Runtime Implementation for Logist

This module provides a DirectCommandRuntime that handles direct Cline execution
without going through the agent system, used for LLM-based job execution.
"""

import os
from typing import List, Dict, Optional, Tuple, Any

from .base import Runtime
from logist.job_processor import execute_llm_with_cline


class DirectCommandRuntime(Runtime):
    """
    Runtime for direct Cline command execution.

    This runtime handles LLM-based job execution by directly calling
    execute_llm_with_cline, bypassing the agent command generation system.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the DirectCommandRuntime.

        Args:
            working_dir: Optional working directory for execution
        """
        super().__init__(working_dir)

    def spawn(self, cmd: List[str], env: Dict[str, str], labels: Optional[Dict[str, str]] = None) -> str:
        """
        Execute LLM with Cline directly.

        This runtime doesn't spawn traditional processes but executes
        LLM calls directly via execute_llm_with_cline.

        Args:
            cmd: Not used for this runtime (LLM execution is configured via context)
            env: Environment variables (may include LLM configuration)
            labels: Optional metadata labels

        Returns:
            Unique execution identifier

        Raises:
            RuntimeError: If execution setup fails
        """
        # For direct command runtime, we don't spawn actual processes
        # Instead, we prepare for LLM execution
        # The actual execution happens in execute_job_step()
        import time
        execution_id = f"direct_{int(time.time() * 1000000)}"
        return execution_id

    def is_alive(self, process_id: str) -> bool:
        """
        Check if execution is still running.

        For direct command runtime, executions are synchronous,
        so they complete immediately.

        Args:
            process_id: The execution identifier

        Returns:
            Always False since executions complete synchronously
        """
        return False

    def get_logs(self, process_id: str, tail: Optional[int] = None) -> str:
        """
        Get logs from execution.

        For direct command runtime, logs are returned from execute_job_step.

        Args:
            process_id: The execution identifier
            tail: Optional number of lines to return from the end

        Returns:
            Empty string since logs are handled by execute_job_step

        Raises:
            RuntimeError: If process_id is invalid
        """
        return ""

    def terminate(self, process_id: str, force: bool = False) -> bool:
        """
        Terminate execution.

        For direct command runtime, since executions are synchronous,
        termination is not applicable.

        Args:
            process_id: The execution identifier
            force: If True, use force termination

        Returns:
            Always False since executions complete synchronously
        """
        return False

    def wait(self, process_id: str, timeout: Optional[float] = None) -> Tuple[int, str]:
        """
        Wait for execution to complete.

        For direct command runtime, executions complete synchronously
        in execute_job_step, so this returns empty results.

        Args:
            process_id: The execution identifier
            timeout: Optional timeout (ignored)

        Returns:
            Tuple of (0, empty_string) since execution already completed

        Raises:
            TimeoutError: Never raised for this runtime
        """
        return 0, ""

    def cleanup(self, process_id: str) -> None:
        """
        Clean up resources associated with execution.

        For direct command runtime, no cleanup is needed since
        executions are synchronous.

        Args:
            process_id: The execution identifier
        """
        pass

    def execute_job_step(self, context: Dict[str, Any], workspace_dir: str,
                        file_arguments: List[str], dry_run: bool = False) -> Tuple[Dict[str, Any], float]:
        """
        Execute a job step using LLM with Cline.

        This method provides the core execution logic for direct command runtime.

        Args:
            context: Job context dictionary
            workspace_dir: Workspace directory path
            file_arguments: List of file arguments for Cline
            dry_run: If True, simulate execution without actual LLM calls

        Returns:
            Tuple of (processed_response, execution_time)
        """
        return execute_llm_with_cline(
            context=context,
            workspace_dir=workspace_dir,
            file_arguments=file_arguments,
            dry_run=dry_run
        )

    def provision(self, job_dir: str, workspace_dir: str) -> Dict[str, Any]:
        """
        Provision workspace for direct command execution.

        For direct command runtime, provisioning is minimal since
        the runtime doesn't manage git repositories.

        Args:
            job_dir: Job directory path
            workspace_dir: Workspace directory path

        Returns:
            Dict with provisioning results
        """
        # Direct command runtime doesn't need complex provisioning
        # since it works with existing workspace structure
        return {
            "success": True,
            "attachments_copied": [],
            "discovered_files": [],
            "file_arguments": [],
            "error": None
        }

    def harvest(self, job_dir: str, workspace_dir: str, evidence_files: List[str], summary: str) -> Dict[str, Any]:
        """
        Harvest results from direct command execution.

        For direct command runtime, harvesting is minimal since
        results are handled by the caller.

        Args:
            job_dir: Job directory path
            workspace_dir: Workspace directory path
            evidence_files: List of evidence files
            summary: Summary of the execution

        Returns:
            Dict with harvest results
        """
        # Direct command runtime doesn't perform git operations
        # Results harvesting is handled by the caller
        return {
            "success": True,
            "commit_hash": None,
            "timestamp": None,
            "files_committed": [],
            "error": None
        }

    @property
    def name(self) -> str:
        """Get the runtime name."""
        return "Direct Command Runtime"

    @property
    def version(self) -> str:
        """Get the runtime version."""
        return "1.0.0"