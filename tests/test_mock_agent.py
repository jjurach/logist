"""
Tests for MockAgent functionality.

This module tests the MockAgent implementation and its various modes.
"""

import os
import pytest
import time
from unittest.mock import patch, MagicMock

from src.logist.agents.mock import MockAgent
from src.logist.runtimes.host import HostRuntime


class TestMockAgent:
    """Test cases for MockAgent basic functionality."""

    def test_mock_agent_creation(self, mock_agent):
        """Test that MockAgent can be created and has correct defaults."""
        assert mock_agent.name == "MockAgent-success"
        assert mock_agent.version == "1.0.0"

    def test_mock_agent_cmd_generation(self, mock_agent):
        """Test that cmd() generates correct command list."""
        cmd = mock_agent.cmd("test prompt")
        assert isinstance(cmd, list)
        assert len(cmd) == 2  # python executable + script path
        assert cmd[0].endswith("python") or cmd[0].endswith("python3")
        assert cmd[1].endswith("mock_script.py")

    def test_mock_agent_env_variables(self, mock_agent):
        """Test that env() returns correct environment variables."""
        env = mock_agent.env()
        assert 'MOCK_AGENT_MODE' in env
        assert env['MOCK_AGENT_MODE'] == 'success'
        assert 'PYTHONPATH' in env
        assert 'PATH' in env  # Should include system PATH

    def test_mock_agent_stop_sequences(self, mock_agent):
        """Test that get_stop_sequences() returns expected patterns."""
        sequences = mock_agent.get_stop_sequences()
        assert isinstance(sequences, list)
        assert "Confirm changes?" in sequences
        assert "Waiting for user input" in sequences
        assert "(y/N)" in sequences

    @pytest.mark.parametrize("mode", ["success", "hang", "api_error", "context_full", "auth_error"])
    def test_mock_agent_mode_configuration(self, mode):
        """Test that MockAgent correctly reads MODE environment variable."""
        original_mode = os.environ.get('MODE')
        try:
            os.environ['MODE'] = mode
            agent = MockAgent()
            assert agent.name == f"MockAgent-{mode}"
            assert agent._mode == mode
        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)


class TestMockAgentIntegration:
    """Integration tests combining MockAgent with HostRuntime."""

    def test_mock_agent_success_execution(self, mock_runtime, mock_agent):
        """Test successful execution of MockAgent."""
        # Set up the agent
        mock_agent.set_prompt("test successful execution")

        # Get command and environment
        cmd = mock_agent.cmd("test successful execution")
        env = mock_agent.env()

        # Spawn the process
        process_id = mock_runtime.spawn(cmd, env)

        # Wait for completion
        exit_code, logs = mock_runtime.wait(process_id, timeout=30)

        # Verify successful execution
        assert exit_code == 0
        assert "Task completed successfully" in logs
        assert "Thinking..." in logs

    def test_mock_agent_api_error_execution(self, mock_runtime):
        """Test MockAgent execution with API error mode."""
        # Set mode to api_error
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'api_error'

        try:
            agent = MockAgent()
            cmd = agent.cmd("test api error")
            env = agent.env()

            # Spawn and wait
            process_id = mock_runtime.spawn(cmd, env)
            exit_code, logs = mock_runtime.wait(process_id, timeout=10)

            # Verify error execution
            assert exit_code == 1
            assert "API Error: Rate limit reached (429)" in logs
            assert "Too Many Requests" in logs

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)

    def test_mock_agent_context_full_execution(self, mock_runtime):
        """Test MockAgent execution with context full error mode."""
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'context_full'

        try:
            agent = MockAgent()
            cmd = agent.cmd("test context full")
            env = agent.env()

            process_id = mock_runtime.spawn(cmd, env)
            exit_code, logs = mock_runtime.wait(process_id, timeout=10)

            assert exit_code == 1
            assert "Token limit exceeded" in logs
            assert "Context length is too large" in logs

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)

    def test_mock_agent_hang_detection_setup(self, mock_runtime):
        """Test that hang mode can be initiated (doesn't wait for completion)."""
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'hang'

        try:
            agent = MockAgent()
            cmd = agent.cmd("test hanging")
            env = agent.env()

            # Start the process
            process_id = mock_runtime.spawn(cmd, env)

            # Let it start and begin hanging
            time.sleep(2)

            # Verify it's still alive initially
            assert mock_runtime.is_alive(process_id)

            # Get some logs to verify it started
            logs = mock_runtime.get_logs(process_id)
            assert "Thinking..." in logs

            # Terminate it before it hangs too long
            assert mock_runtime.terminate(process_id, force=True)

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)


class TestMockAgentParameterized:
    """Parameterized tests for different MockAgent modes."""

    @pytest.mark.parametrize("mode,expected_exit_code,expected_log_pattern", [
        ("success", 0, "Task completed successfully"),
        ("api_error", 1, "Rate limit reached"),
        ("context_full", 1, "Token limit exceeded"),
        ("auth_error", 1, "Authentication failed"),
    ])
    def test_mock_agent_modes(self, mock_runtime, mode, expected_exit_code, expected_log_pattern):
        """Test MockAgent execution across different modes."""
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = mode

        try:
            agent = MockAgent()
            cmd = agent.cmd(f"test {mode} mode")
            env = agent.env()

            process_id = mock_runtime.spawn(cmd, env)
            exit_code, logs = mock_runtime.wait(process_id, timeout=15)

            assert exit_code == expected_exit_code
            assert expected_log_pattern in logs

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)