# Isolation Env Setup Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `isolation_env_setup` from the Logist master development plan (Phase 3.6). This feature creates isolated workspace directories for job execution by cloning Git repositories into clean environments.

## Master Plan Requirements
**Description:** Create isolated workspace directory before execution
**Objective:** Create isolated workspace directory before execution
**Scope:** Git clone to `$JOB_DIR/workspace`, setup working environment
**Dependencies:** Job creation works (Phase 1.3)
**Files (Read):** Local `.git` directory from current working directory
**Files (Write):** Creates `$JOB_DIR/workspace/` directory with local Git clone
**Verification:** Workspace directory exists and contains working copy of local project
**Dependency Metadata:** Required for: job_step_command, job_preview_command, job_run_command

## Implementation Sequence
1. **Analyze:** Understand local Git isolation and workspace lifecycle
2. **Design:** Determine local repository discovery and workspace management approach
3. **Build:** Implement workspace setup by cloning local `.git` repo and integrate with execution commands
4. **Test:** Verify local Git operations and workspace isolation
5. **Document:** Update documentation and demo script
6. **Verify:** Ensure workspace setup enables job isolation without breaking existing functionality
7. **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`

## Implementation Details

### Core Functionality
- **Automatic Setup:** Workspace creation happens implicitly before execution commands
- **Local Git Clone:** Clone current working directory's `.git` repository to `$JOB_DIR/workspace/`
- **Repository Discovery:** Automatically detect project root by finding `.git` directory from current working directory
- **Isolation:** Each job gets its own git repository clone for committing changes independently
- **Idempotent:** If workspace exists and is valid git clone, skip setup; otherwise recreate

### Repository Discovery
The implementation must:
1. Find the project root (directory containing `.git`)
2. Use local git clone: `git clone . $JOB_DIR/workspace`
3. Preserve all git history but allow independent commits in workspace

### Workspace Lifecycle
- **Creation:** `git clone . $WORKSPACE_DIR` from project root
- **Validation:** Check `.git` directory exists and working copy is intact
- **Reuse:** Use existing workspace if valid and not stale
- **Replacement:** Remove and recreate if workspace git becomes corrupted

### Error Handling
- No `.git` directory found → Fail with "Not in a git repository" message
- Git clone failure → Fail with specific error (permissions, disk space, etc.)
- Invalid workspace → Auto-recreate or fail with clear messaging

### Integration Points
- `job_step_command`: Ensure workspace exists and call step in workspace directory
- `job_preview_command`: Ensure workspace exists for context and operation visibility
- `job_run_command`: Ensure workspace exists for continuous execution

### Implementation Notes
- All git operations are local - no remote repositories involved
- Workspace should maintain the same project structure as the original
- Jobs can commit freely in workspace without affecting the original repository
- Future integration (git_integration_commit) will handle merging workspace changes back

## Verification Standards
- ✅ Workspace directory created with successful local Git clone
- ✅ Project root `.git` directory automatically discovered
- ✅ Execution commands use workspace for operations
- ✅ Workspace provides independent git history for job changes
- ✅ Demo script validates workspace creation and git integrity
- ✅ Backward compatibility maintained

## Dependencies Check
- **Master Plan:** Phase 3.6 isolation_env_setup
- **Dependencies:** job_create_command (Phase 1.3) must work
- **Prerequisites:** Must be run from within a git repository (`git clone` will fail otherwise)
- **Integration:** Required for job_step, job_preview, job_run commands

## Testing Strategy
- **Mock Git Operations:** Unit tests should mock filesystem checks but test logic flow
- **Integration Tests:** Demo script validates end-to-end workspace setup from actual git repo
- **Error Cases:** Test scenarios without .git directory, corrupted workspaces, permission issues
- **Git Integrity:** Verify workspace contains identical content to original after clone
- **Isolation:** Ensure workspace commits do not affect original repository

## Implementation Deliverables
- ✅ Added `find_git_root()` function for automatic Git repository discovery
- ✅ Implemented `setup_workspace()` method in `PlaceholderJobManager` for workspace isolation
- ✅ Modified `PlaceholderLogistEngine` methods (`run_job`, `step_job`, `preview_job`) to call workspace setup
- ✅ Added `get_job_dir()` helper for CLI job directory resolution
- ✅ Updated CLI commands (`job run`, `job step`, `job preview`) to pass job directories to engine
- ✅ Updated demo script to validate workspace creation and Git integrity
- ✅ Demo script passes all verification tests including workspace setup

## Verification Standards
- ✅ Workspace directory created with successful local Git clone
- ✅ Project root `.git` directory automatically discovered
- ✅ Execution commands use workspace for operations
- ✅ Workspace provides independent git history for job changes
- ✅ Demo script validates workspace creation and git integrity
- ✅ Backward compatibility maintained

**Completion Date:** November 29, 2025
**Implementation:** Successfully completed isolation environment setup feature enabling job workspace isolation.

Implement systematically, consulting this specification file throughout development to maintain complete requirements coverage.