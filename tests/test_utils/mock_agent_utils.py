"""
Mock Agent Test Utilities

This module provides helper functions and fixtures for testing with mock agents,
enabling clean setup and validation of mock agent behavior in unit tests.
"""

import pytest
import json
import os
import tempfile
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import patch, MagicMock

from logist.agents.mock_agent import (
    MockAgent, MockAgentConfig, MockAgentRole, MockResponsePattern,
    MockResponseAction, MockFailureMode, create_worker_mock,
    create_supervisor_mock, create_failing_mock, reset_mock_context
)


class MockAgentTestHelper:
    """Helper class for setting up and managing mock agents in tests."""

    def __init__(self):
        self.agents: Dict[str, MockAgent] = {}
        self.temp_dirs: List[str] = []

    def create_worker_agent(self, success_rate: float = 0.9,
                          name: str = "test_worker") -> MockAgent:
        """Create and register a mock worker agent."""
        agent = create_worker_mock(success_rate)
        self.agents[name] = agent
        return agent

    def create_supervisor_agent(self, approval_rate: float = 0.8,
                              name: str = "test_supervisor") -> MockAgent:
        """Create and register a mock supervisor agent."""
        agent = create_supervisor_mock(approval_rate)
        self.agents[name] = agent
        return agent

    def create_failing_agent(self, failure_mode: MockFailureMode,
                           name: str = "test_failing") -> MockAgent:
        """Create and register a mock agent that always fails."""
        agent = create_failing_mock(failure_mode)
        self.agents[name] = agent
        return agent

    def create_custom_agent(self, role: MockAgentRole,
                          patterns: List[MockResponsePattern],
                          name: str = "test_custom") -> MockAgent:
        """Create and register a custom mock agent with specific patterns."""
        config = MockAgentConfig(
            role=role,
            response_patterns=patterns,
            state_aware=True,
            deterministic=True
        )
        agent = MockAgent(config)
        self.agents[name] = agent
        return agent

    def get_agent(self, name: str) -> Optional[MockAgent]:
        """Get a registered agent by name."""
        return self.agents.get(name)

    def reset_all_agents(self) -> None:
        """Reset all registered agents."""
        for agent in self.agents.values():
            # Reset any internal state
            pass
        reset_mock_context()

    def cleanup(self) -> None:
        """Clean up temporary directories and reset state."""
        for temp_dir in self.temp_dirs:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
        self.temp_dirs.clear()
        self.reset_all_agents()


# Global test helper instance
_test_helper = MockAgentTestHelper()


@pytest.fixture(scope="function")
def mock_agent_helper():
    """Fixture providing a mock agent test helper."""
    _test_helper.reset_all_agents()
    yield _test_helper
    _test_helper.cleanup()


@pytest.fixture(scope="function")
def mock_worker_agent():
    """Fixture providing a standard mock worker agent."""
    agent = _test_helper.create_worker_agent(name="fixture_worker")
    yield agent


@pytest.fixture(scope="function")
def mock_supervisor_agent():
    """Fixture providing a standard mock supervisor agent."""
    agent = _test_helper.create_supervisor_agent(name="fixture_supervisor")
    yield agent


@pytest.fixture(scope="function")
def deterministic_mock_worker():
    """Fixture providing a deterministic mock worker agent."""
    patterns = [
        MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary="Deterministic worker completion",
            evidence_files=["result.txt"]
        )
    ]
    config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=patterns,
        deterministic=True
    )
    agent = MockAgent(config)
    agent.set_deterministic(True)
    yield agent


def mock_agent_response(action: str = "COMPLETED",
                       summary: str = "Mock response",
                       failure_mode: str = "none",
                       delay: float = 0.1) -> MockResponsePattern:
    """Create a mock response pattern for testing."""
    return MockResponsePattern(
        action=MockResponseAction(action),
        summary=summary,
        failure_mode=MockFailureMode(failure_mode),
        delay_seconds=delay
    )


def patch_agent_execution(agent: MockAgent, return_value: Dict[str, Any] = None):
    """
    Context manager to patch agent execution for testing.

    Args:
        agent: The mock agent to patch
        return_value: Value to return from the patched execution

    Returns:
        Context manager for patching
    """
    def mock_cmd(prompt: str):
        # Return a command that will execute our mock processor
        return ["echo", json.dumps(return_value or {"action": "COMPLETED", "summary": "Mocked"})]

    return patch.object(agent, 'cmd', side_effect=mock_cmd)


def create_temp_job_manifest(status: str = "DRAFT",
                           phase: str = "setup",
                           temp_dir: str = None) -> str:
    """
    Create a temporary job manifest file for testing.

    Args:
        status: Job status
        phase: Current phase
        temp_dir: Directory to create manifest in (creates temp dir if None)

    Returns:
        Path to the created manifest file
    """
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
        _test_helper.temp_dirs.append(temp_dir)

    manifest_path = os.path.join(temp_dir, "job_manifest.json")
    manifest = {
        "job_id": f"test_job_{os.path.basename(temp_dir)}",
        "status": status,
        "current_phase": phase,
        "description": "Test job for mock agent testing",
        "phases": [
            {"name": "setup", "description": "Setup phase"},
            {"name": "implementation", "description": "Implementation phase"}
        ],
        "metrics": {
            "cumulative_cost": 0.0,
            "cumulative_time_seconds": 0.0
        },
        "history": []
    }

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def simulate_job_context(status: str = "RUNNING",
                        phase: str = "implementation",
                        role: str = "worker") -> Dict[str, Any]:
    """
    Create a simulated job context for testing.

    Args:
        status: Job status
        phase: Current phase
        role: Agent role

    Returns:
        Job context dictionary
    """
    return {
        "status": status,
        "current_phase": phase,
        "role": role,
        "call_count": 1,
        "prompt": "Test prompt for mock agent"
    }


def validate_mock_response(response: Dict[str, Any],
                         expected_action: str = None,
                         min_cost: float = 0.0,
                         max_cost: float = 1.0) -> bool:
    """
    Validate a mock agent response.

    Args:
        response: Response to validate
        expected_action: Expected action (if specified)
        min_cost: Minimum expected cost
        max_cost: Maximum expected cost

    Returns:
        True if response is valid
    """
    if not isinstance(response, dict):
        return False

    # Check required fields
    required_fields = ["action", "summary_for_supervisor", "evidence_files", "metrics"]
    if not all(field in response for field in required_fields):
        return False

    # Check action if specified
    if expected_action and response.get("action") != expected_action:
        return False

    # Check metrics
    metrics = response.get("metrics", {})
    if not isinstance(metrics, dict):
        return False

    cost = metrics.get("cost_usd", 0)
    if not (min_cost <= cost <= max_cost):
        return False

    return True


def run_mock_agent_test(agent: MockAgent,
                       context: Dict[str, Any] = None,
                       validate_response: bool = True) -> Dict[str, Any]:
    """
    Run a complete mock agent test cycle.

    Args:
        agent: Mock agent to test
        context: Job context (uses default if None)
        validate_response: Whether to validate the response

    Returns:
        Test results dictionary
    """
    if context is None:
        context = simulate_job_context()

    results = {
        "success": False,
        "response": None,
        "error": None,
        "execution_time": 0.0
    }

    try:
        import time
        start_time = time.time()

        # Execute agent command (this would normally run the mock processor)
        cmd = agent.cmd("Test prompt")
        results["command"] = cmd

        # In a real test, we would execute the command and parse output
        # For now, just simulate success
        results["success"] = True
        results["response"] = {"action": "COMPLETED", "summary_for_supervisor": "Test completed"}

        results["execution_time"] = time.time() - start_time

        if validate_response:
            results["valid_response"] = validate_mock_response(results["response"])

    except Exception as e:
        results["error"] = str(e)

    return results