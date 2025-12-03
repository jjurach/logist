#!/usr/bin/env python3
"""
Diagnostic script to help debug pytest hanging issues.
Run individual tests to isolate hanging problems.
"""

import subprocess
import sys
import time

def run_test_with_timeout(test_cmd, timeout_seconds=30):
    """Run a test command with a timeout."""
    print(f"Running: {' '.join(test_cmd)}")
    print(f"Timeout: {timeout_seconds} seconds")

    try:
        result = subprocess.run(
            test_cmd,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            cwd="."
        )
        print(f"Exit code: {result.returncode}")
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"❌ COMMAND HUNG AFTER {timeout_seconds} SECONDS")
        print("This indicates a hanging test or blocking operation.")
        return False

def main():
    """Run diagnostic tests."""
    print("🔍 Logist Pytest Diagnostic Tool")
    print("=" * 50)

    # Test individual CLI tests
    cli_tests = [
        ["python3", "-m", "pytest", "tests/test_cli.py::TestCLICommands::test_job_create_command", "-v"],
        ["python3", "-m", "pytest", "tests/test_cli.py::TestCLICommands::test_command_uses_current_job", "-v"],
        ["python3", "-m", "pytest", "tests/test_cli.py::TestCLICommands::test_role_list_command_after_init", "-v"],
    ]

    for test_cmd in cli_tests:
        print(f"\n{'='*50}")
        success = run_test_with_timeout(test_cmd, timeout_seconds=30)
        if not success:
            print(f"❌ Test failed or hung: {' '.join(test_cmd)}")
        else:
            print(f"✅ Test passed: {' '.join(test_cmd)}")

    print(f"\n{'='*50}")
    print("📋 Summary:")
    print("If tests are hanging, it may be due to:")
    print("- Blocking file operations")
    print("- Network timeouts")
    print("- Subprocess calls without timeouts")
    print("- Infinite loops in test setup")
    print("\nTry running: pytest tests/ -x --tb=short")

if __name__ == "__main__":
    main()