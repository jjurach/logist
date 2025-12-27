"""
Unit tests for workspace_utils.py

Tests workspace utility functions in isolation to ensure they work correctly
without interfering with concurrency tests.
"""

import os
import json
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from logist import workspace_utils


class TestWorkspaceUtils:
    """Unit tests for workspace utility functions."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp(prefix="workspace_utils_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def git_repo_dir(self, temp_dir):
        """Create a mock git repository directory."""
        git_dir = os.path.join(temp_dir, "repo")
        os.makedirs(git_dir)
        # Create .git directory to simulate a git repo
        git_subdir = os.path.join(git_dir, ".git")
        os.makedirs(git_subdir)
        return git_dir

    def test_find_git_root_found(self, temp_dir, git_repo_dir):
        """Test find_git_root when .git directory exists."""
        # Change to a subdirectory of the git repo
        subdir = os.path.join(git_repo_dir, "subdir")
        os.makedirs(subdir)

        with patch('os.getcwd', return_value=subdir):
            result = workspace_utils.find_git_root()
            assert result == git_repo_dir

    def test_find_git_root_not_found(self, temp_dir):
        """Test find_git_root when no .git directory exists."""
        regular_dir = os.path.join(temp_dir, "regular")
        os.makedirs(regular_dir)

        with patch('os.getcwd', return_value=regular_dir):
            result = workspace_utils.find_git_root()
            assert result is None

    @patch('subprocess.run')
    def test_create_or_recreate_job_branch_success(self, mock_run, git_repo_dir):
        """Test successful branch creation."""
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")

        result = workspace_utils.create_or_recreate_job_branch(
            git_repo_dir, "job-test", "main", debug=False
        )
        assert result is True

        # Verify git commands were called
        assert mock_run.call_count >= 2  # At least checkout and create

    @patch('subprocess.run')
    def test_create_or_recreate_job_branch_failure(self, mock_run, git_repo_dir):
        """Test branch creation failure."""
        mock_run.side_effect = Exception("Git command failed")

        result = workspace_utils.create_or_recreate_job_branch(
            git_repo_dir, "job-test", "main", debug=False
        )
        assert result is False

    @patch('subprocess.run')
    def test_setup_target_git_repo_success(self, mock_run, temp_dir, git_repo_dir):
        """Test successful target git repo setup."""
        job_dir = os.path.join(temp_dir, "job")
        os.makedirs(job_dir)

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = workspace_utils.setup_target_git_repo(
            git_repo_dir, job_dir, "job-branch", debug=False
        )
        assert result is True

        # Verify git clone command was called
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert "git" in args[0]
        assert "clone" in args[0]
        assert "--bare" in args[0]

    @patch('subprocess.run')
    def test_setup_target_git_repo_failure(self, mock_run, temp_dir, git_repo_dir):
        """Test target git repo setup failure."""
        job_dir = os.path.join(temp_dir, "job")
        os.makedirs(job_dir)

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Clone failed")

        result = workspace_utils.setup_target_git_repo(
            git_repo_dir, job_dir, "job-branch", debug=False
        )
        assert result is False

    def test_verify_workspace_exists_true(self, temp_dir):
        """Test workspace verification when all components exist."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")
        target_git_dir = os.path.join(job_dir, "target.git")
        workspace_git_link = os.path.join(workspace_dir, ".git")

        # Create directory structure
        os.makedirs(workspace_dir)
        os.makedirs(target_git_dir)

        # Create symlink
        os.symlink("../target.git", workspace_git_link)

        result = workspace_utils.verify_workspace_exists(job_dir)
        assert result is True

    def test_verify_workspace_exists_false_missing_workspace(self, temp_dir):
        """Test workspace verification when workspace directory doesn't exist."""
        job_dir = os.path.join(temp_dir, "job")

        result = workspace_utils.verify_workspace_exists(job_dir)
        assert result is False

    def test_verify_workspace_exists_false_missing_target_git(self, temp_dir):
        """Test workspace verification when target.git doesn't exist."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")

        os.makedirs(workspace_dir)

        result = workspace_utils.verify_workspace_exists(job_dir)
        assert result is False

    def test_verify_workspace_exists_false_bad_symlink(self, temp_dir):
        """Test workspace verification when .git symlink is incorrect."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")
        target_git_dir = os.path.join(job_dir, "target.git")
        workspace_git_link = os.path.join(workspace_dir, ".git")

        # Create directory structure
        os.makedirs(workspace_dir)
        os.makedirs(target_git_dir)

        # Create incorrect symlink
        os.symlink("../wrong.git", workspace_git_link)

        result = workspace_utils.verify_workspace_exists(job_dir)
        assert result is False

    @patch('subprocess.run')
    def test_validate_existing_target_git_success(self, mock_run, temp_dir):
        """Test target git validation success."""
        job_dir = os.path.join(temp_dir, "job")
        target_git_dir = os.path.join(job_dir, "target.git")
        os.makedirs(target_git_dir)

        mock_run.return_value = MagicMock(returncode=0, stdout="true", stderr="")

        result = workspace_utils.validate_existing_target_git(
            job_dir, "job-branch", debug=False
        )
        assert result is True

    @patch('subprocess.run')
    def test_validate_existing_target_git_failure(self, mock_run, temp_dir):
        """Test target git validation failure."""
        job_dir = os.path.join(temp_dir, "job")

        # Directory doesn't exist
        result = workspace_utils.validate_existing_target_git(
            job_dir, "job-branch", debug=False
        )
        assert result is False

    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_validate_existing_workspace_success(self, mock_exists, mock_run, temp_dir):
        """Test workspace validation success."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")

        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="job-branch\n", stderr="")

        result = workspace_utils.validate_existing_workspace(
            job_dir, "job-branch", debug=False
        )
        assert result is True

    @patch('os.path.exists')
    def test_validate_existing_workspace_missing_dir(self, mock_exists, temp_dir):
        """Test workspace validation when directory doesn't exist."""
        job_dir = os.path.join(temp_dir, "job")

        mock_exists.return_value = False

        result = workspace_utils.validate_existing_workspace(
            job_dir, "job-branch", debug=False
        )
        assert result is False

    @patch('workspace_utils.verify_workspace_exists')
    def test_get_workspace_files_summary_exists(self, mock_verify, temp_dir):
        """Test getting workspace files summary when workspace exists."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")

        # Create workspace structure
        os.makedirs(workspace_dir)
        test_file = os.path.join(workspace_dir, "test.py")
        with open(test_file, 'w') as f:
            f.write("print('test')")

        mock_verify.return_value = True

        result = workspace_utils.get_workspace_files_summary(job_dir)

        assert "tree" in result
        assert "important_files" in result
        assert len(result["tree"]) > 0
        assert "test.py" in result["tree"]

    @patch('workspace_utils.verify_workspace_exists')
    def test_get_workspace_files_summary_not_exists(self, mock_verify, temp_dir):
        """Test getting workspace files summary when workspace doesn't exist."""
        job_dir = os.path.join(temp_dir, "job")

        mock_verify.return_value = False

        result = workspace_utils.get_workspace_files_summary(job_dir)

        assert result["tree"] == []
        assert result["important_files"] == {}

    @patch('workspace_utils.verify_workspace_exists')
    def test_get_workspace_git_status_exists(self, mock_verify, temp_dir):
        """Test getting workspace git status when workspace exists."""
        job_dir = os.path.join(temp_dir, "job")

        mock_verify.return_value = True

        result = workspace_utils.get_workspace_git_status(job_dir)

        assert "is_git_repo" in result
        assert "current_branch" in result
        assert "staged_changes" in result
        assert "unstaged_changes" in result
        assert "untracked_files" in result
        assert "recent_commits" in result

    @patch('workspace_utils.verify_workspace_exists')
    def test_get_workspace_git_status_not_exists(self, mock_verify, temp_dir):
        """Test getting workspace git status when workspace doesn't exist."""
        job_dir = os.path.join(temp_dir, "job")

        mock_verify.return_value = False

        result = workspace_utils.get_workspace_git_status(job_dir)

        assert result["is_git_repo"] is False
        assert result["current_branch"] is None
        assert result["has_changes"] is False

    def test_discover_file_arguments_with_prompt(self, temp_dir):
        """Test discovering file arguments from prompt content."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")
        prompt_file = os.path.join(job_dir, "prompt.md")

        # Create workspace and files
        os.makedirs(workspace_dir)
        test_file = os.path.join(workspace_dir, "script.py")
        with open(test_file, 'w') as f:
            f.write("print('hello')")

        # Create prompt that references the file
        with open(prompt_file, 'w') as f:
            f.write("Please run script.py to execute the code.")

        result = workspace_utils.discover_file_arguments(job_dir, prompt_file)

        assert len(result) > 0
        assert test_file in result

    def test_discover_file_arguments_no_prompt(self, temp_dir):
        """Test discovering file arguments without specific prompt file."""
        job_dir = os.path.join(temp_dir, "job")

        result = workspace_utils.discover_file_arguments(job_dir)

        # Should return empty list when no prompt or workspace exists
        assert isinstance(result, list)

    def test_collect_attachment_files_exists(self, temp_dir):
        """Test collecting attachment files when attachments directory exists."""
        job_dir = os.path.join(temp_dir, "job")
        attachments_dir = os.path.join(job_dir, "attachments")

        os.makedirs(attachments_dir)
        attachment_file = os.path.join(attachments_dir, "data.json")
        with open(attachment_file, 'w') as f:
            f.write('{"test": "data"}')

        result = workspace_utils.collect_attachment_files(job_dir)

        assert len(result) == 1
        assert attachment_file in result

    def test_collect_attachment_files_not_exists(self, temp_dir):
        """Test collecting attachment files when attachments directory doesn't exist."""
        job_dir = os.path.join(temp_dir, "job")

        result = workspace_utils.collect_attachment_files(job_dir)

        assert result == []

    @patch('workspace_utils.verify_workspace_exists')
    @patch('workspace_utils.setup_isolated_workspace')
    def test_setup_isolated_workspace_success(self, mock_setup, mock_verify, temp_dir):
        """Test successful isolated workspace setup."""
        job_dir = os.path.join(temp_dir, "job")

        mock_verify.return_value = False  # Workspace doesn't exist initially
        mock_setup.return_value = {"success": True}

        result = workspace_utils.setup_isolated_workspace("test-job", job_dir)

        assert result["success"] is True
        assert result["workspace_prepared"] is True
        assert result["target_repo_created"] is True

    @patch('workspace_utils.verify_workspace_exists')
    @patch('workspace_utils.validate_existing_target_git')
    @patch('workspace_utils.validate_existing_workspace')
    def test_setup_isolated_workspace_reuse_existing(self, mock_validate_ws, mock_validate_git, mock_verify, temp_dir):
        """Test reusing existing valid workspace setup."""
        job_dir = os.path.join(temp_dir, "job")

        mock_validate_git.return_value = True
        mock_validate_ws.return_value = True
        mock_verify.return_value = True

        result = workspace_utils.setup_isolated_workspace("test-job", job_dir)

        assert result["success"] is True
        assert result["workspace_prepared"] is True
        assert result["target_repo_created"] is True

    @patch('workspace_utils.find_git_root')
    def test_setup_isolated_workspace_no_git_repo(self, mock_find_git, temp_dir):
        """Test workspace setup when not in a git repository."""
        job_dir = os.path.join(temp_dir, "job")

        mock_find_git.return_value = None

        result = workspace_utils.setup_isolated_workspace("test-job", job_dir)

        assert result["success"] is False
        assert "Not in a Git repository" in result["error"]

    @patch('workspace_utils.verify_workspace_exists')
    def test_get_workspace_lifecycle_status_exists(self, mock_verify, temp_dir):
        """Test getting workspace lifecycle status when workspace exists."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")

        os.makedirs(workspace_dir)
        # Set directory modification time
        os.utime(workspace_dir, (0, 1000000))  # Set mtime to a fixed value

        mock_verify.return_value = True

        result = workspace_utils.get_workspace_lifecycle_status(job_dir)

        assert result["workspace_exists"] is True
        assert result["last_modified"] is not None

    @patch('workspace_utils.verify_workspace_exists')
    def test_get_workspace_lifecycle_status_not_exists(self, mock_verify, temp_dir):
        """Test getting workspace lifecycle status when workspace doesn't exist."""
        job_dir = os.path.join(temp_dir, "job")

        mock_verify.return_value = False

        result = workspace_utils.get_workspace_lifecycle_status(job_dir)

        assert result["workspace_exists"] is False
        assert result["current_branch"] is None
        assert result["job_status"] is None

    def test_should_cleanup_workspace_completed_job(self, temp_dir):
        """Test cleanup decision for completed jobs."""
        job_dir = os.path.join(temp_dir, "job")
        os.makedirs(job_dir)

        # Create mock manifest
        manifest = {"status": "SUCCESS"}
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        should_cleanup, reason = workspace_utils.should_cleanup_workspace(job_dir)

        assert should_cleanup is True
        assert "completed successfully" in reason

    def test_should_cleanup_workspace_active_job(self, temp_dir):
        """Test cleanup decision for active jobs."""
        job_dir = os.path.join(temp_dir, "job")
        os.makedirs(job_dir)

        # Create mock manifest
        manifest = {"status": "RUNNING"}
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        should_cleanup, reason = workspace_utils.should_cleanup_workspace(job_dir)

        assert should_cleanup is False
        assert "still active" in reason

    def test_should_cleanup_workspace_failed_job_preserve(self, temp_dir):
        """Test cleanup decision for failed jobs when preserve_failed_jobs is enabled."""
        job_dir = os.path.join(temp_dir, "job")
        os.makedirs(job_dir)

        # Create mock manifest
        manifest = {"status": "FAILED"}
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        should_cleanup, reason = workspace_utils.should_cleanup_workspace(job_dir)

        assert should_cleanup is False
        assert "Preserving failed job" in reason

    def test_should_cleanup_workspace_cancelled_recent(self, temp_dir):
        """Test cleanup decision for recently cancelled jobs."""
        job_dir = os.path.join(temp_dir, "job")
        workspace_dir = os.path.join(job_dir, "workspace")
        os.makedirs(workspace_dir)

        # Set recent modification time
        recent_time = workspace_utils.datetime.now() - workspace_utils.timedelta(hours=1)
        os.utime(workspace_dir, (recent_time.timestamp(), recent_time.timestamp()))

        # Create mock manifest
        manifest = {"status": "CANCELED"}
        manifest_path = os.path.join(job_dir, "job_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        should_cleanup, reason = workspace_utils.should_cleanup_workspace(job_dir)

        assert should_cleanup is False
        assert "Within grace period" in reason