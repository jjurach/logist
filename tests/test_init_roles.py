#!/usr/bin/env python3
"""
Tests for logist init command role configuration functionality.

Tests that the init command properly creates JSON role configuration files
from the default roles configuration.
"""

import json
import os
from pathlib import Path

import pytest

from logist.cli import init_command


class TestInitRoles:
    """Test init command role configuration functionality."""

    def test_init_creates_role_json_files(self, tmp_path):
        """Test that init creates role .json files."""
        jobs_dir = tmp_path / "test_jobs"
        success = init_command(str(jobs_dir))

        assert success, "init_command should return True on success"
        assert (jobs_dir / "worker.json").exists(), "worker.json should be created"
        assert (jobs_dir / "supervisor.json").exists(), "supervisor.json should be created"

        # Verify JSON content structure for worker
        with open(jobs_dir / "worker.json") as f:
            worker_config = json.load(f)
        assert "name" in worker_config, "Worker config should have name field"
        assert "instructions" in worker_config, "Worker config should have instructions field"
        assert "description" in worker_config, "Worker config should have description field"
        assert "llm_model" in worker_config, "Worker config should have llm_model field"
        assert worker_config["name"] == "Worker", "Worker config name should be 'Worker'"

        # Verify JSON content structure for supervisor
        with open(jobs_dir / "supervisor.json") as f:
            supervisor_config = json.load(f)
        assert "name" in supervisor_config, "Supervisor config should have name field"
        assert "instructions" in supervisor_config, "Supervisor config should have instructions field"
        assert "description" in supervisor_config, "Supervisor config should have description field"
        assert "llm_model" in supervisor_config, "Supervisor config should have llm_model field"
        assert supervisor_config["name"] == "Supervisor", "Supervisor config name should be 'Supervisor'"

    def test_init_preserves_existing_md_files(self, tmp_path):
        """Test that init still creates .md files alongside .json files."""
        jobs_dir = tmp_path / "test_jobs"
        success = init_command(str(jobs_dir))

        assert success, "init_command should return True on success"
        assert (jobs_dir / "worker.md").exists(), "worker.md should still be created"
        assert (jobs_dir / "supervisor.md").exists(), "supervisor.md should still be created"
        assert (jobs_dir / "system.md").exists(), "system.md should still be created"

    def test_init_handles_missing_default_roles_file(self, tmp_path, monkeypatch):
        """Test that init handles missing default-roles.json gracefully."""
        jobs_dir = tmp_path / "test_jobs"

        # Mock the path to a non-existent file
        def mock_join(*args):
            if len(args) >= 4 and args[-1] == 'default-roles.json':
                return str(tmp_path / "nonexistent.json")
            return os.path.join(*args)

        monkeypatch.setattr(os.path, "join", mock_join)

        # Should still succeed but log warnings
        success = init_command(str(jobs_dir))

        assert success, "init_command should succeed even with missing default-roles.json"

        # .md files should still be created
        assert (jobs_dir / "worker.md").exists(), "worker.md should still be created"
        assert (jobs_dir / "supervisor.md").exists(), "supervisor.md should still be created"

        # .json files should not be created (since source is missing)
        assert not (jobs_dir / "worker.json").exists(), "worker.json should not be created when source missing"
        assert not (jobs_dir / "supervisor.json").exists(), "supervisor.json should not be created when source missing"

    def test_init_handles_malformed_default_roles_file(self, tmp_path, monkeypatch):
        """Test that init handles malformed default-roles.json gracefully."""
        jobs_dir = tmp_path / "test_jobs"

        # Create a temporary malformed JSON file
        malformed_file = tmp_path / "malformed.json"
        malformed_file.write_text('{"roles": {"Worker": {invalid json}')

        def mock_join(*args):
            if len(args) >= 4 and args[-1] == 'default-roles.json':
                return str(malformed_file)
            return os.path.join(*args)

        monkeypatch.setattr(os.path, "join", mock_join)

        # Should still succeed but log warnings
        success = init_command(str(jobs_dir))

        assert success, "init_command should succeed even with malformed default-roles.json"

        # .md files should still be created
        assert (jobs_dir / "worker.md").exists(), "worker.md should still be created"
        assert (jobs_dir / "supervisor.md").exists(), "supervisor.md should still be created"

        # .json files should not be created (since source is malformed)
        assert not (jobs_dir / "worker.json").exists(), "worker.json should not be created when source malformed"
        assert not (jobs_dir / "supervisor.json").exists(), "supervisor.json should not be created when source malformed"


class TestInitIntegration:
    """Integration tests for init command in complete workflow."""

    def test_init_creates_jobs_index(self, tmp_path):
        """Test that init creates the jobs_index.json file."""
        jobs_dir = tmp_path / "test_jobs"
        success = init_command(str(jobs_dir))

        assert success, "init_command should return True on success"
        assert (jobs_dir / "jobs_index.json").exists(), "jobs_index.json should be created"

        # Verify jobs_index structure
        with open(jobs_dir / "jobs_index.json") as f:
            jobs_index = json.load(f)
        assert "current_job_id" in jobs_index, "jobs_index should have current_job_id"
        assert "jobs" in jobs_index, "jobs_index should have jobs dict"
        assert "queue" in jobs_index, "jobs_index should have queue list"
        assert jobs_index["current_job_id"] is None, "current_job_id should be None initially"
        assert isinstance(jobs_index["jobs"], dict), "jobs should be a dict"
        assert isinstance(jobs_index["queue"], list), "queue should be a list"

    def test_init_idempotent_operation(self, tmp_path):
        """Test that running init multiple times is safe."""
        jobs_dir = tmp_path / "test_jobs"

        # First init
        success1 = init_command(str(jobs_dir))
        assert success1, "First init should succeed"

        # Record timestamps of first run
        worker_json_mtime1 = (jobs_dir / "worker.json").stat().st_mtime
        worker_md_mtime1 = (jobs_dir / "worker.md").stat().st_mtime

        # Wait a moment to ensure different timestamps
        import time
        time.sleep(0.1)

        # Second init
        success2 = init_command(str(jobs_dir))
        assert success2, "Second init should succeed"

        # Files should be overwritten (newer timestamps)
        worker_json_mtime2 = (jobs_dir / "worker.json").stat().st_mtime
        worker_md_mtime2 = (jobs_dir / "worker.md").stat().st_mtime

        # Timestamps should be newer (files overwritten)
        assert worker_json_mtime2 > worker_json_mtime1, "worker.json should be overwritten"
        assert worker_md_mtime2 > worker_md_mtime1, "worker.md should be overwritten"

    def test_init_creates_all_expected_files(self, tmp_path):
        """Test that init creates all expected files for a complete setup."""
        jobs_dir = tmp_path / "test_jobs"
        success = init_command(str(jobs_dir))

        assert success, "init_command should succeed"

        # Check all expected files exist
        expected_files = [
            "jobs_index.json",
            "worker.json", "worker.md",
            "supervisor.json", "supervisor.md",
            "system.md"  # system.md exists but no system.json
        ]

        for filename in expected_files:
            assert (jobs_dir / filename).exists(), f"{filename} should be created"

    def test_role_json_files_valid_json(self, tmp_path):
        """Test that created role JSON files are valid JSON."""
        jobs_dir = tmp_path / "test_jobs"
        success = init_command(str(jobs_dir))

        assert success, "init_command should succeed"

        # Verify both role JSON files are valid JSON
        for role_file in ["worker.json", "supervisor.json"]:
            filepath = jobs_dir / role_file
            assert filepath.exists(), f"{role_file} should exist"

            # Should be able to load as JSON without errors
            with open(filepath) as f:
                config = json.load(f)

            # Should be a dict with required fields
            assert isinstance(config, dict), f"{role_file} should contain a JSON object"
            required_fields = ["name", "description", "instructions", "llm_model"]
            for field in required_fields:
                assert field in config, f"{role_file} should have '{field}' field"
                assert isinstance(config[field], str), f"{field} in {role_file} should be a string"
                assert len(config[field]) > 0, f"{field} in {role_file} should not be empty"