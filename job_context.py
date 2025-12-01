# logist/job_context.py
import json
from typing import Dict, Any, List, Optional

class JobContextError(Exception):
    """Custom exception for job context related errors."""
    pass

def assemble_job_context(
    job_dir: str,
    job_manifest: Dict[str, Any],
    role_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Assembles the comprehensive context for an LLM call per prompt requirements.

    Args:
        job_dir: The absolute path to the job's directory.
        job_manifest: The job manifest dictionary.
        role_config: The configuration for the active agent role.

    Returns:
        A dictionary containing the complete job context.
    """
    # Import workspace_utils for context assembly
    from . import workspace_utils

    workspace_path = os.path.join(job_dir, "workspace")

    # 1. Job Manifest information
    job_id = job_manifest.get("job_id", "unknown")
    current_phase_name = job_manifest.get("current_phase")

    # Get current phase specification
    current_phase_spec = None
    phases = job_manifest.get("phases", [])
    if current_phase_name and phases:
        current_phase_spec = next((p for p in phases if p.get("name") == current_phase_name), None)

    # 2. Role Configuration
    role_name = role_config.get("name", "unknown_role")
    role_instructions = role_config.get("instructions", "No specific instructions.")
    role_model = role_config.get("model", "grok-code-fast-1")

    # 3. Workspace Context
    workspace_files_summary = workspace_utils.get_workspace_files_summary(job_dir)
    workspace_git_status = workspace_utils.get_workspace_git_status(job_dir)

    # 4. Job History and Metrics
    history = job_manifest.get("history", [])
    metrics = job_manifest.get("metrics", {"cumulative_cost": 0, "cumulative_time_seconds": 0})

    # Summarize history (last 5 entries for context brevity)
    history_summary = "No history yet."
    if history:
        recent_history = history[-5:]
        history_entries = []
        for entry in recent_history:
            role = entry.get("role", "unknown")
            action = entry.get("action", "unknown")
            summary = entry.get("summary", "No summary")
            history_entries.append(f"- {role}: {action} - {summary}")
        history_summary = "\n".join(history_entries)

    # Summarize metrics
    metrics_summary = f"Total cost: ${metrics.get('cumulative_cost', 0):.4f}, Total time: {metrics.get('cumulative_time_seconds', 0):.2f}s"

    # 5. Assemble complete context
    context = {
        "job_id": job_id,
        "description": job_manifest.get("description", "A Logist job."),
        "status": job_manifest.get("status", "PENDING"),
        "current_phase": current_phase_name,
        "phase_specification": current_phase_spec,
        "role_name": role_name,
        "role_instructions": role_instructions,
        "role_model": role_model,
        "workspace_files": workspace_files_summary,
        "workspace_git_status": workspace_git_status,
        "job_history_summary": history_summary,
        "job_metrics_summary": metrics_summary,
        "all_phases": phases,
        "manifest_version": job_manifest  # Include full manifest for complete context
    }

    return context

def format_llm_prompt(context: Dict[str, Any], format_type: str = "human-readable") -> str:
    """
    Formats the job context into a prompt for the LLM.
    This is a placeholder implementation.

    Args:
        context: The job context dictionary.
        format_type: The desired output format (e.g., "human-readable", "json").

    Returns:
        A formatted string representing the LLM prompt.
    """
    if format_type == "human-readable":
        prompt = f"""
You are the {context.get('role_name')}.
Job ID: {context.get('job_id')}
Current Phase: {context.get('current_phase')}
Job Description: {context.get('job_description')}

Instructions for you:
{context.get('role_instructions')}

---
Additional Context (Placeholder):
{json.dumps(context.get('workspace_content', {}), indent=2)}
"""
        return prompt.strip()
    elif format_type == "json-files":
        # Placeholder for JSON file based prompt format
        return json.dumps(context, indent=2)
    else:
        raise ValueError(f"Unsupported format type: {format_type}")