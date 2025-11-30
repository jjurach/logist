#!/usr/bin/env python3
"""
Oneshot Monitor Interface - Cline Oneshot Research Unit

Monitors oneshot task completion, detects inactivity, and auto-restarts stuck tasks.
Provides watchdog functionality for batch processing workflows.
"""
import subprocess
import sys
import json
import os
import time
import signal
import argparse
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime

CLINE_DATA_DIR = Path.home() / '.cline' / 'data' / 'tasks'

def run_command(cmd):
    """Run a command and return (returncode, stdout, stderr)"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def get_task_metadata(task_id):
    """Get task metadata from file system"""
    task_dir = CLINE_DATA_DIR / task_id
    metadata_file = task_dir / 'task_metadata.json'

    if not metadata_file.exists():
        return None

    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

def get_task_from_list(task_id):
    """Get task information from cline task list command"""
    returncode, stdout, stderr = run_command("cline task list --output-format json")
    if returncode != 0:
        return None

    lines = stdout.strip().split('\n')
    current_task = {}

    for line in lines:
        line = line.strip()
        if line.startswith('Task ID: ') and line.split(': ')[1].strip() == task_id:
            current_task['task_id'] = task_id
            continue
        elif line.startswith('Task ID: '):
            # New task started, save previous if it matches
            if current_task and current_task.get('task_id') == task_id:
                break
            current_task = {'task_id': line.split(': ')[1].strip()}
        elif line.startswith('Message: '):
            current_task['message'] = line.split(': ', 1)[1] if ': ' in line else ''
        elif line.startswith('Usage  :'):
            # Parse usage line like "↑ 11.1k ↓ 455 → 512 $0.0000"
            usage = line.split(': ', 1)[1] if ': ' in line else line
            current_task['usage'] = usage

    return current_task if current_task.get('task_id') == task_id else None

def is_task_complete(task_id, metadata, timeout_minutes=10):
    """Determine if task is complete based on metadata and activity"""
    if not metadata:
        return False, "NO_METADATA"

    # Check if task directory exists and has been inactive
    task_dir = CLINE_DATA_DIR / task_id
    if not task_dir.exists():
        return False, "TASK_NOT_FOUND"

    # Get latest model usage timestamp
    model_usage = metadata.get('model_usage', [])
    if not model_usage:
        return False, "NO_ACTIVITY"

    latest_ts = max(entry.get('ts', 0) for entry in model_usage)
    current_ts = int(time.time() * 1000)  # milliseconds

    # If no activity in timeout period, consider complete
    inactive_ms = current_ts - latest_ts
    timeout_ms = timeout_minutes * 60 * 1000

    if inactive_ms > timeout_ms:
        return True, "TIMEOUT_COMPLETE"
    else:
        return False, "ACTIVE"

def extract_metadata(task_id, metadata, task_info):
    """Extract relevant metadata for research"""
    result = {
        'task_id': task_id,
        'status': 'UNKNOWN',
        'model': 'unknown',
        'tokens_used': 0,
        'cost_usd': 0.0,
        'created_at': None,
        'completed_at': None,
        'api_calls': 0,
        'evidence_files': [],
        'summary': 'monitored task'
    }

    # Extract from metadata
    if metadata:
        model_usage = metadata.get('model_usage', [])
        result['api_calls'] = len(model_usage)

        if model_usage:
            # Get model from first usage
            result['model'] = model_usage[0].get('model_id', 'unknown')

            # Get timestamps
            timestamps = [entry.get('ts', 0) for entry in model_usage]
            if timestamps:
                result['created_at'] = min(timestamps) / 1000  # Convert to seconds
                result['completed_at'] = max(timestamps) / 1000

        # Extract files modified
        files_context = metadata.get('files_in_context', [])
        result['evidence_files'] = [f.get('path', '') for f in files_context if f.get('record_state') == 'active']

    # Extract from task list if available
    if task_info and 'usage' in task_info:
        # Parse usage string like "↑ 11.1k ↓ 455 → 512 $0.0000"
        usage = task_info['usage']
        # This is a simplified extraction - in practice would need more sophisticated parsing

    return result

def kill_process(pid):
    """Kill a process gracefully with SIGTERM first, then SIGKILL if needed."""
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(2)  # Give process time to terminate gracefully

        # Check if still running
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
            # If we get here, process is still running, force kill it
            os.kill(pid, signal.SIGKILL)
            print(f"Forcibly terminated stuck process {pid}", file=sys.stderr)
        except OSError:
            print(f"Gracefully terminated process {pid}", file=sys.stderr)

        return True
    except OSError as e:
        print(f"Failed to terminate process {pid}: {e}", file=sys.stderr)
        return False

def restart_task(task_id, verbose=False):
    """Restart a stuck task using cline task open with --oneshot --yolo."""
    restart_cmd = f"cline task open {task_id} --oneshot --yolo"
    if verbose:
        print(f"Restarting task with: {restart_cmd}", file=sys.stderr)

    returncode, stdout, stderr = run_command(restart_cmd)

    if returncode != 0:
        print(f"Restart command failed: {stderr.strip()}", file=sys.stderr)
        return False

    print(f"Successfully restarted task {task_id}", file=sys.stderr)
    return True

def monitor_task(
    task_id,
    poll_interval=5,
    timeout_minutes=10,
    auto_restart=False,
    max_retries=3,
    process_pid=None,
    verbose=False
):
    """
    Monitor a task until completion, with optional automatic restart

    Args:
        task_id (str): Task ID to monitor
        poll_interval (int): Seconds between polls
        timeout_minutes (int): Maximum wait time for inactivity
        auto_restart (bool): Enable automatic restart of stuck tasks
        max_retries (int): Maximum number of restart attempts
        process_pid (int): PID of the task process to kill before restart
        verbose (bool): Enable verbose logging

    Returns:
        dict: Task completion metadata with restart information
    """
    start_time = time.time()
    restart_count = 0
    last_restart_time = 0

    print(f"Monitoring task {task_id} (auto_restart={'enabled' if auto_restart else 'disabled'})...", file=sys.stderr)

    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time

        # Check if we've exceeded global timeout (can be longer due to restarts)
        if elapsed_time > (timeout_minutes * 60):
            print(f"Global monitoring timeout exceeded for task {task_id}", file=sys.stderr)
            break

        metadata = get_task_metadata(task_id)
        task_info = get_task_from_list(task_id)

        is_complete, status_reason = is_task_complete(task_id, metadata, timeout_minutes)

        if is_complete:
            # Check if this is a timeout completion and restart is enabled
            if status_reason == "TIMEOUT_COMPLETE" and auto_restart and restart_count < max_retries:
                # Only restart if we haven't restarted too recently (prevent rapid restart loops)
                if current_time - last_restart_time > 60:  # Minimum 1 minute between restarts
                    print(f"Task {task_id} appears stuck (inactive > {timeout_minutes}min), attempting restart...", file=sys.stderr)

                    # Kill the stuck process if PID provided
                    if process_pid:
                        kill_process(process_pid)

                    # Attempt restart
                    if restart_task(task_id, verbose):
                        restart_count += 1
                        last_restart_time = current_time
                        print(f"Restart #{restart_count} completed for task {task_id}", file=sys.stderr)

                        # Continue monitoring (don't return yet)
                        continue
                    else:
                        print(f"Restart #{restart_count + 1} failed for task {task_id}", file=sys.stderr)
                        break
                else:
                    print(f"Skipping restart for task {task_id} (too soon after last restart)", file=sys.stderr)
            else:
                # Task is genuinely complete or no restart available
                if status_reason == "TIMEOUT_COMPLETE" and auto_restart:
                    print(f"Task {task_id} remained stuck after {restart_count}/{max_retries} restart attempts", file=sys.stderr)
                else:
                    print(f"Task {task_id} completed: {status_reason}", file=sys.stderr)

                result = extract_metadata(task_id, metadata, task_info)
                result['restart_attempts'] = restart_count
                return result
        else:
            if verbose:
                print(f"Task {task_id} status: {status_reason}, waiting {poll_interval}s...", file=sys.stderr)
            time.sleep(poll_interval)

    # Final timeout with retry information
    print(f"Final timeout for task {task_id}", file=sys.stderr)
    metadata = get_task_metadata(task_id)
    task_info = get_task_from_list(task_id)
    result = extract_metadata(task_id, metadata, task_info)
    result['status'] = 'FINAL_TIMEOUT'
    result['restart_attempts'] = restart_count
    return result

def main():
    parser = ArgumentParser(
        description="Monitor a Cline oneshot task with automatic restart capability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic monitoring:    oneshot-monitor.py 1734567890123
  With auto-restart:   oneshot-monitor.py 1734567890123 --auto-restart --pid 12345
  Verbose monitoring:  oneshot-monitor.py 1734567890123 --verbose --json
        """
    )
    parser.add_argument('task_id', help='Task ID to monitor')
    parser.add_argument('--poll-interval', '-i', type=int, default=5,
                       help='Poll interval in seconds (default: 5)')
    parser.add_argument('--timeout', '-t', type=int, default=10,
                       help='Timeout per activity period in minutes (default: 10)')
    parser.add_argument('--json', '-j', action='store_true',
                       help='Output as JSON')

    # Auto-restart functionality arguments
    parser.add_argument('--auto-restart', '-r', action='store_true',
                       help='Enable automatic restart of stuck tasks using "cline task open <id> --oneshot --yolo"')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Maximum restart attempts (default: 3)')
    parser.add_argument('--pid', type=int,
                       help='Process ID of running task to terminate before restart')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging of monitoring activity')

    args = parser.parse_args()

    result = monitor_task(
        task_id=args.task_id,
        poll_interval=args.poll_interval,
        timeout_minutes=args.timeout,
        auto_restart=args.auto_restart,
        max_retries=args.max_retries,
        process_pid=args.pid,
        verbose=args.verbose
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Task ID: {result['task_id']}")
        print(f"Status: {result['status']}")
        print(f"Model: {result['model']}")
        print(f"API Calls: {result['api_calls']}")
        print(f"Cost: ${result['cost_usd']:.4f}")
        print(f"Created: {datetime.fromtimestamp(result['created_at']) if result['created_at'] else 'Unknown'}")
        print(f"Completed: {datetime.fromtimestamp(result['completed_at']) if result['completed_at'] else 'Unknown'}")
        print(f"Files: {', '.join(result['evidence_files'])}")
        if 'restart_attempts' in result:
            print(f"Restart Attempts: {result['restart_attempts']}")

if __name__ == '__main__':
    sys.exit(main())