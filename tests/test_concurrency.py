"""
Performance & Concurrency Testing for Logist System

This module provides comprehensive performance and concurrency tests to validate
the Logist system's behavior under load, concurrent operations, and stress conditions.
"""

import os
import json
import tempfile
import shutil
import pytest
import time
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

import psutil

from logist.core_engine import LogistEngine
from logist.services import JobManagerService
from logist.job_state import JobStates, load_job_manifest
from logist.core.job_directory import JobDirectoryManager
from logist.core.locking import JobLockManager, LockError
from logist.core.recovery import JobRecoveryManager
from logist.core.sentinel import ExecutionSentinel, SentinelConfig
from logist.core.observer import LogistObserver


class PerformanceMetrics:
    """Collect and analyze performance metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.operations = []
        self.errors = []
        self.resource_usage = []

    def record_operation(self, operation: str, duration: float, success: bool = True):
        """Record an operation's performance."""
        self.operations.append({
            "operation": operation,
            "duration": duration,
            "success": success,
            "timestamp": time.time()
        })

    def record_error(self, operation: str, error: str):
        """Record an error."""
        self.errors.append({
            "operation": operation,
            "error": error,
            "timestamp": time.time()
        })

    def record_resource_usage(self):
        """Record current resource usage."""
        process = psutil.Process()
        self.resource_usage.append({
            "timestamp": time.time(),
            "cpu_percent": process.cpu_percent(),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "threads": process.num_threads()
        })

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        total_time = time.time() - self.start_time
        successful_ops = [op for op in self.operations if op["success"]]
        failed_ops = [op for op in self.operations if not op["success"]]

        return {
            "total_time": total_time,
            "total_operations": len(self.operations),
            "successful_operations": len(successful_ops),
            "failed_operations": len(failed_ops),
            "success_rate": len(successful_ops) / len(self.operations) if self.operations else 0,
            "operations_per_second": len(self.operations) / total_time if total_time > 0 else 0,
            "average_operation_time": sum(op["duration"] for op in self.operations) / len(self.operations) if self.operations else 0,
            "errors": self.errors,
            "peak_memory_mb": max((ru["memory_mb"] for ru in self.resource_usage), default=0),
            "peak_cpu_percent": max((ru["cpu_percent"] for ru in self.resource_usage), default=0)
        }


class TestConcurrencyPerformance:
    """Comprehensive concurrency and performance tests."""

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create a temporary jobs directory for testing."""
        temp_dir = tempfile.mkdtemp(prefix="logist_concurrency_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def performance_monitor(self):
        """Create a performance monitoring instance."""
        return PerformanceMetrics()

    def test_job_creation_performance(self, temp_jobs_dir, performance_monitor):
        """Test performance of creating multiple jobs concurrently."""
        dir_manager = JobDirectoryManager(temp_jobs_dir)

        def create_job(job_id: str):
            start_time = time.time()
            try:
                config = {"objective": f"Performance test job {job_id}", "prompt": f"Job {job_id}"}
                job_dir = dir_manager.create_job_directory(job_id, config)
                duration = time.time() - start_time
                performance_monitor.record_operation(f"create_job_{job_id}", duration, True)
                return job_id, job_dir, None
            except Exception as e:
                duration = time.time() - start_time
                performance_monitor.record_operation(f"create_job_{job_id}", duration, False)
                performance_monitor.record_error(f"create_job_{job_id}", str(e))
                return job_id, None, str(e)

        # Test with different concurrency levels
        for num_jobs in [10, 50, 100]:
            performance_monitor.operations.clear()
            performance_monitor.errors.clear()

            # Create jobs concurrently
            with ThreadPoolExecutor(max_workers=min(10, num_jobs)) as executor:
                futures = [executor.submit(create_job, f"perf_job_{i}") for i in range(num_jobs)]
                results = [future.result() for future in as_completed(futures)]

            # Verify results
            successful = sum(1 for r in results if r[2] is None)
            assert successful == num_jobs, f"Failed to create {num_jobs - successful} jobs"

            # Check performance
            summary = performance_monitor.get_summary()
            print(f"Job Creation Performance ({num_jobs} jobs):")
            print(".2f")
            print(".1f")
            print(".2f")

            # Performance assertions
            assert summary["success_rate"] == 1.0, "All job creations should succeed"
            assert summary["operations_per_second"] > 10, "Should create at least 10 jobs per second"

    def test_concurrent_job_execution(self, temp_jobs_dir, performance_monitor):
        """Test concurrent execution of multiple jobs."""
        job_manager = JobManagerService()
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        dir_manager = JobDirectoryManager(temp_jobs_dir)

        # Create multiple jobs
        num_jobs = 20
        job_ids = []

        for i in range(num_jobs):
            job_id = f"concurrent_exec_job_{i}"
            config = {"objective": f"Concurrent execution test {i}", "prompt": f"Execute job {i}"}
            dir_manager.create_job_directory(job_id, config)

            # Create prompt file
            job_dir = dir_manager.get_job_directory(job_id)
            with open(os.path.join(job_dir, "prompt.md"), 'w') as f:
                f.write(f"# Concurrent Job {i}\n\nExecute test operation {i}.")

            # Activate job
            job_manager.activate_job(job_id, temp_jobs_dir)
            job_ids.append(job_id)

        # Mock execution function
        def execute_job(job_id: str):
            start_time = time.time()
            try:
                job_dir = dir_manager.get_job_directory(job_id)

                # Mock LLM execution
                with patch('logist.core_engine.execute_llm_with_cline') as mock_execute:
                    mock_execute.return_value = ({
                        "action": "COMPLETED",
                        "summary_for_supervisor": f"Job {job_id} completed successfully",
                        "evidence_files": [],
                        "metrics": {"cost_usd": 0.01, "token_input": 50, "token_output": 25}
                    }, 1.0)

                    # Execute job step
                    engine = LogistEngine()
                    ctx = MagicMock()
                    ctx.obj = {
                        "JOBS_DIR": temp_jobs_dir,
                        "DEBUG": False,
                        "ENHANCE": False,
                        "ENGINE": engine
                    }

                    success = engine.step_job(ctx, job_id, job_dir)

                duration = time.time() - start_time
                performance_monitor.record_operation(f"execute_job_{job_id}", duration, success)

                return job_id, success, None
            except Exception as e:
                duration = time.time() - start_time
                performance_monitor.record_operation(f"execute_job_{job_id}", duration, False)
                performance_monitor.record_error(f"execute_job_{job_id}", str(e))
                return job_id, False, str(e)

        # Execute jobs concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:  # Limit to 5 concurrent executions
            futures = [executor.submit(execute_job, job_id) for job_id in job_ids]
            results = [future.result() for future in as_completed(futures)]

        # Analyze results
        successful = sum(1 for r in results if r[1])
        summary = performance_monitor.get_summary()

        print(f"Concurrent Execution Performance ({num_jobs} jobs):")
        print(".2f")
        print(".1f")
        print(".2f")

        assert successful == num_jobs, f"Failed to execute {num_jobs - successful} jobs concurrently"
        assert summary["success_rate"] == 1.0, "All job executions should succeed"
        assert summary["operations_per_second"] > 1, "Should execute at least 1 job per second"

    def test_locking_contention_performance(self, temp_jobs_dir, performance_monitor):
        """Test performance under high locking contention."""
        lock_manager = JobLockManager(temp_jobs_dir)
        dir_manager = JobDirectoryManager(temp_jobs_dir)

        # Create jobs to lock
        num_jobs = 10
        job_ids = []

        for i in range(num_jobs):
            job_id = f"lock_test_job_{i}"
            config = {"objective": f"Lock contention test {i}"}
            dir_manager.create_job_directory(job_id, config)
            job_ids.append(job_id)

        def lock_and_unlock_job(job_id: str, iterations: int = 10):
            """Perform multiple lock/unlock cycles on a job."""
            total_start = time.time()
            success_count = 0

            for i in range(iterations):
                start_time = time.time()
                try:
                    lock = lock_manager.lock_job_directory(job_id, timeout=5.0)
                    # Simulate some work
                    time.sleep(0.001)
                    lock_manager.unlock_job_directory(job_id)
                    duration = time.time() - start_time
                    performance_monitor.record_operation(f"lock_cycle_{job_id}_{i}", duration, True)
                    success_count += 1
                except Exception as e:
                    duration = time.time() - start_time
                    performance_monitor.record_operation(f"lock_cycle_{job_id}_{i}", duration, False)
                    performance_monitor.record_error(f"lock_cycle_{job_id}_{i}", str(e))

            total_duration = time.time() - total_start
            return job_id, success_count, iterations, total_duration

        # Test concurrent locking with contention
        with ThreadPoolExecutor(max_workers=num_jobs) as executor:
            futures = [executor.submit(lock_and_unlock_job, job_id, 20) for job_id in job_ids]
            results = [future.result() for future in as_completed(futures)]

        # Analyze results
        total_operations = sum(r[1] for r in results)
        summary = performance_monitor.get_summary()

        print(f"Lock Contention Performance ({num_jobs} jobs, {total_operations} operations):")
        print(".2f")
        print(".1f")
        print(".2f")

        assert summary["success_rate"] > 0.95, "Should have high success rate even under contention"
        assert summary["operations_per_second"] > 50, "Should handle at least 50 lock operations per second"

    def test_sentinel_monitoring_performance(self, temp_jobs_dir, performance_monitor):
        """Test sentinel monitoring performance under load."""
        # Create sentinel with fast monitoring for testing
        config = SentinelConfig(
            check_interval=0.1,  # Very fast checks
            worker_timeout=2.0,
            auto_intervene=False  # Disable intervention for testing
        )
        sentinel = ExecutionSentinel(temp_jobs_dir, config)

        dir_manager = JobDirectoryManager(temp_jobs_dir)

        # Create multiple jobs to monitor
        num_jobs = 25
        job_ids = []

        for i in range(num_jobs):
            job_id = f"sentinel_test_job_{i}"
            config_data = {"objective": f"Sentinel monitoring test {i}"}
            dir_manager.create_job_directory(job_id, config_data)

            # Set to running state
            job_dir = dir_manager.get_job_directory(job_id)
            manifest_path = os.path.join(job_dir, "job_manifest.json")
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            manifest["status"] = JobStates.RUNNING
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

            sentinel.add_job(job_id)
            job_ids.append(job_id)

        # Start monitoring
        sentinel.start_monitoring()

        # Let it monitor for a period
        monitor_duration = 3.0  # 3 seconds
        start_time = time.time()

        while time.time() - start_time < monitor_duration:
            performance_monitor.record_resource_usage()
            time.sleep(0.1)

        # Stop monitoring
        sentinel.stop_monitoring()

        # Get final status
        status = sentinel.get_status_report()

        print(f"Sentinel Monitoring Performance ({num_jobs} jobs, {monitor_duration}s):")
        print(f"  Active Jobs Monitored: {status['active_jobs']}")
        print(f"  Hangs Detected: {status['hangs_detected']}")
        print(f"  Interventions Performed: {status['interventions_performed']}")

        # Performance checks
        assert status["active_jobs"] == num_jobs, "All jobs should be actively monitored"
        assert status["hangs_detected"] == 0, "No hangs should be detected (jobs are fresh)"

        resource_summary = performance_monitor.get_summary()
        print(".1f")
        print(".1f")

        assert resource_summary["peak_memory_mb"] < 200, "Memory usage should be reasonable"

    def test_observer_analysis_performance(self, performance_monitor):
        """Test observer analysis performance with large log volumes."""
        observer = LogistObserver()

        # Generate large log samples
        log_samples = [
            "Job started successfully at 2025-12-26 13:25:00",
            "Worker agent activated and running",
            "Processing input data and validating parameters",
            "Executing core business logic",
            "API call to external service completed",
            "Data validation passed successfully",
            "Task completed successfully",
            "Supervisor review initiated",
            "Supervisor approved the work",
            "Job finished successfully"
        ] * 100  # 1000 log lines

        # Test batch analysis performance
        start_time = time.time()
        analysis = observer.analyze_log_segment(log_samples)
        analysis_duration = time.time() - start_time

        performance_monitor.record_operation("observer_batch_analysis", analysis_duration, True)

        print(f"Observer Analysis Performance ({len(log_samples)} log lines):")
        print(".3f")
        print(f"  States Detected: {len(analysis['detected_states'])}")
        print(f"  Transitions Detected: {len(analysis['detected_transitions'])}")

        # Performance assertions
        assert analysis_duration < 2.0, "Analysis should complete within 2 seconds"
        assert len(analysis["detected_states"]) > 0, "Should detect some states"
        assert analysis["confidence_summary"], "Should have confidence metrics"

    def test_recovery_system_performance(self, temp_jobs_dir, performance_monitor):
        """Test recovery system performance under load."""
        recovery_manager = JobRecoveryManager(temp_jobs_dir)
        dir_manager = JobDirectoryManager(temp_jobs_dir)

        # Create multiple jobs that need recovery
        num_jobs = 15
        job_ids = []

        for i in range(num_jobs):
            job_id = f"recovery_perf_job_{i}"
            config = {"objective": f"Recovery performance test {i}"}
            dir_manager.create_job_directory(job_id, config)

            # Simulate crashed state
            job_dir = dir_manager.get_job_directory(job_id)
            manifest_path = os.path.join(job_dir, "job_manifest.json")
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            manifest["status"] = JobStates.RUNNING  # Mark as running (crashed)
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

            job_ids.append(job_id)

        # Test bulk recovery performance
        start_time = time.time()
        bulk_result = recovery_manager.perform_bulk_recovery(job_ids, force=True)
        recovery_duration = time.time() - start_time

        performance_monitor.record_operation("bulk_recovery", recovery_duration, bulk_result["successful_recoveries"] > 0)

        print(f"Recovery System Performance ({num_jobs} jobs):")
        print(".3f")
        print(f"  Successful Recoveries: {bulk_result['successful_recoveries']}")
        print(f"  Failed Recoveries: {bulk_result['failed_recoveries']}")
        print(".2f")

        # Performance assertions
        assert bulk_result["successful_recoveries"] >= bulk_result["failed_recoveries"], "Most recoveries should succeed"
        assert recovery_duration < 10.0, "Bulk recovery should complete within 10 seconds"

    def test_memory_leak_detection(self, temp_jobs_dir, performance_monitor):
        """Test for memory leaks during extended operation."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024

        # Perform memory-intensive operations
        for cycle in range(10):
            # Create jobs
            dir_manager = JobDirectoryManager(temp_jobs_dir)
            for i in range(5):
                job_id = f"memory_test_job_{cycle}_{i}"
                config = {"objective": f"Memory test job {cycle}-{i}"}
                dir_manager.create_job_directory(job_id, config)

            # Perform operations
            observer = LogistObserver()
            large_log = ["Log entry " + str(i) for i in range(1000)]
            analysis = observer.analyze_log_segment(large_log)

            recovery_manager = JobRecoveryManager(temp_jobs_dir)
            status = recovery_manager.get_recovery_status_report()

            # Record memory usage
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024
            performance_monitor.record_resource_usage()

            # Clean up cycle jobs
            for i in range(5):
                job_id = f"memory_test_job_{cycle}_{i}"
                try:
                    dir_manager.cleanup_job_directory(job_id, force=True)
                except:
                    pass  # Ignore cleanup errors in test

        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory

        resource_summary = performance_monitor.get_summary()

        print(f"Memory Leak Detection:")
        print(".1f")
        print(".1f")
        print(".1f")
        print(".1f")

        # Memory leak check - allow some growth but not excessive
        assert memory_growth < 50, "Memory growth should be less than 50MB (possible leak)"
        assert resource_summary["peak_memory_mb"] < 300, "Peak memory should be reasonable"

    def test_system_stress_test(self, temp_jobs_dir, performance_monitor):
        """Comprehensive stress test combining multiple operations."""
        print("Running comprehensive system stress test...")

        # Initialize all components
        job_manager = JobManagerService()
        job_manager.initialize_jobs_dir(temp_jobs_dir)

        engine = LogistEngine()
        engine.initialize_sentinel(temp_jobs_dir)

        dir_manager = JobDirectoryManager(temp_jobs_dir)
        recovery_manager = JobRecoveryManager(temp_jobs_dir)
        observer = LogistObserver()

        stress_start = time.time()

        # Phase 1: Create many jobs concurrently
        num_jobs = 20
        job_ids = []

        def create_and_setup_job(i):
            job_id = f"stress_test_job_{i}"
            config = {"objective": f"Stress test job {i}", "prompt": f"Execute operation {i}"}
            dir_manager.create_job_directory(job_id, config)

            job_dir = dir_manager.get_job_directory(job_id)
            with open(os.path.join(job_dir, "prompt.md"), 'w') as f:
                f.write(f"# Stress Test Job {i}\n\nExecute stress test operation {i}.")

            job_manager.activate_job(job_id, temp_jobs_dir)
            return job_id

        # Create jobs concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_and_setup_job, i) for i in range(num_jobs)]
            job_ids = [future.result() for future in as_completed(futures)]

        # Phase 2: Execute jobs with monitoring
        engine.start_job_monitoring()

        def execute_stress_job(job_id):
            try:
                job_dir = dir_manager.get_job_directory(job_id)

                with patch('logist.core_engine.execute_llm_with_cline') as mock_execute:
                    mock_execute.return_value = ({
                        "action": "COMPLETED",
                        "summary_for_supervisor": f"Stress test {job_id} completed",
                        "evidence_files": [],
                        "metrics": {"cost_usd": 0.01, "token_input": 30, "token_output": 15}
                    }, 0.8)

                    ctx = MagicMock()
                    ctx.obj = {
                        "JOBS_DIR": temp_jobs_dir,
                        "DEBUG": False,
                        "ENHANCE": False,
                        "ENGINE": engine
                    }

                    success = engine.step_job(ctx, job_id, job_dir)
                    return success

            except Exception as e:
                print(f"Error executing stress job {job_id}: {e}")
                return False

        # Execute jobs concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(execute_stress_job, job_id) for job_id in job_ids]
            results = [future.result() for future in as_completed(futures)]

        engine.stop_job_monitoring()

        # Phase 3: Recovery and cleanup
        successful_executions = sum(1 for r in results if r)

        # Test recovery on any failed jobs
        failed_jobs = [job_id for job_id, success in zip(job_ids, results) if not success]
        if failed_jobs:
            recovery_result = recovery_manager.perform_bulk_recovery(failed_jobs, force=True)
            recovered = recovery_result["successful_recoveries"]
        else:
            recovered = 0

        # Cleanup all jobs
        for job_id in job_ids:
            try:
                dir_manager.cleanup_job_directory(job_id, force=True)
            except:
                pass  # Ignore cleanup errors

        total_time = time.time() - stress_start
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024

        print(f"System Stress Test Results ({num_jobs} jobs):")
        print(".2f")
        print(f"  Successful Executions: {successful_executions}/{num_jobs}")
        print(f"  Recovered Jobs: {recovered}")
        print(".1f")
        print(".1f")
        print(".1f")

        # Success criteria
        assert successful_executions >= num_jobs * 0.9, "At least 90% of jobs should execute successfully"
        assert total_time < 60, "Stress test should complete within 60 seconds"
        assert final_memory < 500, "Memory usage should remain reasonable"

        print("✅ System stress test completed successfully!")


# Performance testing utilities
@contextmanager
def performance_timer(operation_name: str, metrics: PerformanceMetrics):
    """Context manager for timing operations."""
    start_time = time.time()
    try:
        yield
        duration = time.time() - start_time
        metrics.record_operation(operation_name, duration, True)
    except Exception as e:
        duration = time.time() - start_time
        metrics.record_operation(operation_name, duration, False)
        metrics.record_error(operation_name, str(e))
        raise


def benchmark_operation(func, iterations: int = 100, *args, **kwargs) -> Dict[str, Any]:
    """Benchmark a function over multiple iterations."""
    times = []

    for _ in range(iterations):
        start_time = time.time()
        func(*args, **kwargs)
        times.append(time.time() - start_time)

    return {
        "iterations": iterations,
        "total_time": sum(times),
        "average_time": sum(times) / len(times),
        "min_time": min(times),
        "max_time": max(times),
        "operations_per_second": len(times) / sum(times)
    }


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s"])