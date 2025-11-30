#!/usr/bin/env python3
"""
JSON Schema Validation Demo Script

Demonstrates validation of LLM request/response JSON files against the llm-chat-schema.
Loads schema from logist/schemas/llm-chat-schema.json and tests example files.
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema package not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


def load_schema():
    """Load the JSON schema from the project."""
    schema_path = Path(__file__).parent.parent / "schemas" / "llm-chat-schema.json"
    with open(schema_path, 'r') as f:
        return json.load(f)


def validate_request(data):
    """Validate a single LLM request object."""
    schema = load_schema()
    try:
        jsonschema.validate(data, schema)
        if "request" not in data:
            raise jsonschema.ValidationError("Missing 'request' property")
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e)


def validate_response(data):
    """Validate a single LLM response object."""
    schema = load_schema()
    try:
        jsonschema.validate(data, schema)
        if "response" not in data:
            raise jsonschema.ValidationError("Missing 'response' property")
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e)


def test_example_file(filename):
    """Test validation of a single example JSON file."""
    examples_dir = Path(__file__).parent.parent / "docs" / "examples" / "llm-exchange"
    filepath = examples_dir / filename

    if not filepath.exists():
        print(f"ERROR: Example file {filename} not found at {filepath}")
        return

    with open(filepath, 'r') as f:
        data = json.load(f)

    # Determine if this is a request or response
    if "request" in data:
        valid, error = validate_request(data)
    elif "response" in data:
        valid, error = validate_response(data)
    else:
        print(f"ERROR: {filename} contains neither 'request' nor 'response' property")
        return

    if valid:
        print(f"VALID: {filename}")
    else:
        print(f"INVALID: {filename} - {error}")


def main():
    """Run validation tests on all example files."""
    print("Loading schema from logist/schemas/llm-chat-schema.json...\n")

    example_files = [
        "valid-llm-request.json",
        "invalid-llm-request.json",
        "valid-llm-response.json",
        "invalid-llm-response.json"
    ]

    for filename in example_files:
        print(f"Testing {filename}...")
        test_example_file(filename)
        print()


if __name__ == "__main__":
    main()