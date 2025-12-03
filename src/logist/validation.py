"""
JSON Schema Validation Module for LLM Communication

Provides validation functions for LLM request and response objects
against the llm-chat-schema.json specification.
"""

import json
from pathlib import Path

try:
    import jsonschema
except ImportError:
    raise ImportError("jsonschema package is required. Install with: pip install jsonschema")


def _load_schema():
    """Load the JSON schema from the project schemas directory."""
    schema_path = Path(__file__).parent / "llm-chat-schema.json"
    with open(schema_path, 'r') as f:
        return json.load(f)


def validate_llm_request(data):
    """
    Validate an LLM request object against the schema.

    Args:
        data: Dictionary containing the request object

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    schema = _load_schema()
    try:
        jsonschema.validate(data, schema)
        if "request" not in data:
            raise jsonschema.ValidationError("Missing 'request' property")
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"Request validation failed: {str(e)}"


def validate_llm_response(data):
    """
    Validate an LLM response object against the schema.

    Args:
        data: Dictionary containing the response object

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    schema = _load_schema()
    try:
        jsonschema.validate(data, schema)
        if "response" not in data:
            raise jsonschema.ValidationError("Missing 'response' property")
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"Response validation failed: {str(e)}"


def validate_json_string(json_string):
    """
    Validate a JSON string by parsing and validating against schema.

    Args:
        json_string: String containing JSON

    Returns:
        tuple: (is_valid: bool, validated_data: dict or None, error_message: str or None)
    """
    try:
        data = json.loads(json_string)
        if "request" in data:
            valid, error = validate_llm_request(data)
        elif "response" in data:
            valid, error = validate_llm_response(data)
        else:
            return False, None, "JSON must contain 'request' or 'response' property"
        return valid, data if valid else None, error
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {str(e)}"