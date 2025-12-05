import json
import os
from typing import Dict, Any, Tuple

class JobStateError(Exception):
    """Custom exception for job state related errors."""
    pass

# Job state constants
class JobStates:
    """Constants for job lifecycle states."""

    # Initial state - job is configured but not yet activated for execution
    DRAFT = "DRAFT"

    # Ready for execution - job is waiting to run
    PENDING = "PENDING"

    # Core execution states
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SUCCESS = "SUCCESS"
    CANCELED = "CANCELED"
    FAILED = "FAILED"  # Deprecated but kept for compatibility

    # Command-driven intervention states
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWING = "REVIEWING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INTERVENTION_REQUIRED = "INTERVENTION_REQUIRED"

def load_job_manifest(job_dir: str) -> Dict[str, Any]:
    """
    Loads the job manifest from the specified job directory.
    
    Args:
        job_dir: The absolute path to the job directory.
        
    Returns:
        A dictionary representing the job manifest.
        
    Raises:
        JobStateError: If the manifest file is not found or is invalid.
    """
    manifest_path = os.path.join(job_dir, "job_manifest.json")
    if not os.path.exists(manifest_path):
        raise JobStateError(f"Job manifest not found at: {manifest_path}")
        
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        return manifest
    except json.JSONDecodeError as e:
        raise JobStateError(f"Invalid job manifest JSON in {manifest_path}: {e}")
    except OSError as e:
        raise JobStateError(f"Error reading job manifest file {manifest_path}: {e}")

def get_current_state_and_role(manifest: Dict[str, Any]) -> Tuple[str, str]:
    """
    Determines the current phase and the active agent role (Worker/Supervisor)
    based on the job manifest.
    
    Args:
        manifest: The job manifest dictionary.
        
    Returns:
        A tuple containing (current_phase: str, active_role: str).
        
    Raises:
        JobStateError: If current_phase or phases are missing/invalid in the manifest.
    """
    current_phase_name = manifest.get("current_phase")
    phases = manifest.get("phases")
    
    if not current_phase_name:
        raise JobStateError("Job manifest is missing 'current_phase'.")
    
    if not isinstance(phases, list) or not phases:
        raise JobStateError("Job manifest is missing or has an invalid 'phases' list.")
        
    current_phase_data = next((p for p in phases if p.get("name") == current_phase_name), None)
    
    if not current_phase_data:
        raise JobStateError(f"Phase '{current_phase_name}' not found in job manifest phases.")
        
    # Determine the active role based on the phase's state or a simple default logic
    # For now, let's assume 'Worker' is the default and 'Supervisor' if a specific
    # condition is met (e.g., Worker has completed its part for the phase)
    # This logic will need to be expanded as the state machine evolves.
    active_role = current_phase_data.get("active_agent", "Worker") # Default to Worker

    return current_phase_name, active_role


def transition_state(current_status: str, agent_role: str, response_action: str) -> str:
    """
    Determines the next state based on current status, agent role, and LLM response action.

    Args:
        current_status: Current job status (e.g., "DRAFT", "PENDING", "RUNNING").
        agent_role: The agent that executed ("Worker" or "Supervisor").
        response_action: LLM response action ("COMPLETED", "STUCK", "RETRY", "ACTIVATED").

    Returns:
        The next status string.

    Raises:
        JobStateError: If an invalid state transition is attempted.
    """
    # State machine transitions based on 04_state_machine.md
    # Includes DRAFT as initial state and ACTIVATED transition from DRAFT→PENDING
    transitions = {
        # DRAFT state transitions (only ACTIVATED is allowed from DRAFT)
        (JobStates.DRAFT, "System", "ACTIVATED"): JobStates.PENDING,

        # PENDING and execution transitions
        (JobStates.PENDING, "Worker", "COMPLETED"): JobStates.RUNNING,  # Should actually go to REVIEW_REQUIRED after worker
        (JobStates.RUNNING, "Worker", "COMPLETED"): JobStates.REVIEW_REQUIRED,
        (JobStates.RUNNING, "Worker", "STUCK"): JobStates.INTERVENTION_REQUIRED,
        (JobStates.RUNNING, "Worker", "RETRY"): JobStates.PENDING,

        (JobStates.REVIEW_REQUIRED, "Supervisor", "COMPLETED"): JobStates.APPROVAL_REQUIRED,
        (JobStates.REVIEW_REQUIRED, "Supervisor", "STUCK"): JobStates.INTERVENTION_REQUIRED,
        (JobStates.REVIEW_REQUIRED, "Supervisor", "RETRY"): JobStates.REVIEW_REQUIRED,

        (JobStates.REVIEWING, "Supervisor", "COMPLETED"): JobStates.APPROVAL_REQUIRED,
        (JobStates.REVIEWING, "Supervisor", "STUCK"): JobStates.INTERVENTION_REQUIRED,
        (JobStates.REVIEWING, "Supervisor", "RETRY"): JobStates.REVIEW_REQUIRED,
    }

    key = (current_status, agent_role, response_action)
    if key in transitions:
        return transitions[key]

    # Default fallback for unrecognized transitions
    if response_action == "STUCK":
        return "INTERVENTION_REQUIRED"
    elif response_action == "RETRY":
        return current_status  # Stay in current state for retry
    else:
        raise JobStateError(f"Invalid state transition: {current_status} + {agent_role} + {response_action}")


def transition_state_on_error(current_status: str, error_classification: Any) -> str:
    """
    Determines state transition when an error occurs, based on error classification.

    Args:
        current_status: Current job status.
        error_classification: ErrorClassification object from error_classification module.

    Returns:
        New job status string, or None if no status change needed.

    Note:
        This function imports error_classification module internally to avoid circular imports.
    """
    from logist.error_classification import ErrorSeverity, get_new_job_status

    # Use the centralized logic from error_classification module
    new_status = get_new_job_status(error_classification)

    # Special handling for certain states
    if current_status == "RUNNING" and new_status is None:
        # Running jobs that encounter transient errors stay running for retry
        return None
    elif current_status == "REVIEWING" and new_status is None:
        # Reviewing jobs that encounter transient errors stay reviewing for retry
        return None

    return new_status


def can_transition_to_error_state(current_status: str) -> bool:
    """
    Determines if current job state allows transition to error states.

    Args:
        current_status: Current job status.

    Returns:
        True if error transitions are allowed from this state.
    """
    # Only executing states can transition to error states
    executing_states = {"RUNNING", "REVIEWING"}
    return current_status in executing_states


def get_error_recovery_options(current_status: str) -> Dict[str, Any]:
    """
    Provides recovery options available from current error state.

    Args:
        current_status: Current job status (assumed to be error state).

    Returns:
        Dictionary with recovery options and their target states.
    """
    recovery_options = {
        "INTERVENTION_REQUIRED": {
            "can_restart": True,
            "can_rerun": True,
            "can_cancel": True,
            "restart_target": "PENDING",
            "rerun_target": "PENDING",
            "description": "Job requires manual intervention before continuing"
        },
        "CANCELED": {
            "can_restart": False,
            "can_rerun": True,  # Rerun creates new job instance
            "can_cancel": False,
            "rerun_target": "PENDING",
            "description": "Job was canceled due to fatal error"
        },
        "APPROVAL_REQUIRED": {
            "can_restart": False,
            "can_rerun": False,
            "can_cancel": True,
            "can_approve": True,
            "can_reject": True,
            "approve_target": "SUCCESS",
            "reject_target": "PENDING",
            "description": "Job completed and requires final approval"
        }
    }

    return recovery_options.get(current_status, {
        "description": "Unknown error state - manual intervention required"
    })


def validate_error_transition(current_status: str, target_status: str) -> bool:
    """
    Validates that an error-related state transition is allowed.

    Args:
        current_status: Current job status.
        target_status: Target status for transition.

    Returns:
        True if transition is valid, False otherwise.
    """
    # Error states can transition back to execution states for recovery
    error_states = {"INTERVENTION_REQUIRED", "CANCELED", "APPROVAL_REQUIRED"}
    execution_states = {"PENDING", "RUNNING", "REVIEW_REQUIRED", "REVIEWING", "APPROVAL_REQUIRED"}

    if current_status in error_states and target_status in execution_states:
        # Allow recovery transitions from error states
        return True

    # Standard state machine validation
    return True  # For now, be permissive with error transitions


def update_job_manifest(
    job_dir: str,
    new_status: str = None,
    new_phase: str = None,
    cost_increment: float = 0.0,
    time_increment: float = 0.0,
    history_entry: Dict[str, Any] = None,
    skip_backup: bool = False
) -> Dict[str, Any]:
    """
    Updates the job manifest with new state and metrics.

    Args:
        job_dir: The absolute path to the job's directory.
        new_status: New status string to set.
        new_phase: New phase to advance to.
        cost_increment: Amount to add to cumulative cost.
        time_increment: Time in seconds to add to cumulative time.
        history_entry: History entry to append (dict with appropriate fields).
        skip_backup: If True, skip creating a backup before changes (dangerous!).

    Returns:
        Updated manifest dictionary.

    Raises:
        JobStateError: If update fails.
    """
    manifest = load_job_manifest(job_dir)
    modified = False

    # Create backup before making any changes (unless explicitly skipped)
    if not skip_backup and (new_status or new_phase or cost_increment > 0 or time_increment > 0 or history_entry):
        try:
            from logist.recovery import create_job_manifest_backup
            create_job_manifest_backup(job_dir)
        except Exception:
            # Log warning but don't fail - backup is nice but not critical
            import sys
            print("Warning: Failed to create job manifest backup", file=sys.stderr)

    # Update status
    if new_status is not None:
        manifest["status"] = new_status
        modified = True

    # Update current phase
    if new_phase is not None:
        manifest["current_phase"] = new_phase
        modified = True

    # Update metrics
    if cost_increment > 0:
        manifest["metrics"]["cumulative_cost"] += cost_increment
        modified = True

    if time_increment > 0:
        manifest["metrics"]["cumulative_time_seconds"] += time_increment
        modified = True

    # Add history entry
    if history_entry:
        if "history" not in manifest:
            manifest["history"] = []
        # Add timestamp if not present
        if "timestamp" not in history_entry:
            from datetime import datetime
            history_entry["timestamp"] = datetime.now().isoformat()
        manifest["history"].append(history_entry)
        modified = True

    # Save only if modified
    if modified:
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        try:
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        except OSError as e:
            raise JobStateError(f"Failed to write updated manifest to {manifest_path}: {e}")

    # Queue cleanup: remove jobs from queue when transitioning to terminal states
    if new_status is not None and new_status in [JobStates.SUCCESS, JobStates.CANCELED]:
        try:
            job_id = manifest.get("job_id")
            if job_id:
                # Determine jobs directory from job_dir path
                jobs_dir = os.path.dirname(job_dir)
                jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")

                if os.path.exists(jobs_index_path):
                    with open(jobs_index_path, 'r') as f:
                        jobs_index = json.load(f)

                    queue = jobs_index.get("queue", [])
                    if job_id in queue:
                        queue.remove(job_id)
                        # Save updated jobs index
                        with open(jobs_index_path, 'w') as f:
                            json.dump(jobs_index, f, indent=2)
        except Exception as e:
            # Queue cleanup is best-effort; don't fail the status update if cleanup fails
            import sys
            print(f"Warning: Failed to remove job '{job_id or 'unknown'}' from queue during terminal state transition: {e}", file=sys.stderr)

    # Cleanup logic: trigger workspace cleanup when transitioning to terminal states
    if new_status is not None and modified:
        terminal_states = {"SUCCESS", "CANCELED"}
        if new_status in terminal_states:
            try:
                from logist import workspace_utils
                should_cleanup, reason = workspace_utils.should_cleanup_workspace(job_dir)
                if should_cleanup:
                    # Perform cleanup with backup safety
                    backup_result = workspace_utils.backup_workspace_before_cleanup(job_dir)
                    if backup_result["success"]:
                        workspace_dir = os.path.join(job_dir, "workspace")
                        try:
                            import shutil
                            shutil.rmtree(workspace_dir)
                            # Log cleanup event in manifest
                            cleanup_entry = {
                                "timestamp": None,  # Will be set by update_job_manifest if this were called again
                                "event": "WORKSPACE_CLEANUP",
                                "action": f"Workspace cleaned up on transition to {new_status}",
                                "reason": reason,
                                "backup_created": backup_result["backup_archive"]
                            }
                            manifest["history"].append(cleanup_entry)
                            # Save cleanup event (without triggering another cleanup cycle)
                            with open(manifest_path, 'w') as f:
                                json.dump(manifest, f, indent=2)
                        except OSError as cleanup_error:
                            # Cleanup failed, log but don't fail the status update
                            import sys
                            print(f"Warning: Workspace cleanup failed for {job_dir}: {cleanup_error}", file=sys.stderr)
                    else:
                        # Backup failed, skip cleanup for safety
                        import sys
                        print(f"Warning: Workspace cleanup skipped for {job_dir} - backup failed: {backup_result['error']}", file=sys.stderr)
            except Exception as cleanup_error:
                # Cleanup is best-effort; don't fail status update if cleanup fails
                import sys
                print(f"Warning: Advanced cleanup failed for {job_dir}: {cleanup_error}", file=sys.stderr)

    return manifest