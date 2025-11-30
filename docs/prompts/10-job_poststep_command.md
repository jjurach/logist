# Job Poststep Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_poststep_command` from the Logist master development plan (Phase X.X). This command processes a **simulated or manually provided LLM response** as if it were the output of a `job_step_command` execution. It applies the full post-LLM processing pipeline, including state machine transitions, job manifest updates, and Git operations, **without making an actual LLM call**. This tool is crucial for debugging the post-LLM processing logic, allowing for manual intervention in workflows, and for testing state machine advancements with specific LLM outputs.

## Master Plan Requirements
**Description:** Process a simulated LLM response to advance job state and apply post-execution effects.
**Objective:** Advance job state and apply post-execution effects based on a provided LLM response without LLM invocation.
**Scope:** LLM response validation, state machine transitions, job manifest updates, Git commits based on simulated output.
**Dependencies:** Workspace isolation (Phase 3.6), `job_step_command` post-LLM processing logic.
**Files (Read):** `job_manifest.json`, role configs, provided LLM response (JSON). `jobHistory.json` (for context/auditing).
**Files (Write):** Updates `job_manifest.json`, writes to workspace (if evidence files are simulated), Git commits, `jobHistory.json` (to record simulated interactions).
**Verification:** Advances job state (e.g., RUNNING→REVIEW_REQUIRED) and commits simulated workspace changes based on the provided response; records interaction in `jobHistory.json`.
**Dependency Metadata:** Supports debugging and manual intervention in `job_run_command` workflows.

## Implementation Sequence
1.  **Analyze:** Understand the post-LLM processing pipeline within `job_step_command`.
2.  **Design:** Plan how to decouple LLM invocation from response processing, state management, and Git operations. Identify reusable functions like `job_processor.process_llm_response`, `job_state.transition_state`, `job_state.update_job_manifest`, `workspace_utils.perform_git_commit`, and `job_history.record_interaction`.
3.  **Build:** Implement CLI command to accept an LLM response (file path or string) and trigger the post-LLM processing logic using the identified reusable functions.
4.  **Integrate:** Connect with workspace isolation, Git operations, file management, and job history recording, ensuring consistent state updates as `job_step_command`.
5.  **Test:** Verify state transitions, job manifest updates, Git commits, error handling, and history recording with various simulated LLM responses, including `--dry-run` functionality.
6.  **Document:** Update documentation with usage examples for debugging and manual intervention.
7.  **Verify:** Ensure `job_poststep_command` accurately mimics the post-LLM effects of `job_step_command`.
8.  **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`.

## Core Implementation Details

### 1. Command Structure and Arguments
```bash
logist job poststep [JOB_ID] --response-file PATH_TO_JSON | --response-string JSON_STRING [--role ROLE] [--dry-run]
```

**Key Arguments:**
-   `JOB_ID`: Optional job identifier (uses current if unspecified).
-   `--response-file PATH_TO_JSON`: Path to a JSON file containing the simulated LLM response.
-   `--response-string JSON_STRING`: A direct JSON string representing the simulated LLM response.
-   `--role ROLE`: Optional: Specify the agent role (worker/supervisor) for context during state transitions. If not provided, the command will infer the role based on the job's current state using `job_state.get_current_state_and_role`.
-   `--dry-run`: If this flag is present, the command will parse the input and output what it *would* do (manifest updates, Git operations, history recording) but will not perform any actual state changes or file modifications.

### 2. Simulated LLM Response Processing
The core of this command is to take an external LLM response and feed it into the existing `job_step_command`'s post-LLM processing logic, primarily through `job_processor.process_llm_response`.

#### Response Schema Compliance
The provided LLM response (via file or string) *must* conform to `logist/schemas/llm-chat-schema.json`.

**Required Response Fields (as per `job_step_command` and `02_roles_and_data.md`):**
```json
{
  "action": "COMPLETED" | "STUCK" | "RETRY",
  "evidence_files": ["path/to/file1", "path/to/file2"],
  "summary_for_supervisor": "Brief assessment of work done",
  "job_manifest_url": "file:///path/to/manifest" // optional
}
```

#### Response Validation
-   Perform JSON schema validation against `llm-chat-schema.json` using appropriate validation utilities.
-   Validate action semantics (COMPLETED/STUCK/RETRY).
-   Verify `summary_for_supervisor` length limits.
-   Evidence file existence verification can be conditional; for simulated files, their actual presence on the filesystem might not be strictly necessary, but their paths should be valid relative to the workspace.

### 3. State Machine Transitions
-   The command will use `job_state.transition_state` to apply the same state machine transitions as `job_step_command`, based on the provided LLM response's `action` and the job's current state.
    -   Worker Agent Flow: PENDING→RUNNING→REVIEW_REQUIRED
    -   Supervisor Agent Flow: REVIEW_REQUIRED→REVIEWING→APPROVAL_REQUIRED/INTERVENTION_REQUIRED
-   Properly handle error states resulting from the simulated response (e.g., if the response indicates `STUCK` or `RETRY`).

### 4. Job Manifest Updates
-   The command will use `job_state.update_job_manifest` to update the `job_manifest.json` with the new status, potentially advancing `current_phase`.
-   It will append a new history entry (internally to the manifest, and also to `jobHistory.json` as described below) based on the simulated response, including the `action`, `summary_for_supervisor`, and `evidence_files`.
-   Crucially, **cost and time metrics will not be updated** as no actual LLM call occurred. This should be explicitly documented.

### 5. Git Operations
-   The command will use `workspace_utils.perform_git_commit` to stage `evidence_files` (if they exist or are simulated for effect) and create a commit with a descriptive message reflecting the simulated action and summary, when not in `--dry-run` mode.
-   Handle Git failures gracefully, similar to `job_step_command`.

### 6. Job History Integration
-   When not in `--dry-run` mode, `job_poststep_command` will use `job_history.record_interaction` to append a new entry to the `jobHistory.json` file. This entry will capture the details of the simulated LLM request (if a template is used or inferred) and the provided LLM response.
-   The `is_simulated` flag in `record_interaction` should be set to `True` to clearly distinguish these entries from actual LLM executions.
-   This provides an audit trail for manual interventions and testing scenarios.

### 7. Dry Run Mode
-   When `--dry-run` is specified, the command will proceed with parsing and validation but will **skip all operations that modify the job manifest (`job_state.update_job_manifest`), Git history (`workspace_utils.perform_git_commit`), or the `jobHistory.json` file (`job_history.record_interaction`).**
-   Instead, it will output a clear description of:
    -   How the LLM response was parsed and validated.
    -   What state transition *would* occur.
    -   What updates *would* be made to `job_manifest.json`.
    -   What Git operations (staging, committing) *would* be performed.
    -   What interaction *would* be recorded in `jobHistory.json`.
-   This mode is for inspection and verification only, ensuring the logic is correct before making irreversible changes.

### 8. Error Handling
-   Invalid JSON input: Clear error message.
-   Non-compliant schema: Report validation errors.
-   Job not found: Standard error handling.
-   Workspace issues: Verify `isolation_env_setup` has run.

### 9. Integration Points
-   **Shares post-LLM processing logic** with `job_step_command` through functions in `job_processor.py`, `job_state.py`, `workspace_utils.py`.
-   Depends on `job_status`, `job_list`, `job_select` for job identification.
-   Relies on `isolation_env_setup` for workspace context.

## Verification Standards
-   ✅ Advances job through one state transition based on simulated response.
-   ✅ Updates `job_manifest.json` with new state and history via `job_state.update_job_manifest`.
-   ✅ Commits simulated evidence files and workspace changes to Git via `workspace_utils.perform_git_commit` (if applicable).
-   ✅ Records simulated interaction in `jobHistory.json` via `job_history.record_interaction`.
-   ✅ Handles failures gracefully with proper error states.
-   ✅ Processes LLM responses according to `llm-chat-schema.json` validation.
-   ✅ No actual LLM calls are made, and cost/time metrics are not updated.
-   ✅ `--dry-run` option correctly prevents state changes and outputs intended actions.

## Dependencies Check
-   **Master Plan:** Phase X.X for `job_poststep_command`.
-   **Prerequisites:** Functional CLI, job creation, workspace setup, Git available.
-   **Integration:** Relies on core post-LLM processing from `job_step_command`, using shared utility functions.

## Strategic Value

`job_poststep_command` serves as:
-   **Debugging Utility:** Isolate and debug the complex post-LLM processing logic of `job_step_command`.
-   **Manual Intervention Tool:** Allows users to manually advance or modify job states by providing a custom LLM response, effectively "forcing" a state transition.
-   **Testing Aid:** Facilitates unit and integration testing of the state machine and job manifest updates without incurring LLM costs or waiting for real LLM responses.

## Critical Implementation Notes

**Success Metric:** A user should be able to provide a valid LLM response to `logist job poststep`, and observe the job manifest update and Git history change, and `jobHistory.json` recording exactly as if a real LLM call had produced that response through `logist job step`. The `--dry-run` option provides confidence that this logic is sound before applying changes.

**Architecture Pattern:** This command strongly leverages the existing robust post-LLM processing architecture of `job_step_command`, promoting code reuse and consistency through shared utility functions.