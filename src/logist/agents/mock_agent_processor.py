#!/usr/bin/env python3
"""
Mock Agent Processor for LLM Response Simulation

This script simulates the LLM response generation process for mock agents,
providing realistic response patterns and failure modes for unit testing.
"""

import json
import sys
import os
import time
import random
from typing import Dict, Any


def simulate_processing_delay(delay_seconds: float) -> None:
    """Simulate processing delay."""
    if delay_seconds > 0:
        time.sleep(delay_seconds)


def simulate_failure_mode(failure_mode: str) -> Dict[str, Any]:
    """Simulate various failure modes that can occur during LLM processing."""
    failure_responses = {
        "api_error": {
            "error": "API rate limit exceeded",
            "code": 429,
            "message": "Too Many Requests - please try again later"
        },
        "context_full": {
            "error": "Context length exceeded",
            "code": 400,
            "message": "Token limit exceeded for this model"
        },
        "auth_error": {
            "error": "Authentication failed",
            "code": 401,
            "message": "Invalid API key provided"
        },
        "timeout": {
            "error": "Request timeout",
            "code": 408,
            "message": "Request timed out"
        },
        "invalid_response": {
            "error": "Invalid response format",
            "code": 500,
            "message": "LLM returned malformed response"
        },
        "network_error": {
            "error": "Network connection failed",
            "code": 503,
            "message": "Service temporarily unavailable"
        }
    }

    failure_data = failure_responses.get(failure_mode, {
        "error": "Unknown failure",
        "code": 500,
        "message": "Unexpected error occurred"
    })

    # Simulate some delay before failure
    time.sleep(random.uniform(0.1, 1.0))

    # Output failure to stderr and exit with error code
    print(json.dumps(failure_data), file=sys.stderr)
    sys.exit(failure_data["code"])


def generate_mock_response(config_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a mock LLM response based on configuration and context.

    Args:
        config_data: Mock agent configuration
        context: Job execution context

    Returns:
        Mock LLM response dictionary
    """
    # Reconstruct config from serialized data
    response_patterns = []
    for pattern_data in config_data["response_patterns"]:
        pattern = {
            "action": pattern_data["action"],
            "summary": pattern_data["summary"],
            "delay_seconds": pattern_data["delay_seconds"],
            "failure_mode": pattern_data["failure_mode"],
            "evidence_files": pattern_data["evidence_files"],
            "custom_data": pattern_data["custom_data"]
        }
        response_patterns.append(pattern)

    config = {
        "role": config_data["role"],
        "response_patterns": response_patterns,
        "default_failure_rate": config_data.get("default_failure_rate", 0.0),
        "state_aware": config_data.get("state_aware", True),
        "deterministic": config_data.get("deterministic", False)
    }

    # Get appropriate response pattern
    pattern = get_response_for_context(config, context)

    # Simulate failure mode if specified
    if pattern["failure_mode"] != "none":
        simulate_failure_mode(pattern["failure_mode"])

    # Simulate processing delay
    simulate_processing_delay(pattern["delay_seconds"])

    # Generate the response
    response = pattern_to_llm_response(pattern)

    # Add some realistic variations
    if not config["deterministic"]:
        # Add slight variations to metrics for realism
        response["metrics"]["cost_usd"] = round(response["metrics"]["cost_usd"] * random.uniform(0.9, 1.1), 4)
        response["metrics"]["duration_seconds"] = pattern["delay_seconds"]

    return response


def get_response_for_context(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Get appropriate response pattern based on job context."""
    if config["deterministic"] and config["response_patterns"]:
        # Return first pattern for deterministic behavior
        return config["response_patterns"][0]

    # State-aware response selection
    if config["state_aware"]:
        job_state = context.get("status", "UNKNOWN")
        current_phase = context.get("current_phase", "unknown")

        # Filter patterns based on context
        filtered_patterns = []
        for pattern in config["response_patterns"]:
            if pattern_matches_context(pattern, job_state, current_phase, config["role"]):
                filtered_patterns.append(pattern)

        if filtered_patterns:
            return random.choice(filtered_patterns)

    # Random selection with failure rate
    if random.random() < config["default_failure_rate"]:
        # Return a failure pattern
        failure_patterns = [p for p in config["response_patterns"]
                          if p["failure_mode"] != "none"]
        if failure_patterns:
            return random.choice(failure_patterns)

    # Default random selection
    return random.choice(config["response_patterns"]) if config["response_patterns"] else default_pattern(config["role"])


def pattern_matches_context(pattern: Dict[str, Any], job_state: str, current_phase: str, role: str) -> bool:
    """Check if pattern is appropriate for current context."""
    # Simple context matching - can be extended
    if job_state == "REVIEW_REQUIRED" and role == "supervisor":
        return pattern["action"] in ["COMPLETED", "STUCK"]
    elif job_state == "RUNNING" and role == "worker":
        return pattern["action"] in ["COMPLETED", "STUCK", "RETRY"]

    return True  # Allow all patterns by default


def default_pattern(role: str) -> Dict[str, Any]:
    """Get default response pattern."""
    return {
        "action": "COMPLETED",
        "summary": f"Mock {role} task completed successfully",
        "delay_seconds": random.uniform(0.1, 2.0),
        "failure_mode": "none",
        "evidence_files": [],
        "custom_data": {}
    }


def pattern_to_llm_response(pattern: Dict[str, Any]) -> Dict[str, Any]:
    """Convert pattern to standard LLM response format."""
    response = {
        "action": pattern["action"],
        "summary_for_supervisor": pattern["summary"],
        "evidence_files": pattern["evidence_files"],
        "metrics": {
            "cost_usd": round(random.uniform(0.01, 0.1), 4),
            "duration_seconds": pattern["delay_seconds"],
            "token_input": random.randint(100, 1000),
            "token_output": random.randint(50, 500),
        }
    }

    # Add custom data if provided
    response.update(pattern["custom_data"])

    return response


def create_job_context_from_env() -> Dict[str, Any]:
    """Create job context from environment variables."""
    context = {
        "status": os.environ.get("MOCK_JOB_STATUS", "RUNNING"),
        "current_phase": os.environ.get("MOCK_JOB_PHASE", "implementation"),
        "role": os.environ.get("MOCK_AGENT_ROLE", "worker"),
        "call_count": int(os.environ.get("MOCK_AGENT_CALL_COUNT", "1")),
        "prompt": os.environ.get("MOCK_AGENT_LAST_PROMPT", ""),
    }

    # Add any additional context from environment
    for key, value in os.environ.items():
        if key.startswith("MOCK_CONTEXT_"):
            context_key = key[13:].lower()  # Remove MOCK_CONTEXT_ prefix
            context[context_key] = value

    return context


def main():
    """Main entry point for mock agent processing."""
    if len(sys.argv) < 2:
        print("Usage: mock_agent_processor.py <config_json>", file=sys.stderr)
        sys.exit(1)

    try:
        # Parse configuration from command line argument
        config_json = sys.argv[1]
        config_data = json.loads(config_json)

        # Create context from environment
        context = create_job_context_from_env()

        # Generate mock response
        response = generate_mock_response(config_data, context)

        # Output response as JSON
        print(json.dumps(response, indent=2))

    except json.JSONDecodeError as e:
        print(f"Invalid JSON configuration: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Mock agent processor error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()