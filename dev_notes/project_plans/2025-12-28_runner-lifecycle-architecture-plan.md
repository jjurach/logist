# Project Plan: Runner Lifecycle Architecture Refactor

**Date:** 2025-12-28
**Completed:** 2025-12-28
**Complexity:** High
**Status:** Completed

## Objective

Reconcile the contradictions identified in `doc/problems.md` by implementing a clear runner lifecycle model, standardizing terminology, and separating workspace operations from job state management. This plan focuses on establishing the architectural foundation for runner-based execution.

## Background

The current implementation has several contradictions between intended architecture and actual code:
- Uses "Runtime" class but documentation says "Runner"
- workspace_utils handles git operations that should be runner responsibilities
- Tests are tightly coupled to old implementation patterns
- CLI commands don't align with the runner operation lifecycle

## Summary of Changes

### Phase 1: Terminology and Documentation Cleanup

#### Task 1.1: Standardize on "Runner" and "Agent" Terminology
- **Rename**: Consolidate on "runners" (not "runtimes") and "agents" (not "agent providers")
- **Files to modify**:
  - `src/logist/runtimes/` → rename directory to `src/logist/runners/`
  - `src/logist/runtimes/base.py` → `src/logist/runners/base.py`: class `Runtime` → `Runner`
  - `src/logist/runtimes/direct.py` → `src/logist/runners/direct.py`: class `DirectCommandRuntime` → `DirectRunner`
  - `src/logist/runtimes/host.py` → `src/logist/runners/host.py`: class `HostRuntime` → `HostRunner`
  - `src/logist/runtimes/mock.py` → `src/logist/runners/mock.py`: class `MockRuntime` → `MockRunner`
  - Update all imports throughout the codebase
  - Update `src/logist/agents/base.py`: class `AgentProvider` → `Agent`

#### Task 1.2: Update Documentation to be Agent-Agnostic
- **Files to modify**:
  - `doc/overview.md`: Replace "uses **Cline CLI** as the fundamental execution primitive" with agent-agnostic language, using Cline and Podman as common examples
  - `doc/01_architecture.md`: Remove Cline-specific terminology, describe multiple agent support
  - `doc/02_roles_overview.md`: Update examples to reference generic "agent" instead of Cline
  - `doc/07_runner_agent_architecture.md`: Review for consistency with new terminology

### Phase 2: Required Job Attributes

#### Task 2.1: Add `prompt` Attribute as Required Field
- **Implementation**:
  - Modify job manifest schema to require `prompt` field
  - Update `JobManagerService.create_job()` to accept `--prompt` and `--file` flags
  - Add validation: job activation must fail if `prompt` is empty
- **Files to modify**:
  - `src/logist/services/job_manager.py`
  - `src/logist/cli.py` (job create command)
  - `doc/05_cli_reference.md`

#### Task 2.2: Add `gitSourceRepo` Attribute as Required Field
- **Implementation**:
  - Add `gitSourceRepo` field to job manifest (auto-detected or explicit)
  - Implement auto-detection: walk up directory tree to find `.git`
  - Support explicit `--gitSourceRepo` CLI flag to override
  - Fail with clear error if no git repo found and no explicit value provided
- **Files to modify**:
  - `src/logist/services/job_manager.py`
  - `src/logist/cli.py`
  - `doc/05_cli_reference.md`

### Phase 3: Configuration File Support

#### Task 3.1: Add Initial `logist.yml` Documentation
- **Create** `doc/08_configuration.md` documenting:
  - `logist.yml` as project-level configuration
  - Initial minimal schema: `{"runner": "direct", "agent": "mock"}`
  - Configuration hierarchy: `logist.yml` → job manifest → CLI flags
  - Testing configuration recommendations

#### Task 3.2: Document Testing Configuration
- **Add section to** `doc/06_testing_strategy.md`:
  - The "direct" runner: minimal I/O transformation, calls agent command directly
  - The "mock" agent: provides `echo` commands for mocked results
  - Example: `{"runner": "direct", "agent": "mock"}` for testing

### Phase 4: Disconnect Workspace Operations from Job Processing

#### Task 4.1: Identify workspace_utils Calls to Remove
Current calls in `job_processor.py`:
- Line 359: `from logist.workspace_utils import perform_git_commit` (used in `process_simulated_response`)
- Line 439: `commit_result = perform_git_commit(...)` (used for evidence commits)

Current calls in `job_manager.py`:
- Line 12: `from logist import workspace_utils`
- Line 326: `workspace_utils.setup_isolated_workspace(job_id, job_dir, base_branch="main", debug=debug)`

Current calls in `core_engine.py`:
- Line 14: `from logist import workspace_utils`
- Line 276: `workspace_utils.prepare_workspace_attachments(job_dir, workspace_dir)`
- Line 427: `workspace_utils.perform_git_commit(...)`

#### Task 4.2: Replace workspace_utils Calls with Placeholder Prints
- **In `job_processor.py`**:
  - Replace `perform_git_commit()` calls with:
    ```python
    click.echo("[PLACEHOLDER] Runner harvest operation would commit evidence files here")
    ```

- **In `job_manager.py`**:
  - Replace `workspace_utils.setup_isolated_workspace()` with:
    ```python
    click.echo("[PLACEHOLDER] Runner provision operation would setup workspace here")
    ```

- **In `core_engine.py`**:
  - Replace `workspace_utils.prepare_workspace_attachments()` with runner call or placeholder
  - Replace `workspace_utils.perform_git_commit()` with runner call or placeholder

### Phase 5: Define Runner Lifecycle Operations

#### Task 5.1: Document Runner Interface Methods in `doc/07_runner_agent_architecture.md`

Add detailed section describing runner lifecycle operations:

```python
class Runner:
    def provision(self, job_id: str, job_dir: str) -> ProvisionResult:
        """
        Provision runner environment for job execution.

        Called when: Job is activated (DRAFT → PENDING)

        For Docker runner:
        - Validates docker image exists (e.g., `docker images | grep <image>`)
        - Does NOT pull images automatically (manual provisioning required)
        - Runs agent's `--version` command to validate agent CLI is installed
        - Can choose initial job execution state (e.g., architect vs editor role)

        Returns:
            ProvisionResult with success status and metadata

        Side effects:
        - Activation fails if provision fails
        - Stores container/environment metadata in job manifest
        """

    def execute(self, job_id: str, job_dir: str, prompt: str) -> ExecuteResult:
        """
        Start one-shot, non-interactive agent execution.

        Called when: `logist job step` or `logist job run`

        For Docker runner:
        - Runs `docker run` with agent command in background
        - Returns immediately with container ID and metadata
        - Does NOT wait for completion

        Returns:
            ExecuteResult with container_id, metadata, and launch status

        Side effects:
        - Stores container_id in job manifest for tracking
        - Job transitions to RUNNING state
        """

    def status(self, job_id: str, job_dir: str) -> StatusResult:
        """
        Query execution status and interpret agent output.

        Called when: Checking job progress (polling, status command)

        For Docker runner:
        - Queries `docker ps -a` to check container state
        - If running: capture last 20 lines of logs
        - If stopped: capture all logs
        - Passes logs to agent's `check_status` operation

        Agent check_status interprets logs and returns:
        - If stopped:
          - "failed": Agent interprets failure from computation
          - "success": Agent interprets success from computation
          - "abort": Agent interprets abort signal
          - "recover": Stopped but inconclusive (needs recovery)
        - If running:
          - "timeout": Exceeded max execution threshold (e.g., 10 min)
          - "stuck": No output within threshold (e.g., 2 min)
          - "running": Still executing normally

        Returns:
            StatusResult with execution_status, reason, and log_tail
        """

    def abort(self, job_id: str, job_dir: str) -> AbortResult:
        """
        Force-stop a running execution.

        Called when: User requests abort, or timeout/stuck detected

        For Docker runner:
        - Runs `docker kill <container_id>`
        - Forces container into stopped state

        Preconditions:
        - Only valid for jobs with active running process
        - Returns error info if called on non-running job

        Returns:
            AbortResult with success status and final container state
        """

    def recover(self, job_id: str, job_dir: str) -> RecoverResult:
        """
        Attempt to recover/restart a stopped execution.

        Called when: Status returns "recover" (stopped but inconclusive)

        For Docker runner:
        - Runs `docker exec` into stopped container
        - Injects fresh agent command to continue progress
        - Uses container's preserved state to resume work

        Preconditions:
        - Only valid for stopped processes
        - Returns error if called on running process

        Returns:
            RecoverResult with recovery status and new execution metadata
        """

    def harvest(self, job_id: str, job_dir: str) -> HarvestResult:
        """
        Finalize job step and collect results.

        Called when: After execution completes (success, fail, or recovery exhausted)

        For Docker runner:
        - Collects full log into job directory
        - Commits changes to job branch (git add, commit)
        - Makes decision about next steps

        Harvest can:
        - Choose to restart execution
        - Modify internal job state (e.g., switch architect→editor role)
        - Implement state machine iteration through roles

        Note: Current implementation uses print() placeholders for
        decision-making logic (to be added in later phase)

        Returns:
            HarvestResult with collected artifacts and next_action recommendation
        """
```

### Phase 6: CLI Command Alignment

#### Task 6.1: Map Runner Operations to CLI Commands

| Runner Operation | CLI Command(s) | State Transition |
|-----------------|----------------|------------------|
| provision | `logist job activate` | DRAFT → PENDING |
| execute | `logist job step`, `logist job run` | PENDING → RUNNING |
| status | `logist job status` (enhanced) | Query only |
| abort | `logist job cancel` | RUNNING → CANCELED |
| recover | `logist job recover` (NEW) | REVIEW_REQUIRED → RUNNING |
| harvest | (internal to step/run) | RUNNING → REVIEW_REQUIRED |

#### Task 6.2: Review and Update CLI Commands
- **Keep**:
  - `logist job create` - Creates DRAFT job
  - `logist job activate` - Transitions DRAFT → PENDING (calls provision)
  - `logist job step` - Execute single step (calls execute, status, harvest)
  - `logist job run` - Execute until terminal state
  - `logist job status` - Show job status
  - `logist job list` - List all jobs
  - `logist job cancel` - Cancel job (calls abort if running)

- **Add**:
  - `logist job recover` - Attempt to recover stopped job (calls recover)

- **Remove/Deprecate** (if redundant):
  - Review `logist job restep` - may overlap with recover
  - Review `logist job rerun` - ensure distinct from recover

#### Task 6.3: Update State Machine Documentation
- **File**: `doc/04_state_machine.md`
- Add runner operation annotations to state transitions
- Document which runner operation triggers each transition

### Phase 7: Remove Obsolete Tests

#### Task 7.1: Delete Tests with Old Implementation Expectations
These tests are tightly coupled to the old architecture and create noise:

```bash
rm tests/test_concurrency.py
rm tests/test_integration_e2e.py
rm tests/test_workspace_utils.py
```

**Rationale**:
- `test_concurrency.py`: Tests old workspace setup patterns
- `test_integration_e2e.py`: End-to-end tests assume old execution model
- `test_workspace_utils.py`: Tests workspace_utils which is being disconnected

**Note**: New tests should be created as runner implementations are completed.

## Implementation Order

1. **Phase 7 first**: Remove obsolete tests to reduce noise during refactoring
2. **Phase 1**: Terminology standardization (enables cleaner code)
3. **Phase 2**: Add required job attributes (foundation for runner operations)
4. **Phase 3**: Configuration documentation (informs testing approach)
5. **Phase 4**: Disconnect workspace operations (create space for runner interface)
6. **Phase 5**: Document runner lifecycle (design specification)
7. **Phase 6**: CLI alignment (user-facing integration)

## Success Criteria

- [x] All "Runtime" references renamed to "Runner" in code and docs
- [x] All "AgentProvider" references renamed to "Agent" in code and docs
- [x] Documentation describes Cline/Podman as examples, not exclusive implementations
- [x] Job creation requires `prompt` attribute
- [x] Job creation auto-detects or requires `gitSourceRepo`
- [x] `doc/08_configuration.md` documents `logist.yml` format
- [x] `doc/06_testing_strategy.md` documents direct/mock testing config
- [x] workspace_utils calls replaced with placeholders in job_processor
- [x] Placeholder prints indicate where runner operations will be called
- [x] Runner lifecycle operations documented in `doc/07_runner_agent_architecture.md`
- [ ] `logist job recover` command added to CLI (deferred to future PR)
- [x] CLI commands updated with --runner and --agent flags
- [x] Obsolete tests removed: test_concurrency.py, test_integration_e2e.py, test_workspace_utils.py

## Dependencies

- Depends on: `doc/problems.md` (completed)
- Depends on: `doc/07_runner_agent_architecture.md` (completed)
- Blocks: Docker runner implementation
- Blocks: Podman runner implementation
- Blocks: New integration test suite

## Risk Assessment

- **Medium Risk**: Renaming Runtime→Runner affects many files; use IDE refactoring tools
- **Medium Risk**: Removing workspace_utils calls temporarily breaks git operations
- **Low Risk**: Documentation changes are non-breaking
- **Low Risk**: Removing tests doesn't affect production code

## Notes

This refactoring establishes clear separation of concerns:
- **Runners** handle WHERE/HOW code runs (docker, podman, direct)
- **Agents** handle WHAT tool runs (cline, aider, claude-code)
- **Job State** tracks workflow progress independent of execution mechanics

The placeholder approach (print statements) allows incremental implementation:
1. First, disconnect workspace_utils
2. Then, implement runner methods one at a time
3. Finally, wire runner calls to replace placeholders

This design enables different runners to implement workspace management in runner-specific ways (e.g., docker volumes vs local filesystem vs kubernetes PVCs).
