"""
Mock Agent Framework for Unit Testing

This module provides a comprehensive mock agent system that emulates LLM responses
for Worker and Supervisor roles, enabling proper unit testing of job execution flows
without requiring actual LLM service calls.

The mock agents support configurable response patterns, failure modes, and state-aware
behavior to test success/failure interpretation and lifecycle state transitions.
"""

import json
import time
import random
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

from .base import Agent


class MockAgentRole(Enum):
    """Supported mock agent roles."""
    WORKER = "worker"
    SUPERVISOR = "supervisor"


class MockResponseAction(Enum):
    """Mock response actions that drive state transitions."""
    COMPLETED = "COMPLETED"
    STUCK = "STUCK"
    RETRY = "RETRY"
    SUSPEND = "SUSPEND"
    RESUME = "RESUME"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class MockFailureMode(Enum):
    """Types of failures the mock agent can simulate."""
    NONE = "none"
    API_ERROR = "api_error"
    CONTEXT_FULL = "context_full"
    AUTH_ERROR = "auth_error"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    NETWORK_ERROR = "network_error"


@dataclass
class MockResponsePattern:
    """Configuration for mock response generation."""
    action: MockResponseAction
    summary: str
    delay_seconds: float = field(default_factory=lambda: random.uniform(0.1, 2.0))
    failure_mode: MockFailureMode = MockFailureMode.NONE
    evidence_files: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_llm_response(self) -> Dict[str, Any]:
        """Convert to standard LLM response format."""
        response = {
            "action": self.action.value,
            "summary_for_supervisor": self.summary,
            "evidence_files": self.evidence_files,
            "metrics": {
                "cost_usd": round(random.uniform(0.01, 0.1), 4),
                "duration_seconds": self.delay_seconds,
                "token_input": random.randint(100, 1000),
                "token_output": random.randint(50, 500),
            }
        }

        # Add custom data if provided
        response.update(self.custom_data)

        return response


@dataclass
class MockAgentConfig:
    """Configuration for mock agent behavior."""
    role: MockAgentRole
    response_patterns: List[MockResponsePattern]
    default_failure_rate: float = 0.0
    state_aware: bool = True
    deterministic: bool = False

    def get_response_for_context(self, context: Dict[str, Any]) -> MockResponsePattern:
        """
        Get appropriate response pattern based on job context.

        Args:
            context: Job context information

        Returns:
            Selected response pattern
        """
        if self.deterministic and self.response_patterns:
            # Return first pattern for deterministic behavior
            return self.response_patterns[0]

        # State-aware response selection
        if self.state_aware:
            job_state = context.get("status", "UNKNOWN")
            current_phase = context.get("current_phase", "unknown")

            # Filter patterns based on context
            filtered_patterns = []
            for pattern in self.response_patterns:
                if self._pattern_matches_context(pattern, job_state, current_phase):
                    filtered_patterns.append(pattern)

            if filtered_patterns:
                return random.choice(filtered_patterns)

        # Random selection with failure rate
        if random.random() < self.default_failure_rate:
            # Return a failure pattern
            failure_patterns = [p for p in self.response_patterns
                              if p.failure_mode != MockFailureMode.NONE]
            if failure_patterns:
                return random.choice(failure_patterns)

        # Default random selection
        return random.choice(self.response_patterns) if self.response_patterns else self._default_pattern()

    def _pattern_matches_context(self, pattern: MockResponsePattern,
                               job_state: str, current_phase: str) -> bool:
        """Check if pattern is appropriate for current context."""
        # Simple context matching - can be extended
        if job_state == "REVIEW_REQUIRED" and self.role == MockAgentRole.SUPERVISOR:
            return pattern.action in [MockResponseAction.COMPLETED, MockResponseAction.STUCK]
        elif job_state == "RUNNING" and self.role == MockAgentRole.WORKER:
            return pattern.action in [MockResponseAction.COMPLETED, MockResponseAction.STUCK, MockResponseAction.RETRY]

        return True  # Allow all patterns by default

    def _default_pattern(self) -> MockResponsePattern:
        """Get default response pattern."""
        return MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary=f"Mock {self.role.value} task completed successfully"
        )


class MockAgent(Agent):
    """
    Advanced mock agent for unit testing that simulates LLM behavior.

    This agent provides configurable response patterns and state-aware behavior
    to enable comprehensive testing of job execution flows without LLM dependencies.
    """

    def __init__(self, config: MockAgentConfig):
        """
        Initialize mock agent with configuration.

        Args:
            config: Mock agent configuration
        """
        self.config = config
        self._response_history: List[Dict[str, Any]] = []
        self._call_count = 0

    def cmd(self, prompt: str) -> List[str]:
        """
        Generate command to execute mock LLM processing.

        Args:
            prompt: The job prompt (used for context-aware responses)

        Returns:
            Command to execute mock processing
        """
        import sys
        import os

        # Store prompt for context
        self._last_prompt = prompt
        self._call_count += 1

        # Return command to run our mock processing
        script_path = os.path.join(os.path.dirname(__file__), 'mock_agent_processor.py')
        return [sys.executable, script_path, json.dumps(self.config.__dict__)]

    def env(self) -> Dict[str, str]:
        """
        Get environment variables for mock execution.

        Returns:
            Environment variables for mock processing
        """
        import os

        return {
            'MOCK_AGENT_ROLE': self.config.role.value,
            'MOCK_AGENT_CALL_COUNT': str(self._call_count),
            'MOCK_AGENT_LAST_PROMPT': self._last_prompt,
            'PYTHONPATH': os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        }

    def get_stop_sequences(self) -> List[Union[str, str]]:
        """
        Get sequences indicating the agent is waiting for input.

        Returns:
            List of stop sequences (empty for mock agent)
        """
        return []

    @property
    def name(self) -> str:
        """Get the agent name."""
        return f"Mock{self.config.role.value.capitalize()}Agent"

    @property
    def version(self) -> str:
        """Get the agent version."""
        return "1.0.0"

    def get_response_history(self) -> List[Dict[str, Any]]:
        """Get history of all mock responses generated."""
        return self._response_history.copy()

    def add_custom_pattern(self, pattern: MockResponsePattern) -> None:
        """Add a custom response pattern for testing."""
        self.config.response_patterns.append(pattern)

    def set_failure_rate(self, rate: float) -> None:
        """Set the default failure rate for testing."""
        self.config.default_failure_rate = max(0.0, min(1.0, rate))

    def set_deterministic(self, deterministic: bool = True) -> None:
        """Set deterministic behavior for testing."""
        self.config.deterministic = deterministic


# Pre-configured mock agents for common testing scenarios
def create_worker_mock(success_rate: float = 0.9) -> MockAgent:
    """Create a mock worker agent with realistic response patterns."""
    patterns = [
        MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary="Worker task completed successfully",
            evidence_files=["result.txt", "test_output.log"]
        ),
        MockResponsePattern(
            action=MockResponseAction.STUCK,
            summary="Worker encountered an issue requiring intervention",
            failure_mode=MockFailureMode.NONE
        ),
        MockResponsePattern(
            action=MockResponseAction.RETRY,
            summary="Worker task failed, requesting retry",
            failure_mode=MockFailureMode.API_ERROR
        ),
    ]

    config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=patterns,
        default_failure_rate=1.0 - success_rate,
        state_aware=True
    )

    return MockAgent(config)


def create_supervisor_mock(approval_rate: float = 0.8) -> MockAgent:
    """Create a mock supervisor agent with realistic review patterns."""
    patterns = [
        MockResponsePattern(
            action=MockResponseAction.APPROVE,
            summary="Supervisor approved the work - meets all requirements",
            evidence_files=["review_notes.md"]
        ),
        MockResponsePattern(
            action=MockResponseAction.REJECT,
            summary="Supervisor rejected - revisions required",
            evidence_files=["feedback.md"]
        ),
        MockResponsePattern(
            action=MockResponseAction.STUCK,
            summary="Supervisor needs clarification on requirements",
            failure_mode=MockFailureMode.NONE
        ),
    ]

    config = MockAgentConfig(
        role=MockAgentRole.SUPERVISOR,
        response_patterns=patterns,
        default_failure_rate=1.0 - approval_rate,
        state_aware=True
    )

    return MockAgent(config)


def create_failing_mock(failure_mode: MockFailureMode) -> MockAgent:
    """Create a mock agent that always fails with specified mode."""
    pattern = MockResponsePattern(
        action=MockResponseAction.STUCK,
        summary=f"Mock agent failed with {failure_mode.value}",
        failure_mode=failure_mode,
        delay_seconds=0.1
    )

    config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=[pattern],
        default_failure_rate=1.0,
        deterministic=True
    )

    return MockAgent(config)


# Context for tracking mock agent state across tests
_mock_agent_context = {
    'response_history': [],
    'call_count': 0
}


def reset_mock_context() -> None:
    """Reset global mock agent context for testing."""
    global _mock_agent_context
    _mock_agent_context = {
        'response_history': [],
        'call_count': 0
    }


def get_mock_context() -> Dict[str, Any]:
    """Get current mock agent context."""
    return _mock_agent_context.copy()