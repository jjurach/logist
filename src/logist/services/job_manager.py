"""
Job Manager Service

Handles job creation, selection, and management operations.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from logist import workspace_utils
from logist.job_state import JobStateError, load_job_manifest, get_current_state, update_job_manifest, transition_state, JobStates


class JobManagerService:
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

    def create_job(self, job_dir: str, jobs_dir: str, prompt: str = None,
                   git_source_repo: str = None, runner: str = None, agent: str = None) -> str:
        """Create or register a new job with manifest and directory structure.

        Args:
            job_dir: Job directory path (relative or absolute)
            jobs_dir: Base jobs directory
            prompt: Task prompt for the job (required for activation)
            git_source_repo: Git source repository path
            runner: Runner to use (podman, docker, kubernetes, direct)
            agent: Agent provider to use (cline-cli, aider-chat, claude-code, etc.)

        Returns:
            Job ID of the created/updated job
        """
        jobs_dir_abs = os.path.abspath(jobs_dir)

        # Handle job directory path resolution
        if os.path.isabs(job_dir):
            # Absolute path provided - use as-is for backward compatibility
            job_dir_abs = job_dir
            job_id = os.path.basename(job_dir_abs)
        else:
            # Relative path - create inside jobs_dir
            job_id = job_dir  # Use the provided name as job_id
            job_dir_abs = os.path.join(jobs_dir_abs, job_id)

        # Check if the job dir is inside the jobs_dir
        if os.path.dirname(job_dir_abs) != jobs_dir_abs:
            print(
                f"⚠️  Warning: The job directory '{job_dir_abs}' is not inside the configured --jobs-dir '{jobs_dir_abs}'.",
            )
            print("    This is allowed, but not recommended for easier management.")

        # Ensure job directory exists
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Creating job directory: {job_dir_abs}")
        os.makedirs(job_dir_abs, exist_ok=True)
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Job directory created: {job_dir_abs}")

        # Create standard subdirectories
        subdirs = ["workspace", "logs", "backups", "temp"]
        for subdir in subdirs:
            subdir_path = os.path.join(job_dir_abs, subdir)
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Creating subdirectory: {subdir_path}")
            os.makedirs(subdir_path, exist_ok=True)
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Subdirectory created: {subdir_path}")

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
        if os.path.exists(manifest_path):
            print(f"Job manifest already exists in '{job_dir_abs}'. Overwriting?")

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

        # Add required job attributes (prompt and gitSourceRepo)
        if prompt:
            job_manifest["prompt"] = prompt
            # Also write prompt to prompt.md file
            prompt_file_path = os.path.join(job_dir_abs, "prompt.md")
            with open(prompt_file_path, 'w') as f:
                f.write(prompt)

        if git_source_repo:
            job_manifest["gitSourceRepo"] = git_source_repo

        # Add optional runner and agent configuration
        if runner:
            job_manifest["runner"] = runner
        if agent:
            job_manifest["agent"] = agent

        # Add job_spec content if present
        if job_spec:
            # Merge key job spec fields, avoiding conflicts with manifest fields
            for key, value in job_spec.items():
                if key not in ['job_id', 'description']:  # These are handled above
                    job_manifest[key] = value

        # Write job manifest
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing job manifest: {manifest_path}")
        with open(manifest_path, 'w') as f:
            json.dump(job_manifest, f, indent=2)
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Job manifest written: {manifest_path}")

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

        # Use the actual job_id from the manifest
        final_job_id = job_manifest["job_id"]

        # Register the job
        if "jobs" not in jobs_index:
            jobs_index["jobs"] = {}
        jobs_index["jobs"][final_job_id] = job_dir_abs
        jobs_index["current_job_id"] = final_job_id

        # Write updated jobs index
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing jobs index: {jobs_index_path}")
        with open(jobs_index_path, 'w') as f:
            json.dump(jobs_index, f, indent=2)
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Jobs index written: {jobs_index_path}")

        return final_job_id

    def select_job(self, job_id: str, jobs_dir: str) -> None:
        """Set a job as the currently selected job."""
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
        if not os.path.exists(jobs_index_path):
            raise Exception(f"Jobs directory not initialized. Run 'logist init' first.")

        try:
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise Exception(f"Failed to read jobs index: {e}")

        if "jobs" not in jobs_index or job_id not in jobs_index["jobs"]:
            raise Exception(f"Job '{job_id}' not found in jobs index.")

        jobs_index["current_job_id"] = job_id

        try:
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing jobs index in select_job: {jobs_index_path}")
            with open(jobs_index_path, 'w') as f:
                json.dump(jobs_index, f, indent=2)
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Jobs index written in select_job: {jobs_index_path}")
        except OSError as e:
            raise Exception(f"Failed to update jobs index: {e}")

    def get_job_status(self, job_id: str, jobs_dir: str) -> dict:
        """Retrieve detailed job status from job manifest."""
        jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")

        # Check if jobs directory is initialized
        if not os.path.exists(jobs_index_path):
            raise Exception(f"Jobs directory not initialized. Run 'logist init' first.")

        try:
            # Read jobs index to find job path
            with open(jobs_index_path, 'r') as f:
                jobs_index = json.load(f)

            jobs_map = jobs_index.get("jobs", {})
            if job_id not in jobs_map:
                raise Exception(f"Job '{job_id}' not found in jobs index.")

            job_dir = jobs_map[job_id]
            manifest_path = os.path.join(job_dir, "job_manifest.json")

            # Read job manifest
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                return {"directory": job_dir, **manifest}  # Include directory in the return
            else:
                raise Exception(f"Job manifest not found for '{job_id}' at {manifest_path}")

        except (json.JSONDecodeError, OSError) as e:
            raise Exception(f"Failed to read job status: {e}")

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

            # Clean up queue: remove jobs that have terminal status (shouldn't be in queue)
            terminal_states = {"SUCCESS", "CANCELED"}
            cleaned_queue = []
            queue_modified = False

            for job_id in queue:
                job_path = jobs_map.get(job_id)
                if job_path:
                    job_manifest_path = os.path.join(job_path, "job_manifest.json")
                    try:
                        if os.path.exists(job_manifest_path):
                            with open(job_manifest_path, 'r') as f:
                                manifest = json.load(f)
                            status = manifest.get("status", "UNKNOWN")
                            if status not in terminal_states:
                                cleaned_queue.append(job_id)
                            else:
                                # Job is in terminal state, remove from queue
                                queue_modified = True
                        else:
                            # Manifest doesn't exist, keep in queue (assume it's valid)
                            cleaned_queue.append(job_id)
                    except (json.JSONDecodeError, OSError):
                        # Manifest corrupted, keep in queue for now
                        cleaned_queue.append(job_id)
                else:
                    # Job path not found, keep in queue for now
                    cleaned_queue.append(job_id)

            # Update queue if modifications were made
            if queue_modified:
                jobs_index["queue"] = cleaned_queue
                try:
                    print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing jobs index in list_jobs (queue cleanup): {jobs_index_path}")
                    with open(jobs_index_path, 'w') as f:
                        json.dump(jobs_index, f, indent=2)
                    print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Jobs index written in list_jobs (queue cleanup): {jobs_index_path}")
                    queue = cleaned_queue  # Use cleaned queue for processing
                except OSError:
                    # Failed to save cleanup, continue with original queue
                    pass

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

    def run_job_phase(self, ctx: any, job_id: str, job_dir: str, dry_run: bool = False) -> bool:
        """Execute a job phase using the LogistEngine."""
        from ..core_engine import LogistEngine
        engine = LogistEngine()
        return engine.step_job(ctx, job_id, job_dir, dry_run=dry_run)

    def setup_workspace(self, job_dir: str, debug: bool = False, runner=None) -> None:
        """Setup isolated workspace with branch management for advanced isolation.

        This method delegates workspace setup to the runner's provision() method
        when a runner is available. Without a runner, it uses workspace_utils
        as a fallback for backward compatibility.

        Args:
            job_dir: Job directory path
            debug: Enable debug output
            runner: Optional runner instance for workspace provisioning
        """
        # Extract job_id from directory path
        job_id = os.path.basename(os.path.abspath(job_dir))
        workspace_dir = os.path.join(job_dir, "workspace")

        try:
            if runner:
                # Use runner's provision method for workspace setup
                result = runner.provision(job_dir, workspace_dir)
                if not result.get("success", False):
                    raise Exception(f"Runner provisioning failed: {result.get('error', 'Unknown error')}")
                if debug:
                    print(f"[DEBUG] Workspace provisioned via runner for job: {job_id}")
            else:
                # Fallback to workspace_utils for backward compatibility
                result = workspace_utils.setup_isolated_workspace(job_id, job_dir, base_branch="main", debug=debug)
                if not result["success"]:
                    raise Exception(f"Failed to setup isolated workspace: {result['error']}")

        except Exception as e:
            raise Exception(f"Workspace setup failed: {e}")

    def ensure_workspace_ready(self, job_dir: str, debug: bool = False) -> None:
        """
        Ensure workspace is set up and ready for job execution.

        This method coordinates workspace setup to ensure it's only done once per job,
        preventing concurrent setup operations that can cause hangs in tests.

        Uses file-based locking to ensure atomicity across processes/threads.
        """
        import fcntl
        import time

        workspace_dir = os.path.join(job_dir, "workspace")
        workspace_ready_file = os.path.join(workspace_dir, ".workspace_ready")
        lock_file = os.path.join(workspace_dir, ".workspace_setup.lock")

        # Check if workspace is already set up
        if os.path.exists(workspace_ready_file):
            if debug:
                print(f"[DEBUG] Workspace already ready for job: {os.path.basename(job_dir)}")
            return

        # Ensure workspace directory exists
        os.makedirs(workspace_dir, exist_ok=True)

        # Use file locking to prevent concurrent setup
        max_retries = 10
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                # Try to acquire exclusive lock
                with open(lock_file, 'w') as lock_f:
                    fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                    # Double-check after acquiring lock (another process might have completed setup)
                    if os.path.exists(workspace_ready_file):
                        if debug:
                            print(f"[DEBUG] Workspace setup completed by another process for job: {os.path.basename(job_dir)}")
                        return

                    # Set up workspace (this should be called once per job, not concurrently)
                    if debug:
                        print(f"[DEBUG] Setting up workspace for job: {os.path.basename(job_dir)} (attempt {attempt + 1})")

                    try:
                        self.setup_workspace(job_dir, debug=debug)

                        # Mark workspace as ready
                        with open(workspace_ready_file, 'w') as ready_f:
                            ready_f.write(f"Workspace ready for job: {os.path.basename(job_dir)}\n")
                            ready_f.write(f"Setup completed at: {datetime.now().isoformat()}\n")

                        if debug:
                            print(f"[DEBUG] Workspace setup completed successfully for job: {os.path.basename(job_dir)}")

                        return

                    except Exception as setup_error:
                        # Clean up the ready file if setup failed
                        if os.path.exists(workspace_ready_file):
                            try:
                                os.remove(workspace_ready_file)
                            except OSError:
                                pass  # Ignore cleanup errors
                        raise setup_error

            except BlockingIOError:
                # Lock is held by another process, wait and retry
                if debug and attempt == 0:
                    print(f"[DEBUG] Workspace setup lock held by another process, waiting...")
                time.sleep(retry_delay)

            except Exception as e:
                if debug:
                    print(f"[DEBUG] Unexpected error during workspace setup coordination: {e}")
                raise e

        # If we get here, we failed to acquire the lock after all retries
        raise Exception(f"Failed to coordinate workspace setup for job {os.path.basename(job_dir)}: lock acquisition timeout")

    def initialize_jobs_dir(self, jobs_dir: str) -> bool:
        """
        Initialize the jobs directory with default configurations.

        This is a compatibility method for tests that mimics the CLI init command.

        Args:
            jobs_dir: Jobs directory to initialize

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Import the resource loading utilities
            import json
            try:
                from importlib import resources as importlib_resources
            except ImportError:
                import importlib_resources

            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Creating jobs directory in initialize_jobs_dir: {jobs_dir}")
            os.makedirs(jobs_dir, exist_ok=True)
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Jobs directory created in initialize_jobs_dir: {jobs_dir}")

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
                    print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing role file in initialize_jobs_dir: {dest_path}")
                    with open(dest_path, 'w', encoding='utf-8') as f:
                        f.write(role_data)
                    print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Role file written in initialize_jobs_dir: {dest_path}")

                    schema_copied_count += 1

                except (FileNotFoundError, IOError) as e:
                    # Skip missing files silently for compatibility
                    pass
                except Exception as e:
                    # Skip errors silently for compatibility
                    pass

            # Load default roles configuration from package resources
            roles_copied_count = 0
            try:
                resource_file = importlib_resources.files('logist') / 'schemas' / 'roles' / 'default-roles.json'
                with resource_file.open('r', encoding='utf-8') as f:
                    default_roles = json.load(f)
            except (FileNotFoundError, IOError, json.JSONDecodeError) as e:
                # This should never happen in a properly installed package
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
                            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing role JSON file in initialize_jobs_dir: {role_json_path}")
                            with open(role_json_path, 'w') as f:
                                json.dump(role_config, f, indent=2)
                            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Role JSON file written in initialize_jobs_dir: {role_json_path}")
                            roles_copied_count += 1

                        # Create MD instructions file
                        if not os.path.exists(role_md_path) and "instructions" in role_config:
                            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing role MD file in initialize_jobs_dir: {role_md_path}")
                            with open(role_md_path, 'w') as f:
                                f.write(role_config["instructions"])
                            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Role MD file written in initialize_jobs_dir: {role_md_path}")
                    except OSError as e:
                        # Skip errors silently for compatibility
                        pass

            # Create jobs index
            jobs_index_path = os.path.join(jobs_dir, "jobs_index.json")
            jobs_index_data = {
                "current_job_id": None,
                "jobs": {},
                "queue": []
            }
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing jobs index in initialize_jobs_dir: {jobs_index_path}")
            with open(jobs_index_path, 'w') as f:
                json.dump(jobs_index_data, f, indent=2)
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Jobs index written in initialize_jobs_dir: {jobs_index_path}")

            return True
        except Exception as e:
            return False

    def activate_job(self, job_id: str, jobs_dir: str) -> bool:
        """
        Activate a DRAFT job for execution and add to processing queue.

        Args:
            job_id: Job identifier
            jobs_dir: Jobs directory

        Returns:
            True if activation successful, False otherwise
        """
        try:
            # Get job directory
            job_status = self.get_job_status(job_id, jobs_dir)
            job_dir = job_status["directory"]

            # Load job manifest
            from logist.job_state import load_job_manifest, transition_state, update_job_manifest, JobStates
            manifest = load_job_manifest(job_dir)
            current_status = manifest.get("status")

            # Check job state - must be DRAFT to activate
            if current_status != JobStates.DRAFT:
                return False

            # Validate required attributes before activation
            prompt = manifest.get("prompt")
            if not prompt:
                # Also check for prompt.md file
                prompt_file_path = os.path.join(job_dir, "prompt.md")
                if os.path.exists(prompt_file_path):
                    with open(prompt_file_path, 'r') as f:
                        prompt = f.read().strip()
                    if prompt:
                        manifest["prompt"] = prompt

            if not prompt:
                raise Exception("Job activation failed: 'prompt' attribute is required. Use 'logist job config --prompt' to set it.")

            git_source_repo = manifest.get("gitSourceRepo")
            if not git_source_repo:
                raise Exception("Job activation failed: 'gitSourceRepo' attribute is required. Use 'logist job create --git-source-repo' or run from a git repository.")

            # Transition job state from DRAFT to PENDING
            new_status = transition_state(JobStates.DRAFT, "System", "ACTIVATED")
            if new_status != JobStates.PENDING:
                return False

            # Ensure phases and current_phase are initialized when activating
            phases = manifest.get("phases")
            if not phases:
                phases = [{"name": "default", "description": "Default single phase"}]
                manifest["phases"] = phases

            # Set current_phase to first phase if not already set
            if manifest.get("current_phase") is None:
                current_phase = phases[0]["name"]
            else:
                current_phase = manifest["current_phase"]

            # Update job manifest with status, phases, and current_phase all at once
            manifest["phases"] = phases
            manifest["current_phase"] = current_phase
            manifest["status"] = new_status

            # Save the complete updated manifest
            manifest_path = os.path.join(job_dir, "job_manifest.json")
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing job manifest in activate_job: {manifest_path}")
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Job manifest written in activate_job: {manifest_path}")

            # Load/update jobs index to add job to queue
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
            if job_id in jobs_index["queue"]:
                jobs_index["queue"].remove(job_id)

            # Append to end of queue
            jobs_index["queue"].append(job_id)

            # Save updated jobs index
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Writing jobs index in activate_job: {jobs_index_path}")
            with open(jobs_index_path, 'w') as f:
                json.dump(jobs_index, f, indent=2)
            print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')}] Jobs index written in activate_job: {jobs_index_path}")

            return True

        except Exception as e:
            return False