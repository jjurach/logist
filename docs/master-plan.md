# Logist Master Development Plan

This document outlines the ordered implementation of Logist's core features in small, verifiable chunks. Each chunk builds dependencies systematically from simple directory operations to complex workflow orchestration.

## 📊 Phase 0: Research & Prototyping

### 0. json_validation_unit
**Description:** Develop JSON schema validation infrastructure for LLM response processing with demonstration assets
**Objective:** Implement robust parsing and validation of LLM JSON responses according to logist/schemas/llm-chat-schema.json for bidirectional communication, develop system instructions requiring valid schema compliance, create error handling that escalates schema violations to INTERVENTION_REQUIRED with descriptive failure information
**Scope:** Choose jsonschema library and add to requirements.txt, create validation wrapper functions, integrate schema enforcement for both requests (logist→LLM) and responses (LLM→logist), document system prompt additions for reliable JSON output from LLMs, implement descriptive error messaging on validation failures, provide demo script and example JSON files for validation testing
**Dependencies:** None
**Files (Read):** logist/schemas/llm-chat-schema.json, LLM response outputs, example JSON files in logist/docs/examples/llm-exchange/
**Files (Write):** requirements.txt (jsonschema dependency), system instruction templates with schema requirements, JSON validation utilities with wrapper functions, logist/scripts/demo-schema.py validation demonstration script, logist/docs/examples/llm-exchange/ (*.json example files), logist/docs/prompts/01-json_validation_unit.md controlling prompt file
**Verification:** Consistent validation of COMPLETED/STUCK/RETRY responses, descriptive error messages on malformed inputs/outputs, demo script successfully processes valid and rejects invalid example files, system instructions clearly specify JSON schema compliance for bidirection communication
**Dependency Metadata:** Provides validation foundation enabling reliable response processing in Phase 3.9 (job_poststep_command); establishes library selection and demo patterns for future validation units
**Testing Notes:** Comprehensive unit tests for valid/invalid JSON responses showing pass/fail; demo script integrated into testing suite; deliberate malformed JSON responses tested for correct escalation to INTERVENTION_REQUIRED; validate system instructions produce compliant LLM outputs through demo executions

### 0. oneshot_research_unit
**Description:** Research iterative construction of interface for starting, monitoring, and parsing Cline oneshot execution outputs
**Objective:** Construct reliable interface and tooling for external processes to start oneshot executions and monitor completion via JSON state file polling, with documented output formats and iterative cost/token research
**Scope:** Develop monitoring interface, document JSON response schemas (action: COMPLETED for success, RETRY for restart needed, STUCK for intervention required), implement protocol for polling ~/.cline/x/tasks/<ID>/task_metadata.json, include testing by selecting deliberately simple test job and running --oneshot 10-20 times while logging token counts and costs per execution for variance analysis
**Dependencies:** None
**Files (Read):** Cline task state files (~/.cline/x/tasks/<ID>/task_metadata.json)
**Files (Write):** logist/docs/oneshot-research.md (interface docs and findings), wrapper scripts for start/monitoring
**Verification:** Functional monitoring interface with successful parsing of completions, restarts, interventions; documented findings on token/cost patterns; at least 10 test executions completed with full metrics
**Dependency Metadata:** Establishes oneshot monitoring patterns and cost expectations for subsequent job execution phases
**Testing Notes:** Iterative testing protocol: use simple, predictable test job (e.g., file touch or echo task), execute --oneshot mode repeatedly, record API costs/tokens from LLM provider responses, analyze variance and breakpoints

## 🏗️ Phase 1: Foundation (Directory & Config Management)

### 1. init_command
**Description:** Implement `logist init` Command
**Objective:** Set up jobs directory structure and copy default configurations
**Scope:** Command-line argument parsing, directory creation, file copying
**Dependencies:** None
**Files (Read):** `logist/schemas/roles/` (templates)
**Files (Write):** `$JOBS_DIR/jobs_index.json`, `$JOBS_DIR/*.json` (role templates)
**Verification:** Creates `$JOBS_DIR/jobs_index.json`, copies role templates and schema
**Dependency Metadata:** Required for: job_list_command, job_create_command, job_select_command, role_list_command, role_inspect_command
**Testing Notes:** Does not interact with external LLM provider. Add more comprehensive test cases to demo script (see logist/docs/06_testing_strategy.md for extension guidelines).

### 2. job_list_command
**Description:** Implement `logist job list` Command
**Objective:** Display all jobs in the configured jobs directory
**Scope:** Read `jobs_index.json`, directory scanning, formatted output
**Dependencies:** jobs directory setup (Phase 1.1)
**Files (Read):** `$JOBS_DIR/jobs_index.json`, job manifest files
**Files (Write):** Console output
**Verification:** Shows job IDs, statuses, and descriptions from jobs index
**Dependency Metadata:** Required for: job_create_command, job_select_command
**Testing Notes:** Does not interact with external LLM provider. Add more comprehensive test cases to demo script (see logist/docs/06_testing_strategy.md for extension guidelines).

### 3. job_create_command
**Description:** Implement `logist job create` Command
**Objective:** Initialize new job with manifest and directory structure
**Scope:** Job manifest creation, directory mismatch warnings, job registration
**Dependencies:** jobs directory exists (Phase 1.1), job listing works (Phase 1.2)
**Files (Read):** Job specification file (sample-job.json)
**Files (Write):** `job_manifest.json`, updates `$JOBS_DIR/jobs_index.json`
**Verification:** Creates `job_manifest.json`, registers in jobs index, handles directory mismatches
**Dependency Metadata:** Required for: job_status_command, job_select_command, isolation_env_setup, job_step_command, job_preview_command, job_run_command, job_rerun_command, job_restep_command, job_chat_command

## 🔍 Phase 2: Job Status & Selection (Read-Only Operations)

### 4. job_status_command
**Description:** Implement `logist job status` Command
**Objective:** Display current job state, progress, history, and key metrics
**Scope:** Job manifest reading, status parsing, formatted display with metrics summary
**Dependencies:** Job creation works (Phase 1.3)
**Files (Read):** `job_manifest.json`
**Files (Write):** Console output
**Verification:** Shows status, phase, metrics, history from job manifest + concise metrics (cost %, tokens used/remaining, time spent)
**Dependency Metadata:** Required for: isolation_env_setup, job_run_command, metrics_cost_tracking_system

### 5. job_select_command
**Description:** Implement `logist job select` Command
**Objective:** Set currently selected job for commands without explicit job IDs
**Scope:** Update `current_job_id` in jobs index, environment variable precedence
**Dependencies:** Job listing works (Phase 1.2), job creation works (Phase 1.3)
**Files (Read):** `$JOBS_DIR/jobs_index.json`
**Files (Write):** Updates `$JOBS_DIR/jobs_index.json`
**Verification:** Changes current job in jobs index, respects LOGIST_JOB_ID env var
**Dependency Metadata:** Required for units with optional job IDs (most job commands)
**Testing Notes:** Does not interact with external LLM provider. Add more comprehensive test cases to demo script (see logist/docs/06_testing_strategy.md for extension guidelines).

## 🎯 Phase 3: Job Execution Core (Workflow Engine)

### 6. isolation_env_setup
**Description:** Create isolated workspace directory before execution
**Objective:** Create isolated workspace directory before execution
**Scope:** Git clone to `$JOB_DIR/workspace`, setup working environment
**Dependencies:** Job creation works (Phase 1.3)
**Files (Read):** Project repository (for cloning), `job_manifest.json`
**Files (Write):** Creates `$JOB_DIR/workspace/` directory with Git clone
**Verification:** Workspace directory exists and contains working copy of project
**Dependency Metadata:** Required for: job_step_command, job_preview_command, job_run_command

### 7. job_preview_command
**Description:** Implement `logist job preview` Command
**Objective:** Show next agent prompt without execution
**Scope:** Prompt generation, task context assembly from isolated workspace, no state changes
**Dependencies:** Isolation environment set up (Phase 3.6)
**Files (Read):** `job_manifest.json`, role configs, `$JOB_DIR/workspace/` content
**Files (Write):** Console output only (no state or file changes)
**Verification:** Displays formatted prompts for Worker/Supervisor execution using workspace context
**Dependency Metadata:** Required for debugging/inspection (no dependents), enables context validation before job_step
**Testing Notes:** Does not interact with external LLM provider. Add more comprehensive test cases to demo script (see logist/docs/06_testing_strategy.md for extension guidelines).

### 8. job_poststep_command
**Description:** Implement `logist job poststep` Command
**Objective:** Process simulated/mock LLM responses for testing and state transitions
**Scope:** File input processing, JSON schema validation, state machine transitions from RUNNING/PENDING/REVIEWING to INTERVENTION_REQUIRED
**Dependencies:** Preview logic (Phase 3.2), JSON schema validation, state persistence (Phase 6)
**Files (Read):** Input response file, `job_manifest.json`, JSON schema files
**Files (Write):** Updates `job_manifest.json` state, `jobHistory.json` appends interaction
**Verification:** Correctly transitions job state based on response content, validates against schema, records interaction
**Dependency Metadata:** Required for testing infrastructure, enables repeatable LLM response testing
**Testing Notes:** Does not interact with external LLM provider. Add more comprehensive test cases to demo script for different response types and state transitions (see logist/docs/06_testing_strategy.md for extension guidelines).

### 9. job_step_command
**Description:** Implement `logist job step` Command
**Objective:** Execute single workflow step with state transition in isolated workspace
**Scope:** Chdir to workspace, state machine transitions, agent role execution, --dry-run mode
**Dependencies:** Isolation environment set up (Phase 3.6), job status (Phase 2.1), job preview works (Phase 3.7)
**Files (Read):** `job_manifest.json`, role configs, `$JOB_DIR/workspace/` directory
**Files (Write):** Updates `job_manifest.json`, writes to workspace (evidence), Git commits
**Verification:** Advances job through one state (PENDING→RUNNING, etc.), changes committed to workspace
**Dependency Metadata:** Required for: job_run_command, state_persistence_recovery, error_handling_system, metrics_cost_tracking_system
**Testing Notes:** Interacts with external LLM provider via `cline --oneshot`. Unit tests should use careful mocks. May not be easily demoable in live demo script - suggest using regression testing with historical fixtures (see logist/docs/06_testing_strategy.md for details).

### 10. job_run_command
**Description:** Implement `logist job run` Command
**Objective:** Execute continuous workflow until completion or intervention in isolated workspace
**Scope:** Execution loop through state machine, handle PENDING→RUNNING→completion cycles
**Dependencies:** Single step execution (Phase 3.2), isolation environment (Phase 3.1)
**Files (Read):** `job_manifest.json`, role configs, `$JOB_DIR/workspace/` working directory
**Files (Write):** Repeated `job_manifest.json` updates, workspace evidence files, Git commits
**Verification:** Runs until SUCCESS, CANCELED, or intervention required states, all in isolated workspace
**Dependency Metadata:** Final user-facing execution command (depends on all execution infrastructure)
**Testing Notes:** Interacts with external LLM provider through internal `job step` calls. Unit tests should use careful mocks. Add more test cases to demo script for edge cases (see logist/docs/06_testing_strategy.md for extension guidelines).

## 🔧 Phase 4: Job State Management (Modification Operations)

### 11. job_rerun_command
**Description:** Implement `logist job rerun` Command
**Objective:** Reset job to initial state
**Scope:** Manifest reset, state clearing, history preservation option
**Dependencies:** Job creation and status work (Phases 1.3, 2.1)
**Files (Read):** `job_manifest.json`
**Files (Write):** Resets `job_manifest.json`, preserves/updates history
**Verification:** Job returns to PENDING state, history shows reset event
**Dependency Metadata:** Required for: job_restep_command

### 12. job_restep_command
**Description:** Implement `logist job restep` Command
**Objective:** Rewind to previous checkpoint
**Scope:** State restoration from job history, safe rollback
**Dependencies:** Job rerun works (Phase 4.1)
**Files (Read):** `job_manifest.json` (history), `$JOBS_DIR/jobs_index.json`
**Files (Write):** Updates `job_manifest.json` to previous checkpoint state
**Verification:** Job state rewinds to previous checkpoint with preserved history
**Dependency Metadata:** Essential for debugging failed workflows

### 13. job_chat_command
**Description:** Implement `logist job chat` Command
**Objective:** Interactive debugging and intervention via `cline task chat`
**Scope:** State validation (not RUNNING/REVIEWING), pass-through to cline
**Dependencies:** Basic CLI integration (early phases), state checking (Phase 2.1)
**Files (Read):** `job_manifest.json` (state validation), role configs, context files
**Files (Write):** Console interaction only (no permanent file changes)
**Verification:** Only works in safe states, provides direct agent interaction
**Dependency Metadata:** Debugging tool (depends on execution infrastructure)

## 👥 Phase 5: Role Management System

### 14. role_list_command
**Description:** Implement `logist role list` Command
**Objective:** Display available agent roles
**Scope:** Scan role configurations, format and display role metadata
**Dependencies:** Role configuration system (partial from init command)
**Files (Read):** `$JOBS_DIR/*.json` (role files in jobs directory)
**Files (Write):** Console output
**Verification:** Shows role names, descriptions, model assignments
**Dependency Metadata:** Required for: role_inspect_command

### 15. role_inspect_command
**Description:** Implement `logist role inspect` Command
**Objective:** Display full role configuration details
**Scope:** Load and format complete role instructions, parameters, metadata
**Dependencies:** Role listing works (Phase 5.1)
**Files (Read):** Individual role JSON files (`$JOBS_DIR/worker.json`, etc.)
**Files (Write):** Formatted JSON console output
**Verification:** Shows complete role JSON/structure for debugging/inspection
**Dependency Metadata:** Required for configuring roles

## 🔄 Phase 6: Execution Environment & Error Handling

### 16. state_persistence_recovery
**Description:** State Persistence & Recovery
**Objective:** Job manifest creation, updates, and crash recovery
**Scope:** Filesystem operations, state serialization, automatic recovery detection
**Dependencies:** All job operations (Phases 1-5)
**Files (Read):** Various project files for state detection, `job_manifest.json` backups
**Files (Write):** `job_manifest.json` (state updates), recovery logs, backup manifests
**Verification:** Job state survives restarts, detects hung processes, auto-recovery
**Dependency Metadata:** Required for robust job execution

### 17. error_handling_system
**Description:** Error Handling & Intervention System
**Objective:** Process exit codes, trigger state transitions, manage human intervention
**Scope:** JSON response parsing, state machine transitions, intervention state handling
**Dependencies:** Core execution works (Phase 3)
**Files (Read):** Subprocess exit codes, JSON response files, state machine config
**Files (Write):** Error logs, state transitions in `job_manifest.json`
**Verification:** Failure scenarios properly escalate to appropriate human intervention states
**Dependency Metadata:** Required for all error-prone operations (Phase 3 onwards)

### 18. advanced_isolation_cleanup
**Description:** Advanced Job Isolation & Cleanup
**Objective:** Git isolation maintenance, workspace lifecycle management, cleanup automation
**Scope:** Branch management, workspace preservation across sessions, automated cleanup policies
**Dependencies:** Basic isolation (Phase 3.1) and execution (Phase 3) working
**Files (Read):** `$JOB_DIR/workspace/` contents, Git status, job configurations
**Files (Write):** Git maintenance operations, workspace lifecycle tracking, cleanup logs
**Verification:** Workspaces persist between sessions, automatic cleanup by policy, no workspace conflicts
**Dependency Metadata:** Required for: git_integration_commit, structured_logging_debug

## 📊 Phase 7: Advanced Features & Integration

### 19. metrics_cost_tracking_system
**Description:** Metrics & Cost Tracking System
**Objective:** Complete cost monitoring, token usage tracking, and budget enforcement
**Scope:** Two-command metrics system with threshold management
**Dependencies:** Execution engine works (Phase 3), job status works (Phase 2.1)
**Files (Read):** API response metadata, job manifests, time tracking, cost databases
**Files (Write):** Metrics files, cost databases, threshold warning logs, CSV exports
**Verification:**
  - Enhanced `job status`: Shows concise metrics summary (cost %, tokens used, time spent)
  - New `job metrics` command: Detailed per-step breakdown, threshold warnings (green/yellow/red)
  - Threshold enforcement: Blocks execution when cost/time limits exceeded
  - Data export: CSV format for external analysis
  - Projections: Estimated completion costs with recommendations
**Dependency Metadata:** Production safety requirement - prevents runaway AI costs

### 20. git_integration_commit
**Description:** Git Integration & Commit Management
**Objective:** Branch isolation, commit tracking, merge preparation
**Scope:** Git operations, commit history, patch file generation for manual merge
**Dependencies:** Advanced job isolation works (Phase 7.1)
**Files (Read):** Git working directory, job configurations, evidence files
**Files (Write):** Git commits, branches, patch files for merge
**Verification:** Changes isolated in branches, commit history preserved, merge artifacts created
**Dependency Metadata:** Essential for safe AI-assisted development

### 21. structured_logging_debug
**Description:** Structured Logging & Debugging
**Objective:** Comprehensive logging system for troubleshooting and monitoring
**Scope:** Structured JSON logging, configurable log levels, error correlation
**Dependencies:** All core features (Phases 1-7)
**Files (Read):** All system state, configurations, execution results
**Files (Write):** Log files, audit trails, debugging databases
**Verification:** Complete execution traceability, debug-friendly output format
**Dependency Metadata:** Final diagnostic layer (depends on everything)

## 🎯 Implementation Strategy

- **Complete each phase before starting the next**
- **Test each chunk independently using CLI arguments**
- **Use placeholder implementations initially, then enhance with full functionality**
- **Verify integration points between phases before proceeding**
- **Maintain backward compatibility with existing CLI patterns**

This plan provides 20 verifiable units progressing from simple directory operations to full AI orchestration workflows, ensuring systematic and testable development.
