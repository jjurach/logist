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
    instruction_files: Optional[List[str]] = None
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
        # TEMPORARY: Simulate an error for testing purposes
        # raise JobProcessorError("Simulated CLINE execution failure for testing.")
        # To test subprocess failure:
        # process = subprocess.run(
        #     ["false"], # command that always fails
        #     cwd=cwd_dir,
        #     capture_output=True,
        #     text=True,
        #     timeout=timeout,
        #     check=True # this makes it raise CalledProcessError
        # )
        # To test invalid JSON:
        # with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        #     f.write("THIS IS NOT JSON")
        #     prompt_file = f.name
        #     cmd = ["cat", prompt_file] # command that outputs non-json
        #     process = subprocess.run(cmd, capture_output=True, text=True)


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
        if instruction_files:
            for f_path in instruction_files:
                cmd.extend(["--file", f_path])

        # Change to workspace directory if specified
        cwd_dir = workspace_dir if workspace_dir else os.getcwd()

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

        if process.returncode != 0:
            full_output = process.stdout + process.stderr
            raise JobProcessorError(
                f"CLINE execution failed with code {process.returncode}:\n{full_output}"
            )

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
            "cost_usd": metadata.get("metrics", {}).get("cost_usd", 0.0),
            "duration_seconds": metadata.get("duration_seconds", execution_time)
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
    from logist.workspace_utils import perform_git_commit
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

        # Perform Git commit if there are evidence files
        if evidence_files:
            commit_result = perform_git_commit(
                job_dir=job_dir,
                evidence_files=evidence_files,
                summary=f"feat: simulated job step - {summary_for_supervisor}"
            )
            if commit_result["success"]:
                click.secho(f"   📝 Committed {len(commit_result.get('files_committed', []))} files", fg="green")
            else:
                click.secho(f"⚠️  Git commit failed: {commit_result.get('error', 'Unknown error')}", fg="yellow")
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
    Handles an execution error, updates job manifest to INTERVENTION_REQUIRED,
    and logs the error.

    Args:
        job_dir: The absolute path to the job's directory.
        job_id: The ID of the job.
        error: The exception object that occurred.
        raw_output: Optional raw output from the failing process for debugging.
    """
    from logist.job_state import update_job_manifest
    from datetime import datetime
    import click # For logging to console

    error_message = str(error)
    click.secho(f"❌ Error during job '{job_id}' execution: {error_message}", fg="red")

    history_entry = {
        "event": "ERROR",
        "description": f"Execution failed: {error_message}",
        "details": f"Error Type: {type(error).__name__}",
        "raw_output": raw_output if raw_output else "No raw output available."
    }

    try:
        updated_manifest = update_job_manifest(
            job_dir=job_dir,
            new_status="INTERVENTION_REQUIRED",
            history_entry=history_entry
        )
        click.secho(f"⚠️ Job '{job_id}' status updated to INTERVENTION_REQUIRED.", fg="yellow")
    except Exception as e:
        click.secho(f"Critical error: Failed to update manifest for job '{job_id}' after an execution error: {e}", fg="red")
        click.secho(f"Original error for job '{job_id}': {error_message}", fg="red")