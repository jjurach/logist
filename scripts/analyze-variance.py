#!/usr/bin/env python3
"""
Variance Analysis Tool - Cline Oneshot Research Unit

Analyzes cost/token variance from test execution logs.
"""
import json
import sys
import os
import statistics
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime
import re

def parse_usage_string(usage_str):
    """
    Parse usage string like '↑ 11.1k ↓ 455 → 512 $0.0000'

    Returns (input_tokens, output_tokens, total_tokens, cost_usd) or None
    """
    if not usage_str:
        return None

    # Extract numbers and units
    # Pattern: ↑ 11.1k ↓ 455 → 512 $0.0000
    pattern = r'↑\s*([\d.]+)([km]?)\s*↓\s*(\d+)([km]?)\s*→\s*([\d.]+)([km]?)\s*\$\s*([\d.]+)'
    match = re.search(pattern, usage_str)

    if not match:
        return None

    input_val, input_unit, output_val, output_unit, total_val, total_unit, cost_str = match.groups()

    def convert_value(val, unit):
        """Convert k/m units to numbers"""
        val = float(val)
        if unit == 'k':
            val *= 1000
        elif unit == 'm':
            val *= 1000000
        return int(val)

    input_tokens = convert_value(input_val, input_unit)
    output_tokens = convert_value(output_val, output_unit)
    total_tokens = convert_value(total_val, total_unit)
    cost_usd = float(cost_str)

    return input_tokens, output_tokens, total_tokens, cost_usd

def collect_execution_data(log_file=None, task_list_file=None):
    """
    Collect execution data from logs or task list

    Args:
        log_file: Path to execution log file (JSON lines format)
        task_list_file: Path to saved task list output

    Returns:
        List of execution records
    """
    executions = []

    if log_file and Path(log_file).exists():
        # Parse JSON log file
        with open(log_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        executions.append(record)
                    except json.JSONDecodeError:
                        continue

    if task_list_file and Path(task_list_file).exists():
        # Parse saved task list
        with open(task_list_file, 'r') as f:
            content = f.read()

        # Parse the task list format
        lines = content.strip().split('\n')
        current_task = {}

        for line in lines:
            line = line.strip()
            if line.startswith('Task ID: '):
                if current_task and 'usage_raw' in current_task:
                    executions.append(current_task)
                current_task = {'task_id': line.split(': ')[1].strip()}
            elif line.startswith('Message: ') and current_task:
                current_task['prompt'] = line.split(': ', 1)[1] if ': ' in line else ''
            elif line.startswith('Usage  :') and current_task:
                usage_str = line.split(': ', 1)[1] if ': ' in line else line
                parsed_usage = parse_usage_string(usage_str)
                if parsed_usage:
                    input_tokens, output_tokens, total_tokens, cost_usd = parsed_usage
                    current_task.update({
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': total_tokens,
                        'cost_usd': cost_usd,
                        'usage_raw': usage_str
                    })

        # Don't forget the last task
        if current_task and 'usage_raw' in current_task:
            executions.append(current_task)

    return executions

def calculate_statistics(executions):
    """Calculate variance statistics from executions"""
    if not executions:
        return {}

    # Filter executions with valid data
    valid_executions = [e for e in executions if 'total_tokens' in e and 'cost_usd' in e]

    if not valid_executions:
        return {'error': 'No valid execution data found'}

    # Extract metrics
    total_tokens = [e['total_tokens'] for e in valid_executions]
    costs_usd = [e['cost_usd'] for e in valid_executions]

    # Calculate statistics
    stats = {
        'executions_total': len(executions),
        'executions_valid': len(valid_executions),
        'tokens': {
            'mean': statistics.mean(total_tokens),
            'median': statistics.median(total_tokens),
            'min': min(total_tokens),
            'max': max(total_tokens),
            'stdev': statistics.stdev(total_tokens) if len(total_tokens) > 1 else 0,
            'variance': statistics.variance(total_tokens) if len(total_tokens) > 1 else 0
        },
        'costs': {
            'mean': statistics.mean(costs_usd),
            'median': statistics.median(costs_usd),
            'min': min(costs_usd),
            'max': max(costs_usd),
            'stdev': statistics.stdev(costs_usd) if len(costs_usd) > 1 else 0,
            'variance': statistics.variance(costs_usd) if len(costs_usd) > 1 else 0,
            'total': sum(costs_usd)
        }
    }

    return stats

def generate_report(stats, executions):
    """Generate variance analysis report"""
    report = []
    report.append("# Cline Oneshot Variance Analysis Report")
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append("")

    if 'error' in stats:
        report.append(f"Error: {stats['error']}")
        return '\n'.join(report)

    report.append("## Summary Statistics")
    report.append(f"- Total executions: {stats['executions_total']}")
    report.append(f"- Valid executions: {stats['executions_valid']}")
    report.append("")

    report.append("## Token Usage")
    tokens = stats['tokens']
    report.append(f"- Mean: {tokens['mean']:.1f} tokens")
    report.append(f"- Median: {tokens['median']:.1f} tokens")
    report.append(f"- Range: {tokens['min']:.1f} - {tokens['max']:.1f} tokens")
    report.append(f"- Standard deviation: {tokens['stdev']:.1f} tokens")
    report.append(f"- Variance: {tokens['variance']:.1f}")
    report.append("")

    report.append("## Cost Analysis")
    costs = stats['costs']
    report.append(f"- Mean: ${costs['mean']:.4f}")
    report.append(f"- Median: ${costs['median']:.4f}")
    report.append(f"- Range: ${costs['min']:.4f} - ${costs['max']:.4f}")
    report.append(f"- Standard deviation: ${costs['stdev']:.4f}")
    report.append(f"- Variance: ${costs['variance']:.4f}")
    report.append(f"- Total cost: ${costs['total']:.4f}")
    report.append("")

    report.append("## Cost Efficiency")
    if tokens['mean'] > 0:
        cost_per_token = costs['mean'] / tokens['mean']
        report.append(f"- Average cost per token: ${cost_per_token:.6f}")
    report.append("")

    report.append("## Detailed Execution Data")
    for i, exec in enumerate(executions):
        if 'total_tokens' in exec and 'cost_usd' in exec:
            report.append(f"### Execution {i+1}")
            report.append(f"- Task ID: {exec.get('task_id', 'unknown')}")
            report.append(f"- Tokens: {exec['total_tokens']}")
            report.append(f"- Cost: ${exec['cost_usd']:.4f}")
            if 'usage_raw' in exec:
                report.append(f"- Raw usage: {exec['usage_raw']}")
            report.append("")

    return '\n'.join(report)

def main():
    parser = ArgumentParser(description="Analyze variance from oneshot executions")
    parser.add_argument('--log-file', '-l', help='JSON log file with execution records')
    parser.add_argument('--task-list', '-t', help='Saved task list output file')
    parser.add_argument('--output', '-o', help='Output report file (default: stdout)')
    parser.add_argument('--json', '-j', action='store_true', help='Output statistics as JSON')

    args = parser.parse_args()

    if not args.log_file and not args.task_list:
        print("Error: Must provide either --log-file or --task-list", file=sys.stderr)
        return 1

    # Collect execution data
    executions = collect_execution_data(args.log_file, args.task_list)

    if not executions:
        print("No execution data found", file=sys.stderr)
        return 1

    # Calculate statistics
    stats = calculate_statistics(executions)

    # Output results
    if args.json:
        output = json.dumps(stats, indent=2)
    else:
        output = generate_report(stats, executions)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 0

if __name__ == '__main__':
    sys.exit(main())