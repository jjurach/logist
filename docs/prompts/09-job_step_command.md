# Job Step Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_step_command` from the Logist master development plan (Phase 3.7). This is the **core execution primitive** that runs single workflow steps using LLM agents, manages state machine transitions, and updates job state. The `logist job step` command is the fundamental execution mechanism that advances jobs through their workflow lifecycle.

## Master Plan Requirements
**Description:** Execute single workflow step with state transition in isolated workspace
**Objective:** Execute single workflow step with state transition in isolated workspace
**Scope:** Chdir to workspace, state machine transitions, agent role execution, --dry-run mode
**Dependencies:** Workspace isolation (Phase 3.6) must work
**Files (Read):** `job_manifest.json`, role configs, `$JOB_DIR/workspace/` directory
**Files (Write):** Updates `job_manifest.json`, writes to workspace, Git commits
**Verification:** Advances job state (PENDING→RUNNING→REVIEW_REQUIRED) and commits workspace changes
**Dependency Metadata:** Core execution engine for job_run_command, job_preview_command, job_poststep_command

## Implementation Sequence
1. **Analyze:** Understand state machine, agent selection logic, and LLM execution requirements
2. **Design:** Plan agent selection, context assembly, LLM integration, and state management
3. **Build:** Implement CLI command, agent execution pipeline, response processing, and state updates
4. **Integrate:** Connect workspace isolation, Git operations, and file management
5. **Test:** Verify state transitions, LLM responses, error handling, and workspace operations
6. **Document:** Update documentation and demo script integration
7. **Verify:** Ensure state machine correctness and integration with dependent commands
8. **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`

## Core Implementation Details

### 1. Command Structure and Arguments
```bash
logist job step [JOB_ID] [--dry-run] [--model MODEL]
```

**Key Parameters:**
- `JOB_ID`: Optional job identifier (uses current if unspecified)
- `--dry-run`: Skip LLM execution and show what would be done
- `--model`: Override default model selection for agents

### 2. Agent Selection Logic
The command must determine which agent to execute based on current job state:

**State → Agent Mapping:**
- `PENDING/RUNNING/SUCCESS` (but PENDING always transitions to RUNNING): **Worker** agent
- `REVIEW_REQUIRED/REVIEWING`: **Supervisor** agent for quality assessment

**Agent Configuration:**
- Load role config JSON from `$JOBS_DIR/worker.json` or `$JOBS_DIR/supervisor.json`
- Extract `instructions`, `model` (with override support), and `name`
- Handle missing role configurations with clear error messages

### 3. Workspace Integration
**Prerequisite Verification:**
- Ensure `isolation_env_setup` has created `$JOB_DIR/workspace/` directory
- Verify workspace contains valid Git clone (`.git` directory exists)
- Change working directory to workspace for all operations

**Workspace Context:**
- Include `.gitignore` patterns (if any)
- Scan workspace files for context assembly
- Track evidence files created/modified during step execution

### 4. LLM Execution Pipeline

#### Context Assembly
Build comprehensive prompt from multiple sources:

**Required Attachments:**
- **Job Manifest:** Current `job_manifest.json` with status, history, metrics
- **Role Configuration:** Complete role JSON (instructions, model, capabilities)
- **Workspace Context:** File listings, recent commits, current working state
- **Phase Specifications:** From job manifest's `phases` array for current phase

**Context Sources:**
```python
# Example context structure
{
    "job_manifest": {...},  # Current state
    "role_config": {...},   # Worker or Supervisor instructions
    "workspace_files": [...], # Files in workspace directory
    "current_phase": {...},   # Phase specification from manifest
    "job_history": [...]     # Previous completed phases
}
```

#### CLINE Integration
Execute LLM with proper file attachments and command structure:

**Command Construction:**
```bash
cline --yolo --oneshot \
  --file AGENTS.md \
  --file _meta_prompt_instructions.md \
  --file job_manifest.json \
  --file role_config.json \
  --file workspace_context.txt \
  "Execute job step: [phase_description]"
```

**Timeout and Monitoring:**
- 5-minute default timeout (configurable)
- Capture stdout/stderr for logging
- Monitor for premature termination

### 5. LLM Response Processing

#### Response Schema Compliance
LLM responses must follow `logist/schemas/llm-chat-schema.json`:

**Required Response Fields:**
```json
{
  "action": "COMPLETED" | "STUCK" | "RETRY",
  "evidence_files": ["path/to/file1", "path/to/file2"],
  "summary_for_supervisor": "Brief assessment of work done",
  "job_manifest_url": "file:///path/to/manifest" // optional
}
```

**Action Semantics:**
- **COMPLETED:** Phase work finished, review evaluation needed
- **STUCK:** Agent cannot progress, human intervention required
- **RETRY:** Try again (e.g., fix code errors, gather more context)

#### Response Validation
- JSON schema validation against `llm-chat-schema.json`
- Action validation (must be COMPLETED/STUCK/RETRY)
- Evidence file existence verification
- Summary length limits (max 1000 chars)

### 6. State Machine Transitions

#### Worker Agent Flow (PENDING→RUNNING→REVIEW_REQUIRED)
```
PENDING → RUNNING (immediately, trigger Worker execution)
RUNNING → REVIEW_REQUIRED (after Worker COMPLETED/STUCK/RETRY)
```

#### Supervisor Agent Flow (REVIEW_REQUIRED→REVIEWING→APPROVAL_REQUIRED/INTERVENTION_REQUIRED)
```
REVIEW_REQUIRED → REVIEWING (immediately, trigger Supervisor execution)
REVIEWING → APPROVAL_REQUIRED (Supervisor COMPLETED - approves Worker's work)
REVIEWING → INTERVENTION_REQUIRED (Supervisor STUCK/RETRY - needs human help)
```

**Error State Handling:**
- LLM timeout: Return to previous state, log error
- Invalid response: INTERVENTION_REQUIRED with descriptive error
- Git operation failures: INTERVENTION_REQUIRED for manual cleanup

### 7. Job Manifest Updates

#### State Updates
```json
{
  "status": "REVIEW_REQUIRED",  // New state based on agent+response
  "current_phase": "implementation",  // May advance based on phase completion
  "metrics": {
    "cumulative_cost": 120,  // Add LLM call cost
    "cumulative_time_seconds": 900  // Add execution time
  },
  "history": [
    {
      "phase": "requirements_analysis",
      "status": "COMPLETED",
      "timestamp": "2025-11-29T23:00:00Z",
      "evidence_files": ["requirements.md"],
      "summary": "Completed analysis with specification document",
      "llm_model": "gpt-4-turbo",
      "cost": 15
    }
  ]
}
```

#### History Record Structure
Append new history entry for each step:
- Phase name
- Execution status (COMPLETED/STUCK/RETRY)
- Timestamp
- Evidence files list (from LLM response)
- Summary for supervisor (from LLM response)
- LLM model used
- Cost incurred
- Execution time

### 8. Git Operations

#### Post-Execution Commits
- Stage all evidence files from LLM response
- Stage any additional workspace changes
- Create commit with descriptive message:
```bash
git add [evidence_files...]
git commit -m "feat: complete [phase_name] phase

- [LLM summary_for_supervisor]
- Files: [evidence_files]
- Model: [llm_model] ($[cost])"
```

**Git Failure Handling:**
- If repository is dirty: Commit anyway or INTERVENTION_REQUIRED
- If evidence files don't exist: Log warning but continue
- Git command failures: Do not block, log for manual cleanup

### 9. Error Handling and Recovery

#### Execution Failures
- **LLM Timeout:** Return to previous state, log timeout
- **Invalid JSON:** INTERVENTION_REQUIRED, preserve partial results
- **Missing Evidence Files:** Log warnings, continue with available files
- **Workspace Issues:** Verify isolation_setup ran, recreate if corrupted

#### Dry Run Mode
- Show complete context assembly without LLM execution
- Display assembled prompt for inspection
- No state changes or file modifications
- Return success/failure based on context preparation only

### 10. Integration Points

#### Dependent Commands
`job_step_command` is prerequisite for:
- **job_run_command:** Uses internal calls to job_step in loop
- **job_preview_command:** Shows what job_step would execute
- **job_poststep_command:** Processes simulated responses like job_step results

#### File Management
- Read: `job_manifest.json`, role configs from `$JOBS_DIR/*.json`
- Write: Updated `job_manifest.json`, evidence files in workspace
- Execute: All operations in workspace directory via shell commands

### 11. Testing and Validation

#### Unit Testing
- Mock LLM responses with schema-compliant JSON
- Test state transitions with various combinations
- Verify context assembly correctness
- Mock Git operations for commit testing

#### Integration Testing
- End-to-end execution with real LLM calls (expensive, use sparingly)
- Test against real workspace created by isolation_env_setup
- Verify proper file attachments and context inclusion
- Validate state persistence and data integrity

#### Demo Script Integration
- Add job_step execution after workspace creation
- Verify state progression: PENDING → RUNNING → REVIEW_REQUIRED
- Test with both Worker and Supervisor roles
- Demonstrate evidence file collection and commits

## Verification Standards
- ✅ Advances job through one state transition per execution
- ✅ Executes appropriate agent (Worker vs Supervisor) based on state
- ✅ Processes LLM responses and updates manifest correctly
- ✅ Commits evidence files and workspace changes to Git
- ✅ Handles failures gracefully with proper error states
- ✅ Works with --dry-run mode for testing
- ✅ Demonstrates proper workspace isolation
- ✅ Tests pass with comprehensive mocking
- ✅ Backward compatibility maintained

## Dependencies Check
- **Master Plan:** Phase 3.7 job_step_command requires workspace isolation (Phase 3.6)
- **Prerequisites:** Functional CLI, job creation, workspace setup, Git available
- **Integration:** Core dependency for execution workflow (job_run, job_preview, job_poststep)
- **Agent Configs:** Worker and Supervisor role definitions in `$JOBS_DIR/`

## Critical Success Factors

**The job_step_command is the most complex and critical component** - it represents the actual AI agent execution and state management. Success requires:

1. **Reliable LLM Integration:** Robust CLINE calls with proper file handling
2. **Deterministic State Management:** Correct transitions per state machine
3. **Evidence Tracking:** Accurate file collection and commitment
4. **Error Resilience:** Graceful handling of timeouts, invalid responses, git failures
5. **Context Quality:** Comprehensive prompt assembly for high-quality LLM responses

Get this foundation right and the rest of the system will work. Fail here and the entire job execution pipeline collapses.

Implement systematically, referencing this comprehensive specification throughout development to ensure rock-solid workflow execution.