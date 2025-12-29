"""
Pytest configuration and fixtures for Logist testing.

This module provides shared fixtures and configuration for all tests,
particularly focusing on the new Agent/Runtime architecture.

IMPORTANT: This module includes safety fixtures that prevent tests from
modifying the actual git repository (creating branches, checking out, etc.).
"""

import os
import tempfile
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch

from src.logist.agents.mock import MockAgent
from src.logist.runners.mock import MockRunner


@pytest.fixture(autouse=True)
def prevent_git_operations_on_real_repo():
    """
    Autouse fixture that prevents tests from performing git operations
    on the actual logist repository.

    This patches find_git_root() to return None, which causes workspace
    operations to fail safely rather than creating branches in the real repo.
    """
    with patch('logist.workspace_utils.find_git_root', return_value=None):
        yield

# Import new mock agent framework
from tests.test_utils.mock_agent_utils import (
    mock_agent_helper,
    mock_worker_agent,
    mock_supervisor_agent,
    deterministic_mock_worker
)


@pytest.fixture
def mock_runner():
    """
    Fixture providing a MockRunner instance for testing.

    Returns:
        MockRunner: Configured mock runner for testing agent execution
    """
    runner = MockRunner()
    yield runner
    # Mock runner handles its own cleanup


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