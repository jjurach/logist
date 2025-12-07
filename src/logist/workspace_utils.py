import os
import shutil
import subprocess
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

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
    target_git_dir = os.path.join(job_dir, "target.git")
    workspace_git_link = os.path.join(workspace_dir, ".git")

    if not os.path.isdir(workspace_dir):
        return False

    # Check for target.git directory (bare repo)
    if not os.path.isdir(target_git_dir):
        return False

    # Check for symlinked .git pointing to target.git
    if not (os.path.islink(workspace_git_link) and
            os.readlink(workspace_git_link) == "../target.git"):
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
        # Set up environment for git commands with symlinked repo
        env = os.environ.copy()
        env["GIT_DIR"] = os.path.join(job_dir, "target.git")
        env["GIT_WORK_TREE"] = workspace_dir

        # Current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace_dir,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        git_status["current_branch"] = result.stdout.strip()

        # Staged, unstaged, untracked
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_dir,
            env=env,
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
            env=env,
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
        # Set up environment for git commands with symlinked repo
        env = os.environ.copy()
        env["GIT_DIR"] = os.path.join(job_dir, "target.git")
        env["GIT_WORK_TREE"] = workspace_dir

        # Add author info if provided
        if author_info:
            if "name" in author_info:
                env["GIT_AUTHOR_NAME"] = author_info["name"]
                env["GIT_COMMITTER_NAME"] = author_info["name"]
            if "email" in author_info:
                env["GIT_AUTHOR_EMAIL"] = author_info["email"]
                env["GIT_COMMITTER_EMAIL"] = author_info["email"]

        # Check for changes first
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_dir,
            env=env,
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
                        env=env,
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
            env=env,
            capture_output=True,
            text=True,
            check=True
        )

        # Prepare commit message
        commit_message = f"feat: job execution - {summary}"

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
            env=env,
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
                env=env,
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





def setup_isolated_workspace(job_id: str, job_dir: str, base_branch: str = "main") -> Dict[str, Any]:
    """
    Sets up workspace by creating job branch and worktree with symlinked .git.

    Creates job-specific branch in main repo, clones to target.git, and sets up
    workspace as a git worktree with prepare-python-project.sh execution.

    Args:
        job_id: Unique job identifier
        job_dir: Job directory path
        base_branch: Base branch to branch from (default: main)

    Returns:
        Dict with setup status and workspace information
    """
    result = {
        "success": False,
        "workspace_prepared": False,
        "target_repo_created": False,
        "attachments_copied": False,
        "prepare_script_run": False,
        "error": None
    }

    try:
        git_root = find_git_root()
        if git_root is None:
            result["error"] = "Not in a Git repository"
            return result

        # Change to git root directory for all git operations
        original_cwd = os.getcwd()
        os.chdir(git_root)

        workspace_dir = os.path.join(job_dir, "workspace")
        target_git_dir = os.path.join(job_dir, "target.git")
        attachments_dir = os.path.join(job_dir, "attachments")
        job_branch_name = f"job-{job_id}"

        # Always create fresh workspace and target directories for clean state
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)
        if os.path.exists(target_git_dir):
            shutil.rmtree(target_git_dir)

        # 1. Create job-specific branch in main repository (without switching main repo)
        try:
            # Check if branch already exists
            branch_check = subprocess.run(
                ["git", "branch", "--list", job_branch_name],
                cwd=git_root,
                capture_output=True,
                text=True,
                check=True
            )

            if job_branch_name not in branch_check.stdout:
                # Create new branch from base_branch without switching
                subprocess.run(
                    ["git", "branch", job_branch_name, base_branch],
                    cwd=git_root,
                    check=True,
                    capture_output=True,
                    text=True
                )
        except subprocess.CalledProcessError as e:
            result["error"] = f"Failed to create job branch: {e.stderr}"
            return result

        # 2. Clone job branch to target.git as bare repository
        try:
            subprocess.run(
                ["git", "clone", "--bare", "--branch", job_branch_name, git_root, "target.git"],
                cwd=job_dir,
                check=True,
                capture_output=True,
                text=True
            )
            result["target_repo_created"] = True
        except subprocess.CalledProcessError as e:
            result["error"] = f"Failed to clone job branch to target.git: {e.stderr}"
            return result

        # 3. Create workspace directory and set up git worktree
        os.makedirs(workspace_dir, exist_ok=True)

        try:
            # Check if workspace already exists as a worktree and remove it
            worktree_check = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=git_root,
                capture_output=True,
                text=True,
                check=True
            )
            if workspace_dir in worktree_check.stdout:
                # Remove existing worktree if it exists
                subprocess.run(
                    ["git", "worktree", "remove", "--force", workspace_dir],
                    cwd=git_root,
                    capture_output=True,
                    text=True,
                    check=False  # Don't fail if worktree doesn't exist
                )

            # Use git worktree add to create a proper worktree, then adjust .git linkage
            # First, add the worktree
            subprocess.run(
                ["git", "worktree", "add", "--detach", workspace_dir, job_branch_name],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True
            )

            # Now adjust the .git directory to point to our target.git
            workspace_git_link = os.path.join(workspace_dir, ".git")
            if os.path.exists(workspace_git_link):
                # Remove the auto-generated .git file/dir and replace with symlink to target.git
                if os.path.isdir(workspace_git_link):
                    shutil.rmtree(workspace_git_link)
                elif os.path.isfile(workspace_git_link):
                    os.remove(workspace_git_link)
                elif os.path.islink(workspace_git_link):
                    os.remove(workspace_git_link)

            # Create symlink to our target.git
            os.symlink("../target.git", workspace_git_link)

            result["workspace_prepared"] = True
        except (OSError, subprocess.CalledProcessError) as e:
            result["error"] = f"Failed to set up workspace git worktree: {str(e)}"
            return result

        # 4. Run prepare-python-project.sh if it exists
        prepare_script = os.path.join(git_root, "AGENTS", "prepare-python-project.sh")
        if os.path.exists(prepare_script):
            try:
                subprocess.run(
                    [prepare_script],
                    cwd=workspace_dir,
                    check=False,  # Don't fail if prepare script has issues
                    capture_output=True,
                    text=True
                )
                result["prepare_script_run"] = True
            except Exception as e:
                # Prepare script failure shouldn't block workspace creation
                pass

        # 5. Copy attachments if they exist
        if os.path.exists(attachments_dir) and os.listdir(attachments_dir):
            try:
                attachments_dest = os.path.join(workspace_dir, "attachments")
                shutil.copytree(attachments_dir, attachments_dest)
                result["attachments_copied"] = True
            except Exception as e:
                # Attachment copy failure shouldn't block workspace creation
                pass

        result["success"] = True

    except subprocess.CalledProcessError as e:
        result["error"] = f"Git operation failed: {e.stderr}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    finally:
        # Always restore original working directory
        try:
            os.chdir(original_cwd)
        except:
            pass

    return result


def get_workspace_lifecycle_status(job_dir: str) -> Dict[str, Any]:
    """
    Gets comprehensive lifecycle status for a workspace.

    Returns status info needed for cleanup policy decisions.

    Args:
        job_dir: Job directory path

    Returns:
        Dict with workspace lifecycle information
    """
    workspace_dir = os.path.join(job_dir, "workspace")
    status = {
        "workspace_exists": False,
        "current_branch": None,
        "has_changes": False,
        "last_modified": None,
        "job_status": None,
        "ready_for_cleanup": False
    }

    if not os.path.exists(workspace_dir):
        return status

    status["workspace_exists"] = True

    # Get directory modification time
    try:
        status["last_modified"] = datetime.fromtimestamp(os.path.getmtime(workspace_dir))
    except OSError:
        status["last_modified"] = None

    # Check git status
    if verify_workspace_exists(job_dir):
        try:
            # Set up environment for git commands with symlinked repo
            env = os.environ.copy()
            env["GIT_DIR"] = os.path.join(job_dir, "target.git")
            env["GIT_WORK_TREE"] = workspace_dir

            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=workspace_dir,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            status["current_branch"] = branch_result.stdout.strip()

            # Check for uncommitted changes
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace_dir,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            status["has_changes"] = bool(status_result.stdout.strip())

        except subprocess.CalledProcessError:
            pass

    # Check job manifest for job status
    manifest_path = os.path.join(job_dir, "job_manifest.json")
    if os.path.exists(manifest_path):
        try:
            import json
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            status["job_status"] = manifest.get("status")

        except (json.JSONDecodeError, KeyError):
            pass

    return status


def should_cleanup_workspace(job_dir: str, cleanup_policies: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
    """
    Determines if a workspace should be cleaned up based on policies and status.

    Args:
        job_dir: Job directory path
        cleanup_policies: Optional cleanup policy configuration

    Returns:
        Tuple of (should_cleanup, reason)
    """
    if cleanup_policies is None:
        cleanup_policies = {
            "cleanup_completed_jobs": True,
            "cleanup_failed_jobs_after_days": 7,
            "cleanup_cancelled_jobs_after_days": 1,
            "preserve_failed_jobs": True
        }

    status = get_workspace_lifecycle_status(job_dir)

    if not status["workspace_exists"]:
        return False, "Workspace does not exist"

    # Always cleanup if job is successfully completed
    if status["job_status"] == "SUCCESS" and cleanup_policies["cleanup_completed_jobs"]:
        return True, "Job completed successfully"

    # Never cleanup failed jobs if preserve_failed_jobs is enabled
    if status["job_status"] == "FAILED" and cleanup_policies["preserve_failed_jobs"]:
        return False, "Preserving failed job for debugging"

    # Cleanup cancelled jobs after grace period
    if status["job_status"] == "CANCELED":
        grace_days = cleanup_policies.get("cleanup_cancelled_jobs_after_days", 1)
        if status["last_modified"] and \
           (datetime.now() - status["last_modified"]) > timedelta(days=grace_days):
            return True, f"Cancelled job older than {grace_days} days"
        return False, f"Within grace period for cancelled jobs ({grace_days} days)"

    # Cleanup failed jobs after grace period (if not preserving)
    if status["job_status"] == "FAILED":
        grace_days = cleanup_policies.get("cleanup_failed_jobs_after_days", 7)
        if status["last_modified"] and \
           (datetime.now() - status["last_modified"]) > timedelta(days=grace_days):
            return True, f"Failed job older than {grace_days} days"
        return False, f"Within grace period for failed jobs ({grace_days} days)"

    # Don't cleanup active jobs
    if status["job_status"] in ["PENDING", "RUNNING", "REVIEWING", "INTERVENTION_REQUIRED", "APPROVAL_REQUIRED"]:
        return False, "Job is still active"

    return False, "No cleanup policy matched"


def backup_workspace_before_cleanup(job_dir: str, backup_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates backup of workspace before cleanup for safety.

    Args:
        job_dir: Job directory path
        backup_dir: Optional backup directory path

    Returns:
        Dict with backup operation results
    """
    if backup_dir is None:
        backup_dir = os.path.join(job_dir, ".workspace_backup")

    workspace_dir = os.path.join(job_dir, "workspace")
    result = {
        "success": False,
        "backup_path": backup_dir,
        "error": None
    }

    if not os.path.exists(workspace_dir):
        result["error"] = "Workspace does not exist to backup"
        return result

    try:
        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)

        # Get workspace status for backup metadata
        status = get_workspace_lifecycle_status(job_dir)

        # Create archive of workspace
        import tarfile
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_archive = os.path.join(backup_dir, f"workspace_backup_{timestamp}.tar.gz")

        with tarfile.open(backup_archive, "w:gz") as tar:
            tar.add(workspace_dir, arcname="workspace")

        # Save metadata
        metadata = {
            "backup_timestamp": timestamp,
            "original_workspace_path": workspace_dir,
            "job_dir": job_dir,
            "workspace_status": status,
            "backup_created": datetime.now().isoformat()
        }

        metadata_path = os.path.join(backup_dir, f"backup_metadata_{timestamp}.json")
        import json
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        result["success"] = True
        result["backup_archive"] = backup_archive
        result["metadata_path"] = metadata_path

    except Exception as e:
        result["error"] = f"Backup failed: {str(e)}"

    return result


def cleanup_completed_workspaces(jobs_dir: str, cleanup_policies: Optional[Dict[str, Any]] = None,
                                dry_run: bool = True) -> Dict[str, Any]:
    """
    Performs automated cleanup of completed workspaces based on policies.

    Args:
        jobs_dir: Root jobs directory
        cleanup_policies: Optional cleanup policies
        dry_run: If True, only report what would be cleaned without actually cleaning

    Returns:
        Dict with cleanup operation results
    """
    result = {
        "success": True,
        "workspaces_cleaned": [],
        "workspaces_backed_up": [],
        "workspaces_skipped": [],
        "errors": []
    }

    if not cleanup_policies:
        cleanup_policies = {
            "cleanup_completed_jobs": True,
            "cleanup_failed_jobs_after_days": 7,
            "cleanup_cancelled_jobs_after_days": 1,
            "preserve_failed_jobs": True,
            "max_backups_per_job": 3
        }

    # Find all job directories
    if not os.path.exists(jobs_dir):
        result["errors"].append(f"Jobs directory does not exist: {jobs_dir}")
        result["success"] = False
        return result

    try:
        for item in os.listdir(jobs_dir):
            job_path = os.path.join(jobs_dir, item)
            if not os.path.isdir(job_path):
                continue

            # Check if this looks like a job directory
            if not os.path.exists(os.path.join(job_path, "job_manifest.json")):
                continue

            # Evaluate cleanup decision
            should_cleanup, reason = should_cleanup_workspace(job_path, cleanup_policies)

            if should_cleanup:
                if dry_run:
                    result["workspaces_cleaned"].append({
                        "job_path": job_path,
                        "reason": reason,
                        "dry_run": True
                    })
                else:
                    # Perform backup first
                    backup_result = backup_workspace_before_cleanup(job_path)
                    if backup_result["success"]:
                        result["workspaces_backed_up"].append(job_path)
                    else:
                        result["errors"].append(f"Backup failed for {job_path}: {backup_result['error']}")
                        continue  # Skip cleanup if backup failed

                    # Cleanup workspace and target.git
                    workspace_dir = os.path.join(job_path, "workspace")
                    target_git_dir = os.path.join(job_path, "target.git")
                    try:
                        # Clean up both workspace directory and target.git repo
                        if os.path.exists(workspace_dir):
                            shutil.rmtree(workspace_dir)
                        if os.path.exists(target_git_dir):
                            shutil.rmtree(target_git_dir)

                        result["workspaces_cleaned"].append({
                            "job_path": job_path,
                            "reason": reason,
                            "backed_up": True
                        })
                    except OSError as e:
                        result["errors"].append(f"Cleanup failed for {job_path}: {e}")
                        result["success"] = False
            else:
                result["workspaces_skipped"].append({
                    "job_path": job_path,
                    "reason": reason
                })

    except OSError as e:
        result["errors"].append(f"Directory scan failed: {e}")
        result["success"] = False

    return result


def discover_file_arguments(job_dir: str, prompt_file: Optional[str] = None) -> List[str]:
    """
    Discovers files that should be passed as --file arguments to cline.

    Scans prompt.md for file references and collects system/role files.

    Args:
        job_dir: Job directory path
        prompt_file: Optional specific prompt file, defaults to job_dir/prompt.md

    Returns:
        List of file paths to include in --file arguments
    """
    file_args = []

    # Default prompt file location
    if prompt_file is None:
        prompt_file = os.path.join(job_dir, "prompt.md")

    # Scan prompt.md for file references
    if os.path.exists(prompt_file):
        try:
            with open(prompt_file, 'r') as f:
                prompt_content = f.read()

            # Look for relative file paths in workspace
            # This is a simple pattern - could be enhanced with more sophisticated parsing
            workspace_dir = os.path.join(job_dir, "workspace")
            if os.path.exists(workspace_dir):
                for root, dirs, files in os.walk(workspace_dir):
                    # Skip .git directory
                    if ".git" in dirs:
                        dirs.remove(".git")

                    for file in files:
                        rel_path = os.path.relpath(os.path.join(root, file), workspace_dir)
                        # Simple heuristic: if the file name appears in the prompt
                        if file in prompt_content:
                            file_args.append(os.path.join(workspace_dir, rel_path))

        except Exception as e:
            # Don't fail if prompt scanning fails
            pass

    # Add system schema file
    import pkg_resources
    try:
        # Try to find system.md in package data
        system_file = pkg_resources.resource_filename("logist", "schemas/roles/system.md")
        if os.path.exists(system_file):
            file_args.append(system_file)
    except Exception:
        # Fallback to direct path
        system_file = os.path.join(os.path.dirname(__file__), "..", "schemas", "roles", "system.md")
        if os.path.exists(system_file):
            file_args.append(system_file)

    return file_args


def collect_attachment_files(job_dir: str) -> List[str]:
    """
    Collects all attachment files for inclusion in context preparation.

    Returns files from job_dir/attachments/ directory.

    Args:
        job_dir: Job directory path

    Returns:
        List of attachment file paths
    """
    attachments_dir = os.path.join(job_dir, "attachments")
    attachment_files = []

    if os.path.exists(attachments_dir):
        for root, dirs, files in os.walk(attachments_dir):
            for file in files:
                full_path = os.path.join(root, file)
                attachment_files.append(full_path)

    return attachment_files


def prepare_workspace_attachments(job_dir: str, workspace_dir: str) -> Dict[str, Any]:
    """
    Prepares attachments and discovered files for workspace execution.

    This copies attachments to workspace/attachments/ and discovers all files
    that should be included in cline --file arguments.

    Args:
        job_dir: Job directory path
        workspace_dir: Workspace directory path

    Returns:
        Dict with file preparation information
    """
    result = {
        "success": True,
        "attachments_copied": [],
        "discovered_files": [],
        "file_arguments": [],
        "error": None
    }

    try:
        # Collect attachment files
        attachments = collect_attachment_files(job_dir)
        result["attachments_copied"] = attachments

        # Copy attachments to workspace/attachments/
        workspace_attachments_dir = os.path.join(workspace_dir, "attachments")
        for attachment in attachments:
            rel_path = os.path.relpath(attachment, os.path.join(job_dir, "attachments"))
            dest_path = os.path.join(workspace_attachments_dir, rel_path)

            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # Copy the file
            shutil.copy2(attachment, dest_path)

        # Discover files for --file arguments
        discovered_files = discover_file_arguments(job_dir)
        result["discovered_files"] = discovered_files

        # Combine all file arguments
        file_arguments = attachments + discovered_files
        result["file_arguments"] = list(set(file_arguments))  # Remove duplicates

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result