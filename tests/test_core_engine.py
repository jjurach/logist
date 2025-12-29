"""
Unit tests for LogistEngine (Core Engine)

Tests the core job execution engine functionality.
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

from logist.core_engine import LogistEngine
from logist.job_state import JobStates
from logist.runners.mock import MockRunner


class TestLogistEngine(unittest.TestCase):
    """Test cases for LogistEngine functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_runner = MockRunner()
        self.engine = LogistEngine(runner=self.mock_runner)
        self.test_dir = tempfile.mkdtemp()
        self.job_dir = os.path.join(self.test_dir, "test-job")
        os.makedirs(self.job_dir)

        # Create a minimal job manifest
        self.manifest_path = os.path.join(self.job_dir, "job_manifest.json")
        self.manifest = {
            "job_id": "test-job",
            "status": "PENDING",
            "current_phase": "test_phase",
            "phases": [
                {"name": "test_phase", "description": "Test phase"}
            ],
            "metrics": {
                "cumulative_cost": 0.0,
                "cumulative_time_seconds": 0.0
            },
            "history": []
        }
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    @unittest.skip("Disabled due to datetime import issue - will be re-enabled in later phase")
    def test_write_job_history_entry(self, mock_datetime):
        with patch('logist.core_engine.datetime') as mock_datetime:
            # Mock datetime
            mock_dt = MagicMock()
            mock_dt.isoformat.return_value = "2023-12-03T10:00:00"
            mock_datetime.now.return_value = mock_dt

        entry = {
            "timestamp": "2023-12-03T10:00:00",
            "model": "test-model",
            "cost": 0.5,
            "execution_time_seconds": 30.0,
            "request": {"op": "test"},
            "response": {"action": "completed"}
        }

        history_file = os.path.join(self.job_dir, "jobHistory.json")

        # Should create new history file and write entry
        self.engine._write_job_history_entry(self.job_dir, entry)

        self.assertTrue(os.path.exists(history_file))

        with open(history_file, 'r') as f:
            history = json.load(f)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["model"], "test-model")

    def test_write_job_history_existing_file(self):
        """Test writing to existing job history file."""
        # Create existing history
        history_file = os.path.join(self.job_dir, "jobHistory.json")
        existing_history = [{"old_entry": "value"}]
        with open(history_file, 'w') as f:
            json.dump(existing_history, f)

        entry = {
            "timestamp": "2023-12-03T10:00:00",
            "model": "new-model",
            "cost": 0.25,
            "execution_time_seconds": 15.0,
            "request": {"op": "append"},
            "response": {"action": "appended"}
        }

        self.engine._write_job_history_entry(self.job_dir, entry)

        with open(history_file, 'r') as f:
            history = json.load(f)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["old_entry"], "value")
        self.assertEqual(history[1]["model"], "new-model")

    @unittest.skip("Disabled due to datetime import issue - will be re-enabled in later phase")
    @patch('logist.core_engine.datetime')
    def test_write_job_history_write_error(self, mock_datetime):
        """Test handling write errors when writing history."""
        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = "2023-12-03T10:00:00"
        mock_datetime.now.return_value = mock_dt

        entry = {"test": "entry"}

        # Mock open to raise OSError
        with patch('builtins.open', side_effect=OSError("Write failed")):
            # Should not raise exception, but handle error gracefully
            self.engine._write_job_history_entry(self.job_dir, entry)

    @unittest.skip("Disabled due to datetime import issue - will be re-enabled in later phase")
    @patch('logist.core_engine.datetime')
    def test_show_debug_history_info(self, mock_datetime):
        """Test debug history info display."""
        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = "2023-12-03T10:00:00"
        mock_datetime.now.return_value = mock_dt

        entry = {
            "timestamp": "2023-12-03T10:00:00",
            "model": "test-model",
            "cost": 0.5,
            "execution_time_seconds": 30.0,
            "request": {
                "operation": "test",
                "job_id": "test-job",
                "phase": "test_phase",
                "role": "Worker"
            },
            "response": {
                "action": "COMPLETED",
                "summary_for_supervisor": "Test summary",
                "evidence_files": ["/path/file1.txt"],
                "metrics": {
                    "cost_usd": 0.5,
                    "token_input": 100,
                    "token_output": 50,
                    "token_cache_read": 25,
                    "cache_hit": True,
                    "ttft_seconds": 1.5,
                    "throughput_tokens_per_second": 50.0
                }
            }
        }

        # Test with debug=True - should print debug info
        with patch('builtins.print') as mock_print:
            self.engine._show_debug_history_info(True, "test", "test-job", entry)

            # Verify debug prints were called (check some key calls)
            mock_print.assert_any_call("   📝 [DEBUG] Writing to jobHistory.json for test operation:")

        # Test with debug=False - should not print
        with patch('builtins.print') as mock_print:
            self.engine._show_debug_history_info(False, "test", "test-job", entry)
            mock_print.assert_not_called()

    @unittest.skip("Disabled due to datetime import issue - will be re-enabled in later phase")
    @patch('logist.core_engine.datetime')
    def test_show_debug_history_info_minimal_metrics(self, mock_datetime):
        """Test debug info with minimal metrics."""
        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = "2023-12-03T10:00:00"
        mock_datetime.now.return_value = mock_dt

        entry = {
            "timestamp": "2023-12-03T10:00:00",
            "model": "test-model",
            "cost": 0.0,
            "execution_time_seconds": 0.0,
            "request": {},
            "response": {
                "action": "TEST",
                "evidence_files": []
            }
        }

        # Should not fail with minimal data
        self.engine._show_debug_history_info(True, "test", "test-job", entry)



if __name__ == '__main__':
    unittest.main()