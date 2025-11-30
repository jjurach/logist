import json
import os
from typing import Dict, Any, List
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


def process_llm_response(llm_output: str) -> Dict[str, Any]:
    """
    Processes raw LLM output and returns structured response data.

    Args:
        llm_output: Raw output from the LLM execution.

    Returns:
        Processed response dictionary with validation and metadata.

    Raises:
        JobProcessorError: If processing fails.
    """
    try:
        # Parse the LLM output
        response = parse_llm_response(llm_output)

        # Add processing metadata
        processed_response = {
            "action": response["action"],
            "evidence_files": response["evidence_files"],
            "summary_for_supervisor": response["summary_for_supervisor"],
            "job_manifest_url": response.get("job_manifest_url"),  # Optional
            "processed_at": None,  # Will be set by caller
            "raw_response": llm_output  # Keep the original for audit
        }

        return processed_response

    except JobProcessorError:
        raise
    except Exception as e:
        raise JobProcessorError(f"Unexpected processing error: {str(e)}")


def execute_llm_with_cline(
    context: Dict[str, Any],
    model: str = "grok-code-fast-1",
    timeout: int = 300,
    workspace_dir: str = None
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

        # Change to workspace directory if specified
        cwd_dir = workspace_dir if workspace_dir else os.getcwd()

        # Execute CLINE
        process = subprocess.run(
            cmd,
            cwd=cwd_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        execution_time = time.time() - start_time

        if process.returncode != 0:
            raise JobProcessorError(
                f"CLINE execution failed with code {process.returncode}: {process.stderr}"
            )

        # Process the LLM response
        llm_output = process.stdout
        processed_response = process_llm_response(llm_output)

        # Add timestamp of processing
        processed_response["processed_at"] = datetime.now().isoformat()

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