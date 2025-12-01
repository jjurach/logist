# Job Chat Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_chat_command` from the Logist master development plan. Consult this prompts file throughout implementation to ensure every requirement is met - reference it explicitly after each major step to verify compliance.

## Implementation Sequence
1. **Analyze:** Read master plan requirements for this task
2. **Design:** Plan the implementation approach
3. **Build:** Create the required files
4. **Test:** Verify functionality
5. **Document:** Update documentation
6. **Verify:** Ensure requirements are met
7. **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`

## Verification Standards
- ✅ All required functionality implemented
- ✅ Tests pass
- ✅ Documentation updated
- ✅ Backward compatibility maintained

## Dependencies Check
- **Master Plan:** Reference this specific task requirements (Phase 4.13: `job_chat_command`)
- **Dependencies:** `logist init` (Phase 1.1), `logist job create` (Phase 1.3), `logist job status` (Phase 2.1)
- **Testing:** Run appropriate test suites

Implement systematically, consulting this specification file at each milestone to maintain 100% requirements coverage.

---

## Implementation Advice and Source Code Paths

The `logist job chat` command is designed as an interactive debugging and intervention tool. Its primary function is to allow direct interaction with a Cline task associated with a Logist job, but only when the job is in a safe, non-active state.

**Key Requirements:**
- **State Validation:** The command must first validate that the currently selected job is *not* in a `RUNNING` or `REVIEWING` state. This is critical to prevent concurrent modifications or interactions during active job execution. If the job is in an invalid state, an appropriate error message should be displayed, and the `cline task chat` command should not be invoked.
- **Pass-through to `cline task chat`:** If the job is in a valid state, the command should construct and execute the `cline task chat <TASK_ID>` command, where `<TASK_ID>` is the Cline task ID associated with the current Logist job. The `job_manifest.json` file should contain this task ID.

**Likely Source Code Paths for Implementation:**
- `logist/cli.py`: This file will be where the `logist job chat` subcommand is defined and registered using `click`. It will handle argument parsing (e.g., optional job ID) and delegate to core logic.
- `logist/job_state.py`: This module likely contains the `JobState` class or similar structures that hold the current status (e.g., `PENDING`, `RUNNING`, `REVIEWING`, `INTERVENTION_REQUIRED`, `SUCCESS`, `CANCELED`) and the `cline_task_id` for a given job. The implementation will need to read this state.
- `logist/job_processor.py` (or a new module like `logist/chat_interface.py`): This module will contain the core logic for the `chat` command, including:
    - Retrieving the currently selected job or the job specified by ID.
    - Reading the job's current state from its `job_manifest.json`.
    - Performing the state validation check.
    - Constructing the `cline task chat <TASK_ID>` command.
    - Executing the command using a subprocess call (e.g., `subprocess.run`).
- `logist/workspace_utils.py`: This module might be used to resolve the path to the job's isolated workspace, though `cline task chat` typically operates directly on the task ID, so direct workspace interaction might not be necessary for this specific command, but it's good to be aware of.

## Unit Tests and Demo Features

**Unit Tests:**
Add tests to `tests/test_cli.py` (or potentially a new `tests/test_job_commands.py` if the CLI becomes very extensive) to cover the following scenarios:
- **`test_job_chat_valid_state`:** Verify that `logist job chat` can be successfully invoked when a job is in a valid state (e.g., `PENDING`, `INTERVENTION_REQUIRED`, `SUCCESS`, `CANCELED`). Mock the `subprocess.run` call to ensure `cline task chat` is called with the correct arguments.
- **`test_job_chat_invalid_state_running`:** Confirm that `logist job chat` prevents interaction and displays an appropriate error message when the job is in a `RUNNING` state. Ensure `cline task chat` is *not* called.
- **`test_job_chat_invalid_state_reviewing`:** Confirm similar behavior for the `REVIEWING` state.
- **`test_job_chat_no_job_selected`:** Verify proper error handling if no job is selected or specified when running the command.
- **`test_job_chat_non_existent_job`:** Test the behavior when attempting to chat with a non-existent job ID.

**Demo Features:**
Extend the `test-demo.sh` script to include a demonstration of the `logist job chat` command.
- **Setup:**
    - Create a new job using `logist job create`.
    - Select the newly created job using `logist job select`.
    - Optionally, use `logist job step --dry-run` or similar (if available) to advance the job to a state where `chat` would be valid.
- **Demonstrate Valid Chat:**
    - Execute `logist job chat` and assert that it appears to correctly invoke `cline task chat` (e.g., by checking for expected output or mock calls).
- **Demonstrate Invalid Chat (Error Handling):**
    - Potentially, if a mock `job step` or similar command exists, advance the job to a `RUNNING` state.
    - Attempt to execute `logist job chat` again and assert that it fails gracefully with the expected error message, confirming the state validation.

---

## Important Notes for Execution
This prompt should follow the guidelines in `docs/prompts/_meta_prompt_instructions.md` for success/failure reporting, Git status, and commit protocol after implementation.