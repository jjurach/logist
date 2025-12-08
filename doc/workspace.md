# Workspace Setup Documentation

This document describes the workspace creation process in Logist, specifically how `workspace_utils.py` sets up isolated job environments.

## Overview

Each Logist job runs in a completely isolated environment consisting of:
- `target.git/`: A bare Git repository containing the job-specific branch
- `workspace/`: A working directory with symlinked `.git` pointing to `../target.git`

This isolation ensures the main project repository remains untouched during job execution.

## Previous Implementation Issues

The original `setup_isolated_workspace()` function always removed existing `workspace/` and `target.git/` directories, which meant:

1. **No idempotency**: Re-running workspace setup would always destroy and recreate, even if valid
2. **Unnecessarily destructive**: Valid workspaces were destroyed unnecessarily
3. **Potential data loss**: Any uncommitted changes in existing workspaces were lost

## Current Implementation: Idempotent Workspace Creation

The updated implementation follows these steps:

### 1. Validation Phase
```python
target_git_valid = validate_existing_target_git(job_dir, job_branch_name, debug)
workspace_valid = validate_existing_workspace(job_dir, job_branch_name, debug)
```

### 2. Decision Logic
- If both `target.git` and `workspace` exist and are valid: **Reuse existing setup**
- If either is missing or invalid: **Create fresh setup**

### 3. Fresh Setup Commands (when needed)

The implementation uses these git commands executed from the project's git root:

#### Branch Creation
```bash
git branch --list job-{job_id}          # Check if job branch exists
git branch job-{job_id} {base_branch}   # Create from base branch if missing
git checkout {original_branch}          # Restore original branch
```

#### Repository Setup
```bash
git clone --bare --branch job-{job_id} {git_root} target.git
```

#### Worktree Setup
```bash
git worktree list --porcelain | grep workspace  # Check for conflicts
git worktree remove --force workspace           # Remove conflicting worktree if exists
git worktree add --detach workspace job-{job_id}
rm -rf workspace/.git                            # Remove auto-generated .git
ln -s ../target.git workspace/.git              # Create symlink to target.git
```

#### Environment Preparation
```bash
./AGENTS/prepare-python-project.sh  # If exists, run preparation script
cp -r attachments workspace/        # Copy job attachments if any exist
```

## Intended Simplified Approach

The design document suggested a simplified two-command approach:

```bash
git clone --bare --branch {base_branch} $(pwd) $job_dir/target.git
git --git-dir $job_dir/target.git worktree add $job_dir/workspace {base_branch}
```

However, this approach was incompatible with Logist's requirement for job-specific branches. The current implementation:

1. Creates job-specific branches (e.g., `job-123`) from the base branch
2. Uses bare repositories with symlinked `.git` for transparent git operations
3. Maintains isolation between concurrent jobs

## Validation Functions

Two new functions ensure workspace integrity:

### `validate_existing_target_git(job_dir, branch, debug)`
- Verifies `target.git` exists and is a valid git repository
- Confirms the expected job branch exists
- Returns `True` if safe to reuse

### `validate_existing_workspace(job_dir, branch, debug)`
- Verifies `workspace/` exists and `.git` symlink is correct
- Confirms workspace is on the expected branch
- Returns `True` if safe to reuse

## Debug Logging

All subprocess calls now include debug output when `debug=True`:

```
🔧 [DEBUG] Running: git clone --bare --branch job-123 /path/to/project target.git (cwd: /path/to/job)
```

This provides visibility into the git operations during workspace setup.

## Testing Strategy

To test individual steps within this workflow:

### Unit Tests
- `test_validate_existing_target_git()`: Test target.git validation scenarios
- `test_validate_existing_workspace()`: Test workspace validation scenarios
- `test_setup_isolated_workspace_idempotent()`: Test reuse of valid existing setups

### Integration Tests
- Full workspace setup with various branch configurations
- Error handling when git operations fail
- Cleanup behavior for invalid/corrupted workspaces

### Debug Testing
- Enable debug mode to verify correct command execution
- Test with existing vs. non-existing workspace states
- Validate branch switching doesn't affect main repository

## Migration Notes

Existing jobs with manually created workspaces should be compatible. The validation functions will detect and reuse valid setups while recreating invalid ones.

For testing, add the `debug=True` parameter to `setup_isolated_workspace()` calls to see detailed command execution.