#!/usr/bin/env python3
"""
Tests for Logist job context assembly functionality.
"""

import json
import os
import pytest
import tempfile
from pathlib import Path

from logist.job_context import assemble_job_context


class TestJobContextAssembly:
    """Test the assemble_job_context function with enhance flag."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.jobs_dir = self.temp_dir / "jobs"  
        self.jobs_dir.mkdir()
        self.job_dir = self.temp_dir / "test-job"
        self.job_dir.mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_minimal_context_assembly(self):
        """Test minimal context when enhance=False."""
        # Create a basic job manifest
        manifest = {
            "job_id": "test-job",
            "description": "A test job.",
            "status": "PENDING",
            "current_phase": "phase1",
            "phases": [{"name": "phase1", "description": "First phase"}],
            "metrics": {
                "cumulative_cost": 1.0,
                "cumulative_time_seconds": 10.0
            },
            "history": []
        }

        # Create workspace with some files
        workspace_dir = self.job_dir / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / "test.py").write_text("print('hello')")

        # Create basic role files
        worker_md_path = self.jobs_dir / "worker.md"
        worker_md_path.write_text("# Worker Role\n\nDo work")

        system_md_path = self.jobs_dir / "system.md"
        system_md_path.write_text("# System Role\n\nSystem instructions")

        # Test minimal context
        context = assemble_job_context(
            job_dir=str(self.job_dir),
            job_manifest=manifest,
            jobs_dir=str(self.jobs_dir),
            enhance=False
        )

        # Minimal context should have basic fields only
        assert "job_id" in context
        assert context["job_id"] == "test-job"
        assert "description" in context
        assert "status" in context
        assert "current_phase" in context
        assert "workspace_files" in context

        # Enhanced context should NOT be present
        assert "system_instructions" not in context
        assert "job_history_summary" not in context
        assert "job_metrics_summary" not in context
        assert "all_phases" not in context
        assert "phase_specification" not in context

    def test_enhanced_context_assembly(self):
        """Test enhanced context when enhance=True."""
        # Create a comprehensive job manifest
        manifest = {
            "job_id": "test-job",
            "description": "A test job.",
            "status": "RUNNING",
            "current_phase": "phase1",
            "phases": [
                {"name": "phase1", "description": "First phase", "active_agent": "worker"}
            ],
            "metrics": {
                "cumulative_cost": 2.5,
                "cumulative_time_seconds": 30.0
            },
            "history": [
                {
                    "role": "Worker",
                    "action": "PROCESS",
                    "summary": "Started processing",
                    "metrics": {"cost_usd": 1.0, "duration_seconds": 15.0}
                }
            ]
        }

        # Create workspace with some files
        workspace_dir = self.job_dir / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / "input.txt").write_text("test input")

        # Create enhanced role files
        worker_md_path = self.jobs_dir / "worker.md"
        worker_md_path.write_text("# Worker Role\n\nDo work professionally")

        system_md_path = self.jobs_dir / "system.md"
        system_md_path.write_text("# System Role\n\nSystem instructions")

        # Test enhanced context
        context = assemble_job_context(
            job_dir=str(self.job_dir),
            job_manifest=manifest,
            jobs_dir=str(self.jobs_dir),
            enhance=True
        )

        # Enhanced context should include all fields
        assert "job_id" in context
        assert context["job_id"] == "test-job"
        assert "description" in context
        assert "status" in context
        assert "current_phase" in context
        assert "phase_specification" in context
        assert "system_instructions" in context
        assert "workspace_files" in context
        assert "workspace_git_status" in context
        assert "job_history_summary" in context
        assert "job_metrics_summary" in context
        assert "all_phases" in context

        # Check specific enhanced fields
        expected_instructions = "# System Role\n\nSystem instructions"
        assert context["system_instructions"] == expected_instructions
        assert context["job_metrics_summary"] == "Total cost: $2.5000, Total time: 30.00s"

    def test_context_assembly_with_missing_job_manifest(self):
        """Test context assembly handles missing job manifest gracefully."""
        # Use minimal manifest
        manifest = {
            "job_id": "test-job",
            "description": "A test job.",
        }

        context = assemble_job_context(
            job_dir=str(self.job_dir),
            job_manifest=manifest,
            jobs_dir=str(self.jobs_dir),
            enhance=False
        )

        assert context["job_id"] == "test-job"
        assert context["description"] == "A test job."
        # Should have defaults for missing fields
        assert context["status"] == "PENDING"
        assert context["current_phase"] is None or context["current_phase"] == "unknown"

    def test_context_assembly_with_empty_workspace(self):
        """Test context assembly with empty workspace."""
        manifest = {
            "job_id": "test-job",
            "description": "A test job.",
            "status": "PENDING",
        }

        # Create empty workspace
        workspace_dir = self.job_dir / "workspace"
        workspace_dir.mkdir()

        context = assemble_job_context(
            job_dir=str(self.job_dir),
            job_manifest=manifest,
            jobs_dir=str(self.jobs_dir),
            enhance=False
        )

        # Should still have workspace_files field, even if empty
        assert "workspace_files" in context
        assert isinstance(context["workspace_files"], dict)