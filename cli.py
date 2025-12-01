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
from logist.job_state import JobStateError, load_job_manifest, get_current_state_and_role, update_job_manifest, transition_state
from logist.job_processor import execute_llm_with_cline, handle_execution_error, validate_evidence_files, JobProcessorError
from logist.job_context import assemble_job_context, JobContextError # Now exists


class LogistEngine:
    """Orchestration engine for Logist jobs."""

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
            if success:
                click.secho(f"   ✅ Rerun initiated successfully", fg="green")
            else:
                click.secho(f"   ❌ Rerun step failed", fg="red")

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

    def step_job(self, ctx: click.Context, job_id: str, job_dir: str, dry_run: bool = False) -> bool:
        """Execute single phase of job and pause."""
        manager.setup_workspace(job_dir) # Ensure workspace is ready

        if dry_run:
            click.secho("   → Defensive setting detected: --dry-run", fg="yellow")
            click.echo(f"   → Would: Simulate single phase for job '{job_id}' with mock data")
            return True

        click.echo(f"👣 [LOGIST] Executing single phase for job '{job_id}'")

        try:
            # 1. Load job manifest
            manifest = load_job_manifest(job_dir)
            current_status = manifest.get("status", "PENDING")

            # 2. Determine current phase and active role
            current_phase_name, active_role = get_current_state_and_role(manifest)
            click.echo(f"   → Current Phase: {current_phase_name}, Active Role: {active_role}")

            # 3. Load role configuration
            role_config_path = os.path.join(ctx.obj["JOBS_DIR"], f"{active_role.lower()}.json")
            if not os.path.exists(role_config_path):
                raise JobContextError(f"Role configuration not found for '{active_role}' at {role_config_path}")
            with open(role_config_path, 'r') as f:
                role_config = json.load(f)

            # 4. Assemble job context (simplified for now)
            workspace_path = os.path.join(job_dir, "workspace")
            context = assemble_job_context(job_dir, manifest, role_config)

            # 5. Execute LLM with Cline
            processed_response, execution_time = execute_llm_with_cline(
                context=context,
                workspace_dir=workspace_path,
                instruction_files=[role_config_path] # Pass role config as instruction
            )

            response_action = processed_response.get("action")

            click.secho(f"   ✅ LLM responded with action: {response_action}", fg="green")
            click.echo(f"   📝 Summary for Supervisor: {processed_response.get('summary_for_supervisor', 'N/A')}")
            click.echo(f"   ⏱️  Execution time: {execution_time:.2f} seconds")

            # 6. Validate evidence files
            evidence_files = processed_response.get("evidence_files", [])
            if evidence_files:
                validated_evidence = validate_evidence_files(evidence_files, workspace_path)
                click.echo(f"   📁 Validated evidence files: {', '.join(validated_evidence)}")
            else:
                click.echo("   📁 No evidence files reported.")

            # 7. Update job manifest
            new_status = transition_state(current_status, active_role, response_action)

            history_entry = {
                "role": active_role,
                "action": response_action,
                "summary": processed_response.get("summary_for_supervisor"),
                "metrics": processed_response.get("metrics", {}),
                "cline_task_id": processed_response.get("cline_task_id"),
                "new_status": new_status,
                "evidence_files": evidence_files # Store reported evidence files
            }

            update_job_manifest(
                job_dir=job_dir,
                new_status=new_status,
                cost_increment=processed_response.get("metrics", {}).get("cost_usd", 0.0),
                time_increment=execution_time,
                history_entry=history_entry
            )
            click.secho(f"   🔄 Job status updated to: {new_status}", fg="blue")
            return True

        except (JobProcessorError, JobStateError, JobContextError, Exception) as e:
            click.secho(f"❌ Error during job step for '{job_id}': {e}", fg="red")
            raw_cline_output = None
            if isinstance(e, JobProcessorError) and hasattr(e, 'full_output'):
                raw_cline_output = e.full_output # If CLINE execution failed, this might be present
            handle_execution_error(job_dir, job_id, e, raw_output=raw_cline_output)
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

            # 3. Load role configuration
            role_config_path = os.path.join(ctx.obj["JOBS_DIR"], f"{active_role.lower()}.json")
            if not os.path.exists(role_config_path):
                raise JobContextError(f"Role configuration not found for '{active_role}' at {role_config_path}")
            with open(role_config_path, 'r') as f:
                role_config = json.load(f)

            # 4. Prepare manifest for this specific step execution
            # Create a temporary manifest with current_phase set to the target phase
            restep_manifest = manifest.copy()
            restep_manifest["current_phase"] = target_phase_name

            # 5. Assemble job context for the target phase
            workspace_path = os.path.join(job_dir, "workspace")
            context = assemble_job_context(job_dir, restep_manifest, role_config)

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
            "status": "PENDING",
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

            # Process each job
            for job_id, job_path in jobs_map.items():
                job_manifest_path = os.path.join(job_path, "job_manifest.json")
                job_info = {
                    "job_id": job_id,
                    "path": job_path,
                    "status": "UNKNOWN",
                    "description": "No description available",
                    "phase": "unknown"
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
        """Setup isolated workspace by cloning local Git repository."""
        workspace_dir = os.path.join(job_dir, "workspace")
        workspace_git = os.path.join(workspace_dir, ".git")

        git_root = workspace_utils.find_git_root() # Use the function from the new module
        if git_root is None:
            raise click.ClickException("Not in a Git repository. Cannot setup workspace.")

        if os.path.exists(workspace_git):
            # Assume valid workspace exists
            return

        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        os.makedirs(job_dir, exist_ok=True)

        try:
            subprocess.run(
                ["git", "clone", git_root, "workspace"],
                cwd=job_dir,
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"Failed to clone workspace: {e.stderr}")


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
            if filename.endswith(".json"):
                filepath = os.path.join(roles_config_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        role_config = json.load(f)
                    if "name" in role_config and "description" in role_config:
                        roles_data.append({
                            "name": role_config["name"],
                            "description": role_config["description"]
                        })
                    else:
                        click.secho(f"⚠️  Warning: Skipping malformed role file '{filename}'. Missing 'name' or 'description'.", fg="yellow")
                except json.JSONDecodeError:
                    click.secho(f"⚠️  Warning: Skipping malformed JSON role file '{filename}'.", fg="yellow")
                except Exception as e:
                    click.secho(f"⚠️  Warning: Could not read role file '{filename}': {e}", fg="yellow")
        return roles_data

    def inspect_role(self, role_name: str, jobs_dir: str) -> dict:
        """Display the detailed configuration for a specific role."""
        roles_config_path = jobs_dir
        
        # Search for the role by name in the jobs_dir
        for filename in os.listdir(roles_config_path):
            if filename.endswith(".json"):
                filepath = os.path.join(roles_config_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        role_config = json.load(f)
                    if role_config.get("name") == role_name:
                        return role_config
                except json.JSONDecodeError:
                    continue # Skip malformed JSON files
        
        raise click.ClickException(f"Role '{role_name}' not found.")



# Global instances for CLI
engine = LogistEngine()
manager = JobManager()
role_manager = RoleManager()


def init_command(jobs_dir: str) -> bool:
    """Initialize the jobs directory with default configurations."""
    try:
        os.makedirs(jobs_dir, exist_ok=True)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schemas_dir = os.path.join(script_dir, "..", "schemas", "roles")

        roles_to_copy = ["worker.json", "supervisor.json"]
        for role_file in roles_to_copy:
            schema_path = os.path.join(schemas_dir, role_file)
            dest_path = os.path.join(jobs_dir, role_file)
            if os.path.exists(schema_path):
                shutil.copy2(schema_path, dest_path)
            else:
                click.secho(f"⚠️  Warning: Schema file '{role_file}' not found in '{schemas_dir}'", fg="yellow")

        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
        jobs_index_data = {"current_job_id": None}
        with open(jobs_index_path, 'w') as f:
            json.dump(jobs_index_data, f, indent=2)

        return True
    except (OSError, IOError) as e:
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
@click.pass_context
def main(ctx, jobs_dir):
    """Logist - Sophisticated Agent Orchestration."""
    ctx.ensure_object(dict)
    ctx.obj["JOBS_DIR"] = jobs_dir
    click.echo(f"⚓ Welcome to Logist - Using jobs directory: {jobs_dir}")


@main.group()
def job():
    """Manage job workflows and their execution state."""


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


@job.command()
@click.argument("job_id", required=False)
@click.option("--model", default="grok-code-fast-1", help="LLM model for execution")
@click.option("--resume", is_flag=True, help="Resume from last checkpoint")
@click.pass_context
def run(ctx, job_id: str | None, model: str, resume: bool):
    """Execute a job continuously until completion."""
    click.echo("🎯 Executing 'logist job run'")
    if final_job_id := get_job_id(ctx, job_id):
        job_dir = get_job_dir(ctx, final_job_id)
        if job_dir is None:
            click.secho("❌ Could not find job directory.", fg="red")
            return
        click.secho("The 'run' command is temporarily disabled as it's out of scope for this task.", fg="yellow")
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


@job.command()
@click.argument("job_id", required=False)
@click.option(
    "--dry-run", is_flag=True, help="Simulate a full step without making real calls."
)
@click.pass_context
def step(ctx, job_id: str | None, dry_run: bool):
    """Execute single phase of job and pause."""
    click.echo("👣 Executing 'logist job step'")
    if final_job_id := get_job_id(ctx, job_id):
        job_dir = get_job_dir(ctx, final_job_id)
        if job_dir is None:
            click.secho("❌ Could not find job directory.", fg="red")
            return
        engine.step_job(ctx, final_job_id, job_dir, dry_run=dry_run)
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


@job.command()
@click.argument("job_id", required=False)
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON instead of formatted text")
@click.pass_context
def status(ctx, job_id: str | None, output_json: bool):
    """Display job status and manifest."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo("📋 Executing 'logist job status'")
    if final_job_id := get_job_id(ctx, job_id):
        try:
            status_data = manager.get_job_status(final_job_id, jobs_dir)
            if output_json:
                click.echo(json.dumps(status_data, indent=2))
            else:
                click.echo(f"\n📋 Job '{final_job_id}' Status:")
                click.echo(f"   📍 Description: {status_data.get('description', 'No description')}")
                click.echo(f"   🔄 Status: {status_data.get('status', 'UNKNOWN')}")
                click.echo(f"📊 Phase: {status_data.get('current_phase', 'none')}")
                metrics = status_data.get('metrics', {})
                if metrics:
                    click.echo(f"   💰 Cost: ${metrics.get('cumulative_cost', 0):.4f}")
                    click.echo(f"   ⏱️  Time: {metrics.get('cumulative_time_seconds', 0):.2f} seconds")
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
    try:
        if os.path.exists(jobs_index_path):
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
            current_job_id = jobs_index.get("current_job_id")
    except (json.JSONDecodeError, OSError):
        pass

    click.echo("\n📋 Active Jobs:")
    click.echo("-" * 80)
    click.echo("Job ID               Status       Description" )
    click.echo("-" * 80)

    for job in jobs:
        marker = " 👈" if job["job_id"] == current_job_id else ""
        status = job["status"]
        if status == "PENDING":
            status_display = click.style(status, fg="yellow")
        elif status in ["RUNNING", "SUCCESS"]:
            status_display = click.style(status, fg="green")
        elif status in ["STUCK", "FAILED", "CANCELED"]:
            status_display = click.style(status, fg="red")
        else:
            status_display = status
        click.echo(f"{job['job_id']:<20} {status_display:<12} {job['description']}{marker}")


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
        click.echo("   📎 Copied worker.json and supervisor.json")
    else:
        click.secho("❌ Failed to initialize jobs directory.", fg="red")


if __name__ == "__main__":
    main()