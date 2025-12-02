# Job Step Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_step_command` from the Logist master development plan (Phase 3.7). This is the **core execution primitive** that runs single workflow steps using LLM agents, manages state machine transitions, and updates job state. The `logist job step` command is the fundamental execution mechanism that advances jobs through their workflow lifecycle.

## Master Plan Requirements
**Description:** Execute single workflow step with state transition in isolated workspace.
**Objective:** Execute single workflow step with state transition in isolated workspace.
**Scope:** Chdir to workspace, state machine transitions, agent role execution, LLM invocation, `--dry-run` mode, job history recording.
**Dependencies:** Workspace isolation (Phase 3.6) must work. Uses `job_context.py`, `job_processor.py`, `job_state.py`, `workspace_utils.py`, `job_history.py`.
**Files (Read):** `job_manifest.json`, role configs, `$JOB_DIR/workspace/` directory.
**Files (Write):** Updates `job_manifest.json`, writes to workspace, Git commits, `jobHistory.json`.
**Verification:** Advances job state (PENDING→RUNNING→REVIEW_REQUIRED) and commits workspace changes; records interaction in `jobHistory.json`.
**Dependency Metadata:** Core execution engine for `job_run_command`, `job_preview_command`, `job_poststep_command`.

## Implementation Sequence
1.  **Analyze:** Understand state machine, agent selection logic, LLM execution requirements, and job history recording, leveraging `job_state.py`, `job_context.py`, and `job_history.py`.
2.  **Design:** Plan agent selection, context assembly, LLM integration, state management, and history recording, ensuring code reuse from `job_context.py`, `job_processor.py`, etc.
3.  **Build:** Implement CLI command, agent execution pipeline, response processing, state updates, and history recording using the identified reusable functions.
4.  **Integrate:** Connect workspace isolation (`workspace_utils.py`), Git operations (`workspace_utils.perform_git_commit`), file management, and `job_history.record_interaction`.
5.  **Test:** Verify state transitions, LLM responses, error handling, workspace operations, and history recording, including `--dry-run` mode.
6.  **Document:** Update documentation and demo script integration, referencing the underlying utility functions.
7.  **Verify:** Ensure state machine correctness and integration with dependent commands.
8.  **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`.

## Core Implementation Details

### 1. Command Structure and Arguments
```bash
logist job step [JOB_ID] [--dry-run] [--model MODEL]
```

**Key Parameters:**
-   `JOB_ID`: Optional job identifier (uses current if unspecified).
-   `--dry-run`: Skip LLM execution and state changes, show what would be done.
-   `--model`: Override default model selection for agents.

### 2. Agent Selection Logic
-   The command will use `job_state.get_current_state_and_role` to determine which agent (Worker or Supervisor) to execute based on the current job state, adhering to the state machine defined in `04_state_machine.md`.
-   Agent configuration (instructions, model) will be loaded from role manifests.

### 3. Workspace Integration
**Prerequisite Verification:**
-   Ensure `isolation_env_setup` has created `$JOB_DIR/workspace/` directory.
-   Verify workspace contains valid Git clone (`.git` directory exists) using `workspace_utils` functions.
-   Change working directory to workspace for all operations.

**Workspace Context:**
-   Include `.gitignore` patterns (if any).
-   Scan workspace files for context assembly using `workspace_utils.get_workspace_files_summary`.
-   Track evidence files created/modified during step execution.

### 4. LLM Execution Pipeline

#### Context Assembly
-   The `job_context.assemble_job_context` function will be used to build a comprehensive prompt from multiple sources:
    -   **Job Manifest:** Current `job_manifest.json` with status, history, metrics (`job_state.load_job_manifest`).
    -   **Role Configuration:** Complete role JSON (instructions, model, capabilities).
    -   **Workspace Context:** File listings, recent commits, current working state (`workspace_utils.get_workspace_files_summary`, `workspace_utils.get_workspace_git_status`).
    -   **Phase Specifications:** From job manifest's `phases` array for current phase.

#### CLINE Integration
-   Execute LLM using a `cline` call, passing the formatted prompt (from `job_context.format_llm_prompt`) and required file attachments.
-   Implement timeout and monitoring mechanisms.

### 5. LLM Response Processing
-   The `job_processor.process_llm_response` function will be used to handle LLM responses.
-   This function will perform:
    -   JSON schema validation against `logist/schemas/llm-chat-schema.json`.
    -   Validation of `action` semantics (`COMPLETED`/`STUCK`/`RETRY`).
    -   Evidence file existence verification.
    -   Summary length limits.

### 6. State Machine Transitions
-   `job_state.transition_state` will be used to manage state machine transitions based on the LLM response's `action` and the current role, adhering to the logic defined in `04_state_machine.md`.
    -   Worker Agent Flow: PENDING→RUNNING→REVIEW_REQUIRED
    -   Supervisor Agent Flow: REVIEW_REQUIRED→REVIEWING→APPROVAL_REQUIRED/INTERVENTION_REQUIRED
-   Error State Handling: For LLM timeouts, invalid responses, or Git operation failures, transition to `INTERVENTION_REQUIRED` or retry states as defined by the state machine.

### 7. Job Manifest Updates
-   `job_state.update_job_manifest` will be used to update the `job_manifest.json` with:
    -   New `status` based on agent+response.
    -   Potentially advanced `current_phase`.
    -   Updated `metrics` (`cumulative_cost`, `cumulative_time_seconds`).
    -   A new `history` entry for the completed step.

### 8. Git Operations
-   `workspace_utils.perform_git_commit` will be used to:
    -   Stage all `evidence_files` from the LLM response.
    -   Stage any additional workspace changes.
    -   Create a commit with a descriptive message.
-   Handle Git failures gracefully.

### 9. Job History Integration
-   After each successful LLM interaction and post-processing (and if not in `--dry-run` mode), `job_history.record_interaction` will be used to append a new entry to the `jobHistory.json` file.
-   This entry will capture the full request (prompt, `files_context`, `metadata`) and the complete LLM response (`action`, `evidence_files`, `summary_for_supervisor`, `raw_response`), providing a comprehensive audit trail.

### 10. Error Handling and Recovery
-   Leverage a centralized error handling system (as outlined in `prompts/19-error_handling_system.md`) for robust reporting and recovery.
-   **Dry Run Mode:**
    -   When `--dry-run` is specified, the command will assemble the full context and simulate the LLM call and post-processing without making any actual LLM calls, state changes, manifest updates, Git operations, or history recordings.
    -   It will display the assembled prompt, the simulated LLM response (if a mock is used), and the intended state changes.

### 11. Integration Points
-   **Dependent Commands:** `job_step_command` is prerequisite for `job_run_command`, `job_preview_command`, `job_poststep_command`.
-   **Shared Logic:** Leverages `job_context.py`, `job_processor.py`, `job_state.py`, `workspace_utils.py`, `job_history.py`.

### 12. Testing and Validation
-   Unit Testing: Mock LLM responses; test state transitions; verify context assembly; mock Git/history operations.
-   Integration Testing: End-to-end execution (sparingly); test against real workspace; verify file attachments, state persistence, data integrity, and history recording.

## Verification Standards
-   ✅ Advances job through one state transition per execution.
-   ✅ Executes appropriate agent (Worker vs Supervisor) based on state.
-   ✅ Processes LLM responses and updates manifest correctly via `job_processor.process_llm_response` and `job_state.update_job_manifest`.
-   ✅ Commits evidence files and workspace changes to Git via `workspace_utils.perform_git_commit`.
-   ✅ Records LLM interaction in `jobHistory.json` via `job_history.record_interaction`.
-   ✅ Handles failures gracefully with proper error states.
-   ✅ Works with `--dry-run` mode for testing.
-   ✅ Demonstrates proper workspace isolation.
-   ✅ Tests pass with comprehensive mocking.

## Dependencies Check
-   **Master Plan:** Phase 3.7 `job_step_command` requires `isolation_env_setup` (Phase 3.6).
-   **Prerequisites:** Functional CLI, job creation, workspace setup, Git available.
-   **Integration:** Core dependency for execution workflow; relies on new utility modules.
-   **Agent Configs:** Worker and Supervisor role definitions.

## Critical Success Factors

The `job_step_command` is the most complex and critical component, representing the actual AI agent execution and state management. Success requires:

1.  **Reliable LLM Integration:** Robust CLINE calls with proper file handling.
2.  **Deterministic State Management:** Correct transitions per state machine, using `job_state.transition_state`.
3.  **Evidence Tracking:** Accurate file collection and commitment, using `workspace_utils.perform_git_commit`.
4.  **Error Resilience:** Graceful handling of timeouts, invalid responses, Git failures.
5.  **Context Quality:** Comprehensive prompt assembly for high-quality LLM responses, using `job_context.assemble_job_context`.
6.  **History Auditing:** Consistent and complete recording of all interactions in `jobHistory.json` via `job_history.record_interaction`.

Get this foundation right and the rest of the system will work. Fail here and the entire job execution pipeline collapses.

Implement systematically, referencing this comprehensive specification throughout development to ensure rock-solid workflow execution, and leveraging the new utility modules for modularity and reuse.