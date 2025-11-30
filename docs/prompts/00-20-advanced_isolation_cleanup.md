# Advanced Isolation Cleanup Implementation - Cline Oneshot Prompt

Refer to `docs/prompts/_meta_prompt_instructions.md` for overall guidelines on task execution, verification, and Git protocol.

## Task Overview
You are implementing the `advanced_isolation_cleanup` feature from the Logist master development plan. This feature is responsible for cleaning up the isolated workspace directories created for job execution, ensuring that temporary files and Git clones are properly removed after a job completes or when they become stale. This is the counterpart to the `isolation_env_setup` feature (Phase 3.6).

## Master Plan Requirements
**Description:** Clean up isolated workspace directories after execution or when stale.
**Objective:** Ensure isolated job workspaces are removed to free up resources and maintain a clean environment.
**Scope:** Remove `$JOB_DIR/workspace` directory and its contents.
**Dependencies:** Job execution works, `isolation_env_setup` (Phase 3.6) is implemented.
**Files (Read):** `$JOB_DIR/workspace` directory (to verify existence before deletion).
**Files (Write):** Deletes `$JOB_DIR/workspace/` directory.
**Verification:** Workspace directory no longer exists, and no lingering processes associated with the workspace are found.
**Dependency Metadata:** Depends on: `job_run_command`, `job_step_command`.

## Implementation Sequence
1.  **Analyze:** Understand the lifecycle of job workspaces and when cleanup should occur.
2.  **Design:** Determine the best approach for automatic and manual cleanup, considering different job outcomes (success/failure) and potential stale workspaces.
3.  **Build:** Implement the cleanup functionality and integrate it with relevant job execution commands.
4.  **Test:** Verify the cleanup operations thoroughly, including edge cases.
5.  **Document:** Update this prompt and any relevant internal documentation.
6.  **Verify:** Ensure cleanup works as expected without affecting other parts of the system.
7.  **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`.

## Implementation Details

### Core Functionality
-   **Automatic Cleanup:** Implement a mechanism to automatically remove a job's workspace directory (`$JOB_DIR/workspace/`) upon job completion (success or failure).
-   **On-demand Cleanup:** Consider a CLI subcommand (e.g., `logist job cleanup <job_id>`) for manual cleanup of specific job workspaces.
-   **Stale Workspace Detection:** Optionally, implement logic to identify and suggest cleanup for workspaces that are older than a configurable threshold and not associated with active jobs.
-   **Resource Release:** Ensure that any resources (e.g., open files, processes) associated with the workspace are properly terminated before deletion.

### Workspace Lifecycle
-   **Creation:** Handled by `isolation_env_setup`.
-   **Usage:** During job execution (`job run`, `job step`).
-   **Cleanup:**
    -   Immediately after `job run` or `job step` completes.
    -   Via a manual cleanup command.
    -   Via a system health check for stale workspaces.

### Error Handling
-   **Permissions:** Gracefully handle cases where the system lacks permissions to delete files or directories within the workspace.
-   **Non-existent Workspace:** Ensure the cleanup function does not error if the target workspace directory already doesn't exist.
-   **Active Processes:** Implement checks or mechanisms to handle scenarios where processes might still be running within the workspace, preventing deletion.

### Integration Points
-   Modify `logist/job_processor.py` (or similar core logic) to trigger cleanup after a job's execution cycle.
-   Potentially add a new subcommand to `logist/cli.py` for manual cleanup.
-   Update `logist/workspace_utils.py` to include cleanup functions.

### Likely Source Code Paths
-   `logist/cli.py`: For adding a potential `job cleanup` command.
-   `logist/job_processor.py`: To integrate automatic cleanup after job execution.
-   `logist/workspace_utils.py`: To implement the core cleanup logic (e.g., `remove_workspace(job_dir)`).
-   `logist/job_context.py`: To manage job-specific directories and paths.

## Verification Standards
-   ✅ `$JOB_DIR/workspace` directory is successfully removed after job completion.
-   ✅ Manual cleanup command (if implemented) correctly deletes specified workspaces.
-   ✅ No errors occur when attempting to clean up a non-existent workspace.
-   ✅ No lingering files or processes are left behind after cleanup.
-   ✅ Demo script (if updated) verifies successful workspace cleanup.
-   ✅ Backward compatibility maintained, existing `isolation_env_setup` functionality remains stable.

## Dependencies Check
-   **Master Plan:** Phase X.X `advanced_isolation_cleanup`
-   **Dependencies:** `isolation_env_setup` (Phase 3.6) must be fully functional.
-   **Prerequisites:** Robust error handling in file system operations.
-   **Integration:** Will integrate with `job_run_command` and `job_step_command`.

## Testing Strategy
-   **Unit Tests:**
    -   Test the `remove_workspace` function in `logist/workspace_utils.py` with valid, non-existent, and permission-denied directories.
    -   Test scenarios where the workspace contains files, subdirectories, or is empty.
-   **Integration Tests:**
    -   Update `test-demo.sh` to:
        1.  Create a job and run it (triggering `isolation_env_setup`).
        2.  Verify the workspace exists.
        3.  Allow the job to complete (triggering `advanced_isolation_cleanup`).
        4.  Verify the workspace is removed.
    -   Test the manual cleanup command (if implemented) by creating a job, verifying its workspace, and then explicitly cleaning it up.
-   **Error Cases:**
    -   Test cleanup when a job fails mid-execution.
    -   Test cleanup with a "locked" file or directory within the workspace.

## Implementation Deliverables
-   [ ] Implemented `remove_workspace()` function in `logist/workspace_utils.py`.
-   [ ] Modified `logist/job_processor.py` to call `remove_workspace()` after job execution.
-   [ ] (Optional) Added `job cleanup` command to `logist/cli.py`.
-   [ ] Updated `test-demo.sh` to include cleanup verification.
-   [ ] All unit tests for cleanup functionality pass.
-   [ ] Demo script passes all verification tests, including workspace cleanup.

## Verification Standards
-   [ ] Workspace directory (`$JOB_DIR/workspace`) is successfully removed after job completion.
-   [ ] (If implemented) Manual cleanup command correctly deletes specified workspaces.
-   [ ] No errors occur when attempting to clean up a non-existent workspace.
-   [ ] No lingering files or processes are left behind after cleanup.
-   [ ] Demo script validates successful workspace cleanup.
-   [ ] Backward compatibility maintained.

**Completion Date:** (To be filled upon completion)
**Implementation:** (To be filled upon completion)