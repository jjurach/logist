#!/usr/bin/env python3
"""
Logist CLI - Command Line Interface for Job Orchestration

Main entry point for the Logist CLI application.
"""

import json
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional

import click

from logist import workspace_utils # Import the new module
from logist.job_state import JobStateError, load_job_manifest, get_current_state_and_role, update_job_manifest, transition_state, JobStates
from logist.job_processor import (
    execute_llm_with_cline, handle_execution_error, validate_evidence_files, JobProcessorError,
    save_latest_outcome, prepare_outcome_for_attachments, enhance_context_with_previous_outcome
)
from logist.job_context import assemble_job_context, JobContextError # Now exists
from logist.recovery import validate_state_persistence, get_recovery_status, RecoveryError
from logist.metrics_utils import check_thresholds_before_execution, calculate_detailed_metrics, generate_cost_projections, export_metrics_to_csv, ThresholdExceededError


class LogistEngine:
    """Orchestration engine for Logist jobs."""

    def _write_job_history_entry(self, job_dir: str, entry: dict) -> None:
        """Write a job history entry to jobHistory.json."""
        job_history_path = os.path.join(job_dir, "jobHistory.json")

        # Load existing history or create empty array
        if os.path.exists(job_history_path):
            try:
                with open(job_history_path, 'r') as f:
                    history = json.load(f)
                    if not isinstance(history, list):
                        history = []
            except (json.JSONDecodeError, OSError):
                history = []
        else:
            history = []

        # Append new entry
        history.append(entry)

        # Write back to file
        try:
            with open(job_history_path, 'w') as f:
                json.dump(history, f, indent=2)
        except OSError as e:
            click.secho(f"⚠️  Failed to write job history entry: {e}", fg="yellow")

    def _show_debug_history_info(self, debug_mode: bool, operation: str, job_id: str, entry: dict) -> None:
        """Display detailed debug information when writing to jobHistory.json."""
        if not debug_mode:
            return

        click.echo(f"   📝 [DEBUG] Writing to jobHistory.json for {operation} operation:")
        click.echo(f"      📅 Timestamp: {entry.get('timestamp', 'unknown')}")
        click.echo(f"      🧠 Model: {entry.get('model', 'unknown')}")
        click.echo(f"      💰 Cost: ${entry.get('cost', 0):.4f}")
        click.echo(f"      ⏱️  Execution Time: {entry.get('execution_time_seconds', 0):.2f}s")

        # Show metrics if available
        metrics = entry.get("response", {}).get("metrics", {})
        if metrics:
            if "cost_usd" in metrics:
                click.echo(f"      💸 LLM Cost: ${metrics['cost_usd']:.4f}")
            if "token_input" in metrics:
                click.echo(f"      📥 Input Tokens: {metrics['token_input']:,}")
            if "token_output" in metrics:
                click.echo(f"      📤 Output Tokens: {metrics['token_output']:,}")
            if "token_cache_read" in metrics and metrics['token_cache_read'] > 0:
                click.echo(f"      📚 Cached Read Tokens: {metrics['token_cache_read']:,}")
            if "cache_hit" in metrics:
                click.echo(f"      🎯 Cache Hit: {'Yes' if metrics['cache_hit'] else 'No'}")
            if "ttft_seconds" in metrics and metrics['ttft_seconds'] is not None:
                click.echo(f"      ⏱️  TTFT: {metrics['ttft_seconds']:.2f}s")
            if "throughput_tokens_per_second" in metrics and metrics['throughput_tokens_per_second'] is not None:
                click.echo(f"      ⚡ Throughput: {metrics['throughput_tokens_per_second']:.2f} tokens/s")
            total_tokens = metrics.get("token_input", 0) + metrics.get("token_output", 0) + metrics.get("token_cache_read", 0)
            if total_tokens > 0:
                click.echo(f"      🔢 Total Tokens (Input+Output+Cached): {total_tokens:,}")

        request_info = entry.get("request", {})
        if request_info.get("job_id"):
            click.echo(f"      🎯 Job ID: {request_info['job_id']}")
        if request_info.get("phase"):
            click.echo(f"      📍 Phase: {request_info['phase']}")
        if request_info.get("role"):
            click.echo(f"      👤 Role: {request_info['role']}")

        response_info = entry.get("response", {})
        if response_info.get("action"):
            click.echo(f"      🎬 Action: {response_info['action']}")

        evidence_files = response_info.get("evidence_files", [])
        if evidence_files:
            click.echo(f"      📁 Evidence Files: {len(evidence_files)}")
            for i, evidence in enumerate(evidence_files[:3]):  # Show first 3
                click.echo(f"         • {evidence}")
            if len(evidence_files) > 3:
                click.echo(f"         ... and {len(evidence_files) - 3} more")

    def rerun_job(self, ctx: click.Context, job_id: str, job_dir: str, start_step: int | None = None) -> None:
        """Re-execute a job, optionally starting from a specific phase."""
        manager.setup_workspace(job_dir) # Ensure workspace is ready

        try:
            # 1. Load and validate job manifest
            manifest = load_job_manifest(job_dir)

            # 2. Determine available phases
            phases = manifest.get("phases", [])
            if not phases:
                click.secho("⚠️  Job has no defined phases. Treating as single-phase job.", fg="yellow")
                phases = [{"name": "default", "description": "Default single phase"}]

            # 3. Validate start_step if provided
            if start_step is not None:
                if start_step >= len(phases):
                    available_steps = len(phases)
                    raise click.ClickException(
                        f"Invalid step number {start_step}. Job has {available_steps} phases (0-{available_steps-1})."
                    )
                start_phase_name = phases[start_step]["name"]
                click.echo(f"   → Starting rerun from phase {start_step} ('{start_phase_name}')")
            else:
                start_phase_name = phases[0]["name"]
                click.echo("   → Starting rerun from the beginning (phase 0)")

            # 4. Reset job state for rerun
            self._reset_job_for_rerun(job_dir, start_phase_name, new_run=True)

            click.secho(f"   🔄 Job '{job_id}' reset for rerun", fg="blue")

            # 5. Continue with normal execution until completion or intervention
            # For now, execute one step (matching the pattern of other commands)
            # Future enhancement could implement continuous rerun until completion
            success = self.step_job(ctx, job_id, job_dir, dry_run=False)

            # Always report success for the rerun command itself, even if the step fails
            # The rerun state reset was successful, and future runs/steps can be attempted
            click.secho(f"   ✅ Rerun initiated successfully", fg="green")
            if not success:
                click.secho(f"   ⚠️  Initial step failed - use 'logist job step' to retry", fg="yellow")

        except Exception as e:
            click.secho(f"❌ Error during job rerun preparation: {e}", fg="red")
            raise

    def _reset_job_for_rerun(self, job_dir: str, start_phase_name: str, new_run: bool = False) -> None:
        """Reset job state for rerun operation."""
        manifest = load_job_manifest(job_dir)

        # Reset status to PENDING
        manifest["status"] = "PENDING"

        # Set current phase to starting phase
        manifest["current_phase"] = start_phase_name

        # Reset metrics for this run (but preserve total history)
        manifest["metrics"]["cumulative_cost"] = 0.0
        manifest["metrics"]["cumulative_time_seconds"] = 0.0

        # Clear immediate history but preserve overall history in separate structure
        manifest["history"] = []

        # Mark as rerun in manifest for tracking
        manifest["_rerun_info"] = {
            "is_rerun": True,
            "start_phase": start_phase_name,
            "started_at": None  # Will be set when first step executes
        }

        # Save updated manifest
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

    def step_job(self, ctx: click.Context, job_id: str, job_dir: str, dry_run: bool = False, model: str = "grok-code-fast-1") -> bool:
        """Execute single phase of job and pause with enhanced workspace preparation."""
        manager.setup_workspace(job_dir) # Ensure workspace is ready

        # Recovery validation - check for hung processes and recover if needed
        try:
            from logist.recovery import validate_state_persistence
            recovery_result = validate_state_persistence(job_dir)
            if recovery_result["recovered"]:
                click.secho(f"🔄 Recovery performed before execution: {recovery_result['recovery_from']}", fg="blue")
            if recovery_result["errors"]:
                for error in recovery_result["errors"]:
                    click.secho(f"⚠️  Recovery warning: {error}", fg="yellow")
        except Exception as e:
            click.secho(f"⚠️  Recovery validation failed: {e}", fg="yellow")

        if dry_run:
            click.secho("   → Defensive setting detected: --dry-run", fg="yellow")
            click.echo(f"   → Would: Simulate single phase for job '{job_id}' with mock data")
            return True

        click.echo(f"👣 [LOGIST] Executing single phase for job '{job_id}'")

        try:
            # 1. Load job manifest
            manifest = load_job_manifest(job_dir)
            current_status = manifest.get("status", "PENDING")

            # 2. Check threshold limits before execution
            try:
                check_thresholds_before_execution(manifest)
            except ThresholdExceededError as e:
                click.secho(f"❌ {e}", fg="red")
                return False

            # 3. Determine current phase and active role
            current_phase_name, active_role = get_current_state_and_role(manifest)
            click.echo(f"   → Current Phase: {current_phase_name}, Active Role: {active_role}")

            # 4. Prepare workspace with attachments and file discovery
            workspace_dir = os.path.join(job_dir, "workspace")
            prep_result = workspace_utils.prepare_workspace_attachments(job_dir, workspace_dir)
            if prep_result["success"]:
                if prep_result["attachments_copied"]:
                    click.echo(f"   📎 Copied {len(prep_result['attachments_copied'])} attachments to workspace")
                if prep_result["discovered_files"]:
                    click.echo(f"   🔍 Discovered {len(prep_result['discovered_files'])} context files")
            else:
                click.secho(f"   ⚠️  Workspace preparation warning: {prep_result['error']}", fg="yellow")

            # 6. Prepare outcome attachments from previous step
            outcome_prep = prepare_outcome_for_attachments(job_dir, workspace_dir)
            if outcome_prep["attachments_added"]:
                click.echo(f"   🏆 Prepared outcome data from previous {len(outcome_prep['attachments_added'])} steps")

            # 7. Assemble job context with enhanced preparation
            context = assemble_job_context(job_dir, manifest, ctx.obj["JOBS_DIR"], active_role, enhance=ctx.obj.get("ENHANCE", False))
            context = enhance_context_with_previous_outcome(context, job_dir)

            # 8. Execute LLM with Cline using discovered file arguments
            file_arguments = prep_result["file_arguments"] + outcome_prep["attachments_added"] if prep_result["success"] else []

            processed_response, execution_time = execute_llm_with_cline(
                context=context,
                workspace_dir=workspace_dir,
                file_arguments=file_arguments
            )

            response_action = processed_response.get("action")

            click.secho(f"   ✅ LLM responded with action: {response_action}", fg="green")
            click.echo(f"   📝 Summary for Supervisor: {processed_response.get('summary_for_supervisor', 'N/A')}")
            click.echo(f"   ⏱️  Execution time: {execution_time:.2f} seconds")

            # Debug: Write to jobHistory.json for step operation
            debug_mode = ctx.obj.get("DEBUG", False)
            if debug_mode:
                from datetime import datetime
                job_history_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "model": model,
                    "cost": processed_response.get("metrics", {}).get("cost_usd", 0.0),
                    "execution_time_seconds": execution_time,
                    "request": {
                        "operation": "step",
                        "job_id": job_id,
                        "phase": current_phase_name,
                        "role": active_role,
                        "dry_run": dry_run
                    },
                    "response": {
                        "action": response_action,
                        "summary_for_supervisor": processed_response.get("summary_for_supervisor", ""),
                        "evidence_files": evidence_files,
                        "metrics": processed_response.get("metrics", {})
                    }
                }
                self._write_job_history_entry(job_dir, job_history_entry)
                self._show_debug_history_info(debug_mode, "step", job_id, job_history_entry)

            # 9. Save outcome to latest-outcome.json
            outcome_save = save_latest_outcome(job_dir, processed_response)
            if outcome_save["success"]:
                click.echo("   💾 Saved LLM response to latest-outcome.json")
            else:
                click.secho(f"   ⚠️  Failed to save outcome: {outcome_save['error']}", fg="yellow")

            # 10. Validate evidence files
            evidence_files = processed_response.get("evidence_files", [])
            if evidence_files:
                validated_evidence = validate_evidence_files(evidence_files, workspace_dir)
                click.echo(f"   📁 Validated evidence files: {', '.join(validated_evidence)}")
            else:
                click.echo("   📁 No evidence files reported.")

            # 11. Update job manifest
            new_status = transition_state(current_status, active_role, response_action)

            history_entry = {
                "role": active_role,
                "action": response_action,
                "summary": processed_response.get("summary_for_supervisor"),
                "metrics": processed_response.get("metrics", {}), # Includes new cached token metrics
                "cline_task_id": processed_response.get("cline_task_id"),
                "new_status": new_status,
                "evidence_files": evidence_files, # Store reported evidence files
                "file_attachments": len(file_arguments) if file_arguments else 0
            }

            update_job_manifest(
                job_dir=job_dir,
                new_status=new_status,
                cost_increment=processed_response.get("metrics", {}).get("cost_usd", 0.0),
                time_increment=execution_time,
                history_entry=history_entry
            )
            click.secho(f"   🔄 Job status updated to: {new_status}", fg="blue")

            # 12. Perform git commit for evidence files and changes
            try:
                commit_summary = processed_response.get("summary_for_supervisor", f"{active_role} step: {current_phase_name}")
                commit_result = workspace_utils.perform_git_commit(
                    job_dir=job_dir,
                    evidence_files=evidence_files,
                    summary=commit_summary
                )

                if commit_result["success"]:
                    click.secho(f"   💾 Changes committed: {commit_result['commit_hash'][:8]}", fg="green")
                    click.echo(f"   📁 Files committed: {len(commit_result['files_committed'])}")
                else:
                    click.secho(f"   ⚠️  Git commit failed: {commit_result['error']}", fg="yellow")
                    # Don't fail the step for git commit issues - continue execution

            except Exception as e:
                click.secho(f"   ⚠️  Git commit error: {e}", fg="yellow")
                # Continue - git commit failures shouldn't fail the job step

            return True

        except (JobProcessorError, JobStateError, JobContextError, Exception) as e:
            click.secho(f"❌ Error during job step for '{job_id}': {e}", fg="red")
            raw_cline_output = None
            if isinstance(e, JobProcessorError) and hasattr(e, 'full_output'):
                raw_cline_output = e.full_output # If CLINE execution failed, this might be present
            handle_execution_error(job_dir, job_id, e, raw_output=raw_cline_output)
            return False

    def run_job(self, ctx: click.Context, job_id: str, job_dir: str) -> bool:
        """
        Execute a job continuously until completion, intervention, or cancellation.

        This command orchestrates iterative worker and supervisor executions
        until the job reaches SUCCESS, CANCELED, INTERVENTION_REQUIRED, or APPROVAL_REQUIRED.
        """
        manager.setup_workspace(job_dir)  # Ensure workspace is ready

        # Define terminal states where execution stops
        TERMINAL_STATES = {"SUCCESS", "CANCELED", "INTERVENTION_REQUIRED", "APPROVAL_REQUIRED"}

        click.echo("🎯 [LOGIST] Starting continuous job execution")
        click.echo(f"   📍 Job: {job_id}")
        click.echo(f"   📁 Directory: {job_dir}")

        # Debug: Write to jobHistory.json for run command start
        debug_mode = ctx.obj.get("DEBUG", False)
        if debug_mode:
            from datetime import datetime
            job_history_entry = {
                "timestamp": datetime.now().isoformat(),
                "model": "run-command",
                "cost": 0.0,
                "execution_time_seconds": 0.0,
                "request": {
                    "operation": "run",
                    "job_id": job_id,
                    "description": "Starting continuous job execution loop"
                },
                "response": {
                    "action": "RUN_STARTED",
                    "summary_for_supervisor": f"Continuous execution started for job '{job_id}'",
                    "evidence_files": [],
                    "metrics": {}
                }
            }
            self._write_job_history_entry(job_dir, job_history_entry)
            self._show_debug_history_info(debug_mode, "run-start", job_id, job_history_entry)

        try:
            # Load initial job manifest to check current status
            manifest = load_job_manifest(job_dir)
            current_status = manifest.get("status", "PENDING")

            if current_status in TERMINAL_STATES:
                click.secho(f"⚠️  Job '{job_id}' is already in terminal state: {current_status}", fg="yellow")
                click.echo("   💡 Use 'logist job step' to advance manually or 'logist job rerun' to restart")
                return True  # Not an error, just already complete

            click.echo(f"   🔄 Initial Status: {current_status}")
            click.echo("   🔄 Beginning execution loop...\n")

            step_count = 0
            while True:
                step_count += 1
                click.echo(f"▼ Step {step_count} ▼")

                # Execute one step
                success = self.step_job(ctx, job_id, job_dir, dry_run=False)

                if not success:
                    click.secho(f"❌ Step {step_count} failed - stopping execution", fg="red")
                    return False

                # Check if we've reached a terminal state
                try:
                    manifest = load_job_manifest(job_dir)
                    current_status = manifest.get("status", "PENDING")

                    if current_status in TERMINAL_STATES:
                        click.echo(f"\n🎉 [LOGIST] Job execution completed!")
                        click.secho(f"   📊 Final Status: {current_status}", fg="green")
                        click.echo(f"   📈 Steps executed: {step_count}")

                        if current_status == "SUCCESS":
                            click.echo("   ✅ Job completed successfully!")
                        elif current_status == "CANCELED":
                            click.echo("   🚫 Job was canceled")
                        elif current_status == "INTERVENTION_REQUIRED":
                            click.echo("   👤 Human intervention required")
                            click.echo("   💡 Use 'logist job step' or manual fixes, then 'logist job run' to continue")
                        elif current_status == "APPROVAL_REQUIRED":
                            click.echo("   👍 Final approval required")
                            click.echo("   💡 Use appropriate commands to approve/reject")

                        return True

                except JobStateError as e:
                    click.secho(f"❌ Error checking job status after step {step_count}: {e}", fg="red")
                    return False

                # Small delay between steps for readability
                import time
                time.sleep(0.5)

        except (JobProcessorError, JobStateError, JobContextError, Exception) as e:
            click.secho(f"❌ Error during job run for '{job_id}': {e}", fg="red")
            return False

    def restep_single_step(self, ctx: click.Context, job_id: str, job_dir: str, step_number: int, dry_run: bool = False) -> bool:
        """Re-execute a specific single step (phase) of a job for debugging purposes."""
        manager.setup_workspace(job_dir) # Ensure workspace is ready

        if dry_run:
            click.secho("   → Defensive setting detected: --dry-run", fg="yellow")
            click.echo(f"   → Would: Re-execute step {step_number} for job '{job_id}' with mock data")
            return True

        click.echo(f"🔄 [LOGIST] Re-executing step {step_number} for job '{job_id}'")

        try:
            # 1. Load job manifest and validate step number
            manifest = load_job_manifest(job_dir)
            phases = manifest.get("phases", [])

            if not phases:
                raise JobStateError("Job has no defined phases. Cannot restep.")

            if step_number >= len(phases) or step_number < 0:
                available_steps = len(phases)
                raise JobStateError(f"Invalid step number {step_number}. Job has {available_steps} phases (0-{available_steps-1}).")

            target_phase = phases[step_number]
            target_phase_name = target_phase["name"]
            click.echo(f"   → Target Phase: {target_phase_name} (step {step_number})")

            # 2. Determine active role for this phase
            # For restep, we need to figure out which role should execute this phase
            # This logic matches the current state machine - we use a simple default
            active_role = target_phase.get("active_agent", "Worker")  # Default to Worker
            click.echo(f"   → Active Role: {active_role}")

            # 3. Prepare manifest for this specific step execution
            # Create a temporary manifest with current_phase set to the target phase
            restep_manifest = manifest.copy()
            restep_manifest["current_phase"] = target_phase_name

            # 4. Assemble job context for the target phase
            workspace_path = os.path.join(job_dir, "workspace")
            context = assemble_job_context(job_dir, restep_manifest, ctx.obj["JOBS_DIR"], active_role, enhance=False)

            # 6. Execute LLM with Cline
            processed_response, execution_time = execute_llm_with_cline(
                context=context,
                workspace_dir=workspace_path,
                instruction_files=[role_config_path] # Pass role config as instruction
            )

            response_action = processed_response.get("action")

            click.secho(f"   ✅ LLM responded with action: {response_action}", fg="green")
            click.echo(f"   📝 Summary for Supervisor: {processed_response.get('summary_for_supervisor', 'N/A')}")
            click.echo(f"   ⏱️  Execution time: {execution_time:.2f} seconds")

            # 7. Validate evidence files
            evidence_files = processed_response.get("evidence_files", [])
            if evidence_files:
                validated_evidence = validate_evidence_files(evidence_files, workspace_path)
                click.echo(f"   📁 Validated evidence files: {', '.join(validated_evidence)}")
            else:
                click.echo("   📁 No evidence files reported.")

            # 8. Update job manifest with step-specific history
            # For restep, we don't change the overall job status, just record the restep action
            current_status = manifest.get("status", "PENDING")

            history_entry = {
                "event": "RESTEP",
                "step_number": step_number,
                "phase_name": target_phase_name,
                "role": active_role,
                "action": response_action,
                "summary": processed_response.get("summary_for_supervisor"),
                "metrics": processed_response.get("metrics", {}),
                "cline_task_id": processed_response.get("cline_task_id"),
                "evidence_files": evidence_files
            }

            # Update metrics and add history entry, but preserve overall status
            update_job_manifest(
                job_dir=job_dir,
                # new_status unchanged - restep doesn't affect overall job status
                cost_increment=processed_response.get("metrics", {}).get("cost_usd", 0.0),
                time_increment=execution_time,
                history_entry=history_entry
            )
            click.secho(f"   🔄 Restep completed for phase '{target_phase_name}' (step {step_number})", fg="blue")
            click.secho(f"   📊 Job status remains: {current_status}", fg="cyan")
            return True

        except (JobProcessorError, JobStateError, JobContextError, Exception) as e:
            click.secho(f"❌ Error during job restep for '{job_id}' step {step_number}: {e}", fg="red")
            raw_cline_output = None
            if isinstance(e, JobProcessorError) and hasattr(e, 'full_output'):
                raw_cline_output = e.full_output # If CLINE execution failed, this might be present
            handle_execution_error(job_dir, job_id, e, raw_output=raw_cline_output)
            return False

    def restep_job(self, ctx: click.Context, job_id: str, job_dir: str, step_number: int, dry_run: bool = False) -> bool:
        """
        Rewind job execution to a previous checkpoint within the current run.

        This restores the job state to a specific step (checkpoint) by:
        1. Validating the target step exists
        2. Setting current_phase to the target step's phase
        3. Preserving full history (unlike rerun which clears it)
        4. Resetting metrics to exclude steps after the checkpoint
        5. Recording the restep event in history
        """
        click.echo(f"⏪ [LOGIST] Rewinding job '{job_id}' to step {step_number}")

        if dry_run:
            click.secho("   → Defensive setting detected: --dry-run", fg="yellow")
            click.echo(f"   → Would: Restore job state to step {step_number} checkpoint")
            return True

        try:
            # 1. Load and validate job manifest
            manifest = load_job_manifest(job_dir)
            phases = manifest.get("phases", [])

            if not phases:
                click.secho("❌ Job has no defined phases. Cannot restep.", fg="red")
                return False

            if step_number >= len(phases) or step_number < 0:
                available_steps = len(phases)
                click.secho(f"❌ Invalid step number {step_number}. Job has {available_steps} phases (0-{available_steps-1}).", fg="red")
                return False

            target_phase = phases[step_number]
            target_phase_name = target_phase["name"]
            click.echo(f"   → Target checkpoint: step {step_number} ('{target_phase_name}')")

            # 2. Record the current state before restep for history
            current_phase_before = manifest.get("current_phase")
            current_status_before = manifest.get("status")

            # 3. Calculate metrics reset
            # For restep, we keep all metrics since we're staying within the same run
            # (unlike rerun which resets metrics to zero)
            metrics_before = manifest.get("metrics", {}).copy()

            # 4. Restore job state to checkpoint
            manifest["current_phase"] = target_phase_name
            # Status remains unchanged for restep - we're just rewinding position

            # 5. Record restep event in history
            from datetime import datetime
            history_entry = {
                "timestamp": datetime.now().isoformat(),
                "event": "RESTEP",
                "action": f"Restepped to checkpoint step {step_number} ('{target_phase_name}')",
                "previous_phase": current_phase_before,
                "previous_status": current_status_before,
                "target_step": step_number,
                "target_phase": target_phase_name,
                "metrics_before_restep": metrics_before
            }

            # Append to history (don't clear like rerun does)
            if "history" not in manifest:
                manifest["history"] = []
            manifest["history"].append(history_entry)

            # 6. Save updated manifest
            manifest_path = os.path.join(job_dir, "job_manifest.json")
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

            click.secho(f"   ✅ Job '{job_id}' successfully rewound to checkpoint", fg="green")
            click.echo(f"   📍 Current phase: {target_phase_name} (step {step_number})")
            click.echo(f"   📊 Status unchanged: {current_status_before}")
            click.echo(f"   📚 History: Restep event recorded")

            return True

        except (JobStateError, OSError, KeyError) as e:
            click.secho(f"❌ Error during job restep for '{job_id}': {e}", fg="red")
            return False


class JobManager:
    """Manages job creation, selection, and status."""

    def get_current_job_id(self, jobs_dir: str) -> str | None:
        """Get the current job ID from jobs index."""
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
        if not os.path.exists(jobs_index_path):
            return None

        try:
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
            return jobs_index.get("current_job_id")
        except (json.JSONDecodeError, OSError):
            return None

    def create_job(self, job_dir: str, jobs_dir: str) -> str:
        """Create or register a new job with manifest and directory structure."""
        job_dir_abs = os.path.abspath(job_dir)
        jobs_dir_abs = os.path.abspath(jobs_dir)

        # Derive job_id from directory name
        job_id = os.path.basename(job_dir_abs)

        # Check if the job dir is inside the jobs_dir
        if os.path.dirname(job_dir_abs) != jobs_dir_abs:
            click.secho(
                f"⚠️  Warning: The job directory '{job_dir_abs}' is not inside the configured --jobs-dir '{jobs_dir_abs}'.",
                fg="yellow",
            )
            click.echo("    This is allowed, but not recommended for easier management.")

        # Ensure job directory exists
        os.makedirs(job_dir_abs, exist_ok=True)

        # Try to find and read job specification file
        job_spec = None
        spec_files = ['sample-job.json', 'job.json', 'job-spec.json']
        for spec_file in spec_files:
            spec_path = os.path.join(job_dir_abs, spec_file)
            if os.path.exists(spec_path):
                try:
                    with open(spec_path, 'r') as f:
                        job_spec = json.load(f).get('job_spec', {})
                    break
                except (json.JSONDecodeError, OSError):
                    continue

        # Create job_manifest.json
        manifest_path = os.path.join(job_dir_abs, "job_manifest.json")
        if os.path.exists(manifest_path) and not click.confirm(f"Job manifest already exists in '{job_dir_abs}'. Overwrite?"):
            return job_id

        # Build initial manifest
        job_manifest = {
            "job_id": job_spec.get('job_id', job_id) if job_spec else job_id,
            "description": job_spec.get('description', f'Job {job_id}') if job_spec else f'Job {job_id}',
            "status": JobStates.DRAFT,  # Changed from PENDING to DRAFT as initial state
            "current_phase": job_spec.get('phases', [{}])[0].get('name', None) if job_spec and job_spec.get('phases') else None,
            "metrics": {
                "cumulative_cost": 0,
                "cumulative_time_seconds": 0
            },
            "history": []
        }

        # Add job_spec content if present
        if job_spec:
            # Merge key job spec fields, avoiding conflicts with manifest fields
            for key, value in job_spec.items():
                if key not in ['job_id', 'description']:  # These are handled above
                    job_manifest[key] = value

        # Write job manifest
        with open(manifest_path, 'w') as f:
            json.dump(job_manifest, f, indent=2)

        # Update jobs_index.json
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
        if os.path.exists(jobs_index_path):
            try:
                with open(jobs_index_path, 'r') as f:
                    jobs_index = json.load(f)
            except (json.JSONDecodeError, OSError):
                jobs_index = {"current_job_id": None, "jobs": {}}
        else:
            jobs_index = {"current_job_id": None, "jobs": {}}

        # Register the job
        if "jobs" not in jobs_index:
            jobs_index["jobs"] = {}
        jobs_index["jobs"][job_id] = job_dir_abs
        jobs_index["current_job_id"] = job_id

        # Write updated jobs index
        with open(jobs_index_path, 'w') as f:
            json.dump(jobs_index, f, indent=2)

        return job_id

    def select_job(self, job_id: str, jobs_dir: str) -> None:
        """Set a job as the currently selected job."""
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
        if not os.path.exists(jobs_index_path):
            raise click.ClickException(f"Jobs directory not initialized. Run 'logist init' first.")

        try:
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise click.ClickException(f"Failed to read jobs index: {e}")

        if "jobs" not in jobs_index or job_id not in jobs_index["jobs"]:
            raise click.ClickException(f"Job '{job_id}' not found in jobs index.")

        jobs_index["current_job_id"] = job_id

        try:
            with open(jobs_index_path, 'w') as f:
                json.dump(jobs_index, f, indent=2)
        except OSError as e:
            raise click.ClickException(f"Failed to update jobs index: {e}")

    def get_job_status(self, job_id: str, jobs_dir: str) -> dict:
        """Retrieve detailed job status from job manifest."""
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")

        # Check if jobs directory is initialized
        if not os.path.exists(jobs_index_path):
            raise click.ClickException(f"Jobs directory not initialized. Run 'logist init' first.")

        try:
            # Read jobs index to find job path
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)

            jobs_map = jobs_index.get("jobs", {})
            if job_id not in jobs_map:
                raise click.ClickException(f"Job '{job_id}' not found in jobs index.")

            job_dir = jobs_map[job_id]
            manifest_path = os.path.join(job_dir, "job_manifest.json")

            # Read job manifest
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                return manifest
            else:
                raise click.ClickException(f"Job manifest not found for '{job_id}' at {manifest_path}")

        except (json.JSONDecodeError, OSError) as e:
            raise click.ClickException(f"Failed to read job status: {e}")

    def get_job_history(self, job_id: str) -> list:
        """Simulate retrieving job history."""
        print(f"📚 [LOGIST] Retrieving history for job '{job_id}'")
        return ["1. Worker: Implemented feature X"]

    def inspect_job(self, job_id: str) -> dict:
        """Simulate inspecting a raw job manifest."""
        print(f"🔩 [LOGIST] Inspecting raw manifest for job '{job_id}'")
        return {"job_id": job_id, "raw_data": "..."}

    def list_jobs(self, jobs_dir: str) -> list:
        """List all active jobs from jobs index and their manifests."""
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")

        # Check if jobs directory is initialized
        if not os.path.exists(jobs_index_path):
            return []

        try:
            # Read jobs index
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)

            jobs_data = []
            jobs_map = jobs_index.get("jobs", {})
            queue = jobs_index.get("queue", [])

            # Create queue position mapping
            queue_positions = {}
            for idx, job_id in enumerate(queue):
                queue_positions[job_id] = idx

            # Process each job
            for job_id, job_path in jobs_map.items():
                job_manifest_path = os.path.join(job_path, "job_manifest.json")
                queue_pos = queue_positions.get(job_id)
                job_info = {
                    "job_id": job_id,
                    "path": job_path,
                    "status": "UNKNOWN",
                    "description": "No description available",
                    "phase": "unknown",
                    "queue_position": queue_pos
                }

                try:
                    # Read job manifest
                    if os.path.exists(job_manifest_path):
                        with open(job_manifest_path, 'r') as f:
                            manifest = json.load(f)

                        job_info.update({
                            "status": manifest.get("status", "UNKNOWN"),
                            "description": manifest.get("description", "No description available"),
                            "phase": manifest.get("current_phase", "unknown")
                        })

                except (json.JSONDecodeError, KeyError):
                    # Manifest exists but is malformed or missing keys
                    job_info["description"] = "Job manifest corrupted"

                jobs_data.append(job_info)

            return jobs_data

        except (json.JSONDecodeError, OSError) as e:
            # Jobs index is malformed or inaccessible
            return []

    def force_success(self, job_id: str) -> None:
        """Simulate forcing a task to success."""
        print(f"✅ [LOGIST] Forcing task success for job '{job_id}'")

    def terminate_job(self, job_id: str) -> None:
        """Simulate terminating a job."""
        print(f"🛑 [LOGIST] Terminating job '{job_id}' workflow")

    def setup_workspace(self, job_dir: str) -> None:
        """Setup isolated workspace with branch management for advanced isolation."""
        # Extract job_id from directory path
        job_id = os.path.basename(os.path.abspath(job_dir))

        try:
            # Use advanced isolated workspace setup (clones HEAD, no branch creation)
            result = workspace_utils.setup_isolated_workspace(job_id, job_dir, base_branch="main")
            if not result["success"]:
                raise click.ClickException(f"Failed to setup isolated workspace: {result['error']}")

        except Exception as e:
            raise click.ClickException(f"Advanced workspace setup failed: {e}")


class RoleManager:
    """Manages agent roles, loading them from configuration."""

    def list_roles(self, jobs_dir: str) -> list:
        """List all available agent roles by reading configuration files."""
        roles_data = []
        roles_config_path = jobs_dir

        if not os.path.exists(roles_config_path):
            click.secho(f"⚠️  Warning: Role configuration directory '{roles_config_path}' not found.", fg="yellow")
            return []

        for filename in os.listdir(roles_config_path):
            if filename.endswith(".md"):
                filepath = os.path.join(roles_config_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        role_content = f.read()
                    # Extract role name from filename (worker.md -> Worker)
                    role_name = filename.replace('.md', '').title()
                    roles_data.append({
                        "name": role_name,
                        "description": f"Role configuration for {role_name}"
                    })
                except Exception as e:
                    click.secho(f"⚠️  Warning: Could not read role file '{filename}': {e}", fg="yellow")
        return roles_data

    def inspect_role(self, role_name: str, jobs_dir: str) -> str:
        """Display the detailed configuration for a specific role."""
        roles_config_path = jobs_dir

        # Search for the role by filename (worker.md, supervisor.md, system.md)
        expected_filename = f"{role_name.lower()}.md"
        role_file_path = os.path.join(roles_config_path, expected_filename)

        if os.path.exists(role_file_path):
            try:
                with open(role_file_path, 'r') as f:
                    return f.read()
            except OSError as e:
                raise click.ClickException(f"Failed to read role file '{expected_filename}': {e}")

        raise click.ClickException(f"Role '{role_name}' not found (expected file: {expected_filename}).")



# Global instances for CLI
engine = LogistEngine()
manager = JobManager()
role_manager = RoleManager()


def init_command(jobs_dir: str) -> bool:
    """Initialize the jobs directory with default configurations."""
    try:
        # Import the resource loading utilities
        import json
        try:
            from importlib import resources as importlib_resources
        except ImportError:
            import importlib_resources

        os.makedirs(jobs_dir, exist_ok=True)

        roles_and_files_to_copy = ["worker.md", "supervisor.md", "system.md"]
        schema_copied_count = 0

        for role_file in roles_and_files_to_copy:
            # Load the schema from package resources
            try:
                resource_file = importlib_resources.files('logist') / 'schemas' / 'roles' / role_file
                with resource_file.open('r', encoding='utf-8') as f:
                    # Read as text for .md files
                    role_data = f.read()

                # Write to jobs directory
                dest_path = os.path.join(jobs_dir, role_file)
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(role_data)

                schema_copied_count += 1

            except (FileNotFoundError, IOError) as e:
                click.secho(f"⚠️  Warning: Failed to copy schema '{role_file}': {e}", fg="yellow")
            except Exception as e:
                click.secho(f"⚠️  Warning: Unexpected error copying '{role_file}': {e}", fg="yellow")

        # Create jobs index
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
        jobs_index_data = {
            "current_job_id": None,
            "jobs": {},
            "queue": []
        }
        with open(jobs_index_path, 'w') as f:
            json.dump(jobs_index_data, f, indent=2)

        click.echo(f"   📎 Copied {schema_copied_count} schema file(s)")

        return True
    except Exception as e:
        click.secho(f"❌ Error during initialization: {e}", fg="red")
        return False


def get_job_id(ctx, job_id_arg: str | None) -> str | None:
    if job_id_arg:
        return job_id_arg
    env_job_id = os.environ.get("LOGIST_JOB_ID")
    if env_job_id:
        click.echo(f"   → No job ID provided. Using LOGIST_JOB_ID environment variable: '{env_job_id}'")
        return env_job_id
    jobs_dir = ctx.obj["JOBS_DIR"]
    current_job_id = manager.get_current_job_id(jobs_dir)
    if current_job_id:
        click.echo(f"   → No job ID provided. Using current job from index: '{current_job_id}'")
    return current_job_id


def get_job_dir(ctx, job_id: str) -> str | None:
    jobs_dir = ctx.obj["JOBS_DIR"]
    jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
    try:
        with open(jobs_index_path, 'r') as f:
            jobs_index = json.load(f)
        jobs_map = jobs_index.get("jobs", {})
        return jobs_map.get(job_id)
    except (json.JSONDecodeError, OSError):
        return None


@click.group()
@click.version_option(version="0.1.0", prog_name="logist")
@click.option(
    "--jobs-dir",
    envvar="LOGIST_JOBS_DIR",
    default=os.path.expanduser("~/.logist/jobs"),
    help="The root directory for jobs and the jobs_index.json file.",
    type=click.Path(),
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug output for detailed operation logging.",
)
@click.pass_context
def main(ctx, jobs_dir, debug, enhance):
    """Logist - Sophisticated Agent Orchestration."""
    ctx.ensure_object(dict)
    ctx.obj["JOBS_DIR"] = jobs_dir
    ctx.obj["DEBUG"] = debug
    ctx.obj["ENHANCE"] = enhance
    ctx.obj["ENGINE"] = engine # Add the LogistEngine instance to context
    click.echo(f"⚓ Welcome to Logist - Using jobs directory: {jobs_dir}")


@main.group()
def job():
    """Manage job workflows and their execution state."""


@main.group()
def workspace():
    """Manage job workspaces and their lifecycle."""


@main.group()
def role():
    """Manage agent roles and their configurations."""


@job.command(name="create")
@click.argument("directory", type=click.Path(), default=".")
@click.pass_context
def create_job(ctx, directory: str):
    """Initialize a directory as a job or update it."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo(f"✨ Executing 'logist job create' on directory '{directory}'")
    job_id = manager.create_job(directory, jobs_dir)
    click.echo(f"🎯 Job '{job_id}' created/updated and selected.")


@job.command(name="select")
@click.argument("job_id")
@click.pass_context
def select_job(ctx, job_id: str):
    """Set a job as the currently selected one."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo(f"📌 Executing 'logist job select {job_id}'")
    manager.select_job(job_id, jobs_dir)
    click.echo(f"✅ '{job_id}' is now the current job.")


@job.command(name="config")
@click.argument("job_id", required=False)
@click.option("--objective", help="Set the job objective")
@click.option("--details", help="Set the job details/requirements")
@click.option("--acceptance", help="Set the acceptance criteria")
@click.option("--prompt", help="Set the task prompt description")
@click.option("--files", help="Set relevant files (comma-separated)")
@click.pass_context
def config_job(ctx, job_id: str | None, objective: str, details: str, acceptance: str, prompt: str, files: str):
    """Configure a DRAFT job with properties before activation."""
    click.echo("⚙️  Executing 'logist job config'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        raise click.ClickException("❌ No job ID provided and no current job is selected.")

    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        raise click.ClickException(f"❌ Job '{final_job_id}' not found.")

    # Validate that at least one option is provided
    if not any([objective, details, acceptance, prompt, files]):
        raise click.ClickException("❌ At least one configuration option must be provided (--objective, --details, --acceptance, --prompt, or --files)")

    # Check job state - must be DRAFT to configure
    try:
        manifest = load_job_manifest(job_dir)
        current_status = manifest.get("status")
        if current_status != JobStates.DRAFT:
            raise click.ClickException(f"❌ Job '{final_job_id}' is in '{current_status}' state. Only DRAFT jobs can be configured.")
    except JobStateError as e:
        raise click.ClickException(f"❌ Error loading job manifest: {e}")

    # Load existing config or create new one
    config_path = os.path.join(job_dir, "config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}
    except json.JSONDecodeError as e:
        raise click.ClickException(f"❌ Invalid existing config.json: {e}")

    # Update config with provided values
    updated = False
    if objective is not None:
        config["objective"] = objective
        updated = True
        click.echo(f"   📝 Set objective: {objective}")

    if details is not None:
        config["details"] = details
        updated = True
        click.echo(f"   📝 Set details: {details}")

    if acceptance is not None:
        config["acceptance"] = acceptance
        updated = True
        click.echo(f"   📝 Set acceptance criteria: {acceptance}")

    if prompt is not None:
        config["prompt"] = prompt
        updated = True
        click.echo(f"   📝 Set prompt: {prompt}")

    if files is not None:
        files_list = [f.strip() for f in files.split(',') if f.strip()]
        config["files"] = files_list
        updated = True
        click.echo(f"   📝 Set files: {', '.join(files_list)}")

    if updated:
        # Validate against schema
        try:
            from jsonschema import validate, ValidationError
            script_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(script_dir, "..", "schemas", "job_config.json")
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            validate(instance=config, schema=schema)
        except ValidationError as e:
            raise click.ClickException(f"❌ Configuration validation failed: {e.message}")
        except (OSError, json.JSONDecodeError) as e:
            raise click.ClickException(f"❌ Error loading schema: {e}")

        # Save updated config
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            click.secho(f"   ✅ Job '{final_job_id}' configuration updated successfully", fg="green")
        except OSError as e:
            raise click.ClickException(f"❌ Failed to save configuration: {e}")
    else:
        click.echo("   ℹ️  No changes made to configuration")

    # Show current config summary
    click.echo("   📋 Current configuration:")
    for key, value in config.items():
        if key == "files":
            click.echo(f"      {key}: {', '.join(value) if value else 'none'}")
        else:
            click.echo(f"      {key}: {value if value else 'none'}")


@job.command()
@click.argument("job_id", required=False)
@click.option("--model", default="grok-code-fast-1", help="LLM model for execution")
@click.option("--resume", is_flag=True, help="Resume from last checkpoint")
@click.pass_context
def run(ctx, job_id: str | None, model: str, resume: bool):
    """Execute a job continuously until completion."""
    click.echo("🎯 Executing 'logist job run'")

    jobs_dir = ctx.obj["JOBS_DIR"]
    jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")

    # If specific job_id provided, use it (bypass queue)
    if job_id:
        final_job_id = job_id
    else:
        # Get next job from queue
        try:
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise click.ClickException(f"❌ Failed to read jobs index: {e}")

        queue = jobs_index.get("queue", [])
        if not queue:
            click.secho("📭 No jobs in queue. Add jobs with 'logist job activate'.", fg="yellow")
            return

        final_job_id = queue[0]
        click.echo(f"   📋 Selected job from queue: '{final_job_id}' (position 0)")

    job_dir = get_job_dir(ctx, final_job_id)
    if job_dir is None:
        click.secho("❌ Could not find job directory.", fg="red")
        return

    # Execute the job
    success = engine.run_job(ctx, final_job_id, job_dir)

    # If execution completed successfully and job succeeded, remove from queue
    if success:
        try:
            manifest = load_job_manifest(job_dir)
            final_status = manifest.get("status")
            if final_status in ["SUCCESS", "CANCELED"]:
                # Remove completed job from queue
                try:
                    with open(jobs_index_path, 'r') as f:
                        jobs_index = json.load(f)

                    queue = jobs_index.get("queue", [])
                    if final_job_id in queue:
                        queue.remove(final_job_id)
                        click.echo(f"   🗑️  Removed '{final_job_id}' from queue (status: {final_status})")

                        # Save updated queue
                        with open(jobs_index_path, 'w') as f:
                            json.dump(jobs_index, f, indent=2)

                except (json.JSONDecodeError, OSError, JobStateError):
                    # Don't fail if queue cleanup fails - job execution succeeded
                    click.secho("   ⚠️  Warning: Failed to remove job from queue", fg="yellow")

        except Exception as e:
            # Don't fail if status check fails - job execution might still have succeeded
            click.secho(f"   ⚠️  Warning: Failed to check final job status: {e}", fg="yellow")


@job.command()
@click.argument("job_id", required=False)
@click.option(
    "--dry-run", is_flag=True, help="Simulate a full step without making real calls."
)
@click.option(
    "--model", default="grok-code-fast-1", help="Override default model selection for agents"
)
@click.pass_context
def step(ctx, job_id: str | None, dry_run: bool, model: str):
    """Execute single phase of job and pause."""
    click.echo("👣 Executing 'logist job step'")
    if final_job_id := get_job_id(ctx, job_id):
        job_dir = get_job_dir(ctx, final_job_id)
        if job_dir is None:
            click.secho("❌ Could not find job directory.", fg="red")
            return
        engine.step_job(ctx, final_job_id, job_dir, dry_run=dry_run, model=model)
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


@job.command(name="rerun")
@click.argument("job_id")
@click.option(
    "--step",
    type=int,
    default=None,
    help="Zero-indexed phase number to start rerunning from. If not specified, starts from the beginning."
)
@click.pass_context
def rerun(ctx, job_id: str, step: int | None):
    """Re-execute a previously completed job, or resume from a specific step."""
    click.echo("🔄 Executing 'logist job rerun'")

    # Get job directory
    job_dir = get_job_dir(ctx, job_id)
    if job_dir is None:
        click.secho(f"❌ Job '{job_id}' not found.", fg="red")
        return

    # Validate step number if provided
    if step is not None and step < 0:
        click.secho("❌ Step number must be a non-negative integer.", fg="red")
        return

    try:
        # Execute the rerun logic
        engine.rerun_job(ctx, job_id, job_dir, start_step=step)
    except Exception as e:
        click.secho(f"❌ Error during job rerun: {e}", fg="red")


@job.command(name="restep")
@click.argument("job_id", required=False)
@click.option(
    "--step",
    type=int,
    required=True,
    help="Zero-indexed phase number to rewind to as a checkpoint."
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be restored without making changes."
)
@click.pass_context
def restep(ctx, job_id: str | None, step: int, dry_run: bool):
    """Rewind job execution to a previous checkpoint within the current run."""
    click.echo("⏪ Executing 'logist job restep'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")
        return

    # Get job directory
    job_dir = get_job_dir(ctx, final_job_id)
    if job_dir is None:
        click.secho(f"❌ Job '{final_job_id}' not found.", fg="red")
        return

    # Validate step number
    if step < 0:
        click.secho("❌ Step number must be a non-negative integer.", fg="red")
        return

    try:
        # Execute the restep logic
        success = engine.restep_job(ctx, final_job_id, job_dir, step, dry_run=dry_run)
        if success:
            if dry_run:
                click.secho(f"   ✅ Dry run completed - no changes made", fg="blue")
            else:
                click.secho(f"   ✅ Job '{final_job_id}' successfully rewound to step {step}", fg="green")
        else:
            click.secho(f"❌ Failed to restep job '{final_job_id}'", fg="red")
    except Exception as e:
        click.secho(f"❌ Error during job restep: {e}", fg="red")


@job.command()
@click.argument("job_id", required=False)
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON instead of formatted text")
@click.option("--recovery", is_flag=True, help="Show recovery status and perform validation")
@click.pass_context
def status(ctx, job_id: str | None, output_json: bool, recovery: bool):
    """Display job status and manifest."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo("📋 Executing 'logist job status'")
    if final_job_id := get_job_id(ctx, job_id):
        try:
            status_data = manager.get_job_status(final_job_id, jobs_dir)
            job_dir = get_job_dir(ctx, final_job_id)

            # Recovery validation
            if job_dir:
                try:
                    recovery_result = validate_state_persistence(job_dir)
                    if recovery_result["recovered"]:
                        click.secho(f"🔄 Recovery performed: {recovery_result['recovery_from']}", fg="blue")
                        # Reload status data after recovery
                        status_data = manager.get_job_status(final_job_id, jobs_dir)

                    if recovery_result["errors"]:
                        for error in recovery_result["errors"]:
                            click.secho(f"⚠️  Recovery warning: {error}", fg="yellow")

                except (RecoveryError, Exception) as e:
                    click.secho(f"⚠️  Recovery validation failed: {e}", fg="yellow")

            # Show recovery status if requested
            if recovery and job_dir:
                try:
                    recovery_status = get_recovery_status(job_dir)
                    click.echo("🔧 Recovery Status:")
                    click.echo(f"   🗂️  Backups available: {recovery_status['backups_available']}")
                    if recovery_status['last_backup']:
                        click.echo(f"   🕐 Last backup: {recovery_status['last_backup']}")
                    click.echo(f"   💔 State consistent: {recovery_status['state_consistent']}")
                    click.echo(f"   🚨 Recovery needed: {recovery_status['recovery_needed']}")
                    if recovery_status['hung_process_detected']:
                        click.echo("   ⏰ Hung process detected!")
                except Exception as e:
                    click.secho(f"⚠️  Could not get recovery status: {e}", fg="yellow")

            if output_json:
                click.echo(json.dumps(status_data, indent=2))
            else:
                click.echo(f"\n📋 Job '{final_job_id}' Status:")
                click.echo(f"   📍 Description: {status_data.get('description', 'No description')}")
                click.echo(f"   🔄 Status: {status_data.get('status', 'UNKNOWN')}")
                click.echo(f"📊 Phase: {status_data.get('current_phase', 'none')}")

                # Calculate and display enhanced metrics
                try:
                    metrics_snapshot = calculate_detailed_metrics(status_data)

                    # Cost information with threshold status
                    if metrics_snapshot.cost_threshold > 0:
                        cost_percentage = metrics_snapshot.cost_percentage
                        cost_status_icon = "🟢" if metrics_snapshot.status_color == "green" else "🟡" if metrics_snapshot.status_color == "yellow" else "🔴"
                        click.echo(f"   💰 Cost: ${metrics_snapshot.cumulative_cost:.4f} ({cost_percentage:.1f}% of ${metrics_snapshot.cost_threshold:.0f}) {cost_status_icon}")
                        if metrics_snapshot.cost_remaining > 0:
                            click.echo(f"      Remaining budget: ${metrics_snapshot.cost_remaining:.4f}")
                        else:
                            click.echo(f"      Over budget by: ${abs(metrics_snapshot.cost_remaining):.4f}")

                    # Time information with threshold status
                    if metrics_snapshot.time_threshold_minutes > 0:
                        time_percentage = metrics_snapshot.time_percentage
                        time_status_icon = "🟢" if metrics_snapshot.status_color == "green" else "🟡" if metrics_snapshot.status_color == "yellow" else "🔴"
                        total_minutes = metrics_snapshot.cumulative_time_seconds / 60
                        click.echo(f"   ⏱️  Time: {total_minutes:.1f} min ({time_percentage:.1f}% of {metrics_snapshot.time_threshold_minutes:.0f} min) {time_status_icon}")
                        if metrics_snapshot.time_remaining_minutes > 0:
                            click.echo(f"      Remaining time: {metrics_snapshot.time_remaining_minutes:.1f} minutes")
                        else:
                            click.echo(f"      Over time by: {abs(metrics_snapshot.time_remaining_minutes):.1f} minutes")

                    # Token usage summary if available
                    if metrics_snapshot.total_tokens > 0:
                        click.echo(f"   🧠 Total Tokens: {metrics_snapshot.total_tokens:,}")
                        if metrics_snapshot.total_tokens_cache_read > 0:
                            click.echo(f"      📚 Cached Read Tokens: {metrics_snapshot.total_tokens_cache_read:,}")
                        if metrics_snapshot.total_cache_hits > 0:
                            click.echo(f"      🎯 Cache Hits: {metrics_snapshot.total_cache_hits:,}")

                    # Steps summary
                    click.echo(f"   📈 Steps: {metrics_snapshot.step_count}")

                except Exception as e:
                    # Fall back to basic metrics display if enhanced calculation fails
                    click.secho(f"⚠️  Enhanced metrics calculation failed: {e}", fg="yellow")
                    metrics = status_data.get('metrics', {})
                    if metrics:
                        click.echo(f"   💰 Cost: ${metrics.get('cumulative_cost', 0):.4f}")
                        click.echo(f"   ⏱️  Time: {metrics.get('cumulative_time_seconds', 0):.2f} seconds")

                # Show history (unchanged)
                history = status_data.get('history', [])
                if history:
                    click.echo("   📚 Recent History:")
                    for event in history[-3:]:  # Show last 3 events
                        click.echo(f"   • {event}")
                else:
                    click.echo("   📚 History: No events recorded yet")
        except click.ClickException as e:
            click.secho(f"❌ {e}", fg="red")
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


@job.command()
@click.argument("job_id", required=False)
@click.option(
    "--csv",
    "export_csv",
    type=click.Path(),
    help="Export detailed metrics to CSV file at specified path."
)
@click.option(
    "--projections",
    is_flag=True,
    help="Show cost and time projections for job completion."
)
@click.option(
    "--remaining-phases",
    type=int,
    default=5,
    help="Number of remaining phases to use for projections (default: 5)."
)
@click.pass_context
def metrics(ctx, job_id: str | None, export_csv: str, projections: bool, remaining_phases: int):
    """Display detailed metrics, cost tracking, and budget analysis for a job."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo("📊 Executing 'logist job metrics'")

    if final_job_id := get_job_id(ctx, job_id):
        try:
            status_data = manager.get_job_status(final_job_id, jobs_dir)

            click.echo(f"\n📈 Detailed Metrics for Job '{final_job_id}'")
            click.echo("=" * 60)

            # Calculate detailed metrics
            metrics_snapshot = calculate_detailed_metrics(status_data)
            history = status_data.get("history", [])

            # Overall metrics summary
            click.echo("📊 OVERALL METRICS:")
            click.echo(f"   💰 Total Cost: ${metrics_snapshot.cumulative_cost:.4f}")
            click.echo(f"   ⏱️  Total Time: {metrics_snapshot.cumulative_time_seconds:.1f} seconds ({metrics_snapshot.cumulative_time_seconds/60:.1f} minutes)")

            if metrics_snapshot.cost_threshold > 0:
                cost_status_icon = "🟢" if metrics_snapshot.status_color == "green" else "🟡" if metrics_snapshot.status_color == "yellow" else "🔴"
                click.echo(f"   📈 Cost Budget: ${metrics_snapshot.cost_threshold:.0f} ({metrics_snapshot.cost_percentage:.1f}% used) {cost_status_icon}")
                click.echo(f"   💵 Remaining Budget: ${metrics_snapshot.cost_remaining:.4f}")

            if metrics_snapshot.time_threshold_minutes > 0:
                time_status_icon = "🟢" if metrics_snapshot.status_color == "green" else "🟡" if metrics_snapshot.status_color == "yellow" else "🔴"
                click.echo(f"   ⏳ Time Budget: {metrics_snapshot.time_threshold_minutes:.0f} min ({metrics_snapshot.time_percentage:.1f}% used) {time_status_icon}")
                click.echo(f"   🕐 Remaining Time: {metrics_snapshot.time_remaining_minutes:.1f} minutes")

            if metrics_snapshot.total_tokens > 0:
                click.echo(f"   🧠 Total Tokens: {metrics_snapshot.total_tokens:,}")

            click.echo(f"   📈 Steps Executed: {metrics_snapshot.step_count}")

            # Per-step breakdown
            click.echo("\n📋 PER-STEP BREAKDOWN:")
            if history:
                click.echo("   Step | Role      | Action    | Cost     | Time (s) | In Tokens | Out Tokens | Cached Read | Cache Hit")
                click.echo("   ---- | --------- | --------- | -------- | -------- | --------- | ---------- | ----------- | ---------")

                for i, entry in enumerate(history):
                    role = entry.get("role", "Unknown")[:9]
                    action = entry.get("action", "Unknown")[:9]
                    metrics_entry = entry.get("metrics", {})
                    cost = metrics_entry.get("cost_usd", 0.0)
                    time_seconds = metrics_entry.get("duration_seconds", 0.0)
                    token_input = metrics_entry.get("token_input", 0)
                    token_output = metrics_entry.get("token_output", 0)
                    token_cache_read = metrics_entry.get("token_cache_read", 0)
                    cache_hit = "Yes" if metrics_entry.get("cache_hit", False) else "No"

                    click.echo(f"   {i:4d} | {role:<9} | {action:<9} | ${cost:>7.4f} | {time_seconds:>8.1f} | {token_input:>9,d} | {token_output:>10,d} | {token_cache_read:>11,d} | {cache_hit:<9}")
            else:
                click.echo("   No execution history available.")

            # Projections if requested
            if projections:
                click.echo(f"\n🔮 PROJECTIONS (based on {remaining_phases} remaining phases):")

                try:
                    projection_data = generate_cost_projections(status_data, remaining_phases)

                    click.echo("   Cost Analysis:")
                    click.echo(f"   • Current Cost: ${projection_data['current_cost']:.4f}")
                    click.echo(f"   • Average Cost/Step: ${projection_data['average_cost_per_step']:.4f}")
                    click.echo(f"   • Projected Additional: ${projection_data['projected_cost_remaining']:.4f}")
                    click.echo(f"   • Projected Total: ${projection_data['projected_total_cost']:.4f}")
                    click.echo(f"   • Budget Status: {projection_data['cost_status']}")

                    click.echo("   Time Analysis:")
                    click.echo(f"   • Current Time: {projection_data['current_time_minutes']:.1f} minutes")
                    click.echo(f"   • Average Time/Step: {projection_data['average_time_per_step_minutes']:.1f} minutes")
                    click.echo(f"   • Projected Additional: {projection_data['projected_time_remaining_minutes']:.1f} minutes")
                    click.echo(f"   • Projected Total: {projection_data['projected_total_time_minutes']:.1f} minutes")
                    click.echo(f"   • Time Status: {projection_data['time_status']}")

                    click.echo("   Recommendations:")
                    for rec in projection_data['recommendations']:
                        click.echo(f"   • {rec}")

                    click.echo(f"   Confidence: {projection_data['confidence_level']}")

                except Exception as e:
                    click.secho(f"   ⚠️  Projection calculation failed: {e}", fg="yellow")

            # CSV export if requested
            if export_csv:
                try:
                    csv_path = export_metrics_to_csv(get_job_dir(ctx, final_job_id), export_csv)
                    click.secho(f"   📄 Metrics exported to CSV: {csv_path}", fg="green")
                except Exception as e:
                    click.secho(f"   ❌ CSV export failed: {e}", fg="red")

        except Exception as e:
            click.secho(f"❌ Error retrieving metrics: {e}", fg="red")
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


@job.command(name="chat")
@click.argument("job_id", required=False)
@click.pass_context
def job_chat(ctx, job_id: str | None):
    """Start an interactive chat session with the Cline task associated with a job."""
    click.echo("💬 Executing 'logist job chat'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")
        return

    # Get job directory
    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        click.secho(f"❌ Could not find job directory for '{final_job_id}'.", fg="red")
        return

    try:
        # Load job manifest
        manifest = load_job_manifest(job_dir)
        current_status = manifest.get("status", "UNKNOWN")

        # Validate job state - cannot chat during active execution
        if current_status in ["RUNNING", "REVIEWING"]:
            click.secho(f"❌ Cannot chat with job '{final_job_id}' in '{current_status}' state.", fg="red")
            click.echo("   💡 Chat is only available when the job is not actively running.")
            click.echo("   💡 Valid states: PENDING, INTERVENTION_REQUIRED, SUCCESS, CANCELED, etc.")
            return

        # Extract cline_task_id from history
        history = manifest.get("history", [])
        if not history:
            click.secho(f"❌ Job '{final_job_id}' has no execution history - cannot chat.", fg="red")
            click.echo("   💡 Run the job first with 'logist job step' to create a chat session.")
            return

        # Get the most recent history entry with a cline_task_id
        cline_task_id = None
        for entry in reversed(history):  # Most recent first
            if "cline_task_id" in entry and entry["cline_task_id"]:
                cline_task_id = entry["cline_task_id"]
                break

        if not cline_task_id:
            click.secho(f"❌ No Cline task ID found in job '{final_job_id}' history.", fg="red")
            click.echo("   💡 This job may not have been executed yet or has no associated Cline tasks.")
            return

        click.secho(f"⚡ Connecting to Cline task '{cline_task_id}' for job '{final_job_id}'", fg="green")

        # Execute cline task chat
        import subprocess
        cmd = ["cline", "task", "chat", cline_task_id]

        # Run the command - this will block and allow interactive chat
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            click.secho(f"❌ Failed to start chat session: {e}", fg="red")
        except KeyboardInterrupt:
            click.echo("\n💬 Chat session ended.")

    except JobStateError as e:
        click.secho(f"❌ Error accessing job manifest: {e}", fg="red")
    except Exception as e:
        click.secho(f"❌ Unexpected error during chat: {e}", fg="red")


@job.command()
@click.argument("job_id", required=False)
@click.option(
    "--response-file",
    type=click.Path(exists=True),
    help="Path to JSON file containing the simulated LLM response."
)
@click.option(
    "--response-string",
    help="JSON string containing the simulated LLM response."
)
@click.option(
    "--role",
    help="Specify the agent role (Worker/Supervisor). If not provided, uses current state."
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Parse input and show what would happen without making changes."
)
@click.pass_context
def poststep(ctx, job_id: str | None, response_file: str, response_string: str, role: str, dry_run: bool):
    """Process a simulated LLM response to advance job state."""
    click.echo("📤 Executing 'logist job poststep'")

    # Validate input options - exactly one of --response-file or --response-string must be provided
    if not response_file and not response_string:
        raise click.ClickException("Must provide either --response-file or --response-string")
    if response_file and response_string:
        raise click.ClickException("Cannot provide both --response-file and --response-string")

    # Get job ID and validate
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        raise click.ClickException("❌ No job ID provided and no current job is selected.")

    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        raise click.ClickException(f"❌ Could not find job directory for '{final_job_id}'.")

    try:
        # Load and parse the simulated response
        if response_file:
            click.echo(f"   📄 Loading simulated response from file: {response_file}")
            with open(response_file, 'r') as f:
                simulated_response = json.load(f)
        else:
            click.echo("   📋 Processing simulated response from string input")
            try:
                simulated_response = json.loads(response_string)
            except json.JSONDecodeError as e:
                raise click.ClickException(f"Invalid JSON in response string: {e}")

        click.echo(f"   ✅ Loaded simulated response with action: {simulated_response.get('action', 'unknown')}")

        # Validate the response against schema
        from logist.job_processor import validate_llm_response
        validate_llm_response(simulated_response)
        click.echo("   ✅ Response validated against schema")

        # Determine active role
        if role:
            active_role = role
            click.echo(f"   👤 Using specified role: {active_role}")
        else:
            # Get current state and role from job manifest
            from logist.job_state import get_current_state_and_role, load_job_manifest
            manifest = load_job_manifest(job_dir)
            _, active_role = get_current_state_and_role(manifest)
            click.echo(f"   👤 Using role from current job state: {active_role}")

        # Process the simulated response
        from logist.job_processor import process_simulated_response
        results = process_simulated_response(
            job_dir=job_dir,
            job_id=final_job_id,
            simulated_response=simulated_response,
            active_role=active_role,
            dry_run=dry_run
        )

        if results["success"]:
            click.secho(f"   ✅ Successfully processed simulated response for job '{final_job_id}'", fg="green")
        else:
            click.secho(f"❌ Failed to process simulated response: {results.get('error', 'Unknown error')}", fg="red")
            return

    except (click.ClickException, Exception) as e:
        click.secho(f"❌ Error during job poststep: {e}", fg="red")
        raise


@job.command(name="list")
@click.pass_context
def list_jobs(ctx):
    """List all active jobs."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo("📜 Executing 'logist job list'")
    jobs = manager.list_jobs(jobs_dir)

    if not jobs:
        click.echo("📭 No active jobs found")
        return

    jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
    current_job_id = None
    queue = []
    try:
        if os.path.exists(jobs_index_path):
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
            current_job_id = jobs_index.get("current_job_id")
            queue = jobs_index.get("queue", [])
    except (json.JSONDecodeError, OSError):
        pass

    click.echo("\n📋 Active Jobs:")
    click.echo("-" * 100)
    click.echo("Job ID               Status       Queue Pos   Description")
    click.echo("-" * 100)

    for job in jobs:
        marker = " 👈" if job["job_id"] == current_job_id else ""
        status = job["status"]

        # Format queue position
        queue_pos = job.get("queue_position")
        if queue_pos is not None:
            if queue_pos == 0 and len(queue) > 0 and queue[0] == job["job_id"]:
                queue_pos_display = click.style(f"[{queue_pos}] 🏃", fg="green", bold=True)  # Next to run
            else:
                queue_pos_display = f"[{queue_pos}]"
        else:
            queue_pos_display = "—"

        # Color status
        if status == "PENDING":
            status_display = click.style(status, fg="yellow")
        elif status == "DRAFT":
            status_display = click.style(status, fg="blue")
        elif status in ["RUNNING", "SUCCESS"]:
            status_display = click.style(status, fg="green")
        elif status in ["STUCK", "FAILED", "CANCELED"]:
            status_display = click.style(status, fg="red")
        else:
            status_display = status

        click.echo(f"{job['job_id']:<20} {status_display:<12} {queue_pos_display:<12} {job['description']}{marker}")

    # Show queue summary
    if queue:
        click.echo("\n📋 Execution Queue:")
        click.echo("-" * 40)
        for i, job_id in enumerate(queue):
            next_indicator = " 🏃 NEXT" if i == 0 else ""
            job_desc = next((j["description"] for j in jobs if j["job_id"] == job_id), "Unknown job")
            job_desc_truncated = job_desc[:40] + "..." if len(job_desc) > 40 else job_desc
            click.echo(f"  {i}: {job_id} - {job_desc_truncated}{next_indicator}")


@job.command(name="git-status")
@click.argument("job_id", required=False)
@click.pass_context
def git_status(ctx, job_id: str | None):
    """Show detailed git status for a job's workspace."""
    click.echo("📊 Executing 'logist job git-status'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")
        return

    # Get job directory
    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        click.secho(f"❌ Job '{final_job_id}' not found.", fg="red")
        return

    # Use workspace_utils to get git status
    try:
        git_status_info = workspace_utils.get_workspace_git_status(job_dir)
        file_summary = workspace_utils.get_workspace_files_summary(job_dir)

        click.echo(f"\n🔍 Git Status for Job '{final_job_id}'")
        click.echo("=" * 60)
        click.echo(f"   📁 Workspace: {os.path.join(job_dir, 'workspace')}")

        if git_status_info["is_git_repo"]:
            click.echo(f"   🌿 Current Branch: {git_status_info['current_branch']}")
            click.echo(f"   📝 Staged Changes: {len(git_status_info['staged_changes'])} files")
            click.echo(f"   ✏️  Unstaged Changes: {len(git_status_info['unstaged_changes'])} files")
            click.echo(f"   ❓ Untracked Files: {len(git_status_info['untracked_files'])} files")

            if git_status_info["staged_changes"]:
                click.echo("   📝 Staged Files:")
                for file in git_status_info["staged_changes"][:10]:  # Limit display
                    click.echo(f"      • {file}")
                if len(git_status_info["staged_changes"]) > 10:
                    click.echo(f"      ... and {len(git_status_info['staged_changes']) - 10} more")

            if git_status_info["unstaged_changes"]:
                click.echo("   ✏️  Unstaged Files:")
                for file in git_status_info["unstaged_changes"][:10]:
                    click.echo(f"      • {file}")
                if len(git_status_info["unstaged_changes"]) > 10:
                    click.echo(f"      ... and {len(git_status_info['unstaged_changes']) - 10} more")

            if git_status_info["untracked_files"]:
                click.echo("   ❓ Untracked Files:")
                for file in git_status_info["untracked_files"][:10]:
                    click.echo(f"      • {file}")
                if len(git_status_info["untracked_files"]) > 10:
                    click.echo(f"      ... and {len(git_status_info["untracked_files"]) - 10} more")

            if git_status_info["recent_commits"]:
                click.echo("   📚 Recent Commits:")
                for commit in git_status_info["recent_commits"][:5]:
                    click.echo(f"      • {commit}")
        else:
            click.echo("   ⚠️  Not a git repository")

        # Show file summary
        if file_summary["tree"]:
            click.echo(f"   📂 Total Files: {len(file_summary['tree'])}")
            click.echo("   📋 File Types:")
            extensions = {}
            for file_path in file_summary["tree"]:
                if not file_path.endswith("/"):  # Skip directories
                    _, ext = os.path.splitext(file_path)
                    extensions[ext] = extensions.get(ext, 0) + 1

            for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]:
                ext_display = ext if ext else "(no extension)"
                click.echo(f"      • {ext_display}: {count} files")

        click.secho("   ✅ Git status retrieved successfully", fg="green")

    except Exception as e:
        click.secho(f"❌ Error getting git status: {e}", fg="red")


@job.command(name="git-log")
@click.argument("job_id", required=False)
@click.option(
    "--limit",
    type=int,
    default=10,
    help="Maximum number of commits to show (default: 10)."
)
@click.option(
    "--oneline",
    is_flag=True,
    help="Show compact one-line format."
)
@click.pass_context
def git_log(ctx, job_id: str | None, limit: int, oneline: bool):
    """Show commit history for a job's workspace."""
    click.echo("📚 Executing 'logist job git-log'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")
        return

    # Get job directory
    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        click.secho(f"❌ Job '{final_job_id}' not found.", fg="red")
        return

    # Get git log using workspace_utils
    try:
        workspace_dir = os.path.join(job_dir, "workspace")

        if not workspace_utils.verify_workspace_exists(job_dir):
            click.secho(f"❌ Workspace not initialized for job '{final_job_id}'.", fg="red")
            return

        import subprocess

        # Prepare git log command
        if oneline:
            cmd = ["git", "log", "--oneline", f"-{limit}"]
        else:
            cmd = ["git", "log", f"-{limit}", "--pretty=format:%h - %an, %ar : %s"]

        result = subprocess.run(
            cmd,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )

        commits = result.stdout.strip().split('\n') if result.stdout.strip() else []

        click.echo(f"\n📚 Commit History for Job '{final_job_id}'")
        click.echo("=" * 60)

        if commits:
            click.echo(f"   Showing last {min(limit, len(commits))} commits:")
            click.echo("")
            for i, commit in enumerate(commits, 1):
                click.echo(f"   {i:2d}. {commit}")
        else:
            click.echo("   📭 No commits found in this workspace")

        click.secho("   ✅ Git log retrieved successfully", fg="green")

    except subprocess.CalledProcessError as e:
        click.secho(f"❌ Git command failed: {e.stderr}", fg="red")
    except Exception as e:
        click.secho(f"❌ Error getting git log: {e}", fg="red")


@job.command(name="commit")
@click.argument("job_id", required=False)
@click.option(
    "--message",
    "-m",
    help="Commit message. If not provided, will use a default message."
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be committed without making the commit."
)
@click.pass_context
def manual_commit(ctx, job_id: str | None, message: str, dry_run: bool):
    """Manually commit changes in a job's workspace."""
    click.echo("💾 Executing 'logist job commit'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")
        return

    # Get job directory
    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        click.secho(f"❌ Job '{final_job_id}' not found.", fg="red")
        return

    # Prepare commit message
    if not message:
        message = f"Manual commit for job '{final_job_id}'"

    try:
        # Get current status to check for changes
        git_status = workspace_utils.get_workspace_git_status(job_dir)

        if not git_status["is_git_repo"]:
            click.secho(f"❌ Workspace not initialized for job '{final_job_id}'.", fg="red")
            return

        total_changes = len(git_status["staged_changes"]) + len(git_status["unstaged_changes"]) + len(git_status["untracked_files"])

        if total_changes == 0:
            click.secho("ℹ️  No changes to commit.", fg="yellow")
            return

        click.echo("   📝 Changes to commit:")
        if git_status["staged_changes"]:
            click.echo(f"      Staged: {len(git_status['staged_changes'])} files")
        if git_status["unstaged_changes"]:
            click.echo(f"      Unstaged: {len(git_status['unstaged_changes'])} files")
        if git_status["untracked_files"]:
            click.echo(f"      Untracked: {len(git_status['untracked_files'])} files")

        if dry_run:
            click.echo(f"   📋 Would commit with message: '{message}'")
            click.secho("   ✅ Dry run completed", fg="blue")
            return

        # Perform the commit
        commit_result = workspace_utils.perform_git_commit(
            job_dir=job_dir,
            evidence_files=[],  # No specific evidence files for manual commits
            summary=message
        )

        if commit_result["success"]:
            click.secho(f"   ✅ Successfully committed: {commit_result['commit_hash'][:8]}", fg="green")
            click.echo(f"   📂 Files committed: {len(commit_result['files_committed'])}")
            click.echo(f"   💬 Message: {message}")
        else:
            click.secho(f"   ❌ Commit failed: {commit_result['error']}", fg="red")

    except Exception as e:
        click.secho(f"❌ Error during commit: {e}", fg="red")


@job.command(name="merge-preview")
@click.argument("job_id", required=False)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for patch file. Defaults to job directory."
)
@click.option(
    "--format",
    type=click.Choice(["patch", "diff"]),
    default="patch",
    help="Output format: patch (default) or diff."
)
@click.option(
    "--since",
    help="Start point for diff (commit hash, branch, etc.). Defaults to branch creation."
)
@click.pass_context
def merge_preview(ctx, job_id: str | None, output: str, format: str, since: str):
    """Generate patch files from job branch for manual merge preparation."""
    click.echo("📋 Executing 'logist job merge-preview'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")
        return

    # Get job directory
    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        click.secho(f"❌ Job '{final_job_id}' not found.", fg="red")
        return

    try:
        workspace_dir = os.path.join(job_dir, "workspace")

        if not workspace_utils.verify_workspace_exists(job_dir):
            click.secho(f"❌ Workspace not initialized for job '{final_job_id}'.", fg="red")
            return

        # Get current branch info
        import subprocess

        # Get current branch name
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )
        current_branch = branch_result.stdout.strip()

        # Load manifest to get base branch
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        base_branch = "main"  # Default
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    # Try to determine base branch from workspace setup
                    if "workspace_branch" in manifest:
                        # The branch name contains job ID, so base is typically 'main'
                        base_branch = "main"
            except (json.JSONDecodeError, OSError):
                pass

        click.echo(f"\n📋 Merge Preview for Job '{final_job_id}'")
        click.echo("=" * 60)
        click.echo(f"   🌿 Job Branch: {current_branch}")
        click.echo(f"   🎯 Target Branch: {base_branch}")
        click.echo(f"   📁 Workspace: {workspace_dir}")

        # Determine start point for comparison
        start_point = since or base_branch

        # Check if there are differences
        diff_result = subprocess.run(
            ["git", "diff", "--name-only", start_point],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )

        changed_files = diff_result.stdout.strip().split('\n') if diff_result.stdout.strip() else []

        if not changed_files:
            click.secho("ℹ️  No changes to merge. Job branch is identical to base.", fg="yellow")
            return

        click.echo(f"   📝 Files changed: {len(changed_files)}")
        click.echo("   📄 Changed files:")
        for i, file in enumerate(changed_files[:10], 1):
            click.echo(f"      {i:2d}. {file}")
        if len(changed_files) > 10:
            click.echo(f"      ... and {len(changed_files) - 10} more")

        # Generate patch file
        if output:
            patch_path = output
        else:
            timestamp = subprocess.run(
                ["date", "+%Y%m%d_%H%M%S"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            patch_path = os.path.join(job_dir, f"merge_preview_{final_job_id}_{timestamp}.patch" if format == "patch" else f"merge_preview_{final_job_id}_{timestamp}.diff")

        # Use git format-patch for proper patch files, or git diff for simple diffs
        if format == "patch":
            # Generate patch using format-patch if we can determine the range
            # For simplicity, use git diff and create a patch format
            patch_cmd = ["git", "diff", start_point]
        else:
            patch_cmd = ["git", "diff", start_point]

        patch_result = subprocess.run(
            patch_cmd,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )

        if patch_result.stdout.strip():
            # Write patch file
            with open(patch_path, 'w') as f:
                # Add header information
                f.write(f"# Merge preview for job '{final_job_id}'\n")
                f.write(f"# Generated: {subprocess.run(['date'], capture_output=True, text=True, check=True).stdout.strip()}\n")
                f.write("# " + "="*60 + "\n")
                f.write(f"# Job Branch: {current_branch}\n")
                f.write(f"# Target Branch: {base_branch}\n")
                f.write(f"# Changed Files: {len(changed_files)}\n")
                f.write("# " + "="*60 + "\n\n")
                f.write(patch_result.stdout)

            click.secho(f"   📄 Patch file created: {patch_path}", fg="green")
            click.echo(f"   📊 Format: {format}")

            # Show summary statistics
            lines = patch_result.stdout.split('\n')
            additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
            deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))

            click.echo(f"   ➕ Additions: {additions} lines")
            click.echo(f"   ➖ Deletions: {deletions} lines")
            click.echo(f"   📏 Total changes: {additions + deletions} lines")

        else:
            click.secho("ℹ️  No diff content generated.", fg="yellow")

        click.secho("   ✅ Merge preview completed successfully", fg="green")
        click.echo("   💡 To apply this patch: git apply <patch_file>")
        click.echo("   💡 Or merge manually: git checkout main && git merge <job_branch>")

    except subprocess.CalledProcessError as e:
        click.secho(f"❌ Git command failed: {e.stderr}", fg="red")
    except Exception as e:
        click.secho(f"❌ Error generating merge preview: {e}", fg="red")


@role.command(name="list")
@click.pass_context
def list_roles(ctx):
    """List all available agent roles."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo("👥 Executing 'logist role list'")
    roles = role_manager.list_roles(jobs_dir)

    if not roles:
        click.echo("📭 No agent roles found.")
        return

    click.echo("\n📋 Available Agent Roles:")
    click.echo("-" * 40)
    for role_item in roles:
        click.echo(f"- {role_item['name']}: {role_item['description']}")
    click.echo("-" * 40)


@workspace.command(name="cleanup")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be cleaned up without actually doing it."
)
@click.option(
    "--force",
    is_flag=True,
    help="Override safety checks and force cleanup (dangerous)."
)
@click.option(
    "--job-id",
    help="Clean up workspace for a specific job only."
)
@click.option(
    "--max-backups",
    type=int,
    default=3,
    help="Maximum number of backups to keep per job."
)
@click.option(
    "--preserve-failed",
    is_flag=True,
    help="Preserve workspaces for failed jobs (overrides default policy)."
)
@click.pass_context
def workspace_cleanup(ctx, dry_run: bool, force: bool, job_id: str, max_backups: int, preserve_failed: bool):
    """Clean up completed workspaces based on policies."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo("🧹 Executing 'logist workspace cleanup'")

    try:
        # Build cleanup policies
        cleanup_policies = {
            "cleanup_completed_jobs": True,
            "cleanup_failed_jobs_after_days": 7,
            "cleanup_cancelled_jobs_after_days": 1,
            "preserve_failed_jobs": preserve_failed,
            "max_backups_per_job": max_backups
        }

        click.echo("📋 Cleanup policies:")
        click.echo(f"   ✅ Clean completed jobs: {cleanup_policies['cleanup_completed_jobs']}")
        click.echo(f"   📅 Failed job grace period: {cleanup_policies['cleanup_failed_jobs_after_days']} days")
        click.echo(f"   📅 Cancelled job grace period: {cleanup_policies['cleanup_cancelled_jobs_after_days']} days")
        click.echo(f"   🛡️  Preserve failed jobs: {cleanup_policies['preserve_failed_jobs']}")
        click.echo(f"   📦 Max backups per job: {cleanup_policies['max_backups_per_job']}")

        if job_id:
            click.echo(f"   🎯 Specific job: {job_id}")
            # Handle single job cleanup
            job_path = get_job_dir(ctx, job_id)
            if not job_path:
                click.secho(f"❌ Job '{job_id}' not found.", fg="red")
                return

            # Check if cleanup should happen
            should_cleanup, reason = workspace_utils.should_cleanup_workspace(job_path, cleanup_policies)

            if should_cleanup:
                if dry_run:
                    click.echo(f"   📋 Would clean up workspace for job '{job_id}': {reason}")
                    return

                click.echo(f"   🧹 Cleaning up workspace for job '{job_id}': {reason}")

                # Backup first
                backup_result = workspace_utils.backup_workspace_before_cleanup(job_path)
                if backup_result["success"]:
                    click.echo(f"   💾 Backup created: {os.path.basename(backup_result['backup_archive'])}")
                else:
                    if not force:
                        click.secho(f"❌ Backup failed: {backup_result['error']}", fg="red")
                        click.echo("   💡 Use --force to skip backup (dangerous)")
                        return
                    else:
                        click.secho("⚠️  Skipping backup due to --force flag", fg="yellow")

                # Clean up
                workspace_dir = os.path.join(job_path, "workspace")
                try:
                    shutil.rmtree(workspace_dir)
                    click.secho(f"   ✅ Workspace cleaned up for job '{job_id}'", fg="green")
                except OSError as e:
                    click.secho(f"❌ Cleanup failed: {e}", fg="red")
            else:
                click.echo(f"   ⏸️  Skipping job '{job_id}': {reason}")

        else:
            click.echo("   🔍 Scanning all jobs for cleanup opportunities...")
            if dry_run:
                click.echo("   📋 Dry run mode - no changes will be made")

            # Perform batch cleanup
            result = workspace_utils.cleanup_completed_workspaces(jobs_dir, cleanup_policies, dry_run=dry_run)

            if result["success"]:
                click.echo("\n📊 Cleanup Summary:")
                cleaned_count = len(result["workspaces_cleaned"])
                backed_up_count = len(result["workspaces_backed_up"])
                skipped_count = len(result["workspaces_skipped"])
                errors_count = len(result["errors"])

                click.echo(f"   🧹 Workspaces cleaned: {cleaned_count}")
                click.echo(f"   💾 Workspaces backed up: {backed_up_count}")
                click.echo(f"   ⏸️  Workspaces skipped: {skipped_count}")

                if errors_count > 0:
                    click.secho(f"   ❌ Errors: {errors_count}", fg="red")

                    if dry_run:
                        click.echo("   📋 Dry run completed successfully")

                # Show details
                if result["workspaces_cleaned"] and not dry_run:
                    click.echo("\n🧹 Cleaned workspaces:")
                    for item in result["workspaces_cleaned"]:
                        click.echo(f"   • {os.path.basename(item['job_path'])}: {item.get('reason', 'Unknown')}")

                if result["errors"]:
                    click.echo("\n❌ Errors encountered:")
                    for error in result["errors"]:
                        click.echo(f"   • {error}")

                if not dry_run and cleaned_count > 0:
                    click.secho("   ✅ Workspace cleanup completed!", fg="green")
                elif dry_run and cleaned_count > 0:
                    click.echo(f"   📋 Dry run: {cleaned_count} workspaces would be cleaned")
                else:
                    click.echo("   ℹ️  No workspaces needed cleanup")

            else:
                click.secho("❌ Cleanup operation failed", fg="red")
                for error in result["errors"]:
                    click.echo(f"   • {error}")

    except Exception as e:
        click.secho(f"❌ Error during workspace cleanup: {e}", fg="red")


@role.command(name="list")
@click.pass_context
def list_roles(ctx):
    """List all available agent roles."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo("👥 Executing 'logist role list'")
    roles = role_manager.list_roles(jobs_dir)

    if not roles:
        click.echo("📭 No agent roles found.")
        return

    click.echo("\n📋 Available Agent Roles:")
    click.echo("-" * 40)
    for role_item in roles:
        click.echo(f"- {role_item['name']}: {role_item['description']}")
    click.echo("-" * 40)


@role.command(name="inspect")
@click.argument("role_name")
@click.pass_context
def inspect_role(ctx, role_name: str):
    """Display the detailed configuration for a specific role."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo(f"👤 Executing 'logist role inspect {role_name}'")
    try:
        role_data = role_manager.inspect_role(role_name, jobs_dir)
        click.echo(json.dumps(role_data, indent=2))
    except click.ClickException as e:
        click.secho(f"❌ {e.message}", fg="red")


@main.command()
@click.pass_context
def init(ctx):
    """Initialize the jobs directory with default configurations."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo(f"🛠️  Executing 'logist init' with jobs directory: {jobs_dir}")

    jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
    if os.path.exists(jobs_index_path):
        click.secho("⚠️  Jobs directory appears to be already initialized.", fg="yellow")
        if not click.confirm("Do you want to reinitialize? This may overwrite existing files."):
            click.echo("❌ Initialization cancelled.")
            return

    if init_command(jobs_dir):
        click.secho("✅ Jobs directory initialized successfully!", fg="green")
        click.echo(f"   📁 Created directory: {jobs_dir}")
        click.echo("   📋 Created jobs_index.json")
        click.echo("   📎 Copied worker.md, supervisor.md, and system.md")
    else:
        click.secho("❌ Failed to initialize jobs directory.", fg="red")


@job.command(name="preview")
@click.argument("job_id", required=False)
@click.option(
    "--detailed",
    is_flag=True,
    help="Show detailed context preparation information."
)
@click.pass_context
def preview_job(ctx, job_id: str | None, detailed: bool):
    """Preview job execution context and file preparation."""
    click.echo("👁️  Executing 'logist job preview'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")
        return

    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        click.secho(f"❌ Job '{final_job_id}' not found.", fg="red")
        return

    try:
        # Load job manifest
        manifest = load_job_manifest(job_dir)
        current_status = manifest.get("status", "UNKNOWN")

        click.echo(f"🔍 Preview for Job '{final_job_id}'")
        click.echo("=" * 50)
        click.echo(f"   📁 Job Directory: {job_dir}")

        # Setup workspace for preview
        manager.setup_workspace(job_dir)

        # Determine current phase and role
        try:
            current_phase_name, active_role = get_current_state_and_role(manifest)
            click.echo(f"   📍 Current Phase: {current_phase_name}")
            click.echo(f"   👤 Active Role: {active_role}")
            click.echo(f"   📊 Status: {current_status}")
        except JobStateError as e:
            if "current_phase" in str(e):
                click.secho(f"❌ Error during job preview: Job manifest is missing 'current_phase'.", fg="red")
                click.echo("   💡 This job requires a job specification with phases to be previewed.")
                click.echo("   💡 Try one of the following:")
                click.echo("      • Create the job with a sample spec: cp config/sample-job.json job_dir/ && logist job create job_dir")
                click.echo("      • Configure the job manually with phases, then re-run preview")
                return
            else:
                raise

        # Load role configuration
        role_config_path = os.path.join(ctx.obj["JOBS_DIR"], f"{active_role.lower()}.json")
        if os.path.exists(role_config_path):
            with open(role_config_path, 'r') as f:
                role_config = json.load(f)
            click.echo(f"   📋 Role Config: {role_config_path}")
        else:
            click.secho(f"   ⚠️  Role config not found: {role_config_path}", fg="yellow")
            return

        # Simulate what step_job does: prepare context, workspace, and file arguments
        click.echo(f"\n📋 Context assembled for execution:")

        workspace_dir = os.path.join(job_dir, "workspace")
        context = assemble_job_context(job_dir, manifest, ctx.obj["JOBS_DIR"], active_role, enhance=ctx.obj.get("ENHANCE", False))
        context = enhance_context_with_previous_outcome(context, job_dir)

        # Prepare workspace with attachments and file discovery
        prep_result = workspace_utils.prepare_workspace_attachments(job_dir, workspace_dir)

        # Prepare outcome attachments from previous step
        outcome_prep = prepare_outcome_for_attachments(job_dir, workspace_dir)

        # Final file arguments that would be passed to cline
        file_arguments = prep_result["file_arguments"] + outcome_prep["attachments_added"] if prep_result["success"] else []

        if detailed:
            click.echo("\n🔧 Detailed Preparation:")

            if prep_result["success"]:
                if prep_result["attachments_copied"]:
                    click.echo(f"   📎 Attachments copied: {len(prep_result['attachments_copied'])} files")
                    for attachment in prep_result["attachments_copied"][:5]:  # Show first 5
                        click.echo(f"      • {os.path.relpath(attachment, job_dir)}")
                    if len(prep_result["attachments_copied"]) > 5:
                        click.echo(f"      ... and {len(prep_result['attachments_copied']) - 5} more")

                if prep_result["discovered_files"]:
                    click.echo(f"   🔍 Files discovered: {len(prep_result['discovered_files'])} files")
                    for discovered_file in prep_result["discovered_files"][:5]:  # Show first 5
                        click.echo(f"      • {os.path.basename(discovered_file)}")
                    if len(prep_result["discovered_files"]) > 5:
                        click.echo(f"      ... and {len(prep_result['discovered_files']) - 5} more")

            else:
                click.secho(f"   ⚠️  Workspace preparation failed: {prep_result['error']}", fg="yellow")

        click.echo("\n📝 FULL CONTEXT TO BE SENT TO CLINE:")
        click.echo("=" * 60)
        click.echo(context)
        click.echo("=" * 60)

        click.echo(f"\n📁 --FILE ATTACHMENTS ({len(file_arguments)} total):")
        if file_arguments:
            for i, filearg in enumerate(file_arguments, 1):
                click.echo(f"   {i:2d}. {os.path.relpath(filearg, workspace_dir) if workspace_dir in filearg else os.path.basename(filearg)}")
                click.echo(f"       Full path: {filearg}")
        else:
            click.echo("   (none)")

        if not detailed:
            click.echo("\n💡 Use --detailed for comprehensive preparation details")

        debug_mode = ctx.obj.get("DEBUG", False)
        if debug_mode:
            click.echo("\n🔍 DEBUG INFORMATION:")

            # Show manifest details
            click.echo("   📋 Job Manifest:")
            click.echo(f"      Job ID: {manifest.get('job_id')}")
            click.echo(f"      Description: {manifest.get('description')}")
            click.echo(f"      Status: {manifest.get('status')}")
            click.echo(f"      Current Phase: {manifest.get('current_phase')}")

            phases = manifest.get("phases", [])
            if phases:
                click.echo(f"      Phases: {len(phases)} total")
                for i, phase in enumerate(phases):
                    if hasattr(phase, 'get'):
                        prefix = " -> " if phase.get('name') == manifest.get('current_phase') else "    "
                        click.echo(f"{prefix}Phase {i}: {phase.get('name')} - {phase.get('description', 'No description')}")

            # Show metrics if available
            metrics = manifest.get("metrics", {})
            if metrics:
                click.echo(f"      Metrics: ${metrics.get('cumulative_cost', 0):.4f} cost, {metrics.get('cumulative_time_seconds', 0):.1f}s time")

            # Show context details
            click.echo("   🧠 Context Details:")
            click.echo(f"      Context Keys: {list(context.keys()) if isinstance(context, dict) else 'String context'}")
            click.echo(f"      Context Size: {len(context):.1f} KB")
            click.echo(f"      Context Lines: {len(context.split(chr(10))) if isinstance(context, str) else 'N/A'}")

            # Show file attachment details
            if prep_result["success"]:
                click.echo("   📄 File Processing Details:")
                click.echo(f"      Workspace directory: {os.path.relpath(workspace_dir, job_dir)}")
                click.echo(f"      From workspace prep: {len(prep_result.get('file_arguments', []))} files")
                click.echo(f"      From previous outcomes: {len(outcome_prep.get('attachments_added', []))} files")

            # Show role configuration
            click.echo("   👤 Role Configuration:")
            if os.path.exists(role_config_path):
                try:
                    with open(role_config_path, 'r') as f:
                        role_config_display = json.load(f)
                    click.echo(f"      Role: {role_config_display.get('name')}")
                    click.echo(f"      Description: {role_config_display.get('description')}")
                    click.echo(f"      Config Path: {os.path.relpath(role_config_path, job_dir)}")
                except Exception as e:
                    click.echo(f"      Error loading role config: {e}")
            else:
                click.echo(f"      Config not found: {role_config_path}")

            # Show what the actual cline command would look like
            click.echo("   💻 Equivalent Cline Command Preview:")
            click.echo("   Would execute:")
            click.echo(f"      cline oneshot task \\")
            click.echo("        --workspace {workspace_dir} \\")
            if file_arguments:
                for filearg in file_arguments[:5]:  # Show first 5
                    click.echo(f"        --file '{filearg}' \\")
                if len(file_arguments) > 5:
                    click.echo(f"        ... and {len(file_arguments) - 5} more file arguments \\")
            click.echo("        --prompt '...' (full context shown above)")
            click.echo(f"   💡 Total context size: {len(context)} characters")
            if file_arguments:
                click.echo(f"   💡 Total file attachments: {len(file_arguments)}")

        # Write to jobHistory.json for preview operation logging with debug display
        from datetime import datetime
        job_history_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": "preview-only",
            "cost": 0.0,
            "execution_time_seconds": 0.0,
            "request": {
                "operation": "preview",
                "job_id": final_job_id,
                "phase": context.get('current_phase', 'unknown'),
                "role": context.get('role_name', 'unknown'),
                "detailed": detailed
            },
            "response": {
                "action": "PREVIEW_COMPLETED",
                "summary_for_supervisor": f"Preview completed for phase '{current_phase_name}', role '{active_role}'",
                "evidence_files": [],
                "metrics": {}
            }
        }
        # Access the engine from context and write history entry
        engine = ctx.obj.get("ENGINE")
        if engine:
            engine._write_job_history_entry(job_dir, job_history_entry)

            # Debug verbose logging
            debug_mode = ctx.obj.get("DEBUG", False)
            engine._show_debug_history_info(debug_mode, "preview", final_job_id, job_history_entry)
        else:
            click.secho("⚠️  Warning: LogistEngine not available in context for history logging", fg="yellow")

        click.secho("   ✅ Preview completed successfully", fg="green")

    except Exception as e:
        click.secho(f"❌ Error during job preview: {e}", fg="red")


@job.command(name="activate")
@click.argument("job_id", required=False)
@click.option(
    "--rank",
    type=int,
    help="Queue position (0=front, 1=second, etc.). Default: append to end."
)
@click.pass_context
def activate_job(ctx, job_id: str | None, rank: int):
    """Activate a DRAFT job for execution and add to processing queue."""
    click.echo("🚀 Executing 'logist job activate'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        raise click.ClickException("❌ No job ID provided and no current job is selected.")

    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        raise click.ClickException(f"❌ Job '{final_job_id}' not found.")

    # Check job state - must be DRAFT to activate
    try:
        manifest = load_job_manifest(job_dir)
        current_status = manifest.get("status")
        if current_status != JobStates.DRAFT:
            raise click.ClickException(f"❌ Job '{final_job_id}' is in '{current_status}' state. Only DRAFT jobs can be activated.")
    except JobStateError as e:
        raise click.ClickException(f"❌ Error loading job manifest: {e}")

    # Validate rank parameter
    if rank is not None and rank < 0:
        raise click.ClickException("❌ Rank must be a non-negative integer.")

    try:
        # Transition job state from DRAFT to PENDING
        new_status = transition_state(JobStates.DRAFT, "System", "ACTIVATED")
        if new_status != JobStates.PENDING:
            raise click.ClickException(f"❌ State transition failed: expected PENDING, got {new_status}")

        # Ensure current_phase is initialized when activating
        # If phases array is missing or empty, create a default single-phase job
        phases = manifest.get("phases", [])
        if not phases:
            # Create default phase array for jobs without explicit phases
            phases = [{"name": "default", "description": "Default single phase"}]
            manifest["phases"] = phases  # Update manifest with default phases
            click.echo(f"   📍 Initialized job with default single phase")

            # Save the updated manifest with phases before updating status/phase
            manifest_path = os.path.join(job_dir, "job_manifest.json")
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

        # Set current_phase to first phase if not already set
        if manifest.get("current_phase") is None:
            current_phase = phases[0]["name"]
            click.echo(f"   📍 Initialized current_phase to: '{current_phase}'")
        else:
            current_phase = manifest["current_phase"]  # Keep existing if already set

        # Update job manifest (this will only update status and phase now)
        update_job_manifest(job_dir=job_dir, new_status=new_status, new_phase=current_phase)

        # Load/update jobs index to add job to queue
        jobs_dir = ctx.obj["JOBS_DIR"]
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")

        try:
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
        except (json.JSONDecodeError, OSError):
            jobs_index = {"current_job_id": None, "jobs": {}}

        # Initialize queue if not present
        if "queue" not in jobs_index:
            jobs_index["queue"] = []

        # Remove job from queue if already present (shouldn't be, but safety check)
        if final_job_id in jobs_index["queue"]:
            jobs_index["queue"].remove(final_job_id)

        # Insert job at specified rank or append to end
        if rank is not None:
            if rank >= len(jobs_index["queue"]):
                jobs_index["queue"].append(final_job_id)
            else:
                jobs_index["queue"].insert(rank, final_job_id)
        else:
            jobs_index["queue"].append(final_job_id)

        # Save updated jobs index
        with open(jobs_index_path, 'w') as f:
            json.dump(jobs_index, f, indent=2)

        click.secho(f"   ✅ Job '{final_job_id}' activated successfully!", fg="green")
        click.echo(f"   🔄 Status changed: {JobStates.DRAFT} → {new_status}")
        click.echo(f"   📊 Queue position: {jobs_index['queue'].index(final_job_id)}")

        # Generate prompt.md if config exists
        config_path = os.path.join(job_dir, "config.json")
        prompt_path = os.path.join(job_dir, "prompt.md")

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)

                prompt_content = []
                if config.get("prompt"):
                    prompt_content.append(config["prompt"])
                    prompt_content.append("")  # Blank line

                sections = [
                    ("objective", "Objective"),
                    ("details", "Details"),
                    ("acceptance", "Acceptance Criteria")
                ]

                for key, title in sections:
                    if config.get(key):
                        prompt_content.append(f"<{key}>")
                        prompt_content.append(config[key])
                        prompt_content.append(f"</{key}>")
                        prompt_content.append("")  # Blank line

                if prompt_content:
                    with open(prompt_path, 'w') as f:
                        f.write("\n".join(prompt_content).rstrip())

                    click.echo("   📝 Generated prompt.md from configuration")
            except (json.JSONDecodeError, OSError) as e:
                click.secho(f"   ⚠️  Failed to generate prompt.md: {e}", fg="yellow")
        else:
            click.echo("   ℹ️  No configuration found - skipping prompt.md generation")

        # Show final queue state
        if jobs_index["queue"]:
            click.echo("   📋 Current queue:")
            for i, queue_job_id in enumerate(jobs_index["queue"]):
                marker = " ←" if queue_job_id == final_job_id else ""
                click.echo(f"      {i}: {queue_job_id}{marker}")

    except (click.ClickException, Exception) as e:
        click.secho(f"❌ Error during job activation: {e}", fg="red")
        raise


if __name__ == "__main__":
    main()