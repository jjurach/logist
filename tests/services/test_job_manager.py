"""
Unit tests for JobManagerService

Tests the job creation, selection, and management operations.
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, mock_open

from logist.services.job_manager import JobManagerService
from logist.job_state import JobStates


class TestJobManagerService(unittest.TestCase):
    """Test cases for JobManagerService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = JobManagerService()
        self.test_dir = tempfile.mkdtemp()
        self.jobs_dir = os.path.join(self.test_dir, "jobs")
        os.makedirs(self.jobs_dir)

        # Create a minimal jobs_index.json
        self.jobs_index_path = os.path.join(self.jobs_dir, "jobs_index.json")
        with open(self.jobs_index_path, 'w') as f:
            json.dump({"current_job_id": None, "jobs": {}}, f)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_get_current_job_id_no_index(self):
        """Test getting current job ID when jobs index doesn't exist."""
        non_existent_dir = os.path.join(self.test_dir, "nonexistent")
        result = self.service.get_current_job_id(non_existent_dir)
        self.assertIsNone(result)

    def test_get_current_job_id_success(self):
        """Test getting current job ID."""
        # Create jobs index with current job
        with open(self.jobs_index_path, 'w') as f:
            json.dump({"current_job_id": "test-job-123", "jobs": {}}, f)

        result = self.service.get_current_job_id(self.jobs_dir)
        self.assertEqual(result, "test-job-123")

    def test_get_current_job_id_none_current(self):
        """Test getting current job ID when none is set."""
        result = self.service.get_current_job_id(self.jobs_dir)
        self.assertIsNone(result)

    def test_create_job_basic(self):
        """Test basic job creation."""
        job_dir = os.path.join(self.jobs_dir, "my-test-job")
        os.makedirs(job_dir)

        job_id = self.service.create_job(job_dir, self.jobs_dir)

        # Verify job ID is derived from directory name
        self.assertEqual(job_id, "my-test-job")

        # Verify job manifest was created
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        self.assertTrue(os.path.exists(manifest_path))

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        self.assertEqual(manifest["job_id"], "my-test-job")
        self.assertEqual(manifest["status"], JobStates.DRAFT)
        self.assertEqual(manifest["description"], "Job my-test-job")

    def test_create_job_with_explicit_name(self):
        """Test job creation with explicit job_name parameter."""
        job_id = self.service.create_job(".", self.jobs_dir, job_name="my-custom-job")

        # Verify job ID is the explicit name
        self.assertEqual(job_id, "my-custom-job")

        # Verify job manifest was created in the correct directory
        job_dir = os.path.join(self.jobs_dir, "my-custom-job")
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        self.assertTrue(os.path.exists(manifest_path))

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        self.assertEqual(manifest["job_id"], "my-custom-job")

    def test_create_job_random_id_for_current_dir(self):
        """Test job creation generates random ID when directory is '.' and no name specified."""
        job_id = self.service.create_job(".", self.jobs_dir)

        # Verify job ID follows the random format: job-{8 hex chars}
        self.assertTrue(job_id.startswith("job-"))
        self.assertEqual(len(job_id), 12)  # "job-" (4) + 8 hex chars

        # Verify job manifest was created
        job_dir = os.path.join(self.jobs_dir, job_id)
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        self.assertTrue(os.path.exists(manifest_path))

    def test_create_job_no_subdirectories(self):
        """Test that job creation does not create subdirectories."""
        job_id = self.service.create_job(".", self.jobs_dir, job_name="no-subdirs-job")

        job_dir = os.path.join(self.jobs_dir, job_id)

        # Verify no subdirectories are created
        for subdir in ["workspace", "logs", "backups", "temp"]:
            subdir_path = os.path.join(job_dir, subdir)
            self.assertFalse(os.path.exists(subdir_path), f"Subdirectory {subdir} should not exist")

        # Verify only job_manifest.json exists
        contents = os.listdir(job_dir)
        self.assertEqual(contents, ["job_manifest.json"])

    def test_create_job_prompt_only_in_manifest(self):
        """Test that prompt is stored only in manifest, not as prompt.md file."""
        job_id = self.service.create_job(
            ".", self.jobs_dir,
            job_name="prompt-test-job",
            prompt="Test prompt content"
        )

        job_dir = os.path.join(self.jobs_dir, job_id)

        # Verify prompt.md does NOT exist
        prompt_md_path = os.path.join(job_dir, "prompt.md")
        self.assertFalse(os.path.exists(prompt_md_path), "prompt.md should not be created")

        # Verify prompt is in manifest
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        self.assertEqual(manifest["prompt"], "Test prompt content")

    def test_create_job_from_spec_file(self):
        """Test job creation with job specification file."""
        job_dir = os.path.join(self.jobs_dir, "my-test-job")
        os.makedirs(job_dir)

        # Create sample-job.json
        spec_path = os.path.join(job_dir, "sample-job.json")
        spec_data = {
            "job_spec": {
                "job_id": "custom-job-id",
                "description": "Custom job description",
                "custom_field": "custom_value"
            }
        }
        with open(spec_path, 'w') as f:
            json.dump(spec_data, f)

        job_id = self.service.create_job(job_dir, self.jobs_dir)

        # Verify job ID from spec
        self.assertEqual(job_id, "custom-job-id")

        # Verify manifest includes custom fields
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        self.assertEqual(manifest["description"], "Custom job description")
        self.assertEqual(manifest["custom_field"], "custom_value")

    def test_select_job(self):
        """Test job selection."""
        # Create a job first
        job_dir = os.path.join(self.jobs_dir, "test-job")
        os.makedirs(job_dir)
        self.service.create_job(job_dir, self.jobs_dir)

        # Select the job
        self.service.select_job("test-job", self.jobs_dir)

        # Verify it's now current
        result = self.service.get_current_job_id(self.jobs_dir)
        self.assertEqual(result, "test-job")

    def test_select_job_nonexistent(self):
        """Test selecting a nonexistent job."""
        with self.assertRaises(Exception) as context:
            self.service.select_job("nonexistent-job", self.jobs_dir)
        self.assertIn("not found", str(context.exception))

    def test_get_job_status(self):
        """Test retrieving job status."""
        # Create a job
        job_dir = os.path.join(self.jobs_dir, "status-test-job")
        os.makedirs(job_dir)
        self.service.create_job(job_dir, self.jobs_dir)

        # Update manifest with custom status
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        manifest["status"] = "COMPLETED"
        manifest["custom_field"] = "test_value"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        # Retrieve status
        status = self.service.get_job_status("status-test-job", self.jobs_dir)

        self.assertEqual(status["job_id"], "status-test-job")
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(status["custom_field"], "test_value")

    def test_get_job_status_nonexistent_job(self):
        """Test getting status of nonexistent job."""
        with self.assertRaises(Exception) as context:
            self.service.get_job_status("nonexistent-job", self.jobs_dir)
        self.assertIn("not found", str(context.exception))

    def test_get_job_status_no_index(self):
        """Test getting job status when jobs index doesn't exist."""
        nonexistent_jobs_dir = os.path.join(self.test_dir, "nonexistent_jobs")
        with self.assertRaises(Exception) as context:
            self.service.get_job_status("any-job", nonexistent_jobs_dir)
        self.assertIn("not initialized", str(context.exception))

    def test_list_jobs_empty(self):
        """Test listing jobs when none exist."""
        jobs = self.service.list_jobs(self.jobs_dir)
        self.assertEqual(jobs, [])

    def test_list_jobs_with_jobs(self):
        """Test listing jobs."""
        # Create multiple jobs
        job1_dir = os.path.join(self.jobs_dir, "job1")
        job2_dir = os.path.join(self.jobs_dir, "job2")
        os.makedirs(job1_dir)
        os.makedirs(job2_dir)

        self.service.create_job(job1_dir, self.jobs_dir)
        self.service.create_job(job2_dir, self.jobs_dir)

        # Update one job manifest
        manifest_path = os.path.join(job1_dir, "job_manifest.json")
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        manifest["status"] = "COMPLETED"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        jobs = self.service.list_jobs(self.jobs_dir)

        # Should have 2 jobs
        self.assertEqual(len(jobs), 2)

        # Find jobs by ID
        job1_info = next(job for job in jobs if job["job_id"] == "job1")
        job2_info = next(job for job in jobs if job["job_id"] == "job2")

        self.assertEqual(job1_info["status"], "COMPLETED")
        self.assertEqual(job2_info["status"], JobStates.DRAFT)  # Default status

    def test_setup_workspace(self):
        """Test workspace setup."""
        job_dir = os.path.join(self.jobs_dir, "workspace-test")
        os.makedirs(job_dir)

        # Test with mock workspace utils
        with patch('logist.services.job_manager.workspace_utils') as mock_workspace:
            mock_workspace.setup_isolated_workspace.return_value = {"success": True}

            self.service.setup_workspace(job_dir)

            # Verify workspace setup was called
            mock_workspace.setup_isolated_workspace.assert_called_once_with(
                "workspace-test", job_dir, base_branch="main", debug=False
            )

    def test_setup_workspace_failure(self):
        """Test workspace setup failure."""
        job_dir = os.path.join(self.jobs_dir, "workspace-fail")
        os.makedirs(job_dir)

        with patch('logist.services.job_manager.workspace_utils') as mock_workspace:
            mock_workspace.setup_isolated_workspace.return_value = {
                "success": False,
                "error": "Test error"
            }

            with self.assertRaises(Exception) as context:
                self.service.setup_workspace(job_dir, debug=False)
            self.assertIn("Test error", str(context.exception))

    def test_simulate_methods(self):
        """Test methods that currently just simulate/simulate responses."""
        # These methods currently just print and return simple values
        # They'll be expanded in future implementations
        self.assertEqual(self.service.get_job_history("test-job"), ["1. Worker: Implemented feature X"])
        self.assertEqual(self.service.inspect_job("test-job"), {"job_id": "test-job", "raw_data": "..."})

        # These should not raise exceptions
        self.service.force_success("test-job")
        self.service.terminate_job("test-job")


if __name__ == '__main__':
    unittest.main()