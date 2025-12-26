"""
Mock Agent Implementation for Logist

This module provides a MockAgent that simulates AI agent behavior for testing
purposes without requiring external API calls or dependencies.
"""

import os
import sys
import time
from typing import List, Dict, Union

from .base import Agent


class MockAgent(Agent):
    """
    Mock agent that simulates realistic AI agent behavior for testing.

    Supports different execution modes via environment variables:
    - MODE=success: Completes successfully with realistic log output
    - MODE=hang: Goes silent for >120s to simulate hanging
    - MODE=api_error: Simulates API rate limit errors
    """

    def __init__(self):
        """Initialize the MockAgent."""
        self._mode = os.environ.get('MODE', 'success')

    def cmd(self, prompt: str) -> List[str]:
        """
        Generate command to execute the mock agent script.

        Args:
            prompt: The user prompt (used for logging but not processed)

        Returns:
            Command list to execute the mock agent
        """
        # Get the path to the mock agent script
        script_dir = os.path.dirname(__file__)
        mock_script = os.path.join(script_dir, 'mock_script.py')

        return [sys.executable, mock_script]

    def env(self) -> Dict[str, str]:
        """
        Get environment variables for mock agent execution.

        Returns:
            Environment variables including MODE setting
        """
        env = {
            'MOCK_AGENT_MODE': self._mode,
            'MOCK_AGENT_PROMPT': getattr(self, '_last_prompt', ''),
            'PYTHONPATH': os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        }

        # Add any existing environment variables that might be needed
        for key in ['PATH', 'HOME', 'USER', 'SHELL']:
            if key in os.environ:
                env[key] = os.environ[key]

        return env

    def get_stop_sequences(self) -> List[Union[str, str]]:
        """
        Get sequences that indicate the mock agent is waiting for input.

        For the mock agent, we simulate realistic interactive prompts.
        """
        return [
            "Confirm changes?",
            "Waiting for user input",
            "Enter your choice:",
            "Press Enter to continue",
            "(y/N)",
            "[y/N]",
            "[Y/n]",
        ]

    @property
    def name(self) -> str:
        """Get the agent name."""
        return f"MockAgent-{self._mode}"

    @property
    def version(self) -> str:
        """Get the agent version."""
        return "1.0.0"

    def set_prompt(self, prompt: str) -> None:
        """
        Set the prompt for the mock agent (for testing purposes).

        Args:
            prompt: The prompt to simulate processing
        """
        self._last_prompt = prompt