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