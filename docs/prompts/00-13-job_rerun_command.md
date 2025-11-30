# 00-13-job_rerun_command.md

## Task
Implement the `logist job rerun <job_id> [--step <step_number>]` command. This command should allow users to re-execute a previously completed job, or resume a job from a specific step. If `--step` is not provided, the job should rerun from the beginning.

## Intent of `job rerun`
The `job rerun` command is designed to provide flexibility in job execution. It allows users to:
*   **Replay a job:** Execute a job again from the start, for example, to test different environment conditions or parameters.
*   **Resume a failed or interrupted job:** Continue a job from a specific step, avoiding the need to re-run already successful steps. This is crucial for long-running or resource-intensive jobs.
*   **Debug specific steps:** Isolate and re-run particular steps for debugging purposes without affecting the overall job flow unnecessarily.

This command builds upon the existing job execution framework established by `00-12-job_run_command.md` and leverages the job state management and history tracking.

## Implementation Advice

### Core Logic
The `job rerun` command will largely reuse the core job processing logic found in `logist/job_processor.py`. The primary differences will be in how the starting state is determined:

1.  **Job Loading:** The command will need to load the existing job manifest and its associated state using the provided `<job_id>`. This will involve `logist/job_state.py` for reading the current state.
2.  **Starting Step Determination:**
    *   If `--step <step_number>` is provided, the job processor should be instructed to start execution from that specific step. All previous steps will be considered "completed" or "skipped" for the purpose of the rerun, though their history might still be available depending on how `job_history.py` is updated.
    *   If `--step` is not provided, the job should reset its execution pointer to the very first step, effectively re-running the entire job.
3.  **State Management:** During a rerun, the job's state will need to be carefully managed. A rerun should ideally create a new "run" entry in the job's history, rather than overwriting the previous run's history, to preserve a clear audit trail of all executions. This implies careful interaction with `logist/job_history.py` to record new run attempts. The current active state of the job should reflect the rerun, allowing for its progress to be tracked independently.
4.  **CLI Integration:** Integrate `rerun` as a subcommand under `logist job`. It should accept the `job_id` as a required argument and `--step` as an optional integer argument.

### Source Code Paths Likely Used
*   `logist/cli.py`: Command registration (`@click.command()`, `@click.argument()`, `@click.option()`) for `job rerun` and its arguments. This will be the entry point.
*   `logist/job_processor.py`: The `JobProcessor` class will likely need modifications or a new method (`rerun_job` or similar) to handle the logic of starting from an arbitrary step or from the beginning, based on an existing job's state. It will coordinate the execution of steps.
*   `logist/job_state.py`: Used to load the existing job's state, possibly reset it (if rerunning from start), and manage its persistence throughout the rerun.
*   `logist/job_history.py`: Crucial for recording multiple runs of the same job. A rerun should append a new run record rather than modify an old one. This might require adding new methods to `JobHistoryManager` to properly manage rerun attempts.
*   `logist/workspace_utils.py`: For locating job directories and managing workspace paths.

## Unit Tests to Add

Unit tests should be added to `tests/test_cli.py` and potentially `tests/test_job_processor.py` (if new core logic is introduced there).

*   **`test_rerun_command_registered`**: Verify that `logist job rerun` is a recognized command.
*   **`test_rerun_requires_job_id`**: Ensure the command fails if `job_id` is not provided.
*   **`test_rerun_non_existent_job`**: Test appropriate error handling for a `job_id` that does not exist.
*   **`test_rerun_job_from_start`**:
    *   Run a job to completion.
    *   Execute `logist job rerun <job_id>`.
    *   Verify that the job runs from its first step and completes successfully.
    *   Check `job_history.py` to ensure a new run entry is created.
*   **`test_rerun_job_from_specific_step`**:
    *   Run a job, possibly with `logist job step` or manually advance it to a certain point.
    *   Execute `logist job rerun <job_id> --step <N>`.
    *   Verify that the job resumes execution correctly from step `N`.
    *   Verify that steps before `N` are not re-executed by the job processor.
    *   Check `job_history.py` for correct recording of the resumed run.
*   **`test_rerun_invalid_step_number`**: Test error handling when `--step` is out of bounds (e.g., negative, greater than total steps).
*   **`test_rerun_with_modified_parameters` (Optional, Advanced)**: Consider how to handle reruns with new parameters if this feature is desired for future iterations (e.g., `--param key=value`). This might involve creating a new job state or modifying the existing one for the rerun.

## Demo Features to Add to `test-demo.sh`

The `test-demo.sh` script should be updated to showcase the `job rerun` command's capabilities.

*   **Scenario 1: Full Rerun**
    *   Create a simple test job.
    *   Run the job to completion using `logist job run <job_id>`.
    *   Assert its completion.
    *   Execute `logist job rerun <job_id>`.
    *   Assert that the job runs again and completes, verifying two distinct entries in job history (e.g., by checking a log file or `job_history.py` directly).
*   **Scenario 2: Resuming a Job**
    *   Create a multi-step test job.
    *   Run the job for a few steps (e.g., using `logist job step`).
    *   Simulate an interruption (e.g., by not completing all steps).
    *   Execute `logist job rerun <job_id> --step <N>` where N is a step after the last completed one.
    *   Assert that the job completes from step N onwards.
    *   Verify history records the resumed run.
*   **Scenario 3: Rerun after failure (optional)**
    *   Create a job that is designed to fail at a certain step.
    *   Run the job, observe failure.
    *   Hypothetically "fix" the issue (e.g., by modifying a file).
    *   Rerun the job from the failed step (`logist job rerun <job_id> --step <failing_step>`).
    *   Assert that it now completes successfully.

## Meta-Prompt Instructions
This prompt follows the guidelines in `docs/prompts/_meta_prompt_instructions.md` for execution, success/failure reporting, and Git commit protocols.