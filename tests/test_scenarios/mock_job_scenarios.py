"""
Mock Job Scenarios for Unit Testing

This module defines predefined mock scenarios for testing different job execution
lifecycles, state transitions, and failure modes without requiring actual LLM calls.
"""

from typing import Dict, Any, List, Callable
from logist.agents.mock_agent import (
    MockAgent, MockAgentConfig, MockAgentRole, MockResponsePattern,
    MockResponseAction, MockFailureMode
)


class MockJobScenario:
    """Represents a complete mock job execution scenario."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.worker_agent: MockAgent = None
        self.supervisor_agent: MockAgent = None
        self.expected_transitions: List[Dict[str, Any]] = []
        self.failure_points: List[str] = []
        self.setup_actions: List[Callable] = []

    def set_worker(self, agent: MockAgent) -> 'MockJobScenario':
        """Set the worker agent for this scenario."""
        self.worker_agent = agent
        return self

    def set_supervisor(self, agent: MockAgent) -> 'MockJobScenario':
        """Set the supervisor agent for this scenario."""
        self.supervisor_agent = agent
        return self

    def add_transition(self, from_state: str, action: str, to_state: str,
                      agent_role: str = "worker") -> 'MockJobScenario':
        """Add an expected state transition."""
        self.expected_transitions.append({
            "from_state": from_state,
            "action": action,
            "to_state": to_state,
            "agent_role": agent_role
        })
        return self

    def add_failure_point(self, failure_description: str) -> 'MockJobScenario':
        """Add a point where the scenario is expected to fail."""
        self.failure_points.append(failure_description)
        return self

    def add_setup_action(self, action: Callable) -> 'MockJobScenario':
        """Add a setup action to run before the scenario."""
        self.setup_actions.append(action)
        return self

    def run_setup(self) -> None:
        """Run all setup actions."""
        for action in self.setup_actions:
            action()

    def validate_transitions(self, actual_transitions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate that actual transitions match expected transitions."""
        validation = {
            "valid": True,
            "errors": [],
            "missing_transitions": [],
            "unexpected_transitions": []
        }

        expected_set = {(t["from_state"], t["action"], t["to_state"]) for t in self.expected_transitions}
        actual_set = {(t["from_state"], t["action"], t["to_state"]) for t in actual_transitions}

        # Check for missing transitions
        for expected in expected_set:
            if expected not in actual_set:
                validation["missing_transitions"].append(expected)
                validation["valid"] = False

        # Check for unexpected transitions (only if we expect exact matching)
        if len(actual_set) != len(expected_set):
            unexpected = actual_set - expected_set
            if unexpected:
                validation["unexpected_transitions"].extend(unexpected)
                validation["valid"] = False

        return validation


# Predefined scenarios for common testing patterns

def create_successful_job_scenario() -> MockJobScenario:
    """Create a scenario for a completely successful job execution."""
    scenario = MockJobScenario(
        "successful_job",
        "Complete successful job execution from DRAFT to SUCCESS"
    )

    # Worker patterns: always complete successfully
    worker_patterns = [
        MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary="Worker completed task successfully",
            evidence_files=["result.txt", "tests.py"]
        )
    ]
    worker_config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=worker_patterns,
        deterministic=True
    )
    scenario.set_worker(MockAgent(worker_config))

    # Supervisor patterns: always approve
    supervisor_patterns = [
        MockResponsePattern(
            action=MockResponseAction.APPROVE,
            summary="Supervisor approved the work",
            evidence_files=["review.md"]
        )
    ]
    supervisor_config = MockAgentConfig(
        role=MockAgentRole.SUPERVISOR,
        response_patterns=supervisor_patterns,
        deterministic=True
    )
    scenario.set_supervisor(MockAgent(supervisor_config))

    # Expected transitions
    scenario.add_transition("DRAFT", "ACTIVATED", "PENDING", "system")
    scenario.add_transition("PENDING", "COMPLETED", "RUNNING", "worker")
    scenario.add_transition("RUNNING", "COMPLETED", "REVIEW_REQUIRED", "worker")
    scenario.add_transition("REVIEW_REQUIRED", "COMPLETED", "REVIEWING", "supervisor")
    scenario.add_transition("REVIEWING", "APPROVE", "APPROVAL_REQUIRED", "supervisor")
    scenario.add_transition("APPROVAL_REQUIRED", "APPROVE", "SUCCESS", "system")

    return scenario


def create_worker_failure_scenario() -> MockJobScenario:
    """Create a scenario where the worker fails and requires intervention."""
    scenario = MockJobScenario(
        "worker_failure",
        "Job execution with worker failure requiring human intervention"
    )

    # Worker patterns: fail on first attempt, succeed on retry
    worker_patterns = [
        MockResponsePattern(
            action=MockResponseAction.STUCK,
            summary="Worker encountered an error and needs help",
            failure_mode=MockFailureMode.API_ERROR
        ),
        MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary="Worker completed task successfully on retry",
            evidence_files=["result.txt"]
        )
    ]
    worker_config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=worker_patterns,
        deterministic=True  # Use patterns in order
    )
    scenario.set_worker(MockAgent(worker_config))

    # Expected transitions
    scenario.add_transition("DRAFT", "ACTIVATED", "PENDING", "system")
    scenario.add_transition("PENDING", "COMPLETED", "RUNNING", "worker")
    scenario.add_transition("RUNNING", "STUCK", "INTERVENTION_REQUIRED", "worker")
    scenario.add_transition("INTERVENTION_REQUIRED", "RESUBMIT", "PENDING", "human")
    scenario.add_transition("PENDING", "COMPLETED", "RUNNING", "worker")

    return scenario


def create_supervisor_rejection_scenario() -> MockJobScenario:
    """Create a scenario where supervisor rejects work and sends it back."""
    scenario = MockJobScenario(
        "supervisor_rejection",
        "Job execution where supervisor rejects work requiring revisions"
    )

    # Worker patterns: complete work (will be used twice)
    worker_patterns = [
        MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary="Worker completed initial implementation",
            evidence_files=["result.txt"]
        ),
        MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary="Worker completed revisions successfully",
            evidence_files=["result_v2.txt"]
        )
    ]
    worker_config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=worker_patterns,
        deterministic=True
    )
    scenario.set_worker(MockAgent(worker_config))

    # Supervisor patterns: reject first, approve second
    supervisor_patterns = [
        MockResponsePattern(
            action=MockResponseAction.REJECT,
            summary="Supervisor rejected work - needs revisions",
            evidence_files=["feedback.md"]
        ),
        MockResponsePattern(
            action=MockResponseAction.APPROVE,
            summary="Supervisor approved the revised work",
            evidence_files=["final_review.md"]
        )
    ]
    supervisor_config = MockAgentConfig(
        role=MockAgentRole.SUPERVISOR,
        response_patterns=supervisor_patterns,
        deterministic=True
    )
    scenario.set_supervisor(MockAgent(supervisor_config))

    # Expected transitions
    scenario.add_transition("DRAFT", "ACTIVATED", "PENDING", "system")
    scenario.add_transition("PENDING", "COMPLETED", "RUNNING", "worker")
    scenario.add_transition("RUNNING", "COMPLETED", "REVIEW_REQUIRED", "worker")
    scenario.add_transition("REVIEW_REQUIRED", "COMPLETED", "REVIEWING", "supervisor")
    scenario.add_transition("REVIEWING", "REJECT", "APPROVAL_REQUIRED", "supervisor")
    scenario.add_transition("APPROVAL_REQUIRED", "REJECT", "PENDING", "human")
    scenario.add_transition("PENDING", "COMPLETED", "RUNNING", "worker")
    scenario.add_transition("RUNNING", "COMPLETED", "REVIEW_REQUIRED", "worker")
    scenario.add_transition("REVIEW_REQUIRED", "COMPLETED", "REVIEWING", "supervisor")
    scenario.add_transition("REVIEWING", "APPROVE", "APPROVAL_REQUIRED", "supervisor")
    scenario.add_transition("APPROVAL_REQUIRED", "APPROVE", "SUCCESS", "system")

    return scenario


def create_suspension_scenario() -> MockJobScenario:
    """Create a scenario testing job suspension and resumption."""
    scenario = MockJobScenario(
        "job_suspension",
        "Job execution with suspension and resumption"
    )

    # Worker patterns: complete successfully
    worker_patterns = [
        MockResponsePattern(
            action=MockResponseAction.COMPLETED,
            summary="Worker completed task successfully",
            evidence_files=["result.txt"]
        )
    ]
    worker_config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=worker_patterns,
        deterministic=True
    )
    scenario.set_worker(MockAgent(worker_config))

    # Expected transitions with suspension
    scenario.add_transition("DRAFT", "ACTIVATED", "PENDING", "system")
    scenario.add_transition("PENDING", "SUSPEND", "SUSPENDED", "system")
    scenario.add_transition("SUSPENDED", "RESUME", "PENDING", "system")
    scenario.add_transition("PENDING", "COMPLETED", "RUNNING", "worker")
    scenario.add_transition("RUNNING", "COMPLETED", "REVIEW_REQUIRED", "worker")

    return scenario


def create_failure_cascade_scenario() -> MockJobScenario:
    """Create a scenario with multiple failures leading to cancellation."""
    scenario = MockJobScenario(
        "failure_cascade",
        "Job execution with multiple failures leading to cancellation"
    )

    # Worker patterns: always fail
    worker_patterns = [
        MockResponsePattern(
            action=MockResponseAction.STUCK,
            summary="Worker failed repeatedly",
            failure_mode=MockFailureMode.NETWORK_ERROR
        )
    ]
    worker_config = MockAgentConfig(
        role=MockAgentRole.WORKER,
        response_patterns=worker_patterns,
        deterministic=True
    )
    scenario.set_worker(MockAgent(worker_config))

    # Expected transitions
    scenario.add_transition("DRAFT", "ACTIVATED", "PENDING", "system")
    scenario.add_transition("PENDING", "COMPLETED", "RUNNING", "worker")
    scenario.add_transition("RUNNING", "STUCK", "INTERVENTION_REQUIRED", "worker")
    scenario.add_transition("INTERVENTION_REQUIRED", "TERMINATE", "CANCELED", "human")

    scenario.add_failure_point("Worker fails with network error")
    scenario.add_failure_point("Job reaches intervention required state")
    scenario.add_failure_point("Human operator terminates job")

    return scenario


# Registry of all available scenarios
SCENARIO_REGISTRY = {
    "successful_job": create_successful_job_scenario,
    "worker_failure": create_worker_failure_scenario,
    "supervisor_rejection": create_supervisor_rejection_scenario,
    "job_suspension": create_suspension_scenario,
    "failure_cascade": create_failure_cascade_scenario,
}


def get_scenario(name: str) -> MockJobScenario:
    """Get a scenario by name."""
    if name not in SCENARIO_REGISTRY:
        available = list(SCENARIO_REGISTRY.keys())
        raise ValueError(f"Unknown scenario '{name}'. Available: {available}")

    return SCENARIO_REGISTRY[name]()


def list_scenarios() -> List[str]:
    """List all available scenario names."""
    return list(SCENARIO_REGISTRY.keys())


def create_custom_scenario(name: str, description: str,
                          worker_agent: MockAgent = None,
                          supervisor_agent: MockAgent = None) -> MockJobScenario:
    """Create a custom scenario with provided agents."""
    scenario = MockJobScenario(name, description)

    if worker_agent:
        scenario.set_worker(worker_agent)
    if supervisor_agent:
        scenario.set_supervisor(supervisor_agent)

    return scenario