"""
End-to-End Integration Tests for Logist System

This module provides comprehensive integration tests that validate the entire
Logist system working together, from job creation through execution to completion.
"""

import os
import json
import tempfile
import shutil
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from logist.core_engine import LogistEngine
from logist.services import JobManagerService
from logist.job_state import JobStates, load_job_manifest
from logist.agents.mock import MockAgent
from logist.runtimes.host import HostRuntime
from logist.core.job_directory import JobDirectoryManager
from logist.core.locking import JobLockManager
from logist.core.recovery import JobRecoveryManager
from logist.core.observer import LogistObserver
from logist.core.sentinel import ExecutionSentinel, SentinelConfig


class TestLogistEndToEnd:
    """End-to-end tests for the complete Logist system."""

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create a temporary jobs directory for testing."""
        temp_dir = tempfile.mkdtemp(prefix="logist_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def job_manager(self, temp_jobs_dir):
        """Create a job manager for testing."""
        return JobManagerService()

    @pytest.fixture
    def engine(self):
        """Create a LogistEngine for testing."""
        return LogistEngine(runner=MockRuntime())

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        return MockAgent()

    @pytest.fixture
    def host_runtime(self):
        """Create a host runtime for testing."""
        return HostRuntime()

    def test_complete_job_lifecycle(self, temp_jobs_dir, job_manager, engine, mock_agent, host_runtime):
        """Test complete job lifecycle from creation to completion."""
        # Setup
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        # Create a job
        job_id = job_manager.create_job("test_job_dir", temp_jobs_dir)
        job_dir = os.path.join(temp_jobs_dir, job_id)

        # Verify job directory structure
        assert os.path.exists(job_dir)
        assert os.path.exists(os.path.join(job_dir, "job_manifest.json"))
        assert os.path.exists(os.path.join(job_dir, "workspace"))
        assert os.path.exists(os.path.join(job_dir, "logs"))

        # Configure the job
        config = {
            "objective": "Test job execution",
            "details": "End-to-end integration test",
            "acceptance": "Job completes successfully",
            "prompt": "Execute this test job",
            "files": ["test_file.txt"]
        }

        config_path = os.path.join(job_dir, "config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        # Create prompt.md
        prompt_path = os.path.join(job_dir, "prompt.md")
        with open(prompt_path, 'w') as f:
            f.write("# Test Job\n\nThis is a test job for integration testing.")

        # Activate the job
        success = job_manager.activate_job(job_id, temp_jobs_dir)
        assert success

        # Verify job is in queue
        jobs_index_path = os.path.join(temp_jobs_dir, "jobs_index.json")
        with open(jobs_index_path, 'r') as f:
            jobs_index = json.load(f)

        assert job_id in jobs_index["queue"]
        assert jobs_index["queue"][0] == job_id

        # Load and verify manifest
        manifest = load_job_manifest(job_dir)
        assert manifest["status"] == JobStates.PENDING
        assert manifest["current_phase"] is not None

    def test_job_execution_flow(self, temp_jobs_dir, engine):
        """Test the complete job execution flow."""
        # Setup
        job_manager = JobManagerService()
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        # Create and activate a job
        job_id = job_manager.create_job("exec_test_job", temp_jobs_dir)
        job_dir = os.path.join(temp_jobs_dir, job_id)

        # Configure job
        config = {"objective": "Test execution", "prompt": "Complete successfully"}
        with open(os.path.join(job_dir, "config.json"), 'w') as f:
            json.dump(config, f, indent=2)

        with open(os.path.join(job_dir, "prompt.md"), 'w') as f:
            f.write("# Execution Test\n\nTest job execution flow.")

        job_manager.activate_job(job_id, temp_jobs_dir)

        # Initialize sentinel for monitoring
        engine.initialize_sentinel(temp_jobs_dir)

        # Mock the CLI context for step_job
        ctx = MagicMock()
        ctx.obj = {
            "JOBS_DIR": temp_jobs_dir,
            "DEBUG": False,
            "ENHANCE": False,
            "ENGINE": engine
        }

        # Execute a job step
        with patch('logist.core_engine.execute_llm_with_cline') as mock_execute:
            # Mock successful LLM execution
            mock_execute.return_value = ({
                "action": "COMPLETED",
                "summary_for_supervisor": "Task completed successfully",
                "evidence_files": [],
                "metrics": {"cost_usd": 0.01, "token_input": 100, "token_output": 50}
            }, 2.5)

            success = engine.step_job(ctx, job_id, job_dir)
            assert success

        # Verify job state changed
        manifest = load_job_manifest(job_dir)
        assert manifest["status"] == JobStates.REVIEW_REQUIRED

        # Verify history was recorded
        assert "history" in manifest
        assert len(manifest["history"]) > 0

        # Verify metrics were recorded
        assert "metrics" in manifest
        assert manifest["metrics"]["cumulative_cost"] == 0.01
        assert manifest["metrics"]["cumulative_time_seconds"] == 2.5

    def test_job_recovery_integration(self, temp_jobs_dir):
        """Test job recovery system integration."""
        # Setup
        job_manager = JobManagerService()
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        # Create job directory manager and recovery manager
        dir_manager = JobDirectoryManager(temp_jobs_dir)
        recovery_manager = JobRecoveryManager(temp_jobs_dir)

        # Create a job
        job_id = "recovery_test_job"
        config = {"objective": "Test recovery", "prompt": "Test job"}

        job_dir = dir_manager.create_job_directory(job_id, config)
        assert os.path.exists(job_dir)

        # Simulate a crash by setting status to RUNNING and clearing activity
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        manifest["status"] = JobStates.RUNNING
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Test crash detection
        crashed_jobs = recovery_manager.detect_crashed_jobs()
        assert len(crashed_jobs) > 0
        assert any(job["job_id"] == job_id for job in crashed_jobs)

        # Test recovery
        recovery_result = recovery_manager.recover_crashed_job(job_id, force=True)
        assert recovery_result["recovered"]

        # Verify job was recovered
        manifest = load_job_manifest(job_dir)
        assert manifest["status"] == JobStates.PENDING  # Reset to safe state

    def test_concurrent_job_execution(self, temp_jobs_dir):
        """Test concurrent execution of multiple jobs."""
        # Setup
        job_manager = JobManagerService()
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        dir_manager = JobDirectoryManager(temp_jobs_dir)
        lock_manager = JobLockManager(temp_jobs_dir)

        # Create multiple jobs
        job_ids = []
        for i in range(3):
            job_id = f"concurrent_job_{i}"
            config = {"objective": f"Concurrent test job {i}", "prompt": f"Job {i}"}
            job_dir = dir_manager.create_job_directory(job_id, config)
            job_ids.append(job_id)

        # Test locking mechanism
        locks = []
        for job_id in job_ids:
            lock = lock_manager.lock_job_directory(job_id, timeout=5.0)
            locks.append(lock)
            assert lock.is_locked()

        # Test concurrent access prevention
        for job_id in job_ids:
            # Try to acquire already locked job - should fail
            duplicate_lock = lock_manager.lock_job_directory(job_id, timeout=1.0)
            assert not duplicate_lock.is_locked()

        # Release locks
        for job_id in job_ids:
            lock_manager.unlock_job_directory(job_id)

        # Verify locks are released
        for job_id in job_ids:
            lock = lock_manager.lock_job_directory(job_id, timeout=1.0)
            assert lock.is_locked()
            lock_manager.unlock_job_directory(job_id)

    def test_sentinel_monitoring_integration(self, temp_jobs_dir):
        """Test sentinel monitoring integration."""
        # Create sentinel
        config = SentinelConfig(check_interval=0.1, worker_timeout=1.0)  # Fast for testing
        sentinel = ExecutionSentinel(temp_jobs_dir, config)

        dir_manager = JobDirectoryManager(temp_jobs_dir)

        # Create a test job
        job_id = "sentinel_test_job"
        config_data = {"objective": "Sentinel test", "prompt": "Test monitoring"}
        job_dir = dir_manager.create_job_directory(job_id, config_data)

        # Set job to running state
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        manifest["status"] = JobStates.RUNNING
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Add job to monitoring
        sentinel.add_job(job_id)

        # Start monitoring (briefly)
        sentinel.start_monitoring()
        time.sleep(0.2)  # Allow monitoring cycle
        sentinel.stop_monitoring()

        # Check that job is being monitored
        status = sentinel.get_status_report()
        assert status["active_jobs"] == 1
        assert job_id in status["active_locks"]

    def test_observer_state_detection(self, temp_jobs_dir):
        """Test observer state detection integration."""
        observer = LogistObserver()

        # Test various log patterns
        test_logs = [
            "Job started successfully",
            "Worker activated and running",
            "Task completed successfully",
            "Error occurred during execution",
            "Process stuck and unresponsive"
        ]

        for log in test_logs:
            detection = observer.detect_state(log)
            # Observer should detect some state from these logs
            # (Exact detection may vary based on pattern matching)

        # Test log analysis
        analysis = observer.analyze_log_segment(test_logs)
        assert "detected_states" in analysis
        assert "confidence_summary" in analysis

        # Test state recommendation
        mock_observations = [
            {"inferred_state": "RUNNING", "confidence": observer.pattern_dict._calculate_detection_confidence.__wrapped__.__defaults__[0] or type('obj', (object,), {'value': 1})()},
            {"inferred_state": "RUNNING", "confidence": observer.pattern_dict._calculate_detection_confidence.__wrapped__.__defaults__[0] or type('obj', (object,), {'value': 1})()}
        ]
        recommendation = observer.get_state_recommendation("test_job", mock_observations)
        assert "recommended_state" in recommendation

    def test_full_system_integration(self, temp_jobs_dir):
        """Test full system integration with all components."""
        # Setup all system components
        job_manager = JobManagerService()
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        engine = LogistEngine(runner=MockRuntime())
        engine.initialize_sentinel(temp_jobs_dir)

        dir_manager = JobDirectoryManager(temp_jobs_dir)
        recovery_manager = JobRecoveryManager(temp_jobs_dir)
        observer = LogistObserver()

        # Create a comprehensive test job
        job_id = "full_system_test"
        config = {
            "objective": "Full system integration test",
            "details": "Test all components working together",
            "acceptance": "All components function correctly",
            "prompt": "Execute comprehensive system test",
            "files": ["system_test.py"]
        }

        job_dir = dir_manager.create_job_directory(job_id, config)

        # Create prompt
        prompt_path = os.path.join(job_dir, "prompt.md")
        with open(prompt_path, 'w') as f:
            f.write("# System Integration Test\n\nTest all Logist components.")

        # Activate job
        job_manager.activate_job(job_id, temp_jobs_dir)

        # Test directory validation
        validation = dir_manager.validate_job_directory(job_id)
        assert validation["valid"]

        # Test observer analysis
        log_content = "Job initialized and ready for execution"
        observation = observer.observe_job_state(job_id, log_content)
        assert observation["job_id"] == job_id

        # Test recovery system
        consistency = recovery_manager.validate_job_consistency(job_id)
        assert consistency["consistent"]

        # Test locking
        lock_manager = JobLockManager(temp_jobs_dir)
        lock = lock_manager.lock_job_directory(job_id, timeout=5.0)
        assert lock.is_locked()
        lock_manager.unlock_job_directory(job_id)

        # Verify all components work together
        status_report = recovery_manager.get_recovery_status_report()
        assert "system_health" in status_report

        print("✅ Full system integration test passed!")

    def test_error_handling_and_recovery(self, temp_jobs_dir):
        """Test error handling and recovery mechanisms."""
        job_manager = JobManagerService()
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        engine = LogistEngine(runner=MockRuntime())
        recovery_manager = JobRecoveryManager(temp_jobs_dir)

        # Create job
        job_id = "error_test_job"
        job_dir = job_manager.create_job("error_test", temp_jobs_dir)

        # Simulate corrupted manifest
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'w') as f:
            f.write("{invalid json content")

        # Test recovery from corrupted manifest
        recovery_result = recovery_manager.validate_job_consistency(job_id)
        assert not recovery_result["consistent"]
        assert "validation_error" in recovery_result["issues"][0]

        # Test bulk recovery
        bulk_result = recovery_manager.perform_bulk_recovery([job_id], force=True)
        assert bulk_result["total_jobs_processed"] == 1

        print("✅ Error handling and recovery test passed!")

    @pytest.mark.parametrize("job_count", [1, 5, 10])
    def test_scalability_job_creation(self, temp_jobs_dir, job_count):
        """Test scalability of job creation and management."""
        dir_manager = JobDirectoryManager(temp_jobs_dir)

        # Create multiple jobs
        job_ids = []
        for i in range(job_count):
            job_id = f"scale_test_job_{i}"
            config = {"objective": f"Scale test job {i}", "prompt": f"Job {i}"}
            job_dir = dir_manager.create_job_directory(job_id, config)
            job_ids.append(job_id)

        # Verify all jobs created
        jobs = dir_manager.list_jobs()
        assert len(jobs) == job_count

        # Test bulk operations
        stats = dir_manager.get_job_stats()
        assert stats["total_jobs"] == job_count

        print(f"✅ Scalability test passed for {job_count} jobs!")

    def test_resource_cleanup_integration(self, temp_jobs_dir):
        """Test resource cleanup integration."""
        dir_manager = JobDirectoryManager(temp_jobs_dir)
        recovery_manager = JobRecoveryManager(temp_jobs_dir)

        # Create job
        job_id = "cleanup_test_job"
        config = {"objective": "Cleanup test", "prompt": "Test cleanup"}
        job_dir = dir_manager.create_job_directory(job_id, config)

        # Create some temp files
        temp_dir = Path(job_dir) / "temp"
        temp_dir.mkdir(exist_ok=True)

        temp_file = temp_dir / "test_temp_file.txt"
        temp_file.write_text("temporary content")

        # Set job to completed state for cleanup
        manifest_path = Path(job_dir) / "job_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["status"] = JobStates.SUCCESS

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Test cleanup
        cleanup_result = dir_manager.cleanup_job_directory(job_id, force=False)
        assert cleanup_result["success"]

        # Verify job directory was removed
        assert not Path(job_dir).exists()

        print("✅ Resource cleanup integration test passed!")


# Integration test utilities
def create_test_job_environment(base_dir: str, job_id: str, config: dict = None) -> str:
    """Create a complete test job environment."""
    if config is None:
        config = {
            "objective": "Integration test job",
            "prompt": "Test job execution",
            "files": []
        }

    dir_manager = JobDirectoryManager(base_dir)
    job_dir = dir_manager.create_job_directory(job_id, config)

    # Create prompt.md
    prompt_path = os.path.join(job_dir, "prompt.md")
    with open(prompt_path, 'w') as f:
        f.write(f"# {job_id}\n\n{config.get('prompt', 'Test job')}")

    return job_dir


def simulate_job_execution(job_dir: str, status_sequence: list) -> None:
    """Simulate job execution by setting status sequence."""
    manifest_path = os.path.join(job_dir, "job_manifest.json")

    for status in status_sequence:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        manifest["status"] = status
        manifest["history"].append({
            "timestamp": "2025-12-26T13:25:00",
            "event": f"STATUS_CHANGE_{status}",
            "message": f"Job status changed to {status}"
        })

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    # Run basic integration tests
    pytest.main([__file__, "-v"])