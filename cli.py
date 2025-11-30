#!/usr/bin/env python3
"""
Logist CLI - Command Line Interface for Job Orchestration

Placeholder implementation that prints intended actions.
"""

import json
import os
import shutil

import click


class PlaceholderLogistEngine:
    """Placeholder orchestration engine that prints what it would do."""

    def run_job(self, job_id: str, model: str = "gpt-4", resume: bool = False) -> bool:
        """Simulate running a job continuously."""
        print(f"🔄 [LOGIST] Running job '{job_id}' continuously with model '{model}'")
        print("   → Would: Execute Worker → Supervisor → Steward loop until completion")
        return False

    def step_job(self, job_id: str, dry_run: bool = False) -> bool:
        """Simulate stepping through one execution phase."""
        if dry_run:
            print("   → Defensive setting detected: --dry-run")
            print(f"   → Would: Simulate single phase for job '{job_id}' with mock data")
            return True

        print(f"👣 [LOGIST] Executing single phase for job '{job_id}'")
        print("   → Would: Run Worker agent, then Supervisor, then pause for Steward")
        return True

    def preview_job(self, job_id: str) -> None:
        """Simulate previewing the next step of a job."""
        print(f"🔍 [LOGIST] Previewing next step for job '{job_id}'")
        print("   → Would: Assemble the complete prompt and display it")
        print("\n--- BEGIN MOCK PROMPT ---")
        print(f"You are the Worker agent. The current task for job '{job_id}' is...")
        print("--- END MOCK PROMPT ---\n")

    def reset_job(self, job_id: str) -> None:
        """Simulate resetting a job."""
        print(f"🔄 [LOGIST] Resetting job '{job_id}' to initial state")
        print("   → Would: Delete evidence files and clear execution history")

    def revert_job(self, job_id: str) -> None:
        """Simulate reverting job to checkpoint."""
        print(f"⏮️ [LOGIST] Reverting job '{job_id}' to previous checkpoint")
        print("   → Would: Restore Job Manifest to its previous state")


class PlaceholderJobManager:
    """Placeholder job manager that prints what it would do."""

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


class PlaceholderRoleManager:
    """Placeholder role manager that prints what it would do."""

    def list_roles(self) -> list:
        """Simulate listing available roles."""
        print("👥 [LOGIST] Listing all available roles")
        return [{"name": "Worker", "description": "The primary agent."}]

    def inspect_role(self, role_name: str) -> dict:
        """Simulate inspecting a specific role."""
        print(f"👤 [LOGIST] Inspecting role '{role_name}'")
        return {"name": role_name, "description": "..."}


# Global instances for CLI
engine = PlaceholderLogistEngine()
manager = PlaceholderJobManager()
role_manager = PlaceholderRoleManager()


def init_command(jobs_dir: str) -> bool:
    """Initialize the jobs directory with default configurations."""
    try:
        # Create jobs directory if it doesn't exist
        os.makedirs(jobs_dir, exist_ok=True)

        # Get the path to the schemas directory relative to this file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schemas_dir = os.path.join(script_dir, "..", "schemas", "roles")

        # Copy role configurations
        roles_to_copy = ["worker.json", "supervisor.json"]
        for role_file in roles_to_copy:
            schema_path = os.path.join(schemas_dir, role_file)
            dest_path = os.path.join(jobs_dir, role_file)
            if os.path.exists(schema_path):
                shutil.copy2(schema_path, dest_path)
            else:
                click.secho(f"⚠️  Warning: Schema file '{role_file}' not found in '{schemas_dir}'", fg="yellow")

        # Create jobs index file
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
        jobs_index_data = {"current_job_id": None}
        with open(jobs_index_path, 'w') as f:
            json.dump(jobs_index_data, f, indent=2)

        return True

    except (OSError, IOError) as e:
        click.secho(f"❌ Error during initialization: {e}", fg="red")
        return False


def get_job_id(ctx, job_id_arg: str | None) -> str | None:
    """Get job ID from argument, environment variable, or context."""
    if job_id_arg:
        return job_id_arg

    # Check for LOGIST_JOB_ID environment variable first
    env_job_id = os.environ.get("LOGIST_JOB_ID")
    if env_job_id:
        click.echo(f"   → No job ID provided. Using LOGIST_JOB_ID environment variable: '{env_job_id}'")
        return env_job_id

    # Fall back to reading current job from jobs index
    jobs_dir = ctx.obj["JOBS_DIR"]
    current_job_id = manager.get_current_job_id(jobs_dir)
    if current_job_id:
        click.echo(f"   → No job ID provided. Using current job from index: '{current_job_id}'")
    return current_job_id


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
@click.option("--model", default="gpt-4", help="LLM model for execution")
@click.option("--resume", is_flag=True, help="Resume from last checkpoint")
@click.pass_context
def run(ctx, job_id: str | None, model: str, resume: bool):
    """Execute a job continuously until completion."""
    click.echo("🎯 Executing 'logist job run'")
    if final_job_id := get_job_id(ctx, job_id):
        engine.run_job(final_job_id, model=model, resume=resume)
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
        engine.step_job(final_job_id, dry_run=dry_run)
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


@job.command()
@click.argument("job_id", required=False)
@click.pass_context
def preview(ctx, job_id: str | None):
    """Display the prompt for the next agent run without executing."""
    click.echo("🔍 Executing 'logist job preview'")
    if final_job_id := get_job_id(ctx, job_id):
        engine.preview_job(final_job_id)
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


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


@job.command()
@click.argument("job_id", required=False)
@click.pass_context
def history(ctx, job_id: str | None):
    """Display the execution history of a job."""
    click.echo("📚 Executing 'logist job history'")
    if final_job_id := get_job_id(ctx, job_id):
        history_data = manager.get_job_history(final_job_id)
        click.echo(f"\n📚 Job '{final_job_id}' History:")
        for event in history_data:
            click.echo(f"   - {event}")
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


@job.command()
@click.argument("job_id", required=False)
@click.pass_context
def inspect(ctx, job_id: str | None):
    """Display the raw job manifest for debugging."""
    click.echo("🔩 Executing 'logist job inspect'")
    if final_job_id := get_job_id(ctx, job_id):
        manifest = manager.inspect_job(final_job_id)
        click.echo(json.dumps(manifest, indent=2))
    else:
        click.secho("❌ No job ID provided and no current job is selected.", fg="red")


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

    # Get current job for marking
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
        # Mark current job
        marker = " 👈" if job["job_id"] == current_job_id else ""

        # Format status with color
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
def list_roles():
    """List all available agent roles."""
    click.echo("👥 Executing 'logist role list'")
    roles = role_manager.list_roles()
    for role_item in roles:
        click.echo(f"- {role_item['name']}: {role_item['description']}")


@role.command(name="inspect")
@click.argument("role_name")
def inspect_role(role_name: str):
    """Display the detailed configuration for a specific role."""
    click.echo(f"👤 Executing 'logist role inspect {role_name}'")
    role_data = role_manager.inspect_role(role_name)
    click.echo(json.dumps(role_data, indent=2))


@main.command()
@click.pass_context
def init(ctx):
    """Initialize the jobs directory with default configurations."""
    jobs_dir = ctx.obj["JOBS_DIR"]
    click.echo(f"🛠️  Executing 'logist init' with jobs directory: {jobs_dir}")

    # Check if already initialized
    jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
    if os.path.exists(jobs_index_path):
        click.secho("⚠️  Jobs directory appears to be already initialized.", fg="yellow")
        if not click.confirm("Do you want to reinitialize? This may overwrite existing files."):
            click.echo("❌ Initialization cancelled.")
            return

    # Initialize the jobs directory
    if init_command(jobs_dir):
        click.secho("✅ Jobs directory initialized successfully!", fg="green")
        click.echo(f"   📁 Created directory: {jobs_dir}")
        click.echo("   📋 Created jobs_index.json")
        click.echo("   📎 Copied worker.json and supervisor.json")
    else:
        click.secho("❌ Failed to initialize jobs directory.", fg="red")


if __name__ == "__main__":
    main()