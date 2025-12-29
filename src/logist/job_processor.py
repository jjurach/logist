import json
import os
from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError

from logist.job_state import JobStateError


class JobProcessorError(Exception):
    """Custom exception for job processing related errors."""
    pass


def validate_llm_response(response: Dict[str, Any]) -> None:
    """
    Validates an LLM response against the expected schema.

    Args:
        response: The LLM response dictionary.

    Raises:
        JobProcessorError: If validation fails.
    """
    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["COMPLETED", "STUCK", "RETRY"]},
            "evidence_files": {"type": "array", "items": {"type": "string"}},
            "summary_for_supervisor": {"type": "string", "maxLength": 1000},
            "job_manifest_url": {"type": "string", "format": "uri"}
        },
        "required": ["action", "evidence_files", "summary_for_supervisor"],
        "additionalProperties": False
    }

    try:
        validate(instance=response, schema=schema)
    except ValidationError as e:
        raise JobProcessorError(f"LLM response validation failed: {e.message}")
    except Exception as e:
        raise JobProcessorError(f"Unexpected validation error: {str(e)}")


def parse_llm_response(llm_output: str) -> Dict[str, Any]:
    """
    Parses raw LLM output to extract the JSON response.

    Args:
        llm_output: Raw output from the LLM execution.

    Returns:
        Parsed response dictionary.

    Raises:
        JobProcessorError: If parsing fails.
    """
    import re

    # Try to extract JSON from the LLM output
    # Look for JSON blocks in the output (common pattern LLMs use)
    json_pattern = r'```json\s*(.*?)\s*```'
    json_match = re.search(json_pattern, llm_output, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON without code blocks
        json_start = llm_output.find('{')
        json_end = llm_output.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = llm_output[json_start:json_end]
        else:
            raise JobProcessorError("Could not find valid JSON in LLM output")

    try:
        response = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise JobProcessorError(f"Failed to parse JSON from LLM output: {e}")

    # Validate the parsed response
    validate_llm_response(response)

    return response


def execute_llm_with_cline(
    context: Dict[str, Any],
    model: str = "grok-code-fast-1",
    timeout: int = 300,
    workspace_dir: str = None,
    instruction_files: Optional[List[str]] = None,
    file_arguments: Optional[List[str]] = None,
    dry_run: bool = False
) -> tuple[Dict[str, Any], float]:
    """
    Executes an LLM call using the CLINE interface.

    Args:
        context: Job context dictionary assembled by job_context.py
        model: Model to use for execution
        timeout: Timeout in seconds
        workspace_dir: Directory to execute from (workspace directory)

    Returns:
        Tuple of (processed_response, execution_time_seconds)

    Raises:
        JobProcessorError: If execution fails.
    """
    import subprocess
    import time
    import tempfile
    from datetime import datetime

    start_time = time.time()

    try:

        # Format the context as a human-readable prompt
        from logist.job_context import format_llm_prompt
        prompt = format_llm_prompt(context, "human-readable")

        # Create a temporary file with the prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        # Prepare CLINE command
        cmd = [
            "cline", "--yolo", "--oneshot",
            "--file", prompt_file
        ]

        # Add file arguments (attachments, discovered files, etc.)
        if file_arguments:
            for file_path in file_arguments:
                cmd.extend(["--file", file_path])

        if instruction_files:
            for f_path in instruction_files:
                cmd.extend(["--file", f_path])

        # Change to workspace directory for execution
        cwd_dir = workspace_dir if workspace_dir else os.getcwd()

        if dry_run:
            return {
                "action": "COMPLETED",
                "evidence_files": [],
                "summary_for_supervisor": "Dry run execution",
                "metrics": {},
            }, 0.0

        # Execute CLINE
        process = subprocess.run(
            cmd,
            cwd=cwd_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False # Prefer shell=False for security and predictability
        )

        execution_time = time.time() - start_time

        # Enhanced error handling with classification
        if process.returncode != 0:
            # Import error classification here to avoid circular imports
            from logist.error_classification import classify_error

            # Classify the subprocess error
            error_classification = classify_error(
                JobProcessorError(f"CLINE execution failed with code {process.returncode}"),
                {
                    "error_type": "subprocess",
                    "returncode": process.returncode,
                    "stderr": process.stderr,
                    "stdout": process.stdout,
                    "operation": "LLM execution with CLINE"
                }
            )

            # Create enhanced error message
            full_output = process.stdout + process.stderr
            enhanced_error_msg = (
                f"CLINE execution failed (Error ID: {error_classification.correlation_id}):\n"
                f"  Classification: {error_classification.category.value} - {error_classification.severity.value}\n"
                f"  User Message: {error_classification.user_message}\n"
                f"  Suggested Action: {error_classification.suggested_action}\n"
                f"  Details: {full_output}"
            )

            # Add classification to the exception for upstream handling
            error = JobProcessorError(enhanced_error_msg)
            error.classification = error_classification
            raise error

        full_cline_output = process.stdout + process.stderr

        # Extract task ID from CLINE output
        task_id_match = re.search(r'Task created: (.*?)\n', full_cline_output)
        if not task_id_match:
            # Fallback for when CLINE output changes or task ID is not explicitly printed.
            # This is a heuristic and might need adjustment if CLINE's output format is inconsistent.
            # A more robust solution might involve 'cline task list' and checking timestamps.
            task_id_match = re.search(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', full_cline_output)
            if not task_id_match:
                 raise JobProcessorError("Could not extract CLINE task ID from output.")

        task_id = task_id_match.group(1).strip() if task_id_match.group(1).strip() else task_id_match.group(0).strip()
        
        # Determine the CLINE task directory
        # Assuming CLINE stores tasks in ~/.cline/data/tasks/
        cline_data_dir = os.path.join(os.path.expanduser("~"), ".cline", "data")
        task_dir = os.path.join(cline_data_dir, "tasks", task_id)

        if not os.path.isdir(task_dir):
            raise JobProcessorError(f"CLINE task directory not found: {task_dir}")

        api_conversation_history_path = os.path.join(task_dir, "api_conversation_history.json")
        metadata_path = os.path.join(task_dir, "metadata.json")

        if not os.path.exists(api_conversation_history_path):
            raise JobProcessorError(f"api_conversation_history.json not found in {task_dir}")
        if not os.path.exists(metadata_path):
            raise JobProcessorError(f"metadata.json not found in {task_dir}")

        # Extract JSON response from api_conversation_history.json
        with open(api_conversation_history_path, 'r') as f:
            conversation_history = json.load(f)

        llm_response_json = None
        # Iterate in reverse chronological order
        for message in reversed(conversation_history):
            if "content" in message:
                try:
                    # Use existing parse_llm_response to extract and validate JSON from content
                    # Note: parse_llm_response expects a string, so we pass message["content"]
                    parsed_candidate = parse_llm_response(message["content"])
                    llm_response_json = parsed_candidate
                    break # Found the first valid JSON
                except JobProcessorError:
                    # Continue searching if this message doesn't contain valid JSON
                    continue

        if llm_response_json is None:
            raise JobProcessorError("No valid LLM response JSON found in conversation history.")

        # Extract metrics from metadata.json
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        metrics = {
            "token_input": metadata.get("metrics", {}).get("token_counts", {}).get("input", 0),
            "token_output": metadata.get("metrics", {}).get("token_counts", {}).get("output", 0),
            "token_cache_read": metadata.get("metrics", {}).get("token_counts", {}).get("cacheRead", 0),
            "token_cache_write": metadata.get("metrics", {}).get("token_counts", {}).get("cacheWrite", 0),
            "cache_hit": metadata.get("metrics", {}).get("cache_hit", False),
            "cost_usd": metadata.get("metrics", {}).get("cost_usd", 0.0),
            "duration_seconds": metadata.get("duration_seconds", execution_time),
            "ttft_seconds": metadata.get("metrics", {}).get("ttft_seconds"),
            "throughput_tokens_per_second": metadata.get("metrics", {}).get("throughput_tokens_per_second"),
        }

        # Combine LLM response with metrics
        processed_response = {
            **llm_response_json, # Unpack the action, evidence_files, summary etc.
            "processed_at": datetime.now().isoformat(),
            "metrics": metrics,
            "raw_cline_output": full_cline_output, # Keep full output for audit/debug
            "cline_task_id": task_id
        }

        return processed_response, execution_time

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        raise JobProcessorError(f"CLINE execution timed out after {execution_time:.1f} seconds")
    except subprocess.CalledProcessError as e:
        execution_time = time.time() - start_time
        raise JobProcessorError(f"CLINE subprocess error: {e}")
    except Exception as e:
        execution_time = time.time() - start_time
        raise JobProcessorError(f"LLM execution error: {str(e)}")
    finally:
        # Clean up temporary file
        try:
            if 'prompt_file' in locals():
                os.unlink(prompt_file)
        except:
            pass


def validate_evidence_files(evidence_files: List[str], workspace_dir: str) -> List[str]:
    """
    Validates that evidence files exist and are accessible.

    Args:
        evidence_files: List of file paths from LLM response
        workspace_dir: Workspace directory for path resolution

    Returns:
        List of validated file paths (relative to workspace)

    Raises:
        JobProcessorError: If files are invalid or inaccessible.
    """
    validated_files = []

    for file_path in evidence_files:
        # Make path relative to workspace and resolve it
        full_path = os.path.join(workspace_dir, file_path.lstrip('/'))

        # Check if file exists
        if not os.path.exists(full_path):
            # Try without stripping leading slash if the original had it
            if file_path.startswith('/') and os.path.exists(os.path.join(workspace_dir, file_path[1:])):
                full_path = os.path.join(workspace_dir, file_path[1:])

        if not os.path.exists(full_path):
            raise JobProcessorError(f"Evidence file not found: {file_path}")

        if not os.path.isfile(full_path):
            raise JobProcessorError(f"Evidence path is not a file: {file_path}")

        # Convert to relative path for storage
        rel_path = os.path.relpath(full_path, workspace_dir)
        validated_files.append(rel_path)

    return validated_files


def process_simulated_response(
    job_dir: str,
    job_id: str,
    simulated_response: Dict[str, Any],
    active_role: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Processes a simulated LLM response through the post-LLM processing pipeline.

    Args:
        job_dir: The absolute path to the job's directory.
        job_id: The ID of the job.
        simulated_response: The simulated LLM response dictionary (already validated).
        active_role: The active agent role for this processing.
        dry_run: If True, parse and report what would happen without making changes.

    Returns:
        Dictionary with processing results and status.

    Raises:
        JobProcessorError: If processing fails.
    """
    import click
    from datetime import datetime
    from logist.job_state import load_job_manifest, transition_state, update_job_manifest
    # Note: Git commit for simulated responses is a placeholder
    # In production, workspace operations go through the runner interface
    from logist.job_history import record_interaction

    results = {
        "success": False,
        "dry_run": dry_run,
        "simulated_response": simulated_response,
        "would_transition_to": None,
        "would_commit_files": [],
        "would_update_manifest": False,
        "would_record_interaction": False,
        "error": None
    }

    try:
        # Load current manifest to get current status
        manifest = load_job_manifest(job_dir)
        current_status = manifest.get("status", "PENDING")

        # Determine response action and other fields
        response_action = simulated_response.get("action")
        summary_for_supervisor = simulated_response.get("summary_for_supervisor", "")
        evidence_files = simulated_response.get("evidence_files", [])

        # Determine new status via state machine
        new_status = transition_state(current_status, active_role, response_action)
        results["would_transition_to"] = new_status

        workspace_path = os.path.join(job_dir, "workspace")

        # Validate evidence files (don't fail if they don't exist for simulated responses)
        validated_evidence = []
        if evidence_files:
            try:
                validated_evidence = validate_evidence_files(evidence_files, workspace_path)
                click.echo(f"   📁 Validated evidence files: {', '.join(validated_evidence)}")
            except JobProcessorError as e:
                if not dry_run:
                    click.secho(f"⚠️  Evidence file validation warning: {e}", fg="yellow")
                # Continue processing even if evidence files aren't found

        results["would_commit_files"] = evidence_files
        results["would_update_manifest"] = True
        results["would_record_interaction"] = True

        if dry_run:
            click.secho("   → Defensive setting detected: --dry-run", fg="yellow")
            click.echo(f"   → Would: Transition job status from '{current_status}' to '{new_status}'")
            click.echo(f"   → Would: Update job manifest with new status and history")
            if evidence_files:
                click.echo(f"   → Would: Commit evidence files to Git: {', '.join(evidence_files)}")
            else:
                click.echo("   → Would: No evidence files to commit")
            click.echo("   → Would: Record simulated interaction in jobHistory.json")
            click.secho("   ✅ Dry run completed - no changes made", fg="green")
            results["success"] = True
            return results

        # Not dry-run: make actual changes

        # Update job manifest (no cost/time increments for simulated responses)
        history_entry = {
            "role": active_role,
            "action": response_action,
            "summary": summary_for_supervisor,
            "evidence_files": evidence_files,
            "cline_task_id": None,  # No actual task for simulated responses
            "event": "POSTSTEP_SIMULATION"  # Special marker for simulated poststep
        }

        update_job_manifest(
            job_dir=job_dir,
            new_status=new_status,
            history_entry=history_entry
            # Note: No cost_increment or time_increment for simulated responses
        )
        click.secho(f"   🔄 Job status updated to: {new_status}", fg="blue")

        # Placeholder for Git commit of evidence files
        # In production, this would go through the runner's harvest() method
        if evidence_files:
            click.secho(f"   📝 [PLACEHOLDER] Would commit {len(evidence_files)} evidence files", fg="cyan")
            click.secho(f"   📁 Evidence: {', '.join(evidence_files[:3])}{'...' if len(evidence_files) > 3 else ''}", fg="cyan")
        else:
            click.echo("   📁 No evidence files to commit.")

        # Record the simulated interaction in job history
        # Create mock request/response for recording purposes
        mock_request = {
            "simulation": True,
            "description": "Manually provided simulated LLM response for debugging/testing"
        }

        mock_response = {
            **simulated_response,
            "processed_at": datetime.now().isoformat(),
            "metrics": {"cost_usd": 0.0, "duration_seconds": 0.0},  # No actual metrics for simulated
            "cline_task_id": None,
            "raw_cline_output": "Simulated response - no actual LLM call made"
        }

        record_interaction(
            job_dir=job_dir,
            request=mock_request,
            response=mock_response,
            execution_time_seconds=0.0,  # No actual execution time
            model_used="simulated",
            cost_incurred=0.0,  # No cost for simulated responses
            is_simulated=True
        )

        click.secho("   📚 Simulated interaction recorded in jobHistory.json", fg="cyan")
        click.secho(f"   ✅ Post-processed simulated response for job '{job_id}'", fg="green")

        results["success"] = True
        return results

    except Exception as e:
        error_msg = f"Error processing simulated response: {str(e)}"
        click.secho(f"❌ {error_msg}", fg="red")
        results["error"] = error_msg
        results["success"] = False
        return results


def handle_execution_error(job_dir: str, job_id: str, error: Exception, raw_output: str = None) -> None:
    """
    Handles an execution error with sophisticated classification and recovery logic.

    Uses error classification system to determine appropriate job status changes,
    user messaging, and recovery strategies.

    Args:
        job_dir: The absolute path to the job's directory.
        job_id: The ID of the job.
        error: The exception object that occurred.
        raw_output: Optional raw output from the failing process for debugging.
    """
    from logist.job_state import update_job_manifest, transition_state_on_error, load_job_manifest
    from logist.error_classification import classify_error, should_retry_error, get_retry_delay
    from datetime import datetime
    import time
    import click # For logging to console

    # Load current job state for context
    try:
        manifest = load_job_manifest(job_dir)
        current_status = manifest.get("status", "UNKNOWN")
    except Exception:
        current_status = "UNKNOWN"

    # Classify the error using the new system
    error_context = {
        "error_type": "subprocess" if hasattr(error, 'classification') and error.classification else "unknown",
        "operation": f"Job '{job_id}' execution",
        "returncode": getattr(error, 'returncode', None),
        "stderr": getattr(error, 'stderr', ''),
        "stdout": getattr(error, 'stdout', ''),
    }

    # If error already has classification from subprocess handling, use it
    if hasattr(error, 'classification'):
        classification = error.classification
    else:
        # Classify based on exception and context
        try:
            classification = classify_error(error, error_context)
        except Exception as classification_error:
            # Fallback classification if classifier fails
            from logist.error_classification import ErrorClassification, ErrorSeverity, ErrorCategory
            import uuid
            classification = ErrorClassification(
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.EXECUTION,
                description="Error classification failed - using fallback",
                user_message="An execution error occurred.",
                can_retry=True,
                max_retries=1,
                intervention_required=True,
                suggested_action="Review error details and retry",
                correlation_id=f"error_fallback_{uuid.uuid4().hex[:8]}"
            )

    # Determine new job status based on classification
    new_status = transition_state_on_error(current_status, classification)

    # Enhanced error messaging
    error_message = str(error) if not hasattr(error, 'classification') else error.args[0] if error.args else str(error)
    click.secho(f"❌ Error during job '{job_id}' execution (ID: {classification.correlation_id})", fg="red")
    click.echo(f"   📊 Classification: {classification.category.value} - {classification.severity.value}")
    click.echo(f"   💬 {classification.user_message}")
    click.echo(f"   💡 {classification.suggested_action}")

    if raw_output and raw_output != error_message:
        click.echo(f"   📄 Raw output: {raw_output[:200]}{'...' if len(raw_output) > 200 else ''}")

    # Create comprehensive history entry
    history_entry = {
        "event": "EXECUTION_ERROR",
        "error_classification": classification.to_dict(),
        "description": f"Execution failed: {classification.description}",
        "error_message": error_message,
        "details": f"Error Type: {type(error).__name__}",
        "raw_output": raw_output if raw_output else "No raw output available.",
        "can_retry": classification.can_retry,
        "max_retries": classification.max_retries,
        "intervention_required": classification.intervention_required
    }

    # Implement retry logic for transient errors
    retry_attempted = False
    if classification.severity.value == "transient" and classification.can_retry:
        # This would be handled by the caller for actual retries
        # For now, just record that retry is possible
        history_entry["retry_recommended"] = True
        history_entry["retry_delay_seconds"] = get_retry_delay(classification, 0)

    try:
        # Update job manifest with appropriate status
        if new_status:
            updated_manifest = update_job_manifest(
                job_dir=job_dir,
                new_status=new_status,
                history_entry=history_entry
            )
            click.secho(f"⚠️ Job '{job_id}' status updated to {new_status}.", fg="yellow")
        else:
            # No status change - just record the error in history
            updated_manifest = update_job_manifest(
                job_dir=job_dir,
                history_entry=history_entry
            )
            click.echo(f"📝 Error recorded in job history (status unchanged).")

        # Provide next steps based on classification
        if classification.severity.value == "fatal":
            click.secho(f"🚫 Fatal error - job '{job_id}' has been canceled.", fg="red")
            click.echo("   💡 Create a new job or contact support for fatal errors.")

        elif classification.severity.value == "recoverable":
            click.echo("   🔄 Recovery options:")
            click.echo("   • Fix the issue described above")
            click.echo("   • Run 'logist job step' to retry")
            click.echo("   • Use 'logist job rerun' for fresh start (clears history)")

        elif classification.severity.value == "transient":
            click.echo("   🔄 This appears to be a temporary issue.")
            click.echo("   • Wait a moment and run 'logist job step' to retry")
            click.echo("   • Check network/API status if issues persist")

    except Exception as manifest_error:
        click.secho(f"Critical error: Failed to update manifest for job '{job_id}' after an execution error: {manifest_error}", fg="red")
        click.secho(f"Original error for job '{job_id}': {error_message}", fg="red")
        # Don't raise - we want to let the caller know about the original error, not manifest update failure

    return  # Allow caller to decide whether to continue or raise the original error


def save_latest_outcome(job_dir: str, llm_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves the latest LLM response to latest-outcome.json in the job directory.

    Args:
        job_dir: Job directory path
        llm_response: The processed LLM response dictionary

    Returns:
        Dict with save operation results
    """
    result = {
        "success": False,
        "outcome_file": os.path.join(job_dir, "latest-outcome.json"),
        "error": None
    }

    try:
        # Extract key fields from LLM response for outcome
        outcome_data = {
            "action": llm_response.get("action"),
            "summary_for_supervisor": llm_response.get("summary_for_supervisor", ""),
            "evidence_files": llm_response.get("evidence_files", []),
            "timestamp": llm_response.get("processed_at"),
            "cline_task_id": llm_response.get("cline_task_id"),
            "metrics": llm_response.get("metrics", {})
        }

        # Save to latest-outcome.json
        with open(result["outcome_file"], 'w') as f:
            json.dump(outcome_data, f, indent=2)

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def load_previous_outcome(job_dir: str) -> Optional[Dict[str, Any]]:
    """
    Loads the previous outcome from latest-outcome.json if it exists.

    Args:
        job_dir: Job directory path

    Returns:
        Previous outcome dictionary or None if not found
    """
    outcome_file = os.path.join(job_dir, "latest-outcome.json")

    if not os.path.exists(outcome_file):
        return None

    try:
        with open(outcome_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def prepare_outcome_for_attachments(job_dir: str, workspace_dir: str) -> Dict[str, Any]:
    """
    Prepares previous outcome data for attachment to next step.

    Copies latest-outcome.json to workspace/attachments/ and returns it as an attachment.

    Args:
        job_dir: Job directory path
        workspace_dir: Workspace directory path

    Returns:
        Dict with outcome preparation results
    """
    result = {
        "success": True,
        "attachments_added": [],
        "error": None
    }

    try:
        previous_outcome = load_previous_outcome(job_dir)
        if previous_outcome is None:
            return result  # No previous outcome, that's fine

        # Copy to workspace attachments
        outcome_file = os.path.join(job_dir, "latest-outcome.json")
        workspace_attachments_dir = os.path.join(workspace_dir, "attachments")
        workspace_outcome_file = os.path.join(workspace_attachments_dir, "latest-outcome.json")

        # Ensure attachments directory exists
        os.makedirs(workspace_attachments_dir, exist_ok=True)

        # Copy the file
        shutil.copy2(outcome_file, workspace_outcome_file)

        result["attachments_added"].append(workspace_outcome_file)

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


def enhance_context_with_previous_outcome(context: Dict[str, Any], job_dir: str) -> Dict[str, Any]:
    """
    Enhances job context with previous outcome information for role-specific guidance.

    Args:
        context: Job context dictionary
        job_dir: Job directory path

    Returns:
        Enhanced context dictionary
    """
    previous_outcome = load_previous_outcome(job_dir)
    if previous_outcome is None:
        return context  # No enhancement needed

    # Add previous outcome to context
    context["previous_outcome"] = previous_outcome

    # Add role-specific instructions based on previous outcome
    active_role = context.get("role_name", "").lower()

    if active_role == "worker":
        context["outcome_instructions"] = (
            "You have access to the previous step's outcome in previous_outcome. "
            "Use this to understand what was accomplished in the prior step and "
            "summarize your work accordingly, noting any struggles or additional "
            "information that helped you succeed."
        )
    elif active_role == "supervisor":
        context["outcome_instructions"] = (
            "You have access to the previous step's outcome in previous_outcome. "
            "Review this to understand what the worker accomplished, assess it "
            "against the overall objectives, and provide guidance regarding any "
            "concerns, criticisms, additional research needed, or approval to proceed."
        )

    return context