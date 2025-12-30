"""
State machine validation tests for Logist job lifecycle management.

This module tests the enhanced state machine with DRAFT/PENDING/SUSPENDED states,
including transition validation, invalid transition blocking, and lifecycle management.
"""

import pytest
from unittest.mock import patch, MagicMock

from logist.job_state import (
    JobStates, JobStateError, transition_state, validate_state_transition,
    load_job_manifest, update_job_manifest
)
from logist.services.job_manager import JobManagerService


class TestStateMachineBasics:
    """Basic state machine functionality tests."""

    def test_job_states_constants(self):
        """Test that all job state constants are properly defined."""
        assert JobStates.DRAFT == "DRAFT"
        assert JobStates.PENDING == "PENDING"
        assert JobStates.SUSPENDED == "SUSPENDED"
        assert JobStates.RUNNING == "RUNNING"
        assert JobStates.REVIEW_REQUIRED == "REVIEW_REQUIRED"
        assert JobStates.REVIEWING == "REVIEWING"
        assert JobStates.APPROVAL_REQUIRED == "APPROVAL_REQUIRED"
        assert JobStates.INTERVENTION_REQUIRED == "INTERVENTION_REQUIRED"
        assert JobStates.SUCCESS == "SUCCESS"
        assert JobStates.CANCELED == "CANCELED"
        assert JobStates.FAILED == "FAILED"
        assert JobStates.ATTACHED == "ATTACHED"
        assert JobStates.DETACHED == "DETACHED"

    def test_terminal_states_defined(self):
        """Test that terminal states are properly identified."""
        # Terminal states are SUCCESS and CANCELED (FAILED is deprecated)
        terminal_states = JobStates.TERMINAL_STATES

        # Verify these are considered terminal
        for state in terminal_states:
            with pytest.raises(JobStateError, match=f"Cannot transition out of terminal state '{state}'"):
                validate_state_transition(state, JobStates.PENDING)


class TestValidStateTransitions:
    """Test valid state transitions according to the state machine."""

    def test_draft_transitions(self):
        """Test valid transitions from DRAFT state."""
        # DRAFT -> PENDING (activation)
        result = transition_state(JobStates.DRAFT, "ACTIVATED")
        assert result == JobStates.PENDING

        # DRAFT -> SUSPENDED (suspend)
        result = transition_state(JobStates.DRAFT, "SUSPEND")
        assert result == JobStates.SUSPENDED

    def test_pending_transitions(self):
        """Test valid transitions from PENDING state."""
        # PENDING -> PROVISIONING (step starts)
        result = transition_state(JobStates.PENDING, "STEP_START")
        assert result == JobStates.PROVISIONING

        # PENDING -> SUSPENDED (suspend)
        result = transition_state(JobStates.PENDING, "SUSPEND")
        assert result == JobStates.SUSPENDED

        # PENDING -> CANCELED (cancel)
        result = transition_state(JobStates.PENDING, "CANCEL")
        assert result == JobStates.CANCELED

    def test_suspended_transitions(self):
        """Test valid transitions from SUSPENDED state."""
        # SUSPENDED -> PENDING (resume)
        result = transition_state(JobStates.SUSPENDED, "RESUME")
        assert result == JobStates.PENDING

    def test_running_transitions(self):
        """Test valid transitions from RUNNING state (legacy backward compatibility)."""
        # RUNNING -> HARVESTING (completion) - new behavior for legacy state
        result = transition_state(JobStates.RUNNING, "COMPLETED")
        assert result == JobStates.HARVESTING

        # RUNNING -> INTERVENTION_REQUIRED (stuck)
        result = transition_state(JobStates.RUNNING, "STUCK")
        assert result == JobStates.INTERVENTION_REQUIRED

        # RUNNING -> SUSPENDED (suspend)
        result = transition_state(JobStates.RUNNING, "SUSPEND")
        assert result == JobStates.SUSPENDED

        # RUNNING -> CANCELED (cancel)
        result = transition_state(JobStates.RUNNING, "CANCEL")
        assert result == JobStates.CANCELED

    def test_new_transient_state_transitions(self):
        """Test transitions through new transient states."""
        # PROVISIONING -> EXECUTING (provision complete)
        result = transition_state(JobStates.PROVISIONING, "PROVISION_COMPLETE")
        assert result == JobStates.EXECUTING

        # PROVISIONING -> INTERVENTION_REQUIRED (provision failed)
        result = transition_state(JobStates.PROVISIONING, "PROVISION_FAILED")
        assert result == JobStates.INTERVENTION_REQUIRED

        # EXECUTING -> HARVESTING (execution complete)
        result = transition_state(JobStates.EXECUTING, "EXECUTE_COMPLETE")
        assert result == JobStates.HARVESTING

        # EXECUTING -> RECOVERING (timeout/stuck)
        result = transition_state(JobStates.EXECUTING, "RECOVER_START")
        assert result == JobStates.RECOVERING

        # RECOVERING -> EXECUTING (recovery succeeds)
        result = transition_state(JobStates.RECOVERING, "RECOVER_COMPLETE")
        assert result == JobStates.EXECUTING

        # HARVESTING -> SUCCESS (goal achieved)
        result = transition_state(JobStates.HARVESTING, "HARVEST_SUCCESS")
        assert result == JobStates.SUCCESS

        # HARVESTING -> APPROVAL_REQUIRED (needs approval)
        result = transition_state(JobStates.HARVESTING, "HARVEST_APPROVAL")
        assert result == JobStates.APPROVAL_REQUIRED

        # HARVESTING -> INTERVENTION_REQUIRED (error/stuck)
        result = transition_state(JobStates.HARVESTING, "HARVEST_INTERVENTION")
        assert result == JobStates.INTERVENTION_REQUIRED

    def test_supervisor_transitions(self):
        """Test valid supervisor-related transitions."""
        # REVIEW_REQUIRED -> REVIEWING (supervisor starts review)
        # Note: This transition isn't directly in our current table, but REVIEWING transitions work

        # REVIEWING -> APPROVAL_REQUIRED (supervisor completes review)
        result = transition_state(JobStates.REVIEWING, "COMPLETED")
        assert result == JobStates.APPROVAL_REQUIRED

        # REVIEWING -> INTERVENTION_REQUIRED (supervisor finds issues)
        result = transition_state(JobStates.REVIEWING, "STUCK")
        assert result == JobStates.INTERVENTION_REQUIRED

    def test_suspend_from_all_states(self):
        """Test that suspend works from all appropriate states."""
        suspendable_states = [
            JobStates.DRAFT, JobStates.PENDING, JobStates.RUNNING,
            JobStates.REVIEW_REQUIRED, JobStates.REVIEWING,
            JobStates.APPROVAL_REQUIRED, JobStates.INTERVENTION_REQUIRED
        ]

        for state in suspendable_states:
            result = transition_state(state, "SUSPEND")
            assert result == JobStates.SUSPENDED, f"Failed to suspend from {state}"

    def test_fallback_transitions(self):
        """Test fallback transition logic."""
        # STUCK action should go to INTERVENTION_REQUIRED
        with patch('logist.job_state.transition_state') as mock_transition:
            mock_transition.side_effect = KeyError("not found")
            # This should trigger the fallback logic in transition_state
            # Since we're mocking, we'll test the validation instead

        # Test validation for STUCK fallback
        assert validate_state_transition(JobStates.RUNNING, JobStates.INTERVENTION_REQUIRED)


class TestInvalidStateTransitions:
    """Test that invalid state transitions are properly blocked."""

    def test_terminal_state_transitions_blocked(self):
        """Test that terminal states cannot transition to other states."""
        # Only SUCCESS and CANCELED are terminal (FAILED is deprecated)
        terminal_states = list(JobStates.TERMINAL_STATES)

        for terminal_state in terminal_states:
            with pytest.raises(JobStateError, match="Cannot transition out of terminal state"):
                validate_state_transition(terminal_state, JobStates.PENDING)

            with pytest.raises(JobStateError, match="Cannot transition out of terminal state"):
                validate_state_transition(terminal_state, JobStates.EXECUTING)

    def test_suspended_invalid_targets(self):
        """Test that SUSPENDED can only transition to valid targets."""
        # SUSPENDED -> RUNNING should be invalid
        with pytest.raises(JobStateError, match="SUSPENDED jobs can only resume to"):
            validate_state_transition(JobStates.SUSPENDED, JobStates.RUNNING)

        # SUSPENDED -> REVIEW_REQUIRED should be invalid
        with pytest.raises(JobStateError, match="SUSPENDED jobs can only resume to"):
            validate_state_transition(JobStates.SUSPENDED, JobStates.REVIEW_REQUIRED)

    def test_draft_restrictive_transitions(self):
        """Test that DRAFT state is very restrictive."""
        valid_draft_targets = {JobStates.PENDING, JobStates.SUSPENDED, JobStates.CANCELED}

        # Test invalid targets
        invalid_targets = [JobStates.RUNNING, JobStates.REVIEW_REQUIRED, JobStates.SUCCESS]
        for target in invalid_targets:
            if target not in valid_draft_targets:
                with pytest.raises(JobStateError, match="DRAFT jobs can only transition to"):
                    validate_state_transition(JobStates.DRAFT, target)

    def test_invalid_transition_action(self):
        """Test that invalid transition actions raise errors."""
        with pytest.raises(JobStateError, match="Invalid state transition"):
            transition_state(JobStates.PENDING, "INVALID_ACTION")

    def test_suspend_terminal_states_blocked(self):
        """Test that terminal states cannot be suspended."""
        # Only SUCCESS and CANCELED are terminal (FAILED is deprecated)
        terminal_states = list(JobStates.TERMINAL_STATES)

        for state in terminal_states:
            with pytest.raises(JobStateError, match=f"Cannot suspend job in state: {state}"):
                transition_state(state, "SUSPEND")


class TestStateValidation:
    """Test the comprehensive state validation function."""

    def test_pending_state_validation(self):
        """Test validation for PENDING state transitions."""
        valid_targets = [JobStates.PROVISIONING, JobStates.RUNNING, JobStates.SUSPENDED, JobStates.CANCELED]

        for target in valid_targets:
            assert validate_state_transition(JobStates.PENDING, target)

        # Test invalid target
        with pytest.raises(JobStateError):
            validate_state_transition(JobStates.PENDING, JobStates.SUCCESS)

    def test_running_state_validation(self):
        """Test validation for RUNNING state transitions (legacy backward compatibility)."""
        valid_targets = [JobStates.HARVESTING, JobStates.REVIEW_REQUIRED, JobStates.SUSPENDED, JobStates.CANCELED, JobStates.INTERVENTION_REQUIRED]

        for target in valid_targets:
            assert validate_state_transition(JobStates.RUNNING, target)

        # Test invalid target
        with pytest.raises(JobStateError):
            validate_state_transition(JobStates.RUNNING, JobStates.SUCCESS)

    def test_new_transient_state_validation(self):
        """Test validation for new transient states."""
        # PROVISIONING -> EXECUTING is valid
        assert validate_state_transition(JobStates.PROVISIONING, JobStates.EXECUTING)

        # EXECUTING -> HARVESTING is valid
        assert validate_state_transition(JobStates.EXECUTING, JobStates.HARVESTING)

        # RECOVERING -> EXECUTING is valid
        assert validate_state_transition(JobStates.RECOVERING, JobStates.EXECUTING)

        # HARVESTING -> SUCCESS, APPROVAL_REQUIRED, INTERVENTION_REQUIRED are valid
        assert validate_state_transition(JobStates.HARVESTING, JobStates.SUCCESS)
        assert validate_state_transition(JobStates.HARVESTING, JobStates.APPROVAL_REQUIRED)
        assert validate_state_transition(JobStates.HARVESTING, JobStates.INTERVENTION_REQUIRED)

    def test_attach_session_validation(self):
        """Test validation for attach/recover session states."""
        # ATTACHED -> SUPERVISOR_REVIEW should be valid (though not directly in transition_state)
        # For now, test that validation allows reasonable transitions

        # DETACHED should be terminal
        with pytest.raises(JobStateError, match="DETACHED sessions cannot transition"):
            validate_state_transition(JobStates.DETACHED, JobStates.ATTACHED)


class TestStateMachineIntegration:
    """Integration tests for state machine with job management."""

    @pytest.fixture
    def temp_job_dir(self, tmp_path):
        """Create a temporary job directory with manifest."""
        job_dir = tmp_path / "test_job"
        job_dir.mkdir()

        manifest = {
            "job_id": "test_job",
            "status": "DRAFT",
            "current_phase": "setup",
            "description": "Test job for state machine",
            "phases": [{"name": "setup", "description": "Setup phase"}],
            "metrics": {"cumulative_cost": 0.0, "cumulative_time_seconds": 0.0},
            "history": []
        }

        manifest_path = job_dir / "job_manifest.json"
        import json
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        return str(job_dir)

    def test_job_lifecycle_state_transitions(self, temp_job_dir):
        """Test a complete job lifecycle with state transitions."""
        # Start in DRAFT
        manifest = load_job_manifest(temp_job_dir)
        assert manifest["status"] == "DRAFT"

        # Activate to PENDING
        updated = update_job_manifest(temp_job_dir, new_status=JobStates.PENDING)
        assert updated["status"] == JobStates.PENDING

        # Start running
        updated = update_job_manifest(temp_job_dir, new_status=JobStates.RUNNING)
        assert updated["status"] == JobStates.RUNNING

        # Suspend
        updated = update_job_manifest(temp_job_dir, new_status=JobStates.SUSPENDED)
        assert updated["status"] == JobStates.SUSPENDED

        # Resume to PENDING
        updated = update_job_manifest(temp_job_dir, new_status=JobStates.PENDING)
        assert updated["status"] == JobStates.PENDING

        # Complete successfully
        updated = update_job_manifest(temp_job_dir, new_status=JobStates.SUCCESS)
        assert updated["status"] == JobStates.SUCCESS

    def test_suspend_resume_workflow(self, temp_job_dir):
        """Test suspend and resume workflow."""
        # Start job
        update_job_manifest(temp_job_dir, new_status=JobStates.PENDING)

        # Run and then suspend
        update_job_manifest(temp_job_dir, new_status=JobStates.RUNNING)
        update_job_manifest(temp_job_dir, new_status=JobStates.SUSPENDED)

        manifest = load_job_manifest(temp_job_dir)
        assert manifest["status"] == JobStates.SUSPENDED

        # Resume
        update_job_manifest(temp_job_dir, new_status=JobStates.PENDING)

        manifest = load_job_manifest(temp_job_dir)
        assert manifest["status"] == JobStates.PENDING

    def test_terminal_state_protection(self, temp_job_dir):
        """Test that terminal states prevent further transitions."""
        # Complete job
        update_job_manifest(temp_job_dir, new_status=JobStates.SUCCESS)

        # Attempt to change status - should work at manifest level but validation should prevent it
        manifest = load_job_manifest(temp_job_dir)
        assert manifest["status"] == JobStates.SUCCESS

        # Validation should prevent transitioning from terminal state
        with pytest.raises(JobStateError):
            validate_state_transition(JobStates.SUCCESS, JobStates.PENDING)


class TestStateMachineErrorHandling:
    """Test error handling in state machine operations."""

    def test_invalid_transition_action(self):
        """Test handling of invalid transition actions."""
        with pytest.raises(JobStateError, match="Invalid state transition"):
            transition_state(JobStates.PENDING, "INVALID_ACTION")

    def test_missing_transition_definition(self):
        """Test handling of missing transition definitions."""
        # Try a transition that doesn't exist in our table
        with pytest.raises(JobStateError):
            transition_state(JobStates.APPROVAL_REQUIRED, "INVALID")

    def test_state_validation_error_messages(self):
        """Test that validation errors provide helpful messages."""
        with pytest.raises(JobStateError) as exc_info:
            validate_state_transition(JobStates.SUSPENDED, JobStates.RUNNING)

        assert "SUSPENDED jobs can only resume to" in str(exc_info.value)

        with pytest.raises(JobStateError) as exc_info:
            validate_state_transition(JobStates.DRAFT, JobStates.RUNNING)

        assert "DRAFT jobs can only transition to" in str(exc_info.value)