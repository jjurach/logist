import json
import os
from typing import Dict, Any, Tuple

class JobStateError(Exception):
    """Custom exception for job state related errors."""
    pass

# Job state constants
class JobStates:
    """Constants for job lifecycle states.

    States are divided into two categories:

    **Resting States** (job waits here until external action):
    - DRAFT: Being configured
    - PENDING: Ready for next step
    - SUCCESS: Complete (terminal)
    - CANCELED: Terminated (terminal)
    - SUSPENDED: Paused
    - APPROVAL_REQUIRED: Needs human sign-off
    - INTERVENTION_REQUIRED: Needs human fix

    **Transient States** (job passes through during step execution):
    - PROVISIONING: Setting up workspace
    - EXECUTING: Agent running
    - RECOVERING: Restarting stuck agent
    - HARVESTING: Collecting results
    """

    # Resting states
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    SUSPENDED = "SUSPENDED"
    SUCCESS = "SUCCESS"
    CANCELED = "CANCELED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INTERVENTION_REQUIRED = "INTERVENTION_REQUIRED"

    # Transient states (during step execution)
    PROVISIONING = "PROVISIONING"
    EXECUTING = "EXECUTING"
    RECOVERING = "RECOVERING"
    HARVESTING = "HARVESTING"

    # Deprecated states (kept for backward compatibility and migration)
    RUNNING = "RUNNING"  # Deprecated: use PROVISIONING/EXECUTING/HARVESTING
    PAUSED = "PAUSED"  # Deprecated: use SUSPENDED
    FAILED = "FAILED"  # Deprecated: use INTERVENTION_REQUIRED or CANCELED
    REVIEW_REQUIRED = "REVIEW_REQUIRED"  # Deprecated: removed (agents self-evaluate)
    REVIEWING = "REVIEWING"  # Deprecated: removed (agents self-evaluate)

    # Attach/recover session states (legacy)
    ATTACHED = "ATTACHED"
    DETACHED = "DETACHED"

    # Lists for validation
    RESTING_STATES = {DRAFT, PENDING, SUSPENDED, SUCCESS, CANCELED, APPROVAL_REQUIRED, INTERVENTION_REQUIRED}
    TRANSIENT_STATES = {PROVISIONING, EXECUTING, RECOVERING, HARVESTING}
    TERMINAL_STATES = {SUCCESS, CANCELED}
    DEPRECATED_STATES = {RUNNING, PAUSED, FAILED, REVIEW_REQUIRED, REVIEWING}

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

def get_current_state(manifest: Dict[str, Any]) -> str:
    """
    Determines the current phase based on the job manifest.

    Args:
        manifest: The job manifest dictionary.

    Returns:
        The current phase name as a string.

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

    return current_phase_name


def transition_state(current_status: str, response_action: str) -> str:
    """
    Determines the next state based on current status and action.

    Args:
        current_status: Current job status (e.g., "DRAFT", "PENDING", "EXECUTING").
        response_action: Action triggering the transition:
            - "ACTIVATED": Activate a DRAFT job
            - "STEP_START": Begin step execution
            - "PROVISION_COMPLETE": Provisioning finished
            - "EXECUTE_COMPLETE": Agent execution finished
            - "RECOVER_START": Begin recovery attempt
            - "RECOVER_COMPLETE": Recovery succeeded
            - "HARVEST_SUCCESS": Harvest determined goal achieved
            - "HARVEST_APPROVAL": Harvest determined approval needed
            - "HARVEST_INTERVENTION": Harvest determined intervention needed
            - "APPROVE": Human approved
            - "REJECT": Human rejected
            - "RESUBMIT": Human resubmitted after fix
            - "SUSPEND": Pause the job
            - "RESUME": Resume a suspended job
            - "CANCEL": Cancel the job
            - Legacy: "COMPLETED", "STUCK", "RETRY"

    Returns:
        The next status string.

    Raises:
        JobStateError: If an invalid state transition is attempted.
    """
    # State machine transitions based on 04_state_machine.md
    transitions = {
        # DRAFT state transitions
        (JobStates.DRAFT, "ACTIVATED"): JobStates.PENDING,
        (JobStates.DRAFT, "SUSPEND"): JobStates.SUSPENDED,
        (JobStates.DRAFT, "CANCEL"): JobStates.CANCELED,

        # PENDING state transitions (step execution begins)
        (JobStates.PENDING, "STEP_START"): JobStates.PROVISIONING,
        (JobStates.PENDING, "SUSPEND"): JobStates.SUSPENDED,
        (JobStates.PENDING, "CANCEL"): JobStates.CANCELED,

        # PROVISIONING state transitions
        (JobStates.PROVISIONING, "PROVISION_COMPLETE"): JobStates.EXECUTING,
        (JobStates.PROVISIONING, "PROVISION_FAILED"): JobStates.INTERVENTION_REQUIRED,
        (JobStates.PROVISIONING, "CANCEL"): JobStates.CANCELED,

        # EXECUTING state transitions
        (JobStates.EXECUTING, "EXECUTE_COMPLETE"): JobStates.HARVESTING,
        (JobStates.EXECUTING, "RECOVER_START"): JobStates.RECOVERING,
        (JobStates.EXECUTING, "CANCEL"): JobStates.CANCELED,

        # RECOVERING state transitions (always returns to EXECUTING)
        (JobStates.RECOVERING, "RECOVER_COMPLETE"): JobStates.EXECUTING,

        # HARVESTING state transitions (determines final resting state)
        (JobStates.HARVESTING, "HARVEST_SUCCESS"): JobStates.SUCCESS,
        (JobStates.HARVESTING, "HARVEST_APPROVAL"): JobStates.APPROVAL_REQUIRED,
        (JobStates.HARVESTING, "HARVEST_INTERVENTION"): JobStates.INTERVENTION_REQUIRED,
        (JobStates.HARVESTING, "CANCEL"): JobStates.CANCELED,

        # Human intervention state transitions
        (JobStates.INTERVENTION_REQUIRED, "RESUBMIT"): JobStates.PENDING,
        (JobStates.INTERVENTION_REQUIRED, "SUSPEND"): JobStates.SUSPENDED,
        (JobStates.INTERVENTION_REQUIRED, "CANCEL"): JobStates.CANCELED,

        # Approval state transitions
        (JobStates.APPROVAL_REQUIRED, "APPROVE"): JobStates.SUCCESS,
        (JobStates.APPROVAL_REQUIRED, "REJECT"): JobStates.PENDING,
        (JobStates.APPROVAL_REQUIRED, "SUSPEND"): JobStates.SUSPENDED,
        (JobStates.APPROVAL_REQUIRED, "CANCEL"): JobStates.CANCELED,

        # SUSPENDED state transitions
        (JobStates.SUSPENDED, "RESUME"): JobStates.PENDING,
        (JobStates.SUSPENDED, "CANCEL"): JobStates.CANCELED,

        # Legacy transitions for backward compatibility
        # Map old RUNNING state to new states
        (JobStates.RUNNING, "COMPLETED"): JobStates.HARVESTING,
        (JobStates.RUNNING, "STUCK"): JobStates.INTERVENTION_REQUIRED,
        (JobStates.RUNNING, "SUSPEND"): JobStates.SUSPENDED,
        (JobStates.RUNNING, "CANCEL"): JobStates.CANCELED,

        # Legacy REVIEW_REQUIRED/REVIEWING transitions
        (JobStates.REVIEW_REQUIRED, "COMPLETED"): JobStates.APPROVAL_REQUIRED,
        (JobStates.REVIEW_REQUIRED, "STUCK"): JobStates.INTERVENTION_REQUIRED,
        (JobStates.REVIEWING, "COMPLETED"): JobStates.APPROVAL_REQUIRED,
        (JobStates.REVIEWING, "STUCK"): JobStates.INTERVENTION_REQUIRED,
    }

    key = (current_status, response_action)
    if key in transitions:
        return transitions[key]

    # Default fallback for unrecognized transitions
    if response_action == "STUCK":
        return JobStates.INTERVENTION_REQUIRED
    elif response_action == "SUSPEND":
        # Allow suspension from any non-terminal state
        if current_status not in JobStates.TERMINAL_STATES and current_status != JobStates.SUSPENDED:
            return JobStates.SUSPENDED
        else:
            raise JobStateError(f"Cannot suspend job in state: {current_status}")
    elif response_action == "CANCEL":
        # Allow cancellation from any non-terminal state
        if current_status not in JobStates.TERMINAL_STATES:
            return JobStates.CANCELED
        else:
            raise JobStateError(f"Cannot cancel job in state: {current_status}")
    else:
        raise JobStateError(f"Invalid state transition: {current_status} + {response_action}")


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
    if current_status in (JobStates.EXECUTING, JobStates.RUNNING) and new_status is None:
        # Executing jobs that encounter transient errors stay executing for retry
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
    # Transient states can transition to error states
    executing_states = {JobStates.PROVISIONING, JobStates.EXECUTING, JobStates.RECOVERING, JobStates.HARVESTING}
    # Include legacy states for backward compatibility
    executing_states.update({JobStates.RUNNING, JobStates.REVIEWING})
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


def validate_state_transition(current_status: str, target_status: str, action: str = "") -> bool:
    """
    Comprehensive validation of state transitions according to the state machine.

    Args:
        current_status: Current job status.
        target_status: Target status for transition.
        action: Action being performed (for logging/validation).

    Returns:
        True if transition is valid, False otherwise.

    Raises:
        JobStateError: If transition violates state machine rules.
    """
    # Terminal states - cannot transition out of these
    if current_status in JobStates.TERMINAL_STATES:
        if target_status != current_status:
            raise JobStateError(f"Cannot transition out of terminal state '{current_status}'")

    # SUSPENDED state validation
    if current_status == JobStates.SUSPENDED:
        valid_resume_targets = {JobStates.PENDING, JobStates.CANCELED}
        if target_status not in valid_resume_targets:
            raise JobStateError(f"SUSPENDED jobs can only resume to {valid_resume_targets}, not '{target_status}'")

    # DRAFT state validation - very restrictive
    if current_status == JobStates.DRAFT:
        valid_draft_targets = {JobStates.PENDING, JobStates.SUSPENDED, JobStates.CANCELED}
        if target_status not in valid_draft_targets:
            raise JobStateError(f"DRAFT jobs can only transition to {valid_draft_targets}, not '{target_status}'")

    # PENDING state validation
    if current_status == JobStates.PENDING:
        valid_pending_targets = {JobStates.PROVISIONING, JobStates.SUSPENDED, JobStates.CANCELED}
        # Include legacy RUNNING for backward compatibility
        valid_pending_targets.add(JobStates.RUNNING)
        if target_status not in valid_pending_targets:
            raise JobStateError(f"PENDING jobs can only transition to {valid_pending_targets}, not '{target_status}'")

    # PROVISIONING state validation
    if current_status == JobStates.PROVISIONING:
        valid_provisioning_targets = {JobStates.EXECUTING, JobStates.INTERVENTION_REQUIRED, JobStates.CANCELED}
        if target_status not in valid_provisioning_targets:
            raise JobStateError(f"PROVISIONING jobs can only transition to {valid_provisioning_targets}, not '{target_status}'")

    # EXECUTING state validation
    if current_status == JobStates.EXECUTING:
        valid_executing_targets = {JobStates.HARVESTING, JobStates.RECOVERING, JobStates.CANCELED}
        if target_status not in valid_executing_targets:
            raise JobStateError(f"EXECUTING jobs can only transition to {valid_executing_targets}, not '{target_status}'")

    # RECOVERING state validation
    if current_status == JobStates.RECOVERING:
        valid_recovering_targets = {JobStates.EXECUTING}
        if target_status not in valid_recovering_targets:
            raise JobStateError(f"RECOVERING jobs can only transition to {valid_recovering_targets}, not '{target_status}'")

    # HARVESTING state validation
    if current_status == JobStates.HARVESTING:
        valid_harvesting_targets = {JobStates.SUCCESS, JobStates.APPROVAL_REQUIRED, JobStates.INTERVENTION_REQUIRED, JobStates.CANCELED}
        if target_status not in valid_harvesting_targets:
            raise JobStateError(f"HARVESTING jobs can only transition to {valid_harvesting_targets}, not '{target_status}'")

    # Legacy RUNNING state validation (for backward compatibility)
    if current_status == JobStates.RUNNING:
        valid_running_targets = {JobStates.HARVESTING, JobStates.SUSPENDED, JobStates.CANCELED, JobStates.INTERVENTION_REQUIRED}
        # Include legacy targets
        valid_running_targets.update({JobStates.REVIEW_REQUIRED})
        if target_status not in valid_running_targets:
            raise JobStateError(f"RUNNING jobs can only transition to {valid_running_targets}, not '{target_status}'")

    # Legacy REVIEW_REQUIRED state validation (for backward compatibility)
    if current_status == JobStates.REVIEW_REQUIRED:
        valid_review_targets = {JobStates.APPROVAL_REQUIRED, JobStates.INTERVENTION_REQUIRED, JobStates.SUSPENDED, JobStates.CANCELED}
        valid_review_targets.add(JobStates.REVIEWING)  # Legacy
        if target_status not in valid_review_targets:
            raise JobStateError(f"REVIEW_REQUIRED jobs can only transition to {valid_review_targets}, not '{target_status}'")

    # Legacy REVIEWING state validation (for backward compatibility)
    if current_status == JobStates.REVIEWING:
        valid_reviewing_targets = {JobStates.APPROVAL_REQUIRED, JobStates.INTERVENTION_REQUIRED, JobStates.SUSPENDED, JobStates.CANCELED}
        if target_status not in valid_reviewing_targets:
            raise JobStateError(f"REVIEWING jobs can only transition to {valid_reviewing_targets}, not '{target_status}'")

    # APPROVAL_REQUIRED state validation
    if current_status == JobStates.APPROVAL_REQUIRED:
        valid_approval_targets = {JobStates.SUCCESS, JobStates.PENDING, JobStates.SUSPENDED, JobStates.CANCELED}
        if target_status not in valid_approval_targets:
            raise JobStateError(f"APPROVAL_REQUIRED jobs can only transition to {valid_approval_targets}, not '{target_status}'")

    # INTERVENTION_REQUIRED state validation
    if current_status == JobStates.INTERVENTION_REQUIRED:
        valid_intervention_targets = {JobStates.PENDING, JobStates.SUSPENDED, JobStates.CANCELED}
        if target_status not in valid_intervention_targets:
            raise JobStateError(f"INTERVENTION_REQUIRED jobs can only transition to {valid_intervention_targets}, not '{target_status}'")

    # ATTACHED/DETACHED validation for attach/recover sessions (legacy)
    if current_status == JobStates.ATTACHED:
        valid_attached_targets = {JobStates.SUSPENDED, JobStates.DETACHED}
        if target_status not in valid_attached_targets:
            raise JobStateError(f"ATTACHED sessions can only transition to {valid_attached_targets}, not '{target_status}'")

    if current_status == JobStates.DETACHED:
        # DETACHED is a terminal state for attach sessions
        if target_status != JobStates.DETACHED:
            raise JobStateError(f"DETACHED sessions cannot transition to other states")

    return True


def validate_error_transition(current_status: str, target_status: str) -> bool:
    """
    Validates that an error-related state transition is allowed.

    Args:
        current_status: Current job status.
        target_status: Target status for transition.

    Returns:
        True if transition is valid, False otherwise.
    """
    # Error/human-intervention states can transition back to execution states for recovery
    error_states = {JobStates.INTERVENTION_REQUIRED, JobStates.CANCELED, JobStates.APPROVAL_REQUIRED}
    execution_states = {JobStates.PENDING, JobStates.PROVISIONING, JobStates.EXECUTING, JobStates.APPROVAL_REQUIRED}
    # Include legacy states for backward compatibility
    execution_states.update({JobStates.RUNNING, JobStates.REVIEW_REQUIRED, JobStates.REVIEWING})

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