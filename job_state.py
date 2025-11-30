import json
import os
from typing import Dict, Any, Tuple

class JobStateError(Exception):
    """Custom exception for job state related errors."""
    pass

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
        current_status: Current job status (e.g., "PENDING", "RUNNING").
        agent_role: The agent that executed ("Worker" or "Supervisor").
        response_action: LLM response action ("COMPLETED", "STUCK", "RETRY").

    Returns:
        The next status string.

    Raises:
        JobStateError: If an invalid state transition is attempted.
    """
    # State machine transitions based on 04_state_machine.md
    transitions = {
        ("PENDING", "Worker", "COMPLETED"): "RUNNING",  # Should actually go to REVIEW_REQUIRED after worker
        ("RUNNING", "Worker", "COMPLETED"): "REVIEW_REQUIRED",
        ("RUNNING", "Worker", "STUCK"): "INTERVENTION_REQUIRED",
        ("RUNNING", "Worker", "RETRY"): "PENDING",

        ("REVIEW_REQUIRED", "Supervisor", "COMPLETED"): "APPROVAL_REQUIRED",
        ("REVIEW_REQUIRED", "Supervisor", "STUCK"): "INTERVENTION_REQUIRED",
        ("REVIEW_REQUIRED", "Supervisor", "RETRY"): "REVIEW_REQUIRED",

        ("REVIEWING", "Supervisor", "COMPLETED"): "APPROVAL_REQUIRED",
        ("REVIEWING", "Supervisor", "STUCK"): "INTERVENTION_REQUIRED",
        ("REVIEWING", "Supervisor", "RETRY"): "REVIEW_REQUIRED",
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


def update_job_manifest(
    job_dir: str,
    new_status: str = None,
    new_phase: str = None,
    cost_increment: float = 0.0,
    time_increment: float = 0.0,
    history_entry: Dict[str, Any] = None
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

    Returns:
        Updated manifest dictionary.

    Raises:
        JobStateError: If update fails.
    """
    manifest = load_job_manifest(job_dir)
    modified = False

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

    return manifest