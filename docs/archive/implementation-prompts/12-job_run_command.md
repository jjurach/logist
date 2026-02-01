# Job Run Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_run_command` (Phase 3.10) from the Logist master development plan. This command is the final user-facing execution command, orchestrating the continuous execution of a job's workflow until completion or intervention.

**Objective:** Execute a job's workflow continuously in the foreground, orchestrating iterative worker and supervisor `oneshot` executions until both roles agree the work is completed (`SUCCESS`), or the job is explicitly canceled (`CANCELED`), or requires human intervention (`INTERVENTION_REQUIRED`), all within an isolated workspace.

**Scope:**
- Implement a persistent execution loop that sequentially invokes worker and supervisor agent steps via `job_step`, continuing until the job reaches a `SUCCESS`, `CANCELED`, or `INTERVENTION_REQUIRED` state. This command runs in the foreground by default.
- Handle state transitions (PENDING → RUNNING → SUCCESS/CANCELED/INTERVENTION_REQUIRED) within this loop.
- Ensure all operations (state updates, workspace modifications, Git commits) occur within the isolated workspace.

**Dependencies:**
- `job_step_command` (Phase 3.9) for single step execution.
- `isolation_env_setup` (Phase 3.6) for managing the isolated workspace.
- Proper state management and history tracking.

Consult this prompts file throughout implementation to ensure every requirement is met - reference it explicitly after each major step to verify compliance.

## Implementation Guidance

The `job run` command will primarily involve a loop that calls the core job execution logic, which in turn utilizes the `job_step` functionality.

*   **`logist/cli.py`**:
    *   Add the `run` subcommand under the `logist job` command group.
    *   Define command-line arguments (e.g., job ID, any potential flags for behavior modification).
    *   Call into the `job_processor` for the main execution logic.
*   **`logist/job_processor.py`**:
    *   Implement the main execution loop for `job run`.
    *   This loop will continuously call a function that encapsulates the logic for a single job step (similar to `job_step`).
    *   Manage state transitions based on the outcome of each step (e.g., `PENDING`, `RUNNING`, `SUCCESS`, `CANCELED`, `INTERVENTION_REQUIRED`).
    *   Orchestrate interactions with external LLM providers (likely via internal calls that leverage `cline --oneshot`).
    *   Handle error conditions and exceptions, transitioning the job to an appropriate state if a critical error occurs.
*   **`logist/job_state.py`**:
    *   Responsible for loading, updating, and saving the `job_manifest.json` file.
    *   Ensure state transitions are correctly recorded and persisted after each step within the `run` loop.
    *   Manage the job history.
*   **`logist/workspace_utils.py`**:
    *   Used to interact with the isolated job workspace.
    *   Ensure the command operates within the correct workspace directory.
    *   Handle any necessary Git operations (e.g., committing evidence files) within the workspace.

## Testing and Demo Features

*   **Unit Tests (`tests/test_cli.py`, `tests/test_job_processor.py`)**:
    *   **Successful Job Completion**: Test `logist job run <job-id>` completes a simple, predefined job from `PENDING` to `SUCCESS` state, verifying all intermediate state transitions and final output.
    *   **Intervention Handling**: Test that if a step within the run loop results in an `INTERVENTION_REQUIRED` state, the `run` command pauses or stops and correctly reports the need for intervention.
    *   **Cancellation Handling**: Test how the `run` command responds if the job is externally canceled during execution.
    *   **Error Scenarios**: Simulate various error conditions during step execution (e.g., LLM response errors, validation failures) and verify the job transitions to an appropriate error state.
    *   **Workspace Integrity**: Verify that `job_manifest.json` is correctly updated and persisted after each step, and that any expected workspace changes (e.g., new files, Git commits for evidence) are present.
    *   **Mocks**: Extensively use mocks for external calls (e.g., `cline --oneshot`, Git commands) to ensure deterministic testing of the execution loop and state machine.
*   **Demo Features (`test-demo.sh` or a new dedicated script)**:
    *   **Full Job Execution**: A clear demonstration of `logist job run <job-id>` where a job starts from `PENDING` and reaches a `SUCCESS` state, showing console output and verifying the final job status.
    *   **Intervention Demo**: A scenario where the `logist job run` command halts due to a simulated `INTERVENTION_REQUIRED` condition, with a message guiding the user on how to proceed.
    *   **State Verification**: Commands to check the job's final status (`logist job status <job-id>`) and inspect the workspace for evidence files after a `run` command completes.

## Implementation Sequence
1. **Analyze:** Read master plan requirements for this task.
2. **Design:** Plan the implementation approach, considering the interaction with `job_step` and state management.
3. **Build:** Implement the `run` subcommand in `logist/cli.py` and the core execution loop in `logist/job_processor.py`.
4. **Test:** Add and run unit tests and update the demo script.
5. **Document:** Ensure `job run` command usage is documented (e.g., in `docs/05_cli_reference.md` if applicable)
6. **Verify:** Ensure all requirements are met.
7. **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`.

## Verification Standards
- ✅ All required functionality implemented.
- ✅ Unit tests pass, covering successful runs, interventions, and errors.
- ✅ `job_manifest.json` is correctly updated throughout the execution loop.
- ✅ Workspace integrity is maintained; evidence and Git commits are handled correctly.
- ✅ Demo script demonstrates successful job execution and intervention scenarios.
- ✅ Backward compatibility maintained with existing CLI patterns.

## Dependencies Check
- **Master Plan:** Reference Phase 3.10 and its dependencies.
- **Dependencies:** Verify that `job_step_command` (Phase 3.9) and `isolation_env_setup` (Phase 3.6) are complete and functional.
- **Testing:** Run comprehensive unit tests and the demo script.

Implement systematically, consulting this specification file at each milestone to maintain 100% requirements coverage.

---

**Note:** When executing this prompt, please follow the instructions in `docs/prompts/_meta_prompt_instructions.md`.
