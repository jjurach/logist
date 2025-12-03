"""
Unit tests for JSON schema validation functions.
"""

import json
import pytest
from pathlib import Path
from logist.validation import validate_llm_request, validate_llm_response, validate_json_string


class TestLLMRequestValidation:
    """Test validation of LLM request objects."""

    def test_valid_request(self):
        """Test validation of a valid request object."""
        request_data = {
            "request": {
                "action": "step",
                "job_id": "test-job",
                "options": {"resume": False}
            }
        }
        valid, error = validate_llm_request(request_data)
        assert valid is True
        assert error is None

    def test_invalid_request_missing_action(self):
        """Test validation fails for missing required action."""
        request_data = {
            "request": {"job_id": "test-job"}
        }
        valid, error = validate_llm_request(request_data)
        assert valid is False
        assert "action" in error

    def test_invalid_request_no_request_property(self):
        """Test validation fails when no request property."""
        request_data = {"action": "step"}
        valid, error = validate_llm_request(request_data)
        assert valid is False
        assert "Request validation failed" in error


class TestLLMResponseValidation:
    """Test validation of LLM response objects."""

    def test_valid_response(self):
        """Test validation of a valid response object."""
        response_data = {
            "response": {
                "action": "COMPLETED",
                "evidence_files": ["file.txt"],
                "summary_for_supervisor": "Completed",
                "job_manifest_url": "https://example.com"
            }
        }
        valid, error = validate_llm_response(response_data)
        assert valid is True
        assert error is None

    def test_invalid_response_wrong_action(self):
        """Test validation fails for invalid action enum."""
        response_data = {
            "response": {
                "action": "FINISHED",  # not in enum
                "evidence_files": [],
                "summary_for_supervisor": "Done",
                "job_manifest_url": "https://example.com"
            }
        }
        valid, error = validate_llm_response(response_data)
        assert valid is False
        assert error is not None

    def test_invalid_response_missing_summary(self):
        """Test validation fails for missing summary."""
        response_data = {
            "response": {
                "action": "COMPLETED",
                "evidence_files": []
            }
        }
        valid, error = validate_llm_response(response_data)
        assert valid is False
        assert "summary_for_supervisor" in error

    def test_invalid_response_no_response_property(self):
        """Test validation fails when no response property."""
        response_data = {"action": "COMPLETED"}
        valid, error = validate_llm_response(response_data)
        assert valid is False
        assert "Response validation failed" in error


class TestJSONStringValidation:
    """Test validation of JSON strings."""

    def test_valid_json_string_request(self):
        """Test validation of JSON string containing valid request."""
        json_str = '{"request": {"action": "step", "job_id": "test"}}'
        valid, data, error = validate_json_string(json_str)
        assert valid is True
        assert data is not None
        assert error is None

    def test_valid_json_string_response(self):
        """Test validation of JSON string containing valid response."""
        json_str = '{"response": {"action": "COMPLETED", "evidence_files": [], "summary_for_supervisor": "Done", "job_manifest_url": "http://example.com"}}'
        valid, data, error = validate_json_string(json_str)
        assert valid is True
        assert data is not None
        assert error is None

    def test_invalid_json_string(self):
        """Test validation of malformed JSON string."""
        json_str = '{"request": {"job_id": "test"}'  # missing closing brace
        valid, data, error = validate_json_string(json_str)
        assert valid is False
        assert data is None
        assert "Invalid JSON" in error

    def test_invalid_schema_json_string(self):
        """Test validation of valid JSON that fails schema."""
        json_str = '{"request": {"job_id": "test"}}'
        valid, data, error = validate_json_string(json_str)
        assert valid is False
        assert data is None
        assert "validation failed" in error


class TestExampleFilesIntegration:
    """Test validation using the actual example files."""

    def test_valid_request_file(self):
        """Test validation of valid-llm-request.json"""
        path = Path(__file__).parent.parent / "doc" / "examples" / "llm-exchange" / "valid-llm-request.json"
        with open(path, 'r') as f:
            data = json.load(f)
        valid, error = validate_llm_request(data)
        assert valid is True

    def test_invalid_request_file(self):
        """Test validation of invalid-llm-request.json fails."""
        path = Path(__file__).parent.parent / "doc" / "examples" / "llm-exchange" / "invalid-llm-request.json"
        with open(path, 'r') as f:
            data = json.load(f)
        valid, error = validate_llm_request(data)
        assert valid is False

    def test_valid_response_file(self):
        """Test validation of valid-llm-response.json"""
        path = Path(__file__).parent.parent / "doc" / "examples" / "llm-exchange" / "valid-llm-response.json"
        with open(path, 'r') as f:
            data = json.load(f)
        valid, error = validate_llm_response(data)
        assert valid is True

    def test_invalid_response_file(self):
        """Test validation of invalid-llm-response.json fails."""
        path = Path(__file__).parent.parent / "doc" / "examples" / "llm-exchange" / "invalid-llm-response.json"
        with open(path, 'r') as f:
            data = json.load(f)
        valid, error = validate_llm_response(data)
        assert valid is False