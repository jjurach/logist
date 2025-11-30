#!/usr/bin/env python3
"""
Basic tests for Logist CLI - do-little tests that verify placeholder
functionality.
"""

import json
import os

from click.testing import CliRunner

from logist.cli import (
    PlaceholderJobManager,
    PlaceholderLogistEngine,
    RoleManager, # Use the real RoleManager now
    main,
)
import shutil # Needed for cleaning up directories


class TestPlaceholderLogistEngine:
    """Test the placeholder engine that prints intentions."""

    def setup_method(self):
        """Setup test instance."""
        self.engine = PlaceholderLogistEngine()

    def test_step_job_dry_run_placeholder(self, capsys):
        """Test job step simulation with dry-run."""
        self.engine.step_job("test-job", dry_run=True)
        captured = capsys.readouterr()
        assert "Defensive setting detected: --dry-run" in captured.out


class TestPlaceholderJobManager:
    """Test the placeholder job manager."""

    def setup_method(self):
        """Setup test instance."""
        self.manager = PlaceholderJobManager()

    def test_create_job_placeholder(self, capsys):
        """Test job creation simulation."""
        self.manager.create_job("./test-job", "/tmp/jobs")
        captured = capsys.readouterr()
        assert "Initializing or updating job" in captured.out
        assert "Set this job as the currently selected job" in captured.out

    def test_create_job_warning_placeholder(self, capsys):
        """Test the warning for job creation outside the jobs dir."""
        self.manager.create_job("/elsewhere/test-job", "/tmp/jobs")
        captured = capsys.readouterr()
        assert "Warning: The job directory" in captured.out
        assert "is not inside the configured --jobs-dir" in captured.out


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
        
        mocker.patch.object(PlaceholderJobManager, "get_current_job_id", return_value=None)
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


# Integration test for CLI installation
def test_import_main():
    """Test that main function can be imported."""
    from logist.cli import main

    assert callable(main), "main should be callable"