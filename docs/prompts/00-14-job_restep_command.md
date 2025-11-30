# 00-14-job_restep_command.md

## Task
Implement the `logist job restep <job_id> <step_number>` command. This command should re-execute a single, specific step of a previously run job. It is intended for fine-grained debugging and precise re-execution of a particular step.

## Intent of `job restep`
The `job restep` command provides granular control over job execution, allowing users to:
*   **Debug specific steps:** Isolate and re-run a particular step to diagnose issues without affecting other steps or re-executing the entire job.
*   **Re-attempt a failed step:** After a manual fix or adjustment, re-execute only the problematic step to confirm the resolution.
*   **Develop iteratively:** Test changes to a single step's logic or input/output processing efficiently.

This command focuses on the execution of a *single* step, unlike `job rerun` which can restart from a step or the beginning. It leverages the existing job state and history, but its impact is limited to the specified step.

## Implementation Advice

### Core Logic
The `job restep` command will require:

1.  **Job and Step Loading:** Load the job manifest and its current state using `job_id`. Identify the specific step (`step_number`) within the job's workflow. This will involve `logist/job_state.py` for reading the current state and `logist/job_processor.py` for accessing the job's steps.
2.  **Isolated Step Execution:** The core of `restep` will involve extracting the logic for executing a single step from `logist/job_processor.py` (likely reusing parts of what `job_step` or `job_run` use for individual step processing). The execution must occur within the isolated workspace associated with the job.
3.  **State Management:**
    *   The `restep` command should update the state for *only* the re-executed step. This means marking the specific step as `RUNNING` during execution and then updating its status (e.g., `SUCCESS`, `FAILURE`) upon completion.
    *   Crucially, `restep` should record the re-execution in the job's history (`logist/job_history.py`) for the *specific step*, rather than creating a new overall job run entry as `rerun` does. This allows for an audit trail of individual step re-attempts.
    *   It should not alter the overall `job_run` status or reset the job's progress beyond the targeted step.
4.  **Input/Output Handling:** Ensure the step receives the correct inputs (from the state *before* this step was originally run, or the current state if intermediate steps were modified) and that its outputs are correctly captured and used to update the job's state for subsequent steps, should the job be continued later.
5.  **CLI Integration:** Register `restep` as a subcommand under `logist job`. It should accept `job_id` and `step_number` as required arguments.

### Source Code Paths Likely Used
*   `logist/cli.py`: Command registration for `job restep`, handling arguments (`job_id`, `step_number`). This will be the entry point.
*   `logist/job_processor.py`: The `JobProcessor` class will need a new method (e.g., `restep_single_step`) to encapsulate the logic for executing a specific step in isolation. This method will orchestrate the actual execution of the agent logic for that step.
*   `logist/job_state.py`: Used to load the job's overall state, access the specific step's definition, update the step's status, and persist changes.
*   `logist/job_history.py`: Will require updates to record `restep` actions at the individual step level, ensuring a detailed history of modifications and re-attempts for each step.
*   `logist/workspace_utils.py`: For navigating to and operating within the job's isolated workspace for the step's execution.

## Unit Tests to Add

Unit tests should be added to `tests/test_cli.py` and potentially `tests/test_job_processor.py`.

*   **`test_restep_command_registered`**: Verify that `logist job restep` is a recognized command.
*   **`test_restep_requires_job_id_and_step_number`**: Ensure the command fails if `job_id` or `step_number` is missing.
*   **`test_restep_non_existent_job`**: Test error handling for an invalid `job_id`.
*   **`test_restep_invalid_step_number`**: Test appropriate error handling when `step_number` is out of bounds (e.g., negative, zero, greater than total steps).
*   **`test_restep_single_step_success`**:
    *   Create a multi-step job.
    *   Run the job partially or fully.
    *   Execute `logist job restep <job_id> <valid_step_number>`.
    *   Verify that only the specified step is re-executed and completes successfully.
    *   Check `job_history.py` to ensure the `restep` event for that specific step is recorded, and the overall job history remains consistent.
    *   Verify the job's state correctly reflects the re-executed step's outcome.
*   **`test_restep_single_step_failure`**:
    *   Create a multi-step job with a step designed to fail.
    *   Execute `logist job restep <job_id> <failing_step_number>`.
    *   Verify that the command correctly handles and reports the failure of the single step, updating its status in the job state.
    *   Ensure the overall job status remains in a state appropriate for a failed step (e.g., `RUNNING` but with a failed step, or `INTERVENTION_REQUIRED`).

## Demo Features to Add to `test-demo.sh`

The `test-demo.sh` script should be updated to showcase the `job restep` command's capabilities.

*   **Scenario 1: Successful `restep` of an intermediate step**
    *   Create a multi-step test job.
    *   Run the job to a certain point (e.g., `logist job run <job_id>` or `logist job step` several times).
    *   Execute `logist job restep <job_id> <intermediate_step_number>`.
    *   Assert that the command executes and reports success for only that step.
    *   Verify the job's history records the `restep` event for that specific step.
*   **Scenario 2: `restep` a failing step after a hypothetical fix**
    *   Create a job with a step intentionally designed to fail (e.g., a script that exits with an error code).
    *   Run the job until it fails at that step.
    *   Simulate a "fix" (e.g., by modifying the job's script in the workspace using `replace_in_file`).
    *   Execute `logist job restep <job_id> <failing_step_number>`.
    *   Assert that the step now completes successfully.
    *   Verify the job's history and state reflect the updated status of the fixed step.

## Meta-Prompt Instructions
This prompt follows the guidelines in `docs/prompts/_meta_prompt_instructions.md` for execution, success/failure reporting, and Git commit protocols.