#!/usr/bin/env python3
"""
Oneshot Start Interface - Cline Oneshot Research Unit

Launches oneshot Cline executions and returns task IDs for monitoring.
"""
import subprocess
import sys
import json
import os
from datetime import datetime
from argparse import ArgumentParser

def run_command(cmd):
    """Run a command and return (returncode, stdout, stderr)"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def get_latest_task_id():
    """Get the most recent task ID from task list"""
    returncode, stdout, stderr = run_command("cline task list --output-format json")
    if returncode != 0:
        print(f"Error getting task list: {stderr}", file=sys.stderr)
        return None

    # Parse the task list output
    lines = stdout.strip().split('\n')
    task_id = None
    for line in lines:
        if line.startswith('Task ID: '):
            task_id = line.split(': ')[1].strip()
    return task_id

def start_oneshot(prompt, model="grok-code-fast-1", no_interactive=True):
    """
    Start a oneshot execution and return the task ID

    Args:
        prompt (str): The task prompt
        model (str): Optional model specification
        no_interactive (bool): Whether to run non-interactively

    Returns:
        str: Task ID if successful, None if failed
    """
    # Build the command
    cmd = f'cline "{prompt}" --oneshot'
    if no_interactive:
        cmd += ' --no-interactive'
    if model:
        cmd += f' --model {model}'

    print(f"Starting oneshot task: {prompt[:50]}...", file=sys.stderr)

    # Get current latest task ID before execution
    pre_task_id = get_latest_task_id()

    # Execute the oneshot command
    returncode, stdout, stderr = run_command(cmd)

    if returncode != 0:
        print(f"Error starting oneshot task: {stderr}", file=sys.stderr)
        return None

    print(stdout, file=sys.stderr)

    # Get the new latest task ID after execution
    post_task_id = get_latest_task_id()

    # Return the new task ID (different from pre-execution ID)
    if post_task_id and post_task_id != pre_task_id:
        return post_task_id

    print("Could not determine task ID", file=sys.stderr)
    return None

def main():
    parser = ArgumentParser(description="Start a Cline oneshot task")
    parser.add_argument('prompt', help='Task prompt')
    parser.add_argument('--model', '-m', default="grok-code-fast-1", help='Model to use (default: grok-code-fast-1)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Allow interactive mode (default: no-interactive)')

    args = parser.parse_args()

    task_id = start_oneshot(
        prompt=args.prompt,
        model=args.model,
        no_interactive=not args.interactive
    )

    if task_id:
        print(task_id)
        return 0
    else:
        print("Failed to start oneshot task", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())