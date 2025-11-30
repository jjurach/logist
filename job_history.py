import json
import os
from typing import Dict, Any
from datetime import datetime


class JobHistoryError(Exception):
    """Custom exception for job history related errors."""
    pass


def record_interaction(
    job_dir: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    execution_time_seconds: float,
    model_used: str,
    cost_incurred: float
) -> None:
    """
    Records a complete LLM interaction to the job history.

    Args:
        job_dir: The absolute path to the job's directory.
        request: The complete LLM request (prompt, files_context, metadata).
        response: The complete LLM response (action, evidence_files, summary_for_supervisor, raw_response).
        execution_time_seconds: Time taken for the LLM call.
        model_used: The LLM model that was used.
        cost_incurred: Cost incurred for this interaction.

    Raises:
        JobHistoryError: If there's an issue writing to the history file.
    """
    history_file = os.path.join(job_dir, "jobHistory.json")

    # Load existing history or create new
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except json.JSONDecodeError as e:
            raise JobHistoryError(f"Invalid JSON in job history file {history_file}: {e}")
    else:
        history = []

    # Create new interaction record
    interaction = {
        "timestamp": datetime.now().isoformat(),
        "model": model_used,
        "cost": cost_incurred,
        "execution_time_seconds": execution_time_seconds,
        "request": request,
        "response": response
    }

    # Append and save
    history.append(interaction)

    try:
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    except (OSError, TypeError) as e:
        raise JobHistoryError(f"Failed to write job history to {history_file}: {e}")


def get_job_history(job_dir: str, limit: int = None) -> list:
    """
    Retrieves the job's execution history.

    Args:
        job_dir: The absolute path to the job's directory.
        limit: Maximum number of interactions to return (most recent first).

    Returns:
        List of interaction records.

    Raises:
        JobHistoryError: If there's an issue reading the history file.
    """
    history_file = os.path.join(job_dir, "jobHistory.json")

    if not os.path.exists(history_file):
        return []

    try:
        with open(history_file, 'r') as f:
            history = json.load(f)

        if limit:
            return history[-limit:]
        return history

    except json.JSONDecodeError as e:
        raise JobHistoryError(f"Invalid JSON in job history file {history_file}: {e}")
    except OSError as e:
        raise JobHistoryError(f"Failed to read job history from {history_file}: {e}")


def get_history_stats(job_dir: str) -> Dict[str, Any]:
    """
    Returns statistics about the job's execution history.

    Args:
        job_dir: The absolute path to the job's directory.

    Returns:
        Dictionary with statistics about the job's history.
    """
    history = get_job_history(job_dir)

    if not history:
        return {
            "total_interactions": 0,
            "total_cost": 0.0,
            "total_time": 0.0,
            "models_used": [],
            "avg_cost_per_interaction": 0.0
        }

    total_cost = sum(interaction.get("cost", 0) for interaction in history)
    total_time = sum(interaction.get("execution_time_seconds", 0) for interaction in history)
    models_used = list(set(interaction.get("model", "unknown") for interaction in history))

    return {
        "total_interactions": len(history),
        "total_cost": total_cost,
        "total_time": total_time,
        "models_used": models_used,
        "avg_cost_per_interaction": total_cost / len(history) if history else 0.0
    }