# Job Preview Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_preview_command` from the Logist master development plan (Phase 3.8). This feature shows the exact prompts that would be sent to LLM agents **without executing them**, enabling users to inspect, debug, and validate context assembly before actual job execution. `job_preview_command` serves as the **dry-run inspection tool** for the Logist workflow system.

## Master Plan Requirements
**Description:** Show next agent prompt without execution
**Objective:** Show next agent prompt without execution
**Scope:** Prompt generation, task context assembly from isolated workspace, no state changes
**Dependencies:** Workspace isolation (Phase 3.6), step preparation logic (Phase 3.7 job_step_command)
**Files (Read):** `job_manifest.json`, role configs, `$JOB_DIR/workspace/` content
**Files (Write):** Console output only (no state changes, no file modifications)
**Verification:** Displays formatted prompts for Worker/Supervisor execution using workspace context
**Dependency Metadata:** Debugging/inspection tool (no dependents)

## Implementation Sequence
1. **Analyze:** Understand agent selection logic and context assembly requirements
2. **Design:** Plan preview-only execution without state changes or LLM calls
3. **Build:** Implement CLI command with workspace integration and context display
4. **Integrate:** Connect with job_step_command logic but skip execution components
5. **Test:** Verify accurate prompt generation and workspace context inclusion
6. **Document:** Add display formatting and usage examples
7. **Verify:** Ensure preview matches what job_step would actually send to LLMs
8. **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`

## Core Implementation Details

### 1. Command Structure and Arguments
```bash
logist job preview [JOB_ID] [--role ROLE] [--phase PHASE_NAME] [--format FORMAT]
```

**Key Arguments:**
- `JOB_ID`: Optional job identifier (uses current if unspecified)
- `--role ROLE`: Override agent selection to preview specific role (worker/supervisor)
- `--phase PHASE_NAME`: Override to preview specific phase instead of current
- `--format FORMAT`: Output format (human-readable, json-files, or raw-context)

### 2. Agent Selection Logic
**Normally follows job_step_command logic:**
- If `REVIEW_REQUIRED/REVIEWING` state → Supervisor agent
- If `PENDING/RUNNING` states → Worker agent

**But --role override allows:**
- `--role worker` → Always show Worker prompt
- `--role supervisor` → Always show Supervisor prompt
- Automatic fallback if role not applicable for current state

### 3. Workspace Integration
**Prerequisite Verification:**
- Ensure `isolation_env_setup` has created valid workspace
- Change to workspace directory for accurate context
- Validate workspace Git state and file presence

**Workspace Context Gathering:**
```python
context = {
    "files": scan_workspace_files(),
    "git_status": get_git_status(),
    "recent_commits": get_recent_history(),
    "file_changes": detect_modified_files(),
    "structure": get_directory_structure()
}
```

### 4. Context Assembly (Similar to job_step_command)

**Required Context Components:**
1. **Job Manifest Context:**
   - Current status, phase, metrics, history
   - Job specifications and configuration
   - Evidence files from previous phases

2. **Role Configuration:**
   - Agent instructions, model, capabilities
   - Phase-specific guidance (if applicable)
   - Response format requirements

3. **Workspace State:**
   - File listings and directory structure
   - Git history and status
   - Relevant files for current phase
   - `.gitignore` patterns (to exclude irrelevant files)

4. **Phase-Specific Context:**
   - Current phase definition and objectives
   - Previous phase outcomes and evidence
   - Success criteria and requirements

**Context Processing:**
- Clean file paths relative to workspace
- Filter out irrelevant files (.git, __pycache__, etc.)
- Limit file content size for practicality
- Include relevant metadata (file sizes, modification dates)

### 5. Prompt Formulation

**Prompt Structure:**
```
You are the [AGENT_NAME] agent.

[ROLE_INSTRUCTIONS]

Current Job Context:
- Job ID: [job_id]
- Current Phase: [phase_name]
- Status: [status]
- Previous Work: [summary of completed phases]

Workspace Files:
[List of relevant files with summaries]

Task:
[Phase-specific instructions and objectives]

Response Format:
[JSON schema requirements for validation]
```

**Format Options:**
- **Human-readable:** Formatted markdown for console display
- **JSON-files:** Structured JSON with file contents and metadata
- **Raw-context:** Complete context object without LLM prompt formatting

### 6. Display and Formatting

**Human-Readable Output Example:**
```
🚀 Logist Job Preview: [job_id]

📋 Agent: Worker (for PENDING → RUNNING transition)
🤖 Model: gpt-4-turbo

📝 Task: requirements_analysis
Complete analysis with specification document

📁 Workspace Context:
├── src/
│   ├── main.py (42 lines)
│   └── utils.py (28 lines)
├── tests/
│   └── test_basic.py (15 lines)
└── README.md (Currently empty)

📋 Previous Phase Outcome:
⚠️  No previous phases completed

🔧 File Attachments for LLM:
- /path/to/job_manifest.json (current state)
- /path/to/worker.json (role configuration)
- /path/to/workspace_context.txt (file summaries)

🎯 Would Execute: logist job step [job_id]

LLM Prompt Preview:
---
[Formatted LLM prompt would appear here]
---
```

### 7. Validation and Verification

**Prompt Completeness Checks:**
- All required context components present
- File paths exist and are accessible
- Role configuration loaded correctly
- Phase definition valid and complete

**Comparison with job_step:**
- Generate what job_step would send to LLM
- Validate file attachment paths match
- Ensure context accuracy without execution
- Catch configuration issues before actual runs

### 8. Error Handling

**Workspace Issues:**
- Workspace not created → Clear error with setup instructions
- Invalid Git state → Report but continue with available context
- Permission issues → Warn about access limitations

**Configuration Errors:**
- Missing role configs → Fallback or clear error message
- Invalid phase references → List available phases
- Job not found → Standard error handling

### 9. Integration Points

**Relationship to job_step_command:**
- **Shares context assembly logic** (reuse code)
- **Uses same agent selection** (validate consistency)
- **Reads same configurations** (ensure alignment)
- **Complements dry-run functionality** in job_step

**Other Command Relationships:**
- **job_status:** Shows current state (preview depends on this)
- **job_list/job_select:** Job identification and selection
- **isolation_env_setup:** Workspace prerequisite

### 10. Testing and Validation

**Unit Testing:**
- Mock workspace contexts and configurations
- Test various job states and phase transitions
- Validate output formatting options
- Error handling for edge cases

**Integration Testing:**
- Compare preview output with actual job_step execution
- Test against different workspace states
- Verify file attachment accuracy
- Cross-platform path handling

**Demo Script Integration:**
- Add preview after workspace setup
- Demonstrate before/after job_step execution
- Show different format options
- Validate context completeness

## Verification Standards
- ✅ Shows complete context that job_step would use for execution
- ✅ Agent selection matches job_step_command logic
- ✅ Workspace files and metadata accurately represented
- ✅ Display formatting clear and informative
- ✅ No state changes or file modifications during preview
- ✅ Multiple format options (human, json, raw) supported
- ✅ Error handling provides clear debugging information
- ✅ Preview context matches actual execution context

## Dependencies Check
- **Master Plan:** Phase 3.8 job_preview_command
- **Dependencies:** isolation_env_setup (Phase 3.6), job_step_command logic (Phase 3.7)
- **Prerequisites:** CLI works, job creation/management functional
- **Integration:** Shares logic with job_step_command, depends on workspace

## Strategic Value

**job_preview_command serves as:**
- **Quality Assurance Tool:** Validate context before expensive LLM calls
- **Debugging Utility:** Inspect what agents will receive
- **Learning Tool:** Understand how Logist constructs agent prompts
- **Development Aid:** Test context assembly without execution costs

## Critical Implementation Notes

**Success Metric:** A user should be able to run `logist job preview`, see exactly what the next agent will receive, and have complete confidence about what `logist job step` will do without any surprises.

**Architecture Pattern:** This command establishes the **context assembly pattern** that job_step_command will rely on, making it an essential prototype for the more complex execution workflow.

**User Experience:** Make the preview output so informative and clear that users naturally reach for this command during development and debugging workflows.

Implement systematically, ensuring preview accuracy matches job_step execution exactly to build user trust in the dry-run functionality.</result>