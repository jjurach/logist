# Project Plan: Separate Workspace Setup from Concurrent Job Execution

**Date:** 2025-12-26 20:43:14
**Estimated Duration:** 45 minutes
**Complexity:** Medium
**Status:** Approved/In Progress

## Objective
Refactor the workspace setup process to eliminate concurrency issues in `tests/test_concurrency.py`. Separate workspace setup from job execution so that workspace_utils can be tested in isolation while concurrent job execution tests avoid git and filesystem conflicts.

## Requirements
- [ ] Move workspace setup out of concurrent job execution paths
- [ ] Ensure workspace is set up once per job before concurrent execution begins
- [ ] Create separate unit tests for workspace_utils functionality
- [ ] Modify concurrency tests to avoid calling setup_workspace concurrently
- [ ] Ensure workspace setup happens in the "runner" (core engine) rather than mock agents
- [ ] Maintain backward compatibility with existing job execution flows

## Implementation Steps
1. **Analyze current workspace setup usage**
   - Identify all places where `setup_workspace` is called
   - Understand the difference between workspace preparation and workspace setup
   - Files to examine: `src/logist/core_engine.py`, `src/logist/services/job_manager.py`
   - Estimated time: 5 minutes
   - Status: [x] Completed

2. **Create workspace setup coordination in core engine**
   - Add method to ensure workspace is set up once per job before execution
   - Modify `step_job` and `run_job` to call workspace setup coordination instead of direct setup
   - Ensure setup happens before concurrent execution begins
   - Files to modify: `src/logist/core_engine.py`
   - Estimated time: 15 minutes
   - Status: [x] Completed

3. **Modify job manager setup_workspace method**
   - Add flag/parameter to prevent redundant workspace setup
   - Implement coordination to ensure setup happens only once
   - Add proper error handling for concurrent setup attempts
   - Files to modify: `src/logist/services/job_manager.py`
   - Estimated time: 10 minutes
   - Status: [x] Completed

4. **Update concurrency tests**
   - Modify `test_concurrent_job_execution` to set up workspaces before concurrent execution
   - Remove direct `setup_workspace` calls from concurrent execution paths
   - Ensure each job has its workspace prepared individually before threading
   - Files to modify: `tests/test_concurrency.py`
   - Estimated time: 10 minutes
   - Status: [ ] Not Started

5. **Create separate workspace_utils unit tests**
   - Create dedicated test file for workspace_utils functionality
   - Test workspace setup, git operations, and file management in isolation
   - Ensure these tests don't interfere with concurrency tests
   - Files to create: `tests/test_workspace_utils.py`
   - Estimated time: 5 minutes
   - Status: [x] Completed

## Success Criteria
- [ ] `tests/test_concurrency.py` no longer hangs during execution
- [ ] Workspace setup happens once per job, not concurrently
- [ ] Separate unit tests exist for workspace_utils
- [ ] Job execution performance is maintained
- [ ] No breaking changes to existing job execution flows
- [ ] Concurrent job execution can run successfully

## Testing Strategy
- [ ] Unit test: Verify workspace setup coordination works correctly
- [ ] Integration test: Run `test_concurrent_job_execution` without hanging
- [ ] Performance test: Ensure concurrent execution performance is maintained
- [ ] Regression test: Verify normal job execution still works
- [ ] Isolation test: Verify workspace_utils unit tests run independently

## Risk Assessment
- **Medium Risk:** Modifying core engine job execution flow - could affect job processing
- **Low Risk:** Adding workspace setup coordination - should be backward compatible
- **Low Risk:** Creating separate unit tests - isolated functionality
- **Low Risk:** Updating concurrency tests - focused on test stability

## Dependencies
- [ ] Current workspace_utils.setup_isolated_workspace implementation
- [ ] Existing job execution flow in core_engine.py
- [ ] Current concurrency test implementation

## Notes
This refactoring addresses the root cause of the hanging concurrency test by eliminating concurrent git operations during workspace setup. Workspace setup will now happen in a coordinated manner before concurrent execution begins, while still allowing workspace_utils to be tested in isolation.

The key insight is that workspace setup should be a "runner" responsibility (happening once per job) rather than a per-execution responsibility that gets called concurrently.