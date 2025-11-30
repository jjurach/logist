#!/usr/bin/env python3
"""
Batch Executor - Enhanced Oneshot Task Manager

Runs Cline oneshot tasks with automatic monitoring and restart capabilities.
Provides reliable batch processing for multiple tasks with watchdog functionality.
"""
import subprocess
import sys
import json
import os
import time
import argparse
from pathlib import Path
from datetime import datetime

# Import our monitoring functions
sys.path.insert(0, str(Path(__file__).parent))
from oneshot_monitor import monitor_task

def run_command(cmd, verbose=False):
    """Run a command and return (returncode, stdout, stderr)"""
    if verbose:
        print(f"Executing: {cmd}", file=sys.stderr)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def launch_oneshot_task(prompt, model="grok-code-fast-1", context_files=None, verbose=False):
    """
    Launch a oneshot task and return task ID and process info.

    Args:
        prompt (str): Task prompt
        model (str): LLM model to use
        context_files (list): Files to include as context
        verbose (bool): Enable verbose logging

    Returns:
        tuple: (task_id or None, process_info or None)
    """
    # Build cline command
    cmd = ["cline", "--oneshot", "--no-interactive"]
    cmd.extend(["--model", model])

    if context_files:
        for context_file in context_files:
            cmd.extend(["--context", context_file])

    # Create a script file with the prompt
    script_content = f"""#!/bin/bash
{prompt}
"""
    script_file = Path("temp_task.sh")
    script_file.write_text(script_content)
    script_file.chmod(0o755)

    cmd.append(str(script_file))

    # Launch in background and capture PID
    full_cmd = " ".join(cmd)
    if verbose:
        print(f"Launching task: {full_cmd}", file=sys.stderr)

    # Use nohup to run in background and capture process info
    bg_cmd = f"nohup {full_cmd} > task_output.log 2>&1 & echo $!"
    returncode, stdout, stderr = run_command(bg_cmd, verbose)

    if returncode != 0:
        print(f"Failed to launch task: {stderr}", file=sys.stderr)
        if script_file.exists():
            script_file.unlink()
        return None, None

    try:
        pid = int(stdout.strip())
        if verbose:
            print(f"Launched task with PID: {pid}", file=sys.stderr)

        # Wait a moment for task to initialize
        time.sleep(2)

        # For now, we'll need to manually get the task ID
        # In practice, you might need to parse CLI output or logs
        task_id = f"task_{int(time.time() * 1000)}"  # Placeholder

        # Clean up script file
        if script_file.exists():
            script_file.unlink()

        return task_id, {"pid": pid, "command": full_cmd}

    except (ValueError, IndexError) as e:
        print(f"Failed to parse PID from output: {e}", file=sys.stderr)
        return None, None

def batch_execute_tasks(tasks, model="grok-code-fast-1", auto_restart=True, timeout_minutes=10, verbose=False):
    """
    Execute multiple tasks in batch with monitoring and restart.

    Args:
        tasks (list): List of task dictionaries with 'prompt', 'context_files', etc.
        model (str): LLM model to use
        auto_restart (bool): Enable auto-restart of stuck tasks
        timeout_minutes (int): Timeout per task
        verbose (bool): Enable verbose logging

    Returns:
        list: Task execution results
    """
    results = []

    print(f"Starting batch execution of {len(tasks)} tasks...", file=sys.stderr)

    for i, task_config in enumerate(tasks, 1):
        task_name = task_config.get('name', f'Task {i}')
        prompt = task_config['prompt']
        context_files = task_config.get('context_files')

        print(f"\n--- Executing {task_name} ({i}/{len(tasks)}) ---", file=sys.stderr)

        # Launch the task
        task_id, process_info = launch_oneshot_task(
            prompt=prompt,
            model=model,
            context_files=context_files,
            verbose=verbose
        )

        if not task_id or not process_info:
            print(f"Failed to launch {task_name}", file=sys.stderr)
            results.append({
                'task_name': task_name,
                'status': 'LAUNCH_FAILED',
                'task_id': None,
                'restart_attempts': 0
            })
            continue

        print(f"Monitoring {task_name} (ID: {task_id})...", file=sys.stderr)

        # Monitor with auto-restart capability
        try:
            monitor_result = monitor_task(
                task_id=task_id,
                poll_interval=5,
                timeout_minutes=timeout_minutes,
                auto_restart=auto_restart,
                max_retries=3,
                process_pid=process_info['pid'],
                verbose=verbose
            )

            monitor_result['task_name'] = task_name
            results.append(monitor_result)

        except Exception as e:
            print(f"Monitoring failed for {task_name}: {e}", file=sys.stderr)
            results.append({
                'task_name': task_name,
                'status': 'MONITOR_FAILED',
                'error': str(e),
                'task_id': task_id,
                'restart_attempts': 0
            })

    print(f"\nBatch execution completed. Results for {len(results)} tasks.", file=sys.stderr)
    return results

def main():
    """Main entry point for batch executor."""
    parser = argparse.ArgumentParser(
        description="Execute multiple Cline oneshot tasks with monitoring and auto-restart",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Execute from JSON file:  batch-executor.py tasks.json
  Execute single task:     batch-executor.py --prompt "Create a hello world script" --name "HelloTask"
  With auto-restart:       batch-executor.py --prompt "..." --auto-restart --timeout 15
        """
    )

    parser.add_argument(
        'task_file',
        nargs='?',
        help='JSON file containing task definitions (optional if --prompt used)'
    )

    parser.add_argument(
        '--prompt', '-p',
        help='Single task prompt (creates a single-task batch)'
    )

    parser.add_argument(
        '--name', '-n',
        default='Task',
        help='Name for single task (default: Task)'
    )

    parser.add_argument(
        '--model', '-m',
        default='gpt-4',
        help='LLM model to use (default: grok-code-fast-1)'
    )

    parser.add_argument(
        '--auto-restart', '-r',
        action='store_true',
        help='Enable automatic restart of stuck tasks'
    )

    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=10,
        help='Timeout per task in minutes (default: 10)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output file for results (default: stdout)'
    )

    parser.add_argument(
        '--json-output',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.task_file and not args.prompt:
        print("Error: Must provide either a task file or a single task prompt (--prompt)", file=sys.stderr)
        sys.exit(1)

    # Load tasks
    if args.task_file:
        if not os.path.exists(args.task_file):
            print(f"Error: Task file '{args.task_file}' not found", file=sys.stderr)
            sys.exit(1)

        with open(args.task_file, 'r') as f:
            tasks = json.load(f)
    else:
        # Create single task from prompt
        tasks = [{
            'name': args.name,
            'prompt': args.prompt,
            'context_files': []
        }]

    # Execute batch
    results = batch_execute_tasks(
        tasks=tasks,
        model=args.model,
        auto_restart=args.auto_restart,
        timeout_minutes=args.timeout,
        verbose=args.verbose
    )

    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results written to {args.output}", file=sys.stderr)
    elif args.json_output:
        print(json.dumps(results, indent=2))
    else:
        # Human-readable summary
        print("\n📊 Batch Execution Summary")
        print("=" * 50)

        completed = sum(1 for r in results if r.get('status') not in ['LAUNCH_FAILED', 'MONITOR_FAILED'])
        total_restarts = sum(r.get('restart_attempts', 0) for r in results)

        print(f"Tasks Processed: {len(results)}")
        print(f"Successful Tasks: {completed}")
        print(f"Total Restarts: {total_restarts}")

        print("\n📋 Task Details:")
        for result in results:
            status_indicator = "✅" if result.get('status') not in ['LAUNCH_FAILED', 'MONITOR_FAILED'] else "❌"
            restarts = result.get('restart_attempts', 0)
            print(f"  {status_indicator} {result.get('task_name', 'Unknown')}: {result.get('status', 'Unknown')} (restarts: {restarts})")

    # Exit with success/failure based on results
    failed_tasks = sum(1 for r in results if r.get('status') in ['LAUNCH_FAILED', 'MONITOR_FAILED'])
    sys.exit(0 if failed_tasks == 0 else 1)

if __name__ == "__main__":
    main()