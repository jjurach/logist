# Job Preview Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_preview_command` from the Logist master development plan (Phase 3.8). This feature shows the exact prompts that would be sent to LLM agents **without executing them**, enabling users to inspect, debug, and validate context assembly before actual job execution. `job_preview_command` serves as the **dry-run inspection tool** for the Logist workflow system.

## Master Plan Requirements
**Description:** Show next agent prompt without execution.
**Objective:** Show next agent prompt without execution.
**Scope:** Prompt generation, task context assembly from isolated workspace, no state changes, no LLM calls.
**Dependencies:** Workspace isolation (Phase 3.6), state machine logic (via `job_state.get_current_state_and_role`), context assembly logic (via `job_context.assemble_job_context`).
**Files (Read):** `job_manifest.json`, role configs, `$JOB_DIR/workspace/` content. `jobHistory.json` (for context/auditing).
**Files (Write):** Console output only (no state changes, no file modifications, no history recording).
**Verification:** Displays formatted prompts for Worker/Supervisor execution using workspace context; ensures no side effects.
**Dependency Metadata:** Debugging/inspection tool (no dependents).

## Implementation Sequence
1.  **Analyze:** Understand agent selection logic and context assembly requirements, leveraging `job_state.get_current_state_and_role` and `job_context.assemble_job_context`.
2.  **Design:** Plan preview-only execution without state changes or LLM calls, focusing on efficient context display.
3.  **Build:** Implement CLI command with workspace integration and context display, utilizing `job_context.assemble_job_context` and `job_context.format_llm_prompt`.
4.  **Integrate:** Connect with job selection logic and context assembly, ensuring no execution components are triggered.
5.  **Test:** Verify accurate prompt generation and workspace context inclusion for various job states and roles.
6.  **Document:** Add display formatting and usage examples, referencing the underlying utility functions.
7.  **Verify:** Ensure preview matches what `job_step_command` would actually send to LLMs.
8.  **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`.

## Core Implementation Details

### 1. Command Structure and Arguments
```bash
logist job preview [JOB_ID] [--role ROLE] [--phase PHASE_NAME] [--format FORMAT]
```

**Key Arguments:**
-   `JOB_ID`: Optional job identifier (uses current if unspecified).
-   `--role ROLE`: Override agent selection to preview specific role (worker/supervisor).
-   `--phase PHASE_NAME`: Override to preview specific phase instead of current.
-   `--format FORMAT`: Output format (human-readable, json-files, or raw-context).

### 2. Agent Selection Logic
-   Uses `job_state.get_current_state_and_role` to determine the active agent (Worker or Supervisor) based on the current job state.
-   The `--role` override allows forcing the preview for a specific role.

### 3. Workspace Integration
**Prerequisite Verification:**
-   Ensure `isolation_env_setup` has created valid workspace.
-   Change to workspace directory for accurate context.
-   Validate workspace Git state and file presence (using `workspace_utils` functions).

**Workspace Context Gathering:**
-   Leverages `job_context.assemble_job_context` to gather comprehensive context, including files, Git status, recent commits, file changes, and directory structure. This function will internally use `workspace_utils` functions for file and Git information.

### 4. Context Assembly (Shared with `job_step_command`)
-   The core logic for building the LLM prompt context is encapsulated in `job_context.assemble_job_context`.
-   This function incorporates:
    1.  **Job Manifest Context:** Current status, phase, metrics, history (`job_state.load_job_manifest`).
    2.  **Role Configuration:** Agent instructions, model, capabilities (from role manifests).
    3.  **Workspace State:** File listings, Git history/status (`workspace_utils.get_workspace_files_summary`, `workspace_utils.get_workspace_git_status`).
    4.  **Phase-Specific Context:** Current phase definition and objectives.

### 5. Prompt Formulation
-   The assembled context is formatted into the final LLM prompt string using `job_context.format_llm_prompt`. This function ensures the prompt structure adheres to defined guidelines.

### 6. Display and Formatting
-   The command outputs the formatted prompt and relevant context based on the `--format` argument.
-   **Human-readable:** Formatted markdown for console display.
-   **JSON-files:** Structured JSON with file contents and metadata.
-   **Raw-context:** Complete context object without LLM prompt formatting.

### 7. Validation and Verification
-   Prompt completeness checks: all required context components present, file paths exist, role configuration loaded correctly, phase definition valid.
-   No state changes: `job_preview_command` must ensure it has no side effects on `job_manifest.json` or the Git repository.

### 8. Error Handling
-   Workspace Issues: Report errors if workspace not created or in an invalid state.
-   Configuration Errors: Handle missing role configs or invalid phase references.
-   Job not found: Standard error handling.

### 9. Integration Points
-   **Shares context assembly logic** with `job_step_command` through `job_context.assemble_job_context` and `job_context.format_llm_prompt`.
-   Uses `job_state.get_current_state_and_role` for agent selection.
-   Relies on `workspace_utils` for workspace introspection.
-   Complements `job_step_command` (as its dry-run) and `job_poststep_command`.

### 10. Testing and Validation
-   Unit testing: Mock workspace contexts and configurations; test various job states and role selections; validate output formatting options; test error handling for edge cases.
-   Integration testing: Compare preview output with actual context prepared for `job_step_command` execution.

## Verification Standards
-   ✅ Shows complete context that `job_step_command` would use for execution.
-   ✅ Agent selection matches `job_step_command` logic.
-   ✅ Workspace files and metadata accurately represented, utilizing `workspace_utils`.
-   ✅ Display formatting clear and informative.
-   ✅ No state changes, file modifications, or history recording during preview.
-   ✅ Multiple format options (human, json, raw) supported.
-   ✅ Error handling provides clear debugging information.
-   ✅ Preview context matches actual execution context prepared by `job_context.assemble_job_context`.

## Dependencies Check
-   **Master Plan:** Phase 3.8 `job_preview_command`.
-   **Dependencies:** `isolation_env_setup` (Phase 3.6), `job_step_command` logic (Phase 3.7), `job_context.py`, `job_state.py`, `workspace_utils.py`.
-   **Prerequisites:** CLI works, job creation/management functional.
-   **Integration:** Shares logic with `job_step_command`, depends on workspace utilities.

## Strategic Value

`job_preview_command` serves as:
-   **Quality Assurance Tool:** Validate context before expensive LLM calls.
-   **Debugging Utility:** Inspect what agents will receive.
-   **Learning Tool:** Understand how Logist constructs agent prompts.
-   **Development Aid:** Test context assembly without execution costs.

## Critical Implementation Notes

**Success Metric:** A user should be able to run `logist job preview`, see exactly what the next agent will receive, and have complete confidence about what `logist job step` will do without any surprises.

**Architecture Pattern:** This command establishes the **context assembly pattern** that `job_step_command` will rely on, making it an essential prototype for the more complex execution workflow, and leverages shared utility functions from `job_context.py`, `job_state.py`, and `workspace_utils.py`.