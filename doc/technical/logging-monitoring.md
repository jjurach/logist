# Logging, Monitoring & Debugging

## Overview

Logist implements comprehensive logging, monitoring, and debugging systems to ensure transparency, debuggability, and operational safety of AI agent workflows. These systems span multiple layers from high-level job execution tracking to detailed error correlation and metrics monitoring.

### Types of Logging Systems

Logist maintains four distinct logging and monitoring systems, each serving different purposes:

1. **Job Execution History** (`jobHistory.json`) - Complete audit trail of all agent interactions
2. **Error Logging & Classification** - Structured error tracking with recovery guidance
3. **Metrics & Resource Monitoring** - Cost, time, and threshold enforcement
4. **Debug Information Sources** - Various debug aids and execution context

## Job Execution History (`jobHistory.json`)

### Purpose & Architecture

The job execution history serves as a comprehensive journal of all LLM interactions throughout a job's lifecycle. Unlike simple logs, this system stores complete request/response pairs for debugging, auditing, and statistical analysis.

**Key Characteristics:**
- **Agent Interaction Records**: Every LLM call is logged with full context
- **Revenue/performance analysis**: Cost tracking tied to specific actions
- **Debug Environment**: Complete reproduction capability for failed interactions
- **Audit Trail**: Tamper-evident record of all agent decisions and outputs

### Technical Implementation

**Source Code**: `logist/src/logist/job_history.py:record_interaction()`

**Storage Location**: `jobHistory.json` in each job directory

**Data Flow**:
```
Job Processor → record_interaction() → jobHistory.json
```

### Data Structure & Content

Each interaction record contains comprehensive metadata:

```json
{
  "timestamp": "2025-11-30T20:45:57.102450",
  "model": "grok-code-fast-1",
  "cost": 0.0,
  "execution_time_seconds": 0.0,
  "request": {
    "simulation": true,
    "description": "Manually provided simulated LLM response for debugging/testing"
  },
  "response": {
    "action": "COMPLETED",
    "evidence_files": ["example_output.txt"],
    "summary_for_supervisor": "Successfully implemented the job poststep command",
    "processed_at": "2025-11-30T20:45:57.102433",
    "metrics": {
      "cost_usd": 0.0,
      "duration_seconds": 0.0
    },
    "cline_task_id": null,
    "raw_cline_output": "Simulated response - no actual LLM call made"
  },
  "is_simulated": true
}
```

**Field Details:**

| Field | Type | Description | Use Case |
|-------|------|-------------|----------|
| `timestamp` | ISO 8601 | Exact time of interaction | Chronological ordering, performance analysis |
| `model` | string | LLM model used | Cost optimization, capability analysis |
| `cost` | float | USD cost incurred | Budget monitoring, efficiency metrics |
| `execution_time_seconds` | float | Processing duration | Performance profiling |
| `request` | object | Full LLM request context | Debugging failed prompts |
| `response` | object | Complete LLM response + metadata | Response analysis, reproducibility |
| `is_simulated` | boolean | Whether this was development/testing | Production data filtering |

### Relationship to Cline Files

While Logist **reads from** Cline's internal `api_conversation_history.json` (located in `~/.cline/data/tasks/{task_id}/`), the `jobHistory.json` serves as Logist's enhanced, integrated audit trail:

**Cline provides:**
- Raw LLM conversation history
- Token usage and basic metrics
- Internal task metadata

**Job History adds:**
- Logist-specific context (job ID, phase, role)
- Cost calculations in USD
- Processing timestamps and performance metrics
- Simulation markers and debugging aids
- Integration with Logist's state machine

### Usage Patterns

**Debugging Failed Jobs:**
1. Check `jobHistory.json` for the failing interaction
2. Examine `request` to understand prompt/context
3. Analyze `response` for LLM behavior insights
4. Use `raw_cline_output` for subprocess debugging

**Performance Analysis:**
- Track cost accumulation patterns
- Identify slow-performing model choices
- Monitor token efficiency by model

**Audit & Compliance:**
- Complete agent decision logs
- Tamper-evident interaction records
- Evidence file chain-of-custody

### Implementation Status

- **Status**: ✅ **FULLY IMPLEMENTED and ACTIVELY USED**
- **Scope**: Every job execution, simulation, and testing scenario
- **Persistence**: Job-scoped, survives failures and restarts
- **Querying**: Via CLI commands and direct file inspection

## Error Logging & Classification System

### Overview

Logist implements a sophisticated error handling system that goes beyond simple try/catch blocks. The system provides structured error classification, correlation tracking, and automated recovery guidance.

**Key Components:**
- **Error Classification**: Automatic categorization by type, severity, and recovery strategy
- **Structured Logging**: JSON-formatted error logs with correlation IDs
- **State Machine Integration**: Error-driven job state transitions
- **Recovery Automation**: Suggested actions based on error patterns

### Error Classification System

**Source Code**: `logist/src/logist/error_classification.py`

**Supported Error Categories:**
- `NETWORK`: API connectivity, timeouts
- `VALIDATION`: JSON parsing, schema validation
- `RESOURCE`: Quota limits, rate limiting
- `EXECUTION`: CLINE execution failures
- `CONFIGURATION`: Invalid job setup
- `SYSTEM`: File system, permissions

**Severity Levels:**
- `TRANSIENT`: Auto-retry feasible
- `RECOVERABLE`: Human intervention can fix
- `FATAL`: Job cancellation required

**Classification Flow:**
```
Error Occurs → classify_error() → Classification Object → Job State Update
```

### Structured Error Logging

**Source Code**: `logist/src/logist/error_logging.py`

**Features:**
- **Correlation Tracking**: Unique IDs link related errors
- **Rotary File Logging**: 30-day retention with daily rotation
- **JSON Structure**: Searchable, parseable error records
- **Metrics Aggregation**: Error type counts and patterns
- **System Context**: Platform, Python version, working directory in logs

**Example Logged Error:**
```json
{
  "timestamp": "2025-12-01T23:15:43.123456",
  "correlation_id": "error_a1b2c3d4",
  "job_id": "test-job-001",
  "job_dir": "/path/to/job",
  "error_type": "JobProcessorError",
  "error_message": "CLINE execution failed with code 1",
  "classification": {
    "severity": "recoverable",
    "category": "execution",
    "description": "CLINE execution failed",
    "user_message": "LLM execution failed. Please check details.",
    "can_retry": true,
    "max_retries": 1,
    "suggested_action": "Review error output and job configuration"
  }
}
```

### Implementation Gap: Built But Not Integrated

**Important Status Note**: The error logging system is **fully implemented** but **currently NOT used** in the main CLI execution flow.

- **Error classification**: ✅ Used in `handle_execution_error()` function
- **State machine integration**: ✅ Job states update based on classification
- **User messaging**: ✅ Classification drives interactive guidance
- **Structured logging**: ❌ NOT invoked - only Job Manifest updates occur

**Missing Integration**: The CLI calls `handle_execution_error()` which performs classification and updates job state, but does **not** call `error_logger.log_error()` to create structured logs.

**Impact**: Error information is tracked in Job Manifest `history` arrays but not in dedicated error log files with correlation tracking.

### Implementation Status

- **Error Classification**: ✅ **FULLY IMPLEMENTED and ACTIVELY USED**
- **State Machine Integration**: ✅ **FULLY IMPLEMENTED and ACTIVELY USED**
- **Structured Error Logging**: ⚠️ **IMPLEMENTED but DISCONNECTED from main flow**
- **Error Correlation Tracking**: ❌ **NOT IMPLEMENTED** - correlation IDs generated but not used
- **Error Metrics**: ❌ **NOT IMPLEMENTED** - system designed but not collecting data

## Metrics & Resource Monitoring

### Job-Level Metrics Tracking

**Storage Location**: `job_manifest.json` under `metrics` key

**Tracked Metrics:**
- `cumulative_cost`: Total USD spent across all LLM calls
- `cumulative_time_seconds`: Wall-clock execution time
- `current_action_count`: Number of agent tool executions

**Automatic Enforcement:**
- **Cost Thresholds**: Jobs halt when cost limits exceeded
- **Time Thresholds**: Jobs halt when time limits exceeded
- **Iteration Limits**: Prevent infinite loops

### Cost Tracking Implementation

**Integration Points:**
- Post-LLM execution cost accrual
- Pre-execution threshold validation
- CSV export capabilities
- CLI status display with threshold status

**Threshold Status Colors:**
- 🟢 Green: Under 80% of threshold
- 🟡 Yellow: 80-100% of threshold
- 🔴 Red: Over threshold

### Implementation Status

- **Metrics Collection**: ✅ **FULLY IMPLEMENTED and ACTIVELY USED**
- **Threshold Enforcement**: ✅ **FULLY IMPLEMENTED and ACTIVELY USED**
- **Cost Tracking**: ✅ **FULLY IMPLEMENTED and ACTIVELY USED**
- **Time Tracking**: ✅ **FULLY IMPLEMENTED and ACTIVELY USED**
- **CSV Export**: ✅ **IMPLEMENTED**
- **Performance Profiling**: ✅ **AVAILABLE**

## Debug Information Sources

### Latest Outcome Tracking

**File**: `latest-outcome.json` in job directories

**Purpose**: Context preservation between job steps

**Contents**:
```json
{
  "action": "COMPLETED",
  "summary_for_supervisor": "...",
  "evidence_files": ["file1.txt", "file2.py"],
  "timestamp": "2025-12-01T23:00:00.000Z",
  "cline_task_id": "abc123",
  "metrics": {
    "cost_usd": 0.023,
    "duration_seconds": 45.67
  }
}
```

### CLI Execution Logging

**Console Output Features:**
- Real-time progress indicators
- Color-coded status messages
- Structured logging format
- Git operation feedback
- Threshold violation warnings

**Log Levels in Practice:**
- Standard execution steps (blue/green)
- Warnings (yellow)
- Errors (red)
- Debug information (cyan/white)

### Git Integration Debugging

**Automatic Operations:**
- Branch isolation creation
- Commit evidence files
- Git status reporting
- Merge preview generation

**Debug Capabilities:**
- Workspace file system inspection
- Git log analysis
- Commit history tracking
- Diff generation

### Workspace Preparation Logging

**Tracked Operations:**
- File discovery and attachment copying
- Context file resolution
- Outcome preparation from previous steps
- Total file argument counts

**Failure Handling:**
- Graceful degradation for missing files
- Warning-only logging for non-critical failures
- Detailed error context for critical failures

### Implementation Status

- **Latest Outcome**: ✅ **FULLY IMPLEMENTED** - Used for step-to-step context
- **CLI Logging**: ✅ **FULLY IMPLEMENTED** - Human-readable progress tracking
- **Git Integration**: ✅ **FULLY IMPLEMENTED** - Comprehensive workspace management
- **Workspace Prep**: ✅ **FULLY IMPLEMENTED** - File management and discovery
- **Error Context**: ✅ **FULLY IMPLEMENTED** - Detailed failure information

## Debugging Workflows

### Failed Job Root Cause Analysis

**Step 1: Check Job History**
- Inspect `jobHistory.json` for the failing interaction
- Compare request parameters with successful runs
- Analyze LLM response patterns

**Step 2: Examine Error Context**
- Review job manifest `history` array for error entries
- Check relationship to state machine transitions
- Verify threshold violations

**Step 3: Git Investigation**
- Examine git log for the relevant commits
- Check file modifications around failure point
- Verify workspace integrity

### Performance Analysis Workflows

**Cost Optimization:**
1. Query job history for high-cost interactions
2. Analyze model choice vs. complexity correlation
3. Identify retry loops and their cost impact

**Time Profiling:**
1. Track execution_time_seconds across similar interactions
2. Identify consistently slow operations
3. Monitor for timeout patterns

**File System Debugging:**
1. Use `logist job git-status` for workspace inspection
2. Check evidence file existence and modifications
3. Validate workspace preparation logs

## Configuration & Future Development

### Enabling Structured Error Logging

When integrated, structured error logging will provide:

```python
from logist.error_logging import error_logger

# In handle_execution_error() function:
correlation_id = error_logger.log_error(
    classification=classification,
    job_id=job_id,
    job_dir=job_dir,
    error=error,
    context={"operation": "LLM execution"}
)
```

### Extending Monitoring Capabilities

**Proposed Enhancements:**
- Centralized error log aggregation
- Cross-job analytics and anomaly detection
- Performance baseline monitoring
- Automated alert systems for threshold violations

**Configuration Options:**
- Custom metric collection plugins
- External monitoring webhook integration
- Log retention policy customization
- Debug log verbosity levels

## File Locations Summary

### Core Implementation Files
- `logist/src/logist/job_history.py` - Job history management and statistics
- `logist/src/logist/error_logging.py` - Structured error logging system (planned integration)
- `logist/src/logist/error_classification.py` - Error categorization with recovery strategies
- `logist/src/logist/job_processor.py` - Error handling and interaction recording

### Configuration & Schema
- `logist/schemas/roles/` - Role configurations with logging parameters
- Job manifest schemas include metrics and history specifications

### Generated Files (Per Job)
- `jobHistory.json` - Complete interaction audit trail
- `latest-outcome.json` - Step-to-step context preservation
- `~/.logist/logs/errors/*.log` - Structured error logs (planned but not used)

## Cross-References

This document covers the technical implementation details. For related topics, see:

- **Communication Protocol**: `communication-protocol.md` - Data structures and agent interaction schemas
- **CLI Interface**: `../03_cli_and_metrics.md` - User-facing metrics commands
- **State Machine**: `../04_state_machine.md` - How errors drive job state transitions
- **Job Overview**: `../overview.md` - High-level audit trail references

---

**Implementation Status Matrix:**

| Feature Group | Component | Implementation | Usage |
|---------------|-----------|----------------|-------|
| Job History | `jobHistory.json` | ✅ Complete | ✅ Active |
| Job History | Statistics API | ✅ Complete | ✅ Active |
| Error Classification | Severity/Categories | ✅ Complete | ✅ Active |
| Error Classification | Recovery Guidance | ✅ Complete | ✅ Active |
| Error Logging | Structured Logs | ⚠️ Complete but disconnected | ❌ Unused |
| Error Logging | Correlation Tracking | ❌ Not implemented | ❌ N/A |
| Metrics | Cost/Time Tracking | ✅ Complete | ✅ Active |
| Metrics | Threshold Enforcement | ✅ Complete | ✅ Active |
| Debug Info | CLI Logging | ✅ Complete | ✅ Active |
| Debug Info | Git Integration | ✅ Complete | ✅ Active |