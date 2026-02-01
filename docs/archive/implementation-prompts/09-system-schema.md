# 09-system-schema.md: Retesting and Integration of System-Level LLM Schema Compliance

## Task Overview
This document guides the **re-testing and integration** of system-level instructions (`system.md`) to ensure LLM agents produce outputs compliant with predefined JSON schemas, specifically `logist/schemas/llm-chat-schema.json`. The focus is on verifying existing implementations and ensuring `system.md` (to be committed near supervisor and worker instructions) effectively guides LLMs towards structured responses. It also details the process for validating these responses and extracting metrics from `cline` oneshot executions.

## Master Plan Requirements
**Description:** Verify existing `system.md` integration for consistent LLM output; re-test output validation and metric extraction from `cline` tasks.
**Objective:** Confirm all LLM responses adhere to `llist/schemas/llm-chat-schema.json` via system instructions and validate the robust process for verifying these outputs and collecting performance metrics.
**Scope:** Verification of `system.md` content and placement (near role instructions), conceptual modification to `execute_llm_with_cline()` for accepting additional instruction files, re-validation of output parsing and validation, and metric extraction from `cline` task metadata.
**Dependencies:** `logist/schemas/llm-chat-schema.json`, `logist/logist/job_processor.py` for `execute_llm_with_cline()` and response parsing/validation.
**Files (Read):** `system.md`, `logist/schemas/llm-chat-schema.json`, `api_conversation_history.json`, `metadata.json` (from `cline` task directory).
**Files (Write):** (This document only)
**Verification:** LLM outputs consistently match `llm-chat-schema.json`; metrics are accurately extracted.

## Implementation Sequence
1.  **Draft `system.md` Instructions:** Create or review a clear, explicit `system.md` that defines the expected JSON output format, intended for placement in `logist/schemas/roles/`.
2.  **Conceptual `execute_llm_with_cline()` Update:** Outline the conceptual changes to `logist/logist/job_processor.py` to allow `execute_llm_with_cline()` to accept an array of instruction files, including `system.md`.
3.  **Refine Output Parsing and Validation:** Detail the steps for extracting the valid JSON response from `cline` task output, prioritizing the first valid JSON found in `api_conversation_history.json` (from most recent to oldest).
4.  **Outline Metric Extraction:** Describe how to obtain token usage, cost, and elapsed time from `cline` task `metadata.json`.
5.  **Re-test and Verify**: Suggest explicit prompts for LLMs and verification steps to confirm schema compliance and metric extraction.
6.  **Document and Integrate:** Update this `09-system-schema.md` file to centralize this knowledge, clearly indicating what is implemented vs. conceptual for future work.

## Core Implementation Details

### 1. `system.md` Instruction Content - Guiding LLM Output
A `system.md` file (to be committed to `logist/schemas/roles/` alongside `worker.json` and `supervisor.json`) will contain high-level instructions to LLMs. Its primary focus is to ensure their final communication adheres to the required JSON schema. This file will be provided to the `cline` command as a `--file` argument, *in addition* to other role-specific instructions.

#### Draft `system.md` Content (for `logist/schemas/roles/system.md`):
```markdown
# System Instructions for LLM Responses

Your primary goal is to provide a structured JSON response at the end of your interaction. This response MUST conform to the `llm-chat-schema.json`.

---
## LLM Chat Schema Requirements (`llm-chat-schema.json`)

Your final output must be a single JSON object with the following fields:

-   **`action`** (string, required): One of "COMPLETED", "STUCK", or "RETRY".
    -   "COMPLETED": The task was successfully finished.
    -   "STUCK": You cannot proceed and require human intervention.
    -   "RETRY": The current approach failed, and you recommend retrying with potentially different parameters.
-   **`evidence_files`** (array of strings, required): A list of relative file paths (from the workspace root) that were modified, created, or are crucial evidence for your work. Include all relevant files.
-   **`summary_for_supervisor`** (string, required): A concise (2-3 sentences) summary of your accomplishments and the current state of the task, intended for a reviewing agent or human.
-   **`job_manifest_url`** (string, optional): A `file://` URI pointing to the `job_manifest.json` if it was modified.

---
## Output Format Example:

```json
{
  "action": "COMPLETED",
  "evidence_files": ["src/main.py", "tests/test_main.py"],
  "summary_for_supervisor": "Implemented the core feature with corresponding unit tests. All tests passed locally, and the solution adheres to design principles."
}
```

Ensure your final response is ONLY this JSON object, wrapped in markdown code fences (```json ... ```). Do not include any conversational text after the JSON.
```

### 2. Implemented Modification to `execute_llm_with_cline()`
The `execute_llm_with_cline()` function in `logist/logist/job_processor.py` **has been enhanced** to accept an optional list of `instruction_files`. It now also extracts the CLINE task ID, reads `api_conversation_history.json` and `metadata.json`, parses the LLM's structured JSON response, and extracts metrics.

#### Implemented Function Signature Update:
```python
def execute_llm_with_cline(
    context: Dict[str, Any],
    model: str = "grok-code-fast-1",
    timeout: int = 300,
    workspace_dir: str = None,
    instruction_files: Optional[List[str]] = None # New parameter
) -> tuple[Dict[str, Any], float]:
    # ... existing logic modified to:
    # 1. Extend `cmd` with `--file` arguments for instruction_files
    # 2. Capture full CLINE output (stdout + stderr)
    # 3. Extract CLINE task ID using regex
    # 4. Construct path to ~/.cline/data/tasks/<task_id>
    # 5. Read api_conversation_history.json and metadata.json
    # 6. Iterate conversation_history in reverse to find first valid JSON via parse_llm_response
    # 7. Extract token usage, cost, and duration from metadata.json
    # 8. Return combined LLM response (action, evidence_files, summary etc.) with metrics and processing metadata.
```
This enables dynamic inclusion of multiple instruction files (e.g., `system.md`, `worker.json`, `supervisor.json`) in a single `cline` call, allowing for layered instruction, and robustly captures/processes the LLM's output and associated metrics.

### 3. Obtaining LLM Output and Metrics from `cline` Task Execution (Implemented)

#### A. Locating the Task Data
The `execute_llm_with_cline` function now:
1.  Executes `cline --oneshot`.
2.  Parses the full output to extract the CLINE `task_id`.
3.  Constructs the path to the CLINE task directory (`~/.cline/data/tasks/<task_id>`).
4.  Verifies the existence of `api_conversation_history.json` and `metadata.json` within that directory.

#### B. Extracting the JSON Response (Implemented)
The `execute_llm_with_cline` function now:
1.  Reads `api_conversation_history.json`.
2.  Iterates through the messages in *reverse chronological order*.
3.  Uses the existing `parse_llm_response` (which includes `validate_llm_response`) to extract and validate the first JSON object found within a message's "content" that conforms to `logist/schemas/llm-chat-schema.json`.

#### C. Validating the Final Summary (Implemented)
The extracted JSON response is validated against `logist/schemas/llm-chat-schema.json` as part of the `parse_llm_response` function, which is now leveraged by `execute_llm_with_cline`.

#### D. Obtaining Token Usage, Cost, and Elapsed Time (Implemented)
The `execute_llm_with_cline` function now:
1.  Reads `metadata.json` from the CLINE task directory.
2.  Extracts `token_counts.input`, `token_counts.output`, `cost_usd`, and `duration_seconds` (using the measured `execution_time` as a fallback for duration).
3.  These metrics are included in the returned `processed_response` dictionary under a `metrics` key.

### 4. Early Iteration and Testing Strategy
For early development and re-testing of `system.md` and the parsing logic:

1.  **Explicit Prompts**: Craft simple prompts that explicitly instruct the LLM to return a specific, schema-compliant JSON response.
    *   **Example Success Prompt**: "Respond only with a JSON object. Set action to 'COMPLETED', summary to 'Test successful.', and evidence_files to an empty array."
    *   **Example Failure Prompt**: "Respond only with a JSON object. Set action to 'STUCK', summary to 'Encountered an unexpected error.', and evidence_files to ['error.log']."
2.  **Execute `cline` Task**: Run the `cline` command with the prompt and the `system.md` file (once it's placed in `logist/schemas/roles/`).
3.  **Verify Output**:
    *   Use the parsing strategy described above to extract the JSON from `api_conversation_history.json`.
    *   Validate the extracted JSON against `logist/schemas/llm-chat-schema.json`.
    *   Confirm that the `action` and `summary_for_supervisor` match the explicit instructions given in the prompt.
4.  **Confirm Metrics**: Verify that `metadata.json` contains reasonable values for token usage, cost, and duration.

This structured approach ensures that the LLM consistently produces valid, schema-compliant outputs and that Logist can reliably parse these outputs and track essential metrics.