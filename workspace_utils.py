import os
import subprocess
from typing import List, Dict, Any

def find_git_root(cwd=None):
    """Find the root directory of the Git repository from the current working directory."""
    if cwd is None:
        cwd = os.getcwd()

    original = cwd
    while cwd != os.path.dirname(cwd):
        if os.path.isdir(os.path.join(cwd, '.git')):
            return cwd
        cwd = os.path.dirname(cwd)

    return None

def verify_workspace_exists(job_dir: str) -> bool:
    """Verifies if the isolated workspace directory exists and is a git repository."""
    workspace_dir = os.path.join(job_dir, "workspace")
    workspace_git_dir = os.path.join(workspace_dir, ".git")
    
    if not os.path.isdir(workspace_dir):
        return False
    
    if not os.path.isdir(workspace_git_dir):
        return False
        
    return True

def get_workspace_files_summary(job_dir: str) -> Dict[str, Any]:
    """
    Generates a summary of files within the workspace, including a tree structure
    and content of key files.
    """
    workspace_dir = os.path.join(job_dir, "workspace")
    summary = {
        "tree": [],
        "important_files": {}
    }

    if not verify_workspace_exists(job_dir):
        return summary

    # Get file tree
    for root, dirs, files in os.walk(workspace_dir):
        relative_root = os.path.relpath(root, workspace_dir)
        if relative_root == ".":
            relative_root = "" # Root directory itself
        
        # Filter out .git directory
        if ".git" in dirs:
            dirs.remove(".git")

        for d in dirs:
            summary["tree"].append(os.path.join(relative_root, d) + "/")
        for f in files:
            summary["tree"].append(os.path.join(relative_root, f))
            
    # Read content of some important files (e.g., source code, config files)
    # This is a basic example; more sophisticated logic could be added
    files_to_read = ["README.md", "pyproject.toml", "requirements.txt", "logist/cli.py"] # Example files
    for f_name in files_to_read:
        file_path = os.path.join(workspace_dir, f_name)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    summary["important_files"][f_name] = f.read()
            except Exception as e:
                summary["important_files"][f_name] = f"Could not read file: {e}"

    return summary

def get_workspace_git_status(job_dir: str) -> Dict[str, Any]:
    """
    Retrieves the Git status (staged, unstaged, untracked, recent commits)
    of the workspace.
    """
    workspace_dir = os.path.join(job_dir, "workspace")
    git_status = {
        "is_git_repo": False,
        "current_branch": None,
        "staged_changes": [],
        "unstaged_changes": [],
        "untracked_files": [],
        "recent_commits": []
    }

    if not verify_workspace_exists(job_dir):
        return git_status

    git_status["is_git_repo"] = True

    try:
        # Current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )
        git_status["current_branch"] = result.stdout.strip()

        # Staged, unstaged, untracked
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            status = line[0:2]
            file = line[3:]
            if status.startswith("M") or status.startswith("A") or status.startswith("D"): # Staged
                git_status["staged_changes"].append(file)
            elif status.startswith(" M") or status.startswith("D"): # Unstaged
                git_status["unstaged_changes"].append(file)
            elif status.startswith("??"): # Untracked
                git_status["untracked_files"].append(file)

        # Recent commits
        result = subprocess.run(
            ["git", "log", "-5", "--pretty=format:%h - %an, %ar : %s"], # Last 5 commits
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )
        git_status["recent_commits"] = result.stdout.splitlines()

    except subprocess.CalledProcessError as e:
        # Not a git repo or other git error, which should already be caught by verify_workspace_exists
        pass
    except Exception as e:
        # General error
        pass

    return git_status


def perform_git_commit(
    job_dir: str,
    evidence_files: List[str],
    summary: str,
    author_info: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Performs a Git commit in the workspace with evidence files and summary.

    Args:
        job_dir: The absolute path to the job's directory.
        evidence_files: List of evidence files to stage.
        summary: Summary text for the commit message.
        author_info: Optional dict with 'name' and 'email' for commit author.

    Returns:
        Dictionary with commit information and status.

    Raises:
        Exception: If Git operations fail.
    """
    import subprocess
    from datetime import datetime

    workspace_dir = os.path.join(job_dir, "workspace")
    result = {
        "success": False,
        "commit_hash": None,
        "timestamp": datetime.now().isoformat(),
        "files_committed": [],
        "error": None
    }

    if not verify_workspace_exists(job_dir):
        result["error"] = "Workspace not initialized"
        return result

    try:
        # Check for changes first
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )

        if not status_result.stdout.strip():
            result["error"] = "No changes to commit"
            return result

        # Stage evidence files first
        if evidence_files:
            for file in evidence_files:
                try:
                    # Use git add --intent-to-add to track files that may not exist yet
                    subprocess.run(
                        ["git", "add", file],
                        cwd=workspace_dir,
                        capture_output=True,
                        text=True,
                        check=False  # Don't fail if file doesn't exist
                    )
                except subprocess.CalledProcessError:
                    pass  # Continue with other files

        # Stage any remaining changes
        subprocess.run(
            ["git", "add", "."],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )

        # Prepare commit message
        commit_message = f"feat: job execution - {summary}"

        # Add author info if provided
        env = os.environ.copy()
        if author_info:
            if "name" in author_info:
                env["GIT_AUTHOR_NAME"] = author_info["name"]
                env["GIT_COMMITTER_NAME"] = author_info["name"]
            if "email" in author_info:
                env["GIT_AUTHOR_EMAIL"] = author_info["email"]
                env["GIT_COMMITTER_EMAIL"] = author_info["email"]

        # Commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=workspace_dir,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )

        # Get the commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )

        result["success"] = True
        result["commit_hash"] = hash_result.stdout.strip()

        # Try to get list of committed files
        try:
            show_result = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                check=True
            )
            files = [line.strip() for line in show_result.stdout.split('\n') if line.strip()]
            result["files_committed"] = files
        except subprocess.CalledProcessError:
            pass  # Optional, don't fail if we can't get file list

    except subprocess.CalledProcessError as e:
        result["error"] = f"Git command failed: {e.stderr}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"

    return result