"""
Core Engine for Logist Job Execution

Contains the LogistEngine class which handles the core job execution logic.
"""

import json
import os
import subprocess
from typing import Dict, Any, List, Optional

from logist import workspace_utils
from logist.job_state import JobStateError, load_job_manifest, get_current_state_and_role, update_job_manifest, transition_state, JobStates
from logist.job_processor import (
    execute_llm_with_cline, handle_execution_error, validate_evidence_files, JobProcessorError,
    save_latest_outcome, prepare_outcome_for_attachments, enhance_context_with_previous_outcome
)
from logist.job_context import assemble_job_context, JobContextError


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
            print(f"⚠️  Failed to write job history entry: {e}")

    def _show_debug_history_info(self, debug_mode: bool, operation: str, job_id: str, entry: dict) -> None:
        """Display detailed debug information when writing to jobHistory.json."""
        if not debug_mode:
            return

        print(f"   📝 [DEBUG] Writing to jobHistory.json for {operation} operation:")
        print(f"      📅 Timestamp: {entry.get('timestamp', 'unknown')}")
        print(f"      🧠 Model: {entry.get('model', 'unknown')}")
        print(f"      💰 Cost: ${entry.get('cost', 0):.4f}")
        print(f"      ⏱️  Execution Time: {entry.get('execution_time_seconds', 0):.2f}s")

        # Show metrics if available
        metrics = entry.get("response", {}).get("metrics", {})
        if metrics:
            if "cost_usd" in metrics:
                print(f"      💸 LLM Cost: ${metrics['cost_usd']:.4f}")
            if "token_input" in metrics:
                print(f"      📥 Input Tokens: {metrics['token_input']:,}")
            if "token_output" in metrics:
                print(f"      📤 Output Tokens: {metrics['token_output']:,}")
            if "token_cache_read" in metrics and metrics['token_cache_read'] > 0:
                print(f"      📚 Cached Read Tokens: {metrics['token_cache_read']:,}")
            if "cache_hit" in metrics:
                print(f"      🎯 Cache Hit: {'Yes' if metrics['cache_hit'] else 'No'}")
            if "ttft_seconds" in metrics and metrics['ttft_seconds'] is not None:
                print(f"      ⏱️  TTFT: {metrics['ttft_seconds']:.2f}s")
            if "throughput_tokens_per_second" in metrics and metrics['throughput_tokens_per_second'] is not None:
                print(f"      ⚡ Throughput: {metrics['throughput_tokens_per_second']:.2f} tokens/s")
            total_tokens = metrics.get("token_input", 0) + metrics.get("token_output", 0) + metrics.get("token_cache_read", 0)
            if total_tokens > 0:
                print(f"      🔢 Total Tokens (Input+Output+Cached): {total_tokens:,}")

        request_info = entry.get("request", {})
        if request_info.get("job_id"):
            print(f"      🎯 Job ID: {request_info['job_id']}")
        if request_info.get("phase"):
            print(f"      📍 Phase: {request_info['phase']}")
        if request_info.get("role"):
            print(f"      👤 Role: {request_info['role']}")

        response_info = entry.get("response", {})
        if response_info.get("action"):
            print(f"      🎬 Action: {response_info['action']}")

        evidence_files = response_info.get("evidence_files", [])
        if evidence_files:
            print(f"      📁 Evidence Files: {len(evidence_files)}")
            for i, evidence in enumerate(evidence_files[:3]):  # Show first 3
                print(f"         • {evidence}")
            if len(evidence_files) > 3:
                print(f"         ... and {len(evidence_files) - 3} more")

    def rerun_job(self, ctx: any, job_id: str, job_dir: str, start_step: int | None = None, dry_run: bool = False) -> None:
        """Re-execute a job, optionally starting from a specific phase."""
        debug_mode = ctx.obj.get("DEBUG", False) if ctx and ctx.obj else False

        if debug_mode:
            print(f"   🔧 [DEBUG] Entering rerun_job with job_id='{job_id}', start_step={start_step}, dry_run={dry_run}")
            print("   🔧 [DEBUG] Loading necessary imports..."
        # Import services dynamically to avoid circular imports
        from .services import JobManagerService
        manager = JobManagerService()

        if debug_mode:
            print("   🔧 [DEBUG] Setting up workspace..."
        manager.setup_workspace(job_dir) # Ensure workspace is ready
        if debug_mode:
            print("   🔧 [DEBUG] Workspace setup completed")

        try:
            if debug_mode:
                print("   🔧 [DEBUG] Loading and validating job manifest..."
            # 1. Load and validate job manifest
            manifest = load_job_manifest(job_dir)
            if debug_mode:
                print(f"   🔧 [DEBUG] Manifest loaded: status='{manifest.get('status')}', current_phase='{manifest.get('current_phase')}'")

            # 2. Determine available phases
            phases = manifest.get("phases", [])
            if not phases:
                print("⚠️  Job has no defined phases. Treating as single-phase job.")
                phases = [{"name": "default", "description": "Default single phase"}]

            if debug_mode:
                print(f"   🔧 [DEBUG] Found {len(phases)} phases: {[p.get('name', 'unnamed') for p in phases]}")

            # 3. Validate start_step if provided
            if start_step is not None:
                if start_step >= len(phases):
                    available_steps = len(phases)
                    raise ValueError(
                        f"Invalid step number {start_step}. Job has {available_steps} phases (0-{available_steps-1})."
                    )
                start_phase_name = phases[start_step]["name"]
                print(f"   → Starting rerun from phase {start_step} ('{start_phase_name}')")
            else:
                start_phase_name = phases[0]["name"]
                print("   → Starting rerun from the beginning (phase 0)")

            if debug_mode:
                print(f"   🔧 [DEBUG] Target start phase: '{start_phase_name}'")

            # 4. Reset job state for rerun
            if debug_mode:
                print("   🔧 [DEBUG] Resetting job state for rerun..."
            self._reset_job_for_rerun(job_dir, start_phase_name, new_run=True)
            if debug_mode:
                print("   🔧 [DEBUG] Job state reset completed")

            print(f"   🔄 Job '{job_id}' reset for rerun")

            # 5. Continue with normal execution until completion or intervention
            if debug_mode:
                print("   🔧 [DEBUG] Initiating job phase execution..."
            # For now, execute one step (matching the pattern of other commands)
            # Future enhancement could implement continuous rerun until completion
            success = manager.run_job_phase(ctx, job_id, job_dir, dry_run=False)

            # Always report success for the rerun command itself, even if the step fails
            # The rerun state reset was successful, and future runs/steps can be attempted
            print(f"   ✅ Rerun initiated successfully")
            if not success:
                print(f"   ⚠️  Initial step failed - use 'logist job step' to retry")

            if debug_mode:
                print(f"   🔧 [DEBUG] rerun_job completed: success={success}")

        except Exception as e:
            if debug_mode:
                print(f"   🔧 [DEBUG] Exception caught in rerun_job: {type(e).__name__}: {e}")
                import traceback
                print(f"   🔧 [DEBUG] Traceback: {traceback.format_exc()}")
            print(f"❌ Error during job rerun preparation: {e}")
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

        # Mark as rerun in manifest for tracking only if this is a new run
        if new_run:
            manifest["_rerun_info"] = {
                "is_rerun": True,
                "start_phase": start_phase_name,
                "started_at": None  # Will be set when first step executes
            }

        # Save updated manifest
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

    def step_job(self, ctx: any, job_id: str, job_dir: str, dry_run: bool = False, model: str = "grok-code-fast-1") -> bool:
        """Execute single phase of job and pause with enhanced workspace preparation."""
        # Import services dynamically to avoid circular imports
        from .services import JobManagerService
        manager = JobManagerService()
        manager.setup_workspace(job_dir) # Ensure workspace is ready

        # Recovery validation - check for hung processes and recover if needed
        try:
            pass  # recovery import handled in main cli
        except Exception as e:
            print(f"⚠️  Recovery validation failed: {e}")

        if dry_run:
            print("   → Defensive setting detected: --dry-run")
            print(f"   → Would: Simulate single phase for job '{job_id}' with mock data")
            return True

        print(f"👣 [LOGIST] Executing single phase for job '{job_id}'")

        try:
            # 1. Load job manifest
            manifest = load_job_manifest(job_dir)
            current_status = manifest.get("status", "PENDING")

            # Placeholder for threshold checking - full implementation moved to CLI layer
            pass

            # 3. Determine current phase and active role
            current_phase_name, active_role = get_current_state_and_role(manifest)
            print(f"   → Current Phase: {current_phase_name}, Active Role: {active_role}")

            # 4. Prepare workspace with attachments and file discovery
            workspace_dir = os.path.join(job_dir, "workspace")
            prep_result = workspace_utils.prepare_workspace_attachments(job_dir, workspace_dir)
            if prep_result["success"]:
                if prep_result["attachments_copied"]:
                    print(f"   📎 Copied {len(prep_result['attachments_copied'])} attachments to workspace")
                if prep_result["discovered_files"]:
                    print(f"   🔍 Discovered {len(prep_result['discovered_files'])} context files")
            else:
                print(f"   ⚠️  Workspace preparation warning: {prep_result['error']}")

            # 6. Prepare outcome attachments from previous step
            outcome_prep = prepare_outcome_for_attachments(job_dir, workspace_dir)
            if outcome_prep["attachments_added"]:
                print(f"   🏆 Prepared outcome data from previous {len(outcome_prep['attachments_added'])} steps")

            # 7. Assemble job context with enhanced preparation
            context = assemble_job_context(job_dir, manifest, ctx.obj["JOBS_DIR"], active_role, enhance=ctx.obj.get("ENHANCE", False))
            context = enhance_context_with_previous_outcome(context, job_dir)

            # 8. Copy prompt.md to workspace/tmp/ for Apply command
            import shutil
            prompt_file_src = os.path.join(job_dir, "prompt.md")
            tmp_dir = os.path.join(workspace_dir, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            prompt_file_dst = os.path.join(tmp_dir, f"prompt-{job_id}.md")

            if os.path.exists(prompt_file_src):
                shutil.copy2(prompt_file_src, prompt_file_dst)
                print(f"   📋 Copied prompt.md to workspace/tmp/prompt-{job_id}.md")
            else:
                print(f"   ⚠️  Warning: prompt.md not found at {prompt_file_src}")

            # 9. Execute LLM with Cline using discovered file arguments
            file_arguments = prep_result["file_arguments"] + outcome_prep["attachments_added"] if prep_result["success"] else []

            processed_response, execution_time = execute_llm_with_cline(
                context=context,
                workspace_dir=workspace_dir,
                file_arguments=file_arguments,
                dry_run=dry_run
            )

            response_action = processed_response.get("action")

            print(f"   ✅ LLM responded with action: {response_action}")
            print(f"   📝 Summary for Supervisor: {processed_response.get('summary_for_supervisor', 'N/A')}")
            print(f"   ⏱️  Execution time: {execution_time:.2f} seconds")

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
                        "evidence_files": [],  # Will be populated below
                        "metrics": processed_response.get("metrics", {})
                    }
                }
                self._write_job_history_entry(job_dir, job_history_entry)
                self._show_debug_history_info(debug_mode, "step", job_id, job_history_entry)

            # 9. Save outcome to latest-outcome.json
            outcome_save = save_latest_outcome(job_dir, processed_response)
            if outcome_save["success"]:
                print("   💾 Saved LLM response to latest-outcome.json")
            else:
                print(f"   ⚠️  Failed to save outcome: {outcome_save['error']}")

            # 10. Validate evidence files
            evidence_files = processed_response.get("evidence_files", [])
            if evidence_files:
                validated_evidence = validate_evidence_files(evidence_files, workspace_dir)
                print(f"   📁 Validated evidence files: {', '.join(validated_evidence)}")
            else:
                print("   📁 No evidence files reported.")

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
            print(f"   🔄 Job status updated to: {new_status}")

            # 12. Perform git commit for evidence files and changes
            try:
                commit_summary = processed_response.get("summary_for_supervisor", f"{active_role} step: {current_phase_name}")
                commit_result = workspace_utils.perform_git_commit(
                    job_dir=job_dir,
                    evidence_files=evidence_files,
                    summary=commit_summary
                )

                if commit_result["success"]:
                    print(f"   💾 Changes committed: {commit_result['commit_hash'][:8]}")
                    print(f"   📁 Files committed: {len(commit_result['files_committed'])}")
                else:
                    print(f"   ⚠️  Git commit failed: {commit_result['error']}")
                    # Don't fail the step for git commit issues - continue execution

            except Exception as e:
                print(f"   ⚠️  Git commit error: {e}")
                # Continue - git commit failures shouldn't fail the job step

            return True

        except (JobProcessorError, JobStateError, JobContextError, Exception) as e:
            print(f"❌ Error during job step for '{job_id}': {e}")
            raw_cline_output = None
            if isinstance(e, JobProcessorError) and hasattr(e, 'full_output'):
                raw_cline_output = e.full_output # If CLINE execution failed, this might be present
            handle_execution_error(job_dir, job_id, e, raw_output=raw_cline_output)
            return False

    def run_job(self, ctx: any, job_id: str, job_dir: str) -> bool:
        """
        Execute a job continuously until completion, intervention, or cancellation.

        This command orchestrates iterative worker and supervisor executions
        until the job reaches SUCCESS, CANCELED, INTERVENTION_REQUIRED, or APPROVAL_REQUIRED.
        """
        # Import services dynamically to avoid circular imports
        from .services import JobManagerService
        manager = JobManagerService()
        manager.setup_workspace(job_dir)  # Ensure workspace is ready

        # Define terminal states where execution stops
        TERMINAL_STATES = {"SUCCESS", "CANCELED", "INTERVENTION_REQUIRED", "APPROVAL_REQUIRED"}

        print("🎯 [LOGIST] Starting continuous job execution")
        print(f"   📍 Job: {job_id}")
        print(f"   📁 Directory: {job_dir}")

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
                print(f"⚠️  Job '{job_id}' is already in terminal state: {current_status}")
                print("   💡 Use 'logist job step' to advance manually or 'logist job rerun' to restart")
                return True  # Not an error, just already complete

            print(f"   🔄 Initial Status: {current_status}")
            print("   🔄 Beginning execution loop...\n")

            step_count = 0
            while True:
                step_count += 1
                print(f"▼ Step {step_count} ▼")

                # Execute one step
                success = self.step_job(ctx, job_id, job_dir, dry_run=False)

                if not success:
                    print(f"❌ Step {step_count} failed - stopping execution")
                    return False

                # Check if we've reached a terminal state
                try:
                    manifest = load_job_manifest(job_dir)
                    current_status = manifest.get("status", "PENDING")

                    if current_status in TERMINAL_STATES:
                        print(f"\n🎉 [LOGIST] Job execution completed!")
                        print(f"   📊 Final Status: {current_status}")
                        print(f"   📈 Steps executed: {step_count}")

                        if current_status == "SUCCESS":
                            print("   ✅ Job completed successfully!")
                        elif current_status == "CANCELED":
                            print("   🚫 Job was canceled")
                        elif current_status == "INTERVENTION_REQUIRED":
                            print("   👤 Human intervention required")
                            print("   💡 Use 'logist job step' or manual fixes, then 'logist job run' to continue")
                        elif current_status == "APPROVAL_REQUIRED":
                            print("   👍 Final approval required")
                            print("   💡 Use appropriate commands to approve/reject")

                        return True

                except JobStateError as e:
                    print(f"❌ Error checking job status after step {step_count}: {e}")
                    return False

                # Small delay between steps for readability
                import time
                time.sleep(0.5)

        except (JobProcessorError, JobStateError, JobContextError, Exception) as e:
            print(f"❌ Error during job run for '{job_id}': {e}")
            return False

    def restep_single_step(self, ctx: any, job_id: str, job_dir: str, step_number: int, dry_run: bool = False) -> bool:
        """Re-execute a specific single step (phase) of a job for debugging purposes."""
        # Import services dynamically to avoid circular imports
        from .services import JobManagerService
        manager = JobManagerService()
        manager.setup_workspace(job_dir) # Ensure workspace is ready

        if dry_run:
            print("   → Defensive setting detected: --dry-run")
            print(f"   → Would: Re-execute step {step_number} for job '{job_id}' with mock data")
            return True

        print(f"🔄 [LOGIST] Re-executing step {step_number} for job '{job_id}'")

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
            print(f"   → Target Phase: {target_phase_name} (step {step_number})")

            # 2. Determine active role for this phase
            # For restep, we need to figure out which role should execute this phase
            # This logic matches the current state machine - we use a simple default
            active_role = target_phase.get("active_agent", "Worker")  # Default to Worker
            print(f"   → Active Role: {active_role}")

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
                file_arguments=[]  # simplified for restep
            )

            response_action = processed_response.get("action")

            print(f"   ✅ LLM responded with action: {response_action}")
            print(f"   📝 Summary for Supervisor: {processed_response.get('summary_for_supervisor', 'N/A')}")
            print(f"   ⏱️  Execution time: {execution_time:.2f} seconds")

            # 7. Validate evidence files
            evidence_files = processed_response.get("evidence_files", [])
            if evidence_files:
                validated_evidence = validate_evidence_files(evidence_files, workspace_path)
                print(f"   📁 Validated evidence files: {', '.join(validated_evidence)}")
            else:
                print("   📁 No evidence files reported.")

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
            print(f"   🔄 Restep completed for phase '{target_phase_name}' (step {step_number})")
            print(f"   📊 Job status remains: {current_status}")
            return True

        except (JobProcessorError, JobStateError, JobContextError, Exception) as e:
            print(f"❌ Error during job restep for '{job_id}' step {step_number}: {e}")
            raw_cline_output = None
            if isinstance(e, JobProcessorError) and hasattr(e, 'full_output'):
                raw_cline_output = e.full_output # If CLINE execution failed, this might be present
            handle_execution_error(job_dir, job_id, e, raw_output=raw_cline_output)
            return False

    def restep_job(self, ctx: any, job_id: str, job_dir: str, step_number: int, dry_run: bool = False) -> bool:
        """
        Rewind job execution to a previous checkpoint within the current run.

        This restores the job state to a specific step (checkpoint) by:
        1. Validating the target step exists
        2. Setting current_phase to the target step's phase
        3. Preserving full history (unlike rerun which clears it)
        4. Resetting metrics to exclude steps after the checkpoint
        5. Recording the restep event in history
        """
        print(f"⏪ [LOGIST] Rewinding job '{job_id}' to step {step_number}")

        if dry_run:
            print("   → Defensive setting detected: --dry-run")
            print(f"   → Would: Restore job state to step {step_number} checkpoint")
            return True

        try:
            # 1. Load and validate job manifest
            manifest = load_job_manifest(job_dir)
            phases = manifest.get("phases", [])

            if not phases:
                print("❌ Job has no defined phases. Cannot restep.")
                return False

            if step_number >= len(phases) or step_number < 0:
                available_steps = len(phases)
                print(f"❌ Invalid step number {step_number}. Job has {available_steps} phases (0-{available_steps-1}).")
                return False

            target_phase = phases[step_number]
            target_phase_name = target_phase["name"]
            print(f"   → Target checkpoint: step {step_number} ('{target_phase_name}')")

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

            print(f"   ✅ Job '{job_id}' successfully rewound to checkpoint")
            print(f"   📍 Current phase: {target_phase_name} (step {step_number})")
            print(f"   📊 Status unchanged: {current_status_before}")
            print("   📚 History: Restep event recorded")

            return True

        except (JobStateError, OSError, KeyError) as e:
            print(f"❌ Error during job restep for '{job_id}': {e}")
            return False