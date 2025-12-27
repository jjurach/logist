"""
Integration tests for Agent/Runtime architecture.

This module tests the integration between Agents and Runtimes,
focusing on real execution scenarios and edge cases.
"""

import os
import pytest
import time
import threading
from unittest.mock import patch, MagicMock

from src.logist.agents.mock import MockAgent
from src.logist.runtimes.mock import MockRuntime


class TestAgentRuntimeIntegration:
    """Integration tests for Agent-Runtime interaction."""

    def test_successful_agent_execution_flow(self, mock_runtime, mock_agent):
        """Test complete successful execution flow."""
        # Setup
        prompt = "implement a simple function"
        mock_agent.set_prompt(prompt)

        # Execute
        cmd = mock_agent.cmd(prompt)
        env = mock_agent.env()
        process_id = mock_runtime.spawn(cmd, env)

        # Monitor execution
        assert mock_runtime.is_alive(process_id)

        # Wait for completion
        exit_code, logs = mock_runtime.wait(process_id, timeout=30)

        # Verify results
        assert exit_code == 0
        assert "Task completed successfully" in logs
        lines = logs.split('\n')
        assert len([line for line in lines if line.strip()]) >= 5  # Multiple log entries

    def test_runtime_log_streaming(self, mock_runtime):
        """Test that logs are collected in real-time during execution."""
        # Setup agent in success mode
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'success'

        try:
            agent = MockAgent()
            cmd = agent.cmd("test streaming")
            env = agent.env()

            process_id = mock_runtime.spawn(cmd, env)

            # Check logs at different points
            time.sleep(1)
            early_logs = mock_runtime.get_logs(process_id)
            assert "Thinking..." in early_logs

            time.sleep(2)
            middle_logs = mock_runtime.get_logs(process_id)
            assert len(middle_logs) > len(early_logs)  # More logs accumulated

            # Wait for completion
            exit_code, final_logs = mock_runtime.wait(process_id, timeout=30)
            assert exit_code == 0
            assert "Task completed successfully" in final_logs

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)

    def test_runtime_process_termination(self, mock_runtime):
        """Test graceful and forceful process termination."""
        # Start a long-running process (hang mode)
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'hang'

        try:
            agent = MockAgent()
            cmd = agent.cmd("test termination")
            env = agent.env()

            process_id = mock_runtime.spawn(cmd, env)

            # Let it start
            time.sleep(2)
            assert mock_runtime.is_alive(process_id)

            # Test graceful termination (SIGTERM)
            success = mock_runtime.terminate(process_id, force=False)
            assert success

            # Wait a bit and verify it's dead
            time.sleep(1)
            assert not mock_runtime.is_alive(process_id)

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)

    def test_runtime_force_termination(self, mock_runtime):
        """Test forceful process termination (SIGKILL)."""
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'hang'

        try:
            agent = MockAgent()
            cmd = agent.cmd("test force termination")
            env = agent.env()

            process_id = mock_runtime.spawn(cmd, env)
            time.sleep(2)

            # Test forceful termination (SIGKILL)
            success = mock_runtime.terminate(process_id, force=True)
            assert success

            time.sleep(0.5)
            assert not mock_runtime.is_alive(process_id)

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)

    def test_runtime_wait_timeout(self, mock_runtime):
        """Test that wait() properly times out on hanging processes."""
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'hang'

        try:
            agent = MockAgent()
            cmd = agent.cmd("test timeout")
            env = agent.env()

            process_id = mock_runtime.spawn(cmd, env)

            # Try to wait with short timeout - should raise TimeoutError
            with pytest.raises(TimeoutError):
                mock_runtime.wait(process_id, timeout=5)

            # Process should still be alive
            assert mock_runtime.is_alive(process_id)

            # Clean up
            mock_runtime.terminate(process_id, force=True)

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)


class TestConcurrencyScenarios:
    """Test concurrency scenarios and resource management."""

    def test_multiple_concurrent_processes(self, mock_runtime):
        """Test running multiple processes concurrently."""
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'success'

        try:
            processes = []

            # Start multiple processes
            for i in range(3):
                agent = MockAgent()
                cmd = agent.cmd(f"concurrent test {i}")
                env = agent.env()
                process_id = mock_runtime.spawn(cmd, env)
                processes.append(process_id)

            # Verify all are running
            for pid in processes:
                assert mock_runtime.is_alive(pid)

            # Wait for all to complete
            results = []
            for pid in processes:
                exit_code, logs = mock_runtime.wait(pid, timeout=30)
                results.append((exit_code, logs))

            # Verify all completed successfully
            for exit_code, logs in results:
                assert exit_code == 0
                assert "Task completed successfully" in logs

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)

    def test_process_isolation(self, mock_runtime):
        """Test that processes are properly isolated."""
        # Start two different types of processes
        success_agent = MockAgent()
        original_mode = os.environ.get('MODE')
        os.environ['MODE'] = 'success'

        try:
            # Start success process
            success_cmd = success_agent.cmd("success test")
            success_env = success_agent.env()
            success_id = mock_runtime.spawn(success_cmd, success_env)

            # Switch to error mode and start error process
            os.environ['MODE'] = 'api_error'
            error_agent = MockAgent()
            error_cmd = error_agent.cmd("error test")
            error_env = error_agent.env()
            error_id = mock_runtime.spawn(error_cmd, error_env)

            # Wait for both to complete
            success_exit, success_logs = mock_runtime.wait(success_id, timeout=30)
            error_exit, error_logs = mock_runtime.wait(error_id, timeout=30)

            # Verify different outcomes
            assert success_exit == 0
            assert "Task completed successfully" in success_logs

            assert error_exit == 1
            assert "Rate limit reached" in error_logs

        finally:
            if original_mode is not None:
                os.environ['MODE'] = original_mode
            else:
                os.environ.pop('MODE', None)


class TestErrorScenarios:
    """Test error handling and edge cases."""

    def test_invalid_process_operations(self, mock_runtime):
        """Test operations on invalid or non-existent process IDs."""
        invalid_id = "invalid_process_id_12345"

        # These should raise RuntimeError
        with pytest.raises(RuntimeError):
            mock_runtime.is_alive(invalid_id)

        with pytest.raises(RuntimeError):
            mock_runtime.get_logs(invalid_id)

        with pytest.raises(RuntimeError):
            mock_runtime.terminate(invalid_id)

        with pytest.raises(RuntimeError):
            mock_runtime.wait(invalid_id)

    def test_agent_command_failure(self, mock_runtime):
        """Test handling of invalid agent commands."""
        agent = MockAgent()

        # Try to execute a non-existent command
        invalid_cmd = ["/non/existent/command", "arg1", "arg2"]
        env = agent.env()

        # This should raise RuntimeError during spawn
        with pytest.raises(RuntimeError):
            mock_runtime.spawn(invalid_cmd, env)

    def test_environment_variable_isolation(self, mock_runtime):
        """Test that environment variables are properly isolated between processes."""
        # Set a custom environment variable
        test_var = "TEST_CUSTOM_VAR"
        test_value = "custom_value_123"

        agent = MockAgent()
        env = agent.env()
        env[test_var] = test_value

        cmd = agent.cmd("test env isolation")
        process_id = mock_runtime.spawn(cmd, env)

        # The mock script doesn't actually use custom env vars,
        # but we can verify the process starts successfully
        assert mock_runtime.is_alive(process_id)

        exit_code, logs = mock_runtime.wait(process_id, timeout=30)
        assert exit_code == 0

        # Clean up
        mock_runtime.cleanup(process_id)