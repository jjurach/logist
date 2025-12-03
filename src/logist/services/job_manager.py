"""
Job Manager Service

Handles job creation, selection, and management operations.
"""

import json
import os
from typing import Dict, Any, List, Optional

from logist import workspace_utils
from logist.job_state import JobStateError, load_job_manifest, get_current_state_and_role, update_job_manifest, transition_state, JobStates


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

    def create_job(self, job_dir: str, jobs_dir: str) -> str:
        """Create or register a new job with manifest and directory structure."""
        job_dir_abs = os.path.abspath(job_dir)
        jobs_dir_abs = os.path.abspath(jobs_dir)

        # Derive job_id from directory name
        job_id = os.path.basename(job_dir_abs)

        # Check if the job dir is inside the jobs_dir
        if os.path.dirname(job_dir_abs) != jobs_dir_abs:
            print(
                f"⚠️  Warning: The job directory '{job_dir_abs}' is not inside the configured --jobs-dir '{jobs_dir_abs}'.",
            )
            print("    This is allowed, but not recommended for easier management.")

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

        # Use the actual job_id from the manifest
        final_job_id = job_manifest["job_id"]

        # Register the job
        if "jobs" not in jobs_index:
            jobs_index["jobs"] = {}
        jobs_index["jobs"][final_job_id] = job_dir_abs
        jobs_index["current_job_id"] = final_job_id

        # Write updated jobs index
        with open(jobs_index_path, 'w') as f:
            json.dump(jobs_index, f, indent=2)

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
            with open(jobs_index_path, 'w') as f:
                json.dump(jobs_index, f, indent=2)
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
                return manifest
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

    def setup_workspace(self, job_dir: str) -> None:
        """Setup isolated workspace with branch management for advanced isolation."""
        # Extract job_id from directory path
        job_id = os.path.basename(os.path.abspath(job_dir))

        try:
            # Use advanced isolated workspace setup (clones HEAD, no branch creation)
            result = workspace_utils.setup_isolated_workspace(job_id, job_dir, base_branch="main")
            if not result["success"]:
                raise Exception(f"Failed to setup isolated workspace: {result['error']}")

        except Exception as e:
            raise Exception(f"Advanced workspace setup failed: {e}")