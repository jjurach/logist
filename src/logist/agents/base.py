"""
Base Agent Interface for Logist

This module defines the abstract base class for all Agent implementations in Logist.
Agents are responsible for translating high-level prompts into executable commands
and providing the necessary environment configuration.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Union, Optional


class Agent(ABC):
    """
    Abstract base class for all Logist agents.

    Agents encapsulate the logic for converting user prompts into executable
    commands and providing the necessary runtime environment configuration.
    """

    @abstractmethod
    def cmd(self, prompt: str) -> List[str]:
        """
        Convert a user prompt into a list of shell command arguments.

        Args:
            prompt: The user prompt describing the desired action

        Returns:
            List of command arguments suitable for subprocess execution

        Example:
            For a prompt "run tests", this might return:
            ["python", "-m", "pytest", "tests/"]
        """
        pass

    @abstractmethod
    def env(self) -> Dict[str, str]:
        """
        Get environment variables required for agent execution.

        Returns:
            Dictionary of environment variable names to values

        Example:
            {"OPENAI_API_KEY": "sk-...", "LOG_LEVEL": "INFO"}
        """
        pass

    @abstractmethod
    def get_stop_sequences(self) -> List[Union[str, str]]:
        """
        Get sequences that indicate the agent is waiting for user input.

        Returns:
            List of strings or regex patterns that signal the agent
            is in an interactive state requiring user intervention.

        Note:
            These sequences are used by the Runner to detect when
            the agent process is blocked waiting for input.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the human-readable name of this agent.

        Returns:
            String identifier for the agent type
        """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """
        Get the version of this agent implementation.

        Returns:
            Version string (e.g., "1.0.0")
        """
        pass