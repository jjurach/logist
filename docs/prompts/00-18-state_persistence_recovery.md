# 💾 00-18-state_persistence_recovery.md: State Persistence and Recovery System

This prompt details the implementation of a robust state persistence and recovery system for Logist jobs. The goal is to ensure that Logist workflows can be reliably interrupted and resumed, maintaining integrity and continuity across executions.

---

### **Reference:**
This prompt follows the guidelines outlined in `docs/prompts/_meta_prompt_instructions.md` for execution and `AGENTS.md` for Git commit conventions.

---

## 1. 💡 Implementation Advice

The core of state persistence and recovery revolves around the `job_manifest.json` file and the `logist/job_state.py` module.

*   **Centralized State Management**: `logist/job_state.py` is the designated module for all operations related to reading, updating, and transitioning job states.
*   **Manifest Loading**: At the initiation of any Logist job operation (e.g., `logist job run`, `logist job step`), the `job_manifest.json` will be loaded using `logist.job_state.load_job_manifest()`.
*   **Atomic Updates**: To prevent data corruption during state changes, all updates to `job_manifest.json` should be atomic. This can be achieved by:
    1.  Writing the new manifest content to a temporary file in the job's directory.
    2.  Renaming (moving) the temporary file to `job_manifest.json`, overwriting the old one. This ensures that a partially written file never replaces the valid manifest. The `logist.job_state.update_job_manifest` function should encapsulate this logic.
*   **State Transitions**: All state changes must occur through `logist.job_state.transition_state()`. This function ensures that only valid transitions, as defined in `docs/04_state_machine.md`, are permitted. Any attempt at an invalid transition should raise a `JobStateError`.
*   **Recovery Logic**: When a job resumes, the system should read the `status` field from `job_manifest.json` to determine the exact point of interruption and proceed accordingly. This might involve re-executing a previous step or transitioning to an intervention state if an agent was "stuck".

## 2. 📁 Relevant Source Code Paths

The following files are expected to be modified or created as part of this implementation:

*   **`logist/job_state.py`**: This module will contain the core logic for:
    *   Loading (`load_job_manifest`).
    *   Saving (`update_job_manifest`).
    *   Retrieving current state and role (`get_current_state_and_role`).
    *   Handling state transitions (`transition_state`).
    *   Implementing atomic file writes for `job_manifest.json`.
*   **`logist/job_processor.py`**: This module orchestrates the job execution and will integrate `logist/job_state.py` to:
    *   Load the initial job state before processing.
    *   Update the job manifest with new states and metrics after each processing step.
*   **`logist/cli.py`**: The command-line interface will utilize `logist/job_state.py` to:
    *   Read job status for commands like `logist job status`.
    *   Update job states based on user commands (`logist job rerun`, `logist job restep`) or agent actions (`logist job step`).
*   **`tests/test_cli.py`**: Existing CLI tests will need to be reviewed and potentially updated to reflect changes in state management.
*   **`tests/test_job_state.py` (New File)**: A dedicated test file will be created for `logist/job_state.py` to thoroughly test its functionalities.
*   **`test-demo.sh`**: The main demo script will be updated to showcase state persistence and recovery.

## 3. 🧪 Unit Tests and Demo Features

### Unit Tests (`tests/test_job_state.py` or `tests/test_cli.py`)

*   **`test_load_job_manifest`**:
    *   Verify successful loading of a valid `job_manifest.json`.
    *   Test error handling for a missing `job_manifest.json` (raises `JobStateError`).
    *   Test error handling for a malformed JSON file (raises `JobStateError`).
*   **`test_get_current_state_and_role`**:
    *   Verify correct extraction of `current_phase` and `active_agent` for various valid manifests.
    *   Test error handling for manifests missing `current_phase` or `phases`.
*   **`test_transition_state`**:
    *   Test all valid state transitions as defined in `docs/04_state_machine.md`.
    *   Verify that `JobStateError` is raised for invalid or undefined transitions.
    *   Ensure proper handling of "STUCK" and "RETRY" actions leading to correct recovery states.
*   **`test_update_job_manifest`**:
    *   Verify that `update_job_manifest` correctly updates status, phase, cumulative cost, and time.
    *   Ensure history entries are correctly appended with timestamps.
    *   Test the atomic update mechanism to ensure data integrity.
    *   Verify that the manifest file is only written when modifications occur.

### Demo Features (`test-demo.sh`)

The `test-demo.sh` script will be enhanced to illustrate the persistence and recovery capabilities:

1.  **Simulate Interruption**: Introduce a point in the `test-demo.sh` script where a `logist job run` or `logist job step` command is executed, followed by a simulated interruption (e.g., using `kill` or a controlled exit) before the job naturally completes.
2.  **Verify State after Interruption**: After the interruption, use `logist job status` to confirm that the job's state in `job_manifest.json` accurately reflects the point of interruption (e.g., "RUNNING", "REVIEWING", or "INTERVENTION_REQUIRED").
3.  **Resume Job**: Demonstrate resuming the job using the appropriate Logist CLI commands based on the interrupted state:
    *   If `RUNNING` or `REVIEWING` was interrupted, running `logist job step` again should pick up from where it left off, potentially leading to an "INTERVENTION_REQUIRED" if the agent was "stuck".
    *   If the job was in `INTERVENTION_REQUIRED`, demonstrate how a `logist job rerun` or similar command would reset it to a `PENDING` state.
4.  **Full Job Completion**: Ensure the demo script can successfully guide the job through to a `SUCCESS` state, even after one or more interruptions and recoveries.

## 4. ✅ Verification Standards

*   All unit tests for `logist/job_state.py` pass.
*   The `test-demo.sh` script successfully demonstrates a job being interrupted and then recovered to completion.
*   `job_manifest.json` accurately reflects state changes at all points of a job's lifecycle, including after interruptions.
*   Invalid state transitions attempted via API calls or mock scenarios raise `JobStateError`.