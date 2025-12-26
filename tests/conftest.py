"""
Pytest configuration and fixtures for Logist testing.

This module provides shared fixtures and configuration for all tests,
particularly focusing on the new Agent/Runtime architecture.
"""

import os
import tempfile
import pytest
import shutil
from pathlib import Path

from src.logist.agents.mock import MockAgent
from src.logist.runtimes.host import HostRuntime


@pytest.fixture
def mock_runtime():
    """
    Fixture providing a HostRuntime instance for testing.

    Returns:
        HostRuntime: Configured runtime for testing agent execution
    """
    runtime = HostRuntime()
    yield runtime
    # Cleanup any remaining processes
    # Note: In a real implementation, we'd want to track and clean up all processes


@pytest.fixture
def job_dir():
    """
    Fixture providing a temporary directory for job testing.

    Creates a temporary directory that simulates a job workspace,
    and cleans it up after the test.

    Returns:
        Path: Path to the temporary job directory
    """
    temp_dir = tempfile.mkdtemp(prefix="logist_test_job_")
    job_path = Path(temp_dir)

    yield job_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_agent():
    """
    Fixture providing a MockAgent instance in success mode.

    Returns:
        MockAgent: Configured mock agent for testing
    """
    # Ensure we're in success mode by default
    original_mode = os.environ.get('MODE')
    os.environ['MODE'] = 'success'

    agent = MockAgent()

    yield agent

    # Restore original mode
    if original_mode is not None:
        os.environ['MODE'] = original_mode
    else:
        os.environ.pop('MODE', None)


@pytest.fixture(params=['success', 'api_error', 'context_full', 'auth_error'])
def mock_agent_modes(request):
    """
    Parameterized fixture providing MockAgent in different modes.

    Returns:
        MockAgent: Mock agent configured for the parameterized mode
    """
    mode = request.param
    original_mode = os.environ.get('MODE')
    os.environ['MODE'] = mode

    agent = MockAgent()

    yield agent

    # Restore original mode
    if original_mode is not None:
        os.environ['MODE'] = original_mode
    else:
        os.environ.pop('MODE', None)


@pytest.fixture
def temp_workspace():
    """
    Fixture providing a temporary workspace directory.

    Returns:
        Path: Path to temporary workspace directory
    """
    temp_dir = tempfile.mkdtemp(prefix="logist_test_workspace_")
    workspace_path = Path(temp_dir)

    # Create some basic workspace structure
    (workspace_path / "src").mkdir()
    (workspace_path / "tests").mkdir()

    yield workspace_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)