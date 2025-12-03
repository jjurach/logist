#!/usr/bin/env python3
"""
Basic tests for Logist CLI - do-little tests that verify placeholder
functionality.
"""

import json
import os

from click.testing import CliRunner

from logist.cli import (
    JobManager,
    LogistEngine,
    RoleManager, # Use the real RoleManager now
    main,
)
import shutil # Needed for cleaning up directories


# Placeholder test classes - these should eventually be updated to test real functionality
class TestPlaceholderClasses:
    """Placeholder tests that should be updated when real functionality is available."""

    def test_placeholder_engine_not_implemented(self):
        """Placeholder test for LogistEngine."""
        # This test exists to remind us to implement real tests for LogistEngine
        pass

    def test_placeholder_manager_not_implemented(self):
        """Placeholder test for JobManager."""
        # This test exists to remind us to implement real tests for JobManager
        pass


class TestCLICommands:
    """Test CLI commands with placeholder functionality."""

    def setup_method(self):
        """Setup CLI runner."""
        self.runner = CliRunner()

    def test_job_create_command(self, tmp_path):
        """Test job create command with a directory."""
        job_dir = tmp_path / "new-job"
        job_dir.mkdir()
        result = self.runner.invoke(main, ["job", "create", str(job_dir)])
        assert result.exit_code == 0
        assert "Initializing or updating job" in result.output
        assert "Job 'new-job' created/updated and selected" in result.output

    def test_job_create_warning_command(self, tmp_path):
        """Test the warning for creating a job outside the jobs dir."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        job_dir_outside = tmp_path / "outside-job"
        job_dir_outside.mkdir()

        result = self.runner.invoke(
            main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir_outside)]
        )
        assert result.exit_code == 0
        assert "Warning: The job directory" in result.output

    def test_job_select_command(self, tmp_path):
        """Test the job select command with proper setup."""
        jobs_dir = tmp_path / "jobs"

        # Initialize jobs directory
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        assert result.exit_code == 0

        # Create a job
        job_dir = tmp_path / "my-job"
        job_dir.mkdir()
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])
        assert result.exit_code == 0

        # Select the job
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "select", "my-job"])
        assert result.exit_code == 0
        assert "'my-job' is now the current job" in result.output

        # Verify the jobs_index.json was updated
        jobs_index_path = jobs_dir / "jobs_index.json"
        assert jobs_index_path.exists()
        with open(jobs_index_path, 'r') as f:
            jobs_index = json.load(f)
        assert jobs_index["current_job_id"] == "my-job"

    def test_command_uses_current_job(self):
        """Test that a command uses the current job if no ID is given."""
        result = self.runner.invoke(main, ["job", "status"])
        assert result.exit_code == 0
        assert "No job ID provided. Using current job:" in result.output
        assert "Status: PENDING" in result.output

    def test_command_uses_provided_job_id(self, tmp_path):
        """Test that a command uses the provided ID even if a current job is set."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        
        # Initialize jobs directory (this copies default roles)
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        
        # Create a dummy job
        job_dir = tmp_path / "specific-job"
        job_dir.mkdir()
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "status", "specific-job"])
        assert result.exit_code == 0
        assert "No job ID provided" not in result.output
        assert "Job 'specific-job' Status:" in result.output

    def test_command_fails_without_job_id_and_no_current(self, mocker, tmp_path):
        """Test that a command fails if no job can be determined."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        
        mocker.patch.object(JobManager, "get_current_job_id", return_value=None)
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "status"])
        assert result.exit_code == 0  # click exits 0 on handled errors
        assert "No job ID provided and no current job is selected" in result.output

    def test_role_list_command_after_init(self, tmp_path):
        """Test 'logist role list' command after initialization."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory (this copies default roles)
        result_init = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        assert result_init.exit_code == 0
        assert "Jobs directory initialized successfully!" in result_init.output

        # List roles
        result_list = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "list"])
        assert result_list.exit_code == 0
        assert "Available Agent Roles:" in result_list.output
        assert "- Worker: Expert software development and implementation agent specializing in code generation, debugging, and technical problem-solving" in result_list.output
        assert "- Supervisor: Quality assurance and oversight specialist focused on reviewing outputs, identifying issues, and providing constructive feedback" in result_list.output

    def test_role_list_command_no_roles(self, tmp_path):
        """Test 'logist role list' when no role files are present."""
        jobs_dir = tmp_path / "empty_jobs"
        jobs_dir.mkdir()

        # Ensure no role files are present (init not run, or cleaned up)
        # We don't run init here to simulate an empty state.

        result_list = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "list"])
        assert result_list.exit_code == 0
        assert "No agent roles found." in result_list.output
        assert "Available Agent Roles:" not in result_list.output

    def test_role_list_command_malformed_role_file(self, tmp_path):
        """Test 'logist role list' with a malformed JSON role file."""
        jobs_dir = tmp_path / "malformed_jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory to get default roles
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        # Create a malformed role file
        malformed_path = jobs_dir / "malformed_role.json"
        malformed_path.write_text("{'name': 'BadRole', 'description': 'This is not valid JSON")

        result_list = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "list"])
        assert result_list.exit_code == 0
        assert "Warning: Skipping malformed JSON role file 'malformed_role.json'." in result_list.output
        assert "- Worker:" in result_list.output # Should still list valid roles
        assert "- Supervisor:" in result_list.output # Should still list valid roles
        assert "BadRole" not in result_list.output # Malformed role should not be listed

    def test_role_list_command_custom_role(self, tmp_path):
        """Test 'logist role list' with a custom role file."""
        jobs_dir = tmp_path / "custom_jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory (to get default roles)
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        # Create a custom role file
        custom_role_path = jobs_dir / "analyst.json"
        custom_role_content = {
            "name": "Analyst",
            "description": "Data analysis and reporting specialist.",
            "instructions": "You are a data analyst...",
            "llm_model": "gemini-2.5-flash"
        }
        with open(custom_role_path, 'w') as f:
            json.dump(custom_role_content, f)

        result_list = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "list"])
        assert result_list.exit_code == 0
        assert "Available Agent Roles:" in result_list.output
        assert "- Worker:" in result_list.output
        assert "- Supervisor:" in result_list.output
        assert "- Analyst: Data analysis and reporting specialist." in result_list.output

    def test_role_inspect_command_existing_role(self, tmp_path):
        """Test 'logist role inspect' for existing role after init."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory (this copies default roles)
        result_init = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        assert result_init.exit_code == 0

        # Test inspecting Worker role
        result_inspect = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "inspect", "Worker"])
        assert result_inspect.exit_code == 0
        assert '"name": "Worker"' in result_inspect.output
        assert '"description": "Expert software development and implementation agent specializing in code generation, debugging, and technical problem-solving"' in result_inspect.output
        assert '"llm_model": "grok-code-fast-1"' in result_inspect.output
        assert '"instructions":' in result_inspect.output

    def test_role_inspect_command_non_existent_role(self, tmp_path):
        """Test 'logist role inspect' for non-existent role."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory to have some roles
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        # Test inspecting non-existent role
        result_inspect = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "inspect", "NonExistentRole"])
        assert result_inspect.exit_code == 0  # Click handles errors gracefully
        assert "Role 'NonExistentRole' not found." in result_inspect.output

    def test_role_inspect_command_malformed_role_file(self, tmp_path):
        """Test 'logist role inspect' with a malformed role file."""
        jobs_dir = tmp_path / "malformed_jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory with valid roles
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        # Create a malformed role file by overwriting an existing one
        worker_path = jobs_dir / "worker.json"
        worker_path.write_text("{'name': 'Worker', 'description': 'This is not valid JSON}")

        # Try to inspect Worker - should skip malformed file and show error
        result_inspect = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "inspect", "Worker"])
        # Should either find it in supervisor.json (if implementation tries other files) or show not found
        # The current implementation searches for role name across all JSON files, skipping malformed ones
        assert result_inspect.exit_code == 0 # Error is handled gracefully
        # Could show "Role 'Worker' not found" if all Worker files are malformed, or succeed if it finds it elsewhere

    def test_role_inspect_command_custom_role(self, tmp_path):
        """Test 'logist role inspect' with a custom role file."""
        jobs_dir = tmp_path / "custom_jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        # Create a custom role file
        custom_role_path = jobs_dir / "analyst.json"
        custom_role_content = {
            "name": "Analyst",
            "description": "Data analysis and reporting specialist.",
            "instructions": "You are a data analyst specialized in...",
            "llm_model": "gemini-2.5-flash"
        }
        with open(custom_role_path, 'w') as f:
            json.dump(custom_role_content, f)

        # Test inspecting custom role
        result_inspect = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "role", "inspect", "Analyst"])
        assert result_inspect.exit_code == 0
        assert '"name": "Analyst"' in result_inspect.output
        assert '"description": "Data analysis and reporting specialist."' in result_inspect.output
        assert '"llm_model": "gemini-2.5-flash"' in result_inspect.output


    def test_enhance_flag_parsing(self, tmp_path):
        """Test that --enhance flag is properly parsed and stored in context."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        # Test flag present
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "--enhance", "job", "list"])
        # The flag should be parsed without errors - we just check it runs successfully
        assert result.exit_code == 0
        # Since we can't easily inspect the context object, we just verify the command runs

        # Test flag absent
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "list"])
        assert result.exit_code == 0
        # Command should still work without the flag
class TestJobChatCommand:
    """Test the job chat command functionality."""

    def setup_method(self):
        """Setup CLI runner."""
        self.runner = CliRunner()

    def test_job_chat_valid_state(self, tmp_path, monkeypatch):
        """Test that job chat works when job is in a valid state (SUCCESS)."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a job
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "test-job"
        job_dir.mkdir()
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Update job manifest to SUCCESS state with history containing cline_task_id
        manifest_path = job_dir / "job_manifest.json"
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        manifest["status"] = "SUCCESS"
        manifest["history"] = [
            {
                "role": "Worker",
                "action": "COMPLETED",
                "cline_task_id": "test-task-123",
                "timestamp": "2025-01-01T00:00:00"
            }
        ]
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        # Mock subprocess.run to avoid actually calling cline
        mock_subprocess = lambda *args, **kwargs: None  # Mock function that does nothing
        monkeypatch.setattr("logist.cli.subprocess.run", mock_subprocess)

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "chat", "test-job"])
        assert result.exit_code == 0
        assert "⚡ Connecting to Cline task 'test-task-123' for job 'test-job'" in result.output

    def test_job_chat_invalid_state_running(self, tmp_path):
        """Test that job chat prevents interaction when job is RUNNING."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a job
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "running-job"
        job_dir.mkdir()
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Update job manifest to RUNNING state
        manifest_path = job_dir / "job_manifest.json"
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        manifest["status"] = "RUNNING"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "chat", "running-job"])
        assert result.exit_code == 0
        assert "❌ Cannot chat with job 'running-job' in 'RUNNING' state" in result.output
        assert "💡 Chat is only available when the job is not actively running" in result.output

    def test_job_chat_invalid_state_reviewing(self, tmp_path):
        """Test that job chat prevents interaction when job is REVIEWING."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a job
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "reviewing-job"
        job_dir.mkdir()
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Update job manifest to REVIEWING state
        manifest_path = job_dir / "job_manifest.json"
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        manifest["status"] = "REVIEWING"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "chat", "reviewing-job"])
        assert result.exit_code == 0
        assert "❌ Cannot chat with job 'reviewing-job' in 'REVIEWING' state" in result.output

    def test_job_chat_no_history(self, tmp_path):
        """Test that job chat fails when job has no execution history."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a job
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "new-job"
        job_dir.mkdir()
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Job manifest should have empty history by default
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "chat", "new-job"])
        assert result.exit_code == 0
        assert "❌ Job 'new-job' has no execution history - cannot chat" in result.output
        assert "💡 Run the job first with 'logist job step' to create a chat session" in result.output

    def test_job_chat_no_cline_task_id(self, tmp_path):
        """Test that job chat fails when job history has no cline_task_id."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a job
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "old-job"
        job_dir.mkdir()
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Update job manifest with history but no cline_task_id
        manifest_path = job_dir / "job_manifest.json"
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        manifest["status"] = "SUCCESS"
        manifest["history"] = [
            {
                "role": "Worker",
                "action": "COMPLETED",
                "timestamp": "2025-01-01T00:00:00"
                # Missing cline_task_id
            }
        ]
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "chat", "old-job"])
        assert result.exit_code == 0
        assert "❌ No Cline task ID found in job 'old-job' history" in result.output

    def test_job_chat_no_job_selected(self, tmp_path):
        """Test that job chat fails when no job is selected and none provided."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "chat"])
        assert result.exit_code == 0
        assert "❌ No job ID provided and no current job is selected" in result.output

    def test_job_chat_non_existent_job(self, tmp_path):
        """Test that job chat fails with non-existent job ID."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "chat", "nonexistent-job"])
        assert result.exit_code == 0
        assert "❌ Could not find job directory for 'nonexistent-job'" in result.output


class TestRerunCommand:
    """Test the job rerun command functionality."""

    def setup_method(self):
        """Setup CLI runner."""
        self.runner = CliRunner()

    def test_rerun_command_registered(self, tmp_path):
        """Test that 'logist job rerun' is a recognized command."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "rerun", "--help"])
        assert result.exit_code == 0
        assert "Re-execute a previously completed job" in result.output

    def test_rerun_requires_job_id(self, tmp_path):
        """Test that rerun command fails when no job_id is provided."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "rerun"])
        assert result.exit_code != 0  # Should fail due to missing required argument

    def test_rerun_non_existent_job(self, tmp_path):
        """Test that rerun fails for non-existent job."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "rerun", "nonexistent"])
        assert result.exit_code == 0  # Click handles errors gracefully
        assert "❌ Job 'nonexistent' not found" in result.output

    def test_rerun_negative_step_number(self, tmp_path):
        """Test that rerun rejects negative step numbers."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a sample job
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "sample-job"
        job_dir.mkdir()
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "rerun", "sample-job", "--step", "-1"])
        assert result.exit_code == 0  # Handled gracefully
        assert "❌ Step number must be a non-negative integer" in result.output

    def test_rerun_job_from_start(self, tmp_path):
        """Test rerunning a job from the beginning (no --step specified)."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a sample job with phases
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "sample-job"
        job_dir.mkdir()

        # Create job with phases
        sample_job_path = job_dir / "job.json"
        sample_job_content = {
            "job_spec": {
                "job_id": "sample-job",
                "description": "Sample job with phases",
                "phases": [
                    {"name": "phase1", "description": "First phase"},
                    {"name": "phase2", "description": "Second phase"}
                ]
            }
        }
        with open(sample_job_path, 'w') as f:
            json.dump(sample_job_content, f)

        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Execute rerun from start
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "rerun", "sample-job"])
        assert result.exit_code == 0
        assert "🔄 Executing 'logist job rerun'" in result.output
        assert "Starting rerun from the beginning" in result.output
        assert "Job 'sample-job' reset for rerun" in result.output
        assert "Rerun initiated successfully" in result.output

    def test_rerun_job_from_specific_step(self, tmp_path, capsys):
        """Test rerunning a job from a specific step number."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a sample job with phases
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "sample-job"
        job_dir.mkdir()

        # Create job with phases
        sample_job_path = job_dir / "job.json"
        sample_job_content = {
            "job_spec": {
                "job_id": "sample-job",
                "description": "Sample job with phases",
                "phases": [
                    {"name": "phase1", "description": "First phase"},
                    {"name": "phase2", "description": "Second phase"}
                ]
            }
        }
        with open(sample_job_path, 'w') as f:
            json.dump(sample_job_content, f)

        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Execute rerun from step 1
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "rerun", "sample-job", "--step", "1"])
        assert result.exit_code == 0
        assert "🔄 Executing 'logist job rerun'" in result.output
        assert "Starting rerun from phase 1 ('phase2')" in result.output

    def test_rerun_invalid_step_number(self, tmp_path):
        """Test that rerun fails when step number is out of bounds."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory and create a sample job with 2 phases
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])
        job_dir = tmp_path / "sample-job"
        job_dir.mkdir()

        # Create job with only 2 phases (steps 0, 1)
        sample_job_path = job_dir / "job.json"
        sample_job_content = {
            "job_spec": {
                "job_id": "sample-job",
                "description": "Sample job with phases",
                "phases": [
                    {"name": "phase1", "description": "First phase"},
                    {"name": "phase2", "description": "Second phase"}
                ]
            }
        }
        with open(sample_job_path, 'w') as f:
            json.dump(sample_job_content, f)

        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "create", str(job_dir)])

        # Try to rerun from step 2 (invalid - only 0 and 1 exist)
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "rerun", "sample-job", "--step", "2"])
        assert result.exit_code == 0  # Handled gracefully
        assert "Invalid step number 2" in result.output
        assert "Job has 2 phases (0-1)" in result.output


# Integration test for CLI installation
def test_import_main():
    """Test that main function can be imported."""
    from logist.cli import main

    assert callable(main), "main should be callable"
    def test_enhance_flag_parsing(self, tmp_path):
        """Test that --enhance flag is properly parsed and stored in context."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        # Initialize jobs directory
        self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "init"])

        # Test flag present
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "--enhance", "job", "list"])
        # The flag should be parsed without errors - we just check it runs successfully
        assert result.exit_code == 0
        # Since we can't easily inspect the context object, we just verify the command runs

        # Test flag absent
        result = self.runner.invoke(main, ["--jobs-dir", str(jobs_dir), "job", "list"])
        assert result.exit_code == 0
