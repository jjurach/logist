#!/usr/bin/env python3
"""
Mock Agent Script for Logist Testing

This script simulates realistic AI agent behavior for testing purposes.
It supports different execution modes to test various scenarios.
"""

import os
import sys
import time
import random


def simulate_success():
    """Simulate a successful agent execution."""
    print("Thinking...", flush=True)
    time.sleep(random.uniform(0.5, 2.0))

    print("Analyzing requirements...", flush=True)
    time.sleep(random.uniform(1.0, 3.0))

    print("Planning implementation...", flush=True)
    time.sleep(random.uniform(0.5, 1.5))

    print("Applying changes...", flush=True)
    time.sleep(random.uniform(2.0, 5.0))

    print("Running tests...", flush=True)
    time.sleep(random.uniform(1.0, 3.0))

    print("Task completed successfully.", flush=True)
    return 0


def simulate_hang():
    """Simulate an agent that hangs (goes silent for >120s)."""
    print("Thinking...", flush=True)
    time.sleep(random.uniform(0.5, 2.0))

    print("Processing request...", flush=True)
    time.sleep(random.uniform(1.0, 3.0))

    # Go silent for more than 120 seconds to simulate hanging
    print("Working on complex analysis...", flush=True)
    time.sleep(130)  # Exceeds the 120s timeout

    # This should never be reached if sentinel kills the process
    print("Task completed successfully.", flush=True)
    return 0


def simulate_api_error():
    """Simulate an API error scenario."""
    print("Thinking...", flush=True)
    time.sleep(random.uniform(0.5, 2.0))

    print("Preparing API request...", flush=True)
    time.sleep(random.uniform(1.0, 2.0))

    # Simulate API rate limit error
    print("API Error: Rate limit reached (429)", flush=True)
    print("Too Many Requests - please try again later.", flush=True)
    return 1


def simulate_context_full():
    """Simulate context length exceeded error."""
    print("Thinking...", flush=True)
    time.sleep(random.uniform(0.5, 2.0))

    print("Processing large codebase...", flush=True)
    time.sleep(random.uniform(1.0, 3.0))

    print("Token limit exceeded.", flush=True)
    print("Context length is too large for this model.", flush=True)
    return 1


def simulate_auth_error():
    """Simulate authentication error."""
    print("Initializing...", flush=True)
    time.sleep(random.uniform(0.5, 1.0))

    print("Authentication failed.", flush=True)
    print("Invalid API key provided.", flush=True)
    return 1


def simulate_interactive():
    """Simulate an agent that requires user input."""
    print("Thinking...", flush=True)
    time.sleep(random.uniform(0.5, 2.0))

    print("Analyzing changes...", flush=True)
    time.sleep(random.uniform(1.0, 3.0))

    print("Found potential issues that need confirmation.", flush=True)
    time.sleep(random.uniform(0.5, 1.0))

    print("Confirm changes? [y/N]: ", end='', flush=True)

    # Wait for user input (this will cause the agent to appear "hung" from the outside)
    try:
        response = input()
        if response.lower() in ['y', 'yes']:
            print("Applying changes...", flush=True)
            time.sleep(random.uniform(1.0, 3.0))
            print("Task completed successfully.", flush=True)
            return 0
        else:
            print("Changes cancelled by user.", flush=True)
            return 1
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.", flush=True)
        return 1


def main():
    """Main entry point for the mock agent script."""
    # Get the mode from environment variable
    mode = os.environ.get('MOCK_AGENT_MODE', 'success')

    # Map mode to function
    mode_functions = {
        'success': simulate_success,
        'hang': simulate_hang,
        'api_error': simulate_api_error,
        'context_full': simulate_context_full,
        'auth_error': simulate_auth_error,
        'interactive': simulate_interactive,
    }

    # Get the function for this mode, default to success
    simulate_func = mode_functions.get(mode, simulate_success)

    try:
        # Run the simulation
        exit_code = simulate_func()
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nMock agent interrupted.", flush=True)
        sys.exit(130)  # Standard SIGINT exit code

    except Exception as e:
        print(f"Unexpected error in mock agent: {e}", flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()