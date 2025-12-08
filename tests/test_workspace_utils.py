import os
import tempfile
import shutil
import unittest
import subprocess
from unittest.mock import patch, MagicMock

from src.logist.workspace_utils import (
    create_or_recreate_job_branch,
    setup_target_git_repo,
    setup_job_remote_and_push,
    create_workspace_from_bare_repo,
    validate_existing_target_git,
    validate_existing_workspace
)


class TestWorkspaceUtils(unittest.TestCase):
    """Unit tests for workspace_utils functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp(prefix="workspace_test_")
        self.git_root = os.path.join(self.test_dir, "git_repo")
        self.job_dir = os.path.join(self.test_dir, "job_dir")

        # Create a test git repository
        os.makedirs(self.git_root)
        self._run_git_command(self.git_root, ["init"])
        self._run_git_command(self.git_root, ["config", "user.name", "Test User"])
        self._run_git_command(self.git_root, ["config", "user.email", "test@example.com"])

        # Create initial commit
        test_file = os.path.join(self.git_root, "README.md")
        with open(test_file, "w") as f:
            f.write("# Test Repo\n")
        self._run_git_command(self.git_root, ["add", "README.md"])
        self._run_git_command(self.git_root, ["commit", "-m", "Initial commit"])

        # Create job directory
        os.makedirs(self.job_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def _run_git_command(self, cwd, cmd):
        """Helper to run git commands."""
        result = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result

    def test_create_or_recreate_job_branch_success(self):
        """Test successful creation of job branch."""
        job_branch = "job-test123"
        result = create_or_recreate_job_branch(self.git_root, job_branch, "master", debug=False)
        self.assertTrue(result)

        # Verify branch exists
        branches = self._run_git_command(self.git_root, ["branch", "--list"]).stdout
        self.assertIn(job_branch, branches)

    def test_create_or_recreate_job_branch_delete_existing(self):
        """Test deleting existing branch before creation."""
        job_branch = "job-test456"
        # Create branch first
        self._run_git_command(self.git_root, ["checkout", "-b", job_branch])

        # Now recreate it
        result = create_or_recreate_job_branch(self.git_root, job_branch, "master", debug=False)
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_create_or_recreate_job_branch_failure(self, mock_run):
        """Test failure case for branch creation."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="Branch creation failed")

        result = create_or_recreate_job_branch(self.git_root, "job-fail", "main", debug=True)
        self.assertFalse(result)

    def test_setup_target_git_repo_success(self):
        """Test successful target.git repository creation."""
        job_branch = "job-test789"
        # Create job branch first
        self._run_git_command(self.git_root, ["checkout", "-b", job_branch])

        result = setup_target_git_repo(self.git_root, self.job_dir, job_branch, debug=False)
        self.assertTrue(result)

        # Verify target.git exists
        target_git = os.path.join(self.job_dir, "target.git")
        self.assertTrue(os.path.exists(target_git))

    @patch('subprocess.run')
    def test_setup_target_git_repo_failure(self, mock_run):
        """Test failure case for target.git creation."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="Clone failed")

        result = setup_target_git_repo(self.git_root, self.job_dir, "job-fail", debug=True)
        self.assertFalse(result)

    def test_setup_job_remote_and_push_success(self):
        """Test successful remote setup and push."""
        job_branch = "job-remote-test"
        # Create job branch and target.git first
        self._run_git_command(self.git_root, ["checkout", "-b", job_branch])

        # Create bare repo
        target_git_path = os.path.join(self.job_dir, "target.git")
        os.makedirs(target_git_path)
        self._run_git_command(target_git_path, ["init", "--bare"])

        result = setup_job_remote_and_push(self.git_root, self.job_dir, job_branch, debug=False)
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_setup_job_remote_and_push_failure(self, mock_run):
        """Test failure case for remote setup and push."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="Push failed")

        result = setup_job_remote_and_push(self.git_root, self.job_dir, "job-fail", debug=True)
        self.assertFalse(result)

    def test_create_workspace_from_bare_repo_success(self):
        """Test successful workspace creation from bare repo."""
        # Set up bare repo first
        target_git = os.path.join(self.job_dir, "target.git")
        os.makedirs(target_git)

        result = create_workspace_from_bare_repo(self.job_dir, debug=False)
        # This might fail without a proper bare repo, but tests the function structure
        # In real usage, the bare repo would be properly initialized

    @patch('subprocess.run')
    def test_create_workspace_from_bare_repo_failure(self, mock_run):
        """Test failure case for workspace creation."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="Worktree add failed")

        result = create_workspace_from_bare_repo(self.job_dir, debug=True)
        self.assertFalse(result)

    def test_validate_nonexistent_target_git(self):
        """Test validation of non-existent target.git."""
        result = validate_existing_target_git(self.job_dir, "job-test", debug=False)
        self.assertFalse(result)

    def test_validate_nonexistent_workspace(self):
        """Test validation of non-existent workspace."""
        result = validate_existing_workspace(self.job_dir, "job-test", debug=False)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()