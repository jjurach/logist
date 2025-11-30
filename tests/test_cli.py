#!/usr/bin/env python3
"""
Basic tests for Project Logist CLI - do-little tests that verify placeholder
functionality.
"""

import json
import os

from click.testing import CliRunner

from logist.cli import (
    PlaceholderJobManager,
    PlaceholderLogistEngine,
    PlaceholderRoleManager,
    main,
)


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

    def test_job_select_command(self):
        """Test the job select command."""
        result = self.runner.invoke(main, ["job", "select", "my-job"])
        assert result.exit_code == 0
        assert "Setting 'my-job' as the current job" in result.output

    def test_command_uses_current_job(self):
        """Test that a command uses the current job if no ID is given."""
        result = self.runner.invoke(main, ["job", "status"])
        assert result.exit_code == 0
        assert "No job ID provided. Using current job:" in result.output
        assert "Status: PENDING" in result.output

    def test_command_uses_provided_job_id(self):
        """Test that a command uses the provided ID even if a current job is set."""
        result = self.runner.invoke(main, ["job", "status", "specific-job"])
        assert result.exit_code == 0
        assert "No job ID provided" not in result.output
        assert "Job 'specific-job' Status:" in result.output

    def test_command_fails_without_job_id_and_no_current(self, mocker):
        """Test that a command fails if no job can be determined."""
        mocker.patch.object(PlaceholderJobManager, "get_current_job_id", return_value=None)
        result = self.runner.invoke(main, ["job", "status"])
        assert result.exit_code == 0  # click exits 0 on handled errors
        assert "No job ID provided and no current job is selected" in result.output


# Integration test for CLI installation
def test_import_main():
    """Test that main function can be imported."""
    from logist.cli import main

    assert callable(main), "main should be callable"
