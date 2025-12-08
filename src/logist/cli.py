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

from logist import workspace_utils  # Import the new module
from logist.core_engine import LogistEngine
from logist.services import JobManagerService, RoleManagerService
from logist.job_state import JobStateError, load_job_manifest, get_current_state_and_role, update_job_manifest, transition_state, JobStates
from logist.job_processor import (
    execute_llm_with_cline, handle_execution_error, validate_evidence_files, JobProcessorError,
    save_latest_outcome, prepare_outcome_for_attachments, enhance_context_with_previous_outcome
)
from logist.job_context import assemble_job_context, JobContextError  # Now exists
from logist.recovery import validate_state_persistence, get_recovery_status, RecoveryError
from logist.metrics_utils import check_thresholds_before_execution, calculate_detailed_metrics, generate_cost_projections, export_metrics_to_csv, ThresholdExceededError

# Create aliases for backward compatibility with tests
JobManager = JobManagerService
RoleManager = RoleManagerService






# Global instances for CLI
engine = LogistEngine()
manager = JobManagerService()
role_manager = RoleManagerService()


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

        roles_and_files_to_copy = ["worker.md", "worker.json", "supervisor.md", "supervisor.json", "system.md"]
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

        # Load default roles configuration from package resources
        roles_copied_count = 0
        try:
            resource_file = importlib_resources.files('logist') / 'schemas' / 'roles' / 'default-roles.json'
            with resource_file.open('r', encoding='utf-8') as f:
                default_roles = json.load(f)
        except (FileNotFoundError, IOError, json.JSONDecodeError) as e:
            # This should never happen in a properly installed package
            click.secho(f"❌ Error: Failed to load default roles resource: {e}", fg="red")
            click.secho("   This indicates a package installation problem.", fg="red")
            return False

        # Generate individual role JSON files and MD files (only for roles not copied from schemas)
        if default_roles and "roles" in default_roles:
            for role_name, role_config in default_roles["roles"].items():
                role_json_path = os.path.join(jobs_dir, f"{role_name.lower()}.json")
                role_md_path = os.path.join(jobs_dir, f"{role_name.lower()}.md")
                # Skip if we already copied this file from schemas
                if os.path.exists(role_json_path) and os.path.exists(role_md_path):
                    continue
                try:
                    # Create JSON config file
                    if not os.path.exists(role_json_path):
                        with open(role_json_path, 'w') as f:
                            json.dump(role_config, f, indent=2)
                        roles_copied_count += 1
                        click.echo(f"   📄 Generated {role_name.lower()}.json")

                    # Create MD instructions file
                    if not os.path.exists(role_md_path) and "instructions" in role_config:
                        with open(role_md_path, 'w') as f:
                            f.write(role_config["instructions"])
                        click.echo(f"   📝 Generated {role_name.lower()}.md")
                except OSError as e:
                    click.secho(f"⚠️  Warning: Failed to write role files for {role_name.lower()}: {e}", fg="yellow")

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
        click.echo(f"   📋 Generated {roles_copied_count} role config file(s)")
        click.echo("   📝 Generated role instructions file(s)")

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
@click.option(
    "--enhance",
    is_flag=True,
    help="Include full, enhanced context for LLM executions (job manifest, history, workspace details, role instructions, metrics). When absent, only file references and attachments are included."
)
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
def main(ctx, enhance, jobs_dir, debug):
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
@click.option("--rank", type=int, help="Set the execution queue position (0=front, -1=end)")
@click.option("--status", help="Set the job status to a new value")
@click.pass_context
def config_job(ctx, job_id: str | None, objective: str, details: str, acceptance: str, prompt: str, files: str, rank: int, status: str):
    """Configure a DRAFT job with properties or manage execution queue position."""
    click.echo("⚙️  Executing 'logist job config'")

    # Get job ID
    final_job_id = get_job_id(ctx, job_id)
    if not final_job_id:
        raise click.ClickException("❌ No job ID provided and no current job is selected.")

    job_dir = get_job_dir(ctx, final_job_id)
    if not job_dir:
        raise click.ClickException(f"❌ Job '{final_job_id}' not found.")

    # Handle --rank option (queue management)
    if rank is not None:
        # Validate rank value
        if rank < -1:
            raise click.ClickException("❌ Rank must be >= -1 (-1 moves to end, 0 moves to front)")

        # Check that no other config options are provided with --rank
        if any([objective, details, acceptance, prompt, files]):
            raise click.ClickException("❌ --rank cannot be used with other configuration options")

        # Check job state - can rank jobs that are either DRAFT or activated (in queue)
        try:
            manifest = load_job_manifest(job_dir)
            current_status = manifest.get("status")
            # Allow ranking for jobs in any state as long as they're in the queue
        except JobStateError as e:
            raise click.ClickException(f"❌ Error loading job manifest: {e}")

        # Load jobs index and check queue
        jobs_dir_path = ctx.obj["JOBS_DIR"]
        jobs_index_path = os.path.join(jobs_dir_path, "jobs_index.json")

        try:
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise click.ClickException(f"❌ Failed to read jobs index: {e}")

        queue = jobs_index.get("queue", [])
        if final_job_id not in queue:
            raise click.ClickException(f"❌ Job '{final_job_id}' is not in the execution queue. Use 'logist job activate' first.")

        # Get current position for feedback
        current_position = queue.index(final_job_id)

        # Remove from current position
        queue.remove(final_job_id)

        # Insert at new position
        if rank == -1 or rank >= len(queue):
            # Move to end
            queue.append(final_job_id)
            new_position = len(queue) - 1
        else:
            # Insert at specified position, but not beyond end
            actual_rank = min(rank, len(queue))
            queue.insert(actual_rank, final_job_id)
            new_position = actual_rank

        # Save updated jobs index
        try:
            with open(jobs_index_path, 'w') as f:
                json.dump(jobs_index, f, indent=2)
        except OSError as e:
            raise click.ClickException(f"❌ Failed to update jobs index: {e}")

        click.secho(f"   ✅ Job '{final_job_id}' queue position updated successfully!", fg="green")
        click.echo(f"   📊 Moved from position {current_position} to position {new_position}")

        # Show current queue state
        click.echo("   📋 Current queue:")
        for i, queue_job_id in enumerate(queue):
            marker = " ←" if queue_job_id == final_job_id else ""
            next_indicator = " 🏃" if i == 0 else ""
            click.echo(f"      {i}: {queue_job_id}{marker}{next_indicator}")

        return

    # Handle --status option (status update)
    if status is not None:
        # Check that no other config options are provided with --status
        if any([objective, details, acceptance, prompt, files, rank]):
            click.echo("❌ --status cannot be used with other configuration options (--objective, --details, --acceptance, --prompt, --files, or --rank)")
            return

        # Define valid job states
        valid_states = [
            JobStates.DRAFT,
            JobStates.PENDING,
            JobStates.RUNNING,
            JobStates.REVIEW_REQUIRED,
            JobStates.REVIEWING,
            JobStates.APPROVAL_REQUIRED,
            JobStates.INTERVENTION_REQUIRED,
            JobStates.SUCCESS,
            JobStates.CANCELED
        ]

        # Validate status value
        if status not in valid_states:
            valid_states_str = ", ".join(f"'{s}'" for s in valid_states)
            click.echo(f"❌ Invalid status '{status}'. Valid status values are: {valid_states_str}")
            return

        # Load current job manifest to get current status for transition validation
        try:
            manifest = load_job_manifest(job_dir)
            current_status = manifest.get("status", "UNKNOWN")
        except JobStateError as e:
            raise click.ClickException(f"❌ Error loading job manifest: {e}")

        # Simple transition validation - for now, allow most transitions
        # (More sophisticated validation could be added based on state machine rules)
        if current_status == status:
            click.echo(f"   ℹ️  Job '{final_job_id}' already has status '{status}' - no change needed")
            return

        # Update job manifest with new status
        try:
            # Use update_job_manifest to safely update the status
            update_job_manifest(job_dir=job_dir, new_status=status)
            click.secho(f"   ✅ Job '{final_job_id}' status updated successfully!", fg="green")
            click.echo(f"   🔄 Status changed: {current_status} → {status}")
        except JobStateError as e:
            raise click.ClickException(f"❌ Failed to update job status: {e}")

        return

    # Handle configuration options (original functionality)
    # Validate that at least one option is provided
    if not any([objective, details, acceptance, prompt, files, rank, status]):
        click.echo("❌ At least one configuration option must be provided (--objective, --details, --acceptance, --prompt, --files, --status, or --rank)")
        return

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
        click.echo(role_data)
    except Exception as e:
        click.secho(f"❌ Role '{role_name}' not found.", fg="red")
        ctx.exit(1)


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

        # Setup workspace for immediate execution readiness
        try:
            debug_mode = ctx.obj.get("DEBUG", False)
            manager.setup_workspace(job_dir, debug=debug_mode)
            click.echo("   🏗️  Workspace initialized")
        except Exception as e:
            # Log warning but don't fail activation - user can still run commands
            click.secho(f"   ⚠️  Workspace setup failed: {e}", fg="yellow")
            click.echo("   💡 Workspace will be created when execution begins")

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