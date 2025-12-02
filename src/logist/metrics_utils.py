#!/usr/bin/env python3
"""
Metrics utilities for cost tracking and budget management in Logist.

This module provides comprehensive metrics calculation, threshold checking,
and budget enforcement functionality for the Logist CLI system.
"""

import csv
import os
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class BudgetThresholds:
    """Budget and time limitations for a job."""
    cost_threshold_usd: float = 0.0
    time_threshold_minutes: float = 0.0
    warning_percentage: float = 75.0  # Percentage at which warnings start


@dataclass
class MetricsSnapshot:
    """Complete metrics snapshot for a job."""
    cumulative_cost: float
    cumulative_time_seconds: float
    total_tokens: int
    total_tokens_cache_read: int
    total_cache_hits: int
    step_count: int
    cost_threshold: float
    time_threshold_minutes: float
    cost_percentage: float
    time_percentage: float
    time_remaining_minutes: float
    cost_remaining: float
    status_color: str  # 'green', 'yellow', 'red'


class ThresholdExceededError(Exception):
    """Exception raised when budget or time thresholds are exceeded."""
    pass


def extract_metrics_from_history(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract and aggregate metrics from job history entries.

    Args:
        history: List of history entries from job manifest

    Returns:
        Dictionary with aggregated metrics
    """
    total_tokens_input = 0
    total_tokens_output = 0
    total_tokens = 0
    completed_steps = 0
    failed_steps = 0
    total_tokens_cache_read = 0
    total_cache_hits = 0

    for entry in history:
        # Count successful steps (those with action COMPLETED)
        if entry.get("action") == "COMPLETED":
            completed_steps += 1
        elif entry.get("action") in ["STUCK", "RETRY"]:
            failed_steps += 1

        # Aggregate token usage from metrics if present
        metrics = entry.get("metrics", {})
        if metrics:
            total_tokens_input += metrics.get("token_input", 0)
            total_tokens_output += metrics.get("token_output", 0)
            total_tokens_cache_read += metrics.get("token_cache_read", 0)
            if metrics.get("cache_hit", False):
                total_cache_hits += 1

    total_tokens = total_tokens_input + total_tokens_output + total_tokens_cache_read

    return {
        "total_tokens_input": total_tokens_input,
        "total_tokens_output": total_tokens_output,
        "total_tokens_cache_read": total_tokens_cache_read,
        "total_cache_hits": total_cache_hits,
        "total_tokens": total_tokens,
        "completed_steps": completed_steps,
        "failed_steps": failed_steps,
        "total_steps": len(history)
    }


def get_budget_thresholds(manifest: Dict[str, Any]) -> BudgetThresholds:
    """
    Extract budget thresholds from job manifest.

    Checks both the job_spec level and root level configurations.

    Args:
        manifest: Job manifest dictionary

    Returns:
        BudgetThresholds object with configured limits
    """
    job_spec = manifest.get("job_spec", {})

    # Check for thresholds in job_spec first, then fall back to root level
    cost_threshold = (
        job_spec.get("cost_threshold") or
        manifest.get("cost_threshold") or
        0.0
    )

    time_threshold_minutes = (
        job_spec.get("time_threshold_minutes") or
        manifest.get("time_threshold_minutes") or
        0.0
    )

    # Warning percentage can be configured or use default 75%
    warning_percentage = (
        job_spec.get("warning_percentage") or
        manifest.get("warning_percentage") or
        75.0
    )

    return BudgetThresholds(
        cost_threshold_usd=cost_threshold,
        time_threshold_minutes=time_threshold_minutes,
        warning_percentage=warning_percentage
    )


def calculate_detailed_metrics(manifest: Dict[str, Any]) -> MetricsSnapshot:
    """
    Calculate comprehensive metrics for a job including percentages and status.

    Args:
        manifest: Job manifest dictionary

    Returns:
        MetricsSnapshot with complete metrics breakdown
    """
    metrics = manifest.get("metrics", {})
    history = manifest.get("history", [])
    thresholds = get_budget_thresholds(manifest)

    cumulative_cost = metrics.get("cumulative_cost", 0.0)
    cumulative_time_seconds = metrics.get("cumulative_time_seconds", 0.0)

    # Extract token and step metrics from history
    history_metrics = extract_metrics_from_history(history)
    total_tokens = history_metrics["total_tokens"]
    total_tokens_cache_read = history_metrics["total_tokens_cache_read"]
    total_cache_hits = history_metrics["total_cache_hits"]
    step_count = history_metrics["total_steps"]

    # Calculate percentages
    cost_percentage = 0.0
    time_percentage = 0.0

    if thresholds.cost_threshold_usd > 0:
        cost_percentage = (cumulative_cost / thresholds.cost_threshold_usd) * 100

    if thresholds.time_threshold_minutes > 0:
        time_percentage = (cumulative_time_seconds / 60 / thresholds.time_threshold_minutes) * 100

    # Calculate remaining amounts
    time_remaining_minutes = max(0, thresholds.time_threshold_minutes - (cumulative_time_seconds / 60))
    cost_remaining = max(0, thresholds.cost_threshold_usd - cumulative_cost)

    # Determine status color based on thresholds
    status_color = "green"
    if thresholds.cost_threshold_usd > 0 or thresholds.time_threshold_minutes > 0:
        max_percentage = max(cost_percentage, time_percentage)
        if max_percentage >= 100:
            status_color = "red"
        elif max_percentage >= thresholds.warning_percentage:
            status_color = "yellow"

    return MetricsSnapshot(
        cumulative_cost=cumulative_cost,
        cumulative_time_seconds=cumulative_time_seconds,
        total_tokens=total_tokens,
        total_tokens_cache_read=total_tokens_cache_read,
        total_cache_hits=total_cache_hits,
        step_count=step_count,
        cost_threshold=thresholds.cost_threshold_usd,
        time_threshold_minutes=thresholds.time_threshold_minutes,
        cost_percentage=cost_percentage,
        time_percentage=time_percentage,
        time_remaining_minutes=time_remaining_minutes,
        cost_remaining=cost_remaining,
        status_color=status_color
    )


def check_thresholds_before_execution(manifest: Dict[str, Any]) -> None:
    """
    Check if job execution should be blocked due to exceeded thresholds.

    Args:
        manifest: Job manifest dictionary

    Raises:
        ThresholdExceededError: If any threshold is exceeded
    """
    metrics_snapshot = calculate_detailed_metrics(manifest)
    thresholds = get_budget_thresholds(manifest)

    violations = []

    if thresholds.cost_threshold_usd > 0 and metrics_snapshot.cost_percentage >= 100:
        violations.append(
            ".4f"
        )

    if thresholds.time_threshold_minutes > 0 and metrics_snapshot.time_percentage >= 100:
        violations.append(
            ".1f"
        )

    if violations:
        violation_text = "; ".join(violations)
        raise ThresholdExceededError(
            f"Cannot execute job - budget limits exceeded: {violationation_text}"
        )


def generate_cost_projections(manifest: Dict[str, Any], remaining_phases: int = 5) -> Dict[str, Any]:
    """
    Generate cost projections and recommendations based on current spending patterns.

    Args:
        manifest: Job manifest dictionary
        remaining_phases: Estimated number of phases remaining

    Returns:
        Dictionary with projections and recommendations
    """
    metrics = manifest.get("metrics", {})
    history = manifest.get("history", [])
    thresholds = get_budget_thresholds(manifest)

    # Calculate average cost per step from history
    total_cost = metrics.get("cumulative_cost", 0.0)
    total_time_seconds = metrics.get("cumulative_time_seconds", 0.0)
    step_count = len(history)

    avg_cost_per_step = total_cost / step_count if step_count > 0 else 0.0
    avg_time_per_step = total_time_seconds / step_count if step_count > 0 else 0.0

    # Projected costs
    projected_cost_remaining = avg_cost_per_step * remaining_phases
    projected_total_cost = total_cost + projected_cost_remaining
    projected_time_remaining = (avg_time_per_step / 60) * remaining_phases  # in minutes
    projected_total_time = (total_time_seconds / 60) + projected_time_remaining  # in minutes

    # Generate recommendations
    recommendations = []
    cost_status = "🟢 On track"
    time_status = "🟢 On track"

    if thresholds.cost_threshold_usd > 0:
        cost_headroom_percentage = ((thresholds.cost_threshold_usd - total_cost) / thresholds.cost_threshold_usd) * 100
        if projected_total_cost > thresholds.cost_threshold_usd:
            cost_status = ".1f"
            recommendations.append("⚠️  Consider reducing job scope or increasing budget")
        elif cost_headroom_percentage < 25:
            cost_status = "🟡 Low budget remaining"
            recommendations.append("💡 Consider monitoring closely")

    if thresholds.time_threshold_minutes > 0:
        time_headroom_percentage = ((thresholds.time_threshold_minutes - (total_time_seconds / 60)) / thresholds.time_threshold_minutes) * 100
        if projected_total_time > thresholds.time_threshold_minutes:
            time_status = ".1f"
            recommendations.append("⚠️  Consider extending time limits or simplifying requirements")
        elif time_headroom_percentage < 25:
            time_status = "🟡 Low time remaining"
            recommendations.append("💡 Consider assessing progress priorities")

    if not recommendations:
        recommendations.append("✅ Budget and time tracking appear healthy")

    return {
        "current_cost": total_cost,
        "average_cost_per_step": avg_cost_per_step,
        "projected_cost_remaining": projected_cost_remaining,
        "projected_total_cost": projected_total_cost,
        "cost_threshold": thresholds.cost_threshold_usd,
        "cost_status": cost_status,

        "current_time_minutes": total_time_seconds / 60,
        "average_time_per_step_minutes": avg_time_per_step / 60,
        "projected_time_remaining_minutes": projected_time_remaining,
        "projected_total_time_minutes": projected_total_time,
        "time_threshold_minutes": thresholds.time_threshold_minutes,
        "time_status": time_status,

        "recommendations": recommendations,
        "confidence_level": f"Based on {step_count} completed steps"
    }


def export_metrics_to_csv(job_dir: str, output_file: Optional[str] = None) -> str:
    """
    Export detailed metrics data to CSV format.

    Args:
        job_dir: Job directory path
        output_file: Optional output file path (defaults to metrics.csv in job dir)

    Returns:
        Path to the exported CSV file
    """
    from logist.job_state import load_job_manifest

    manifest = load_job_manifest(job_dir)
    history = manifest.get("history", [])

    if not output_file:
        output_file = os.path.join(job_dir, "metrics.csv")

    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = [
            'timestamp', 'step_number', 'role', 'action', 'summary',
            'cost_usd', 'time_seconds', 'token_input', 'token_output', 'token_cache_read', 'cache_hit',
            'ttft_seconds', 'throughput_tokens_per_second', 'total_tokens',
            'cline_task_id', 'status_after'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for i, entry in enumerate(history):
            metrics = entry.get("metrics", {})
            writer.writerow({
                'timestamp': entry.get('timestamp', ''),
                'step_number': i,
                'role': entry.get('role', ''),
                'action': entry.get('action', ''),
                'summary': entry.get('summary', ''),
                'cost_usd': metrics.get('cost_usd', 0.0),
                'time_seconds': metrics.get('duration_seconds', 0.0),
                'token_input': metrics.get('token_input', 0),
                'token_output': metrics.get('token_output', 0),
                'token_cache_read': metrics.get('token_cache_read', 0),
                'cache_hit': 'Yes' if metrics.get('cache_hit', False) else 'No',
                'ttft_seconds': metrics.get('ttft_seconds', ''),
                'throughput_tokens_per_second': metrics.get('throughput_tokens_per_second', ''),
                'total_tokens': metrics.get('token_input', 0) + metrics.get('token_output', 0) + metrics.get('token_cache_read', 0),
                'cline_task_id': entry.get('cline_task_id', ''),
                'status_after': entry.get('new_status', '')
            })

    return output_file