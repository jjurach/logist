# Archived Research Notes: Cline Oneshot Implementation

## 📚 Historical Context

This document consolidates research and testing notes from Logist's Phase 0 implementation for Cline CLI oneshot integration. These were originally separate documents (`oneshot-research.md` and `oneshot-testing.md`) developed during the initial research phase.

**Archive Status**: This research is complete and integrated into the core implementation. The findings informed the design of the job execution system but are no longer actively developed.

---

## Cline Oneshot Research Report

### Executive Summary

This research report documents the findings from implementing the oneshot_research_unit for the Logist project. The study examined Cline CLI's oneshot execution interface, monitoring capabilities, and cost/token variance patterns.

## Cline Oneshot Interface Overview

### Command Interface
Cline CLI supports oneshot mode using the `--oneshot --no-interactive` flags:
```bash
cline "task prompt" --oneshot --no-interactive
```

### Enhanced File Attachment Capabilities
Cline supports attaching multiple documents using the `--file` option for rich context:

```bash
# Single file attachment
cline --oneshot --file requirements.md "Implement the requirements"

# Multiple file attachments
cline --oneshot --file requirements.md --file guidelines.md --file examples.py "Implement following requirements and guidelines using examples as reference"

# Combined with --yolo flag for autonomous execution
cline --yolo --oneshot --file task.md --file context.json --file reference_code.py "Complete the task using the provided context and reference code"
```

### Task State Management
Tasks are managed through a directory-based system at `~/.cline/data/tasks/<TASK_ID>/` containing:
- `task_metadata.json` - Execution metadata
- `api_conversation_history.json` - API conversation log
- `focus_chain_taskid_<ID>.md` - Task focus information
- `ui_messages.json` - UI message history
- `settings.json` - Task settings

### Task Identification
Task IDs are auto-generated Unix timestamps (milliseconds). The most recent task can be identified by checking the latest directory in `~/.cline/data/tasks/`.

## Task Metadata Schema Analysis

### Observed Structure
The actual `task_metadata.json` structure differs from the specification:

```json
{
  "files_in_context": [
    {
      "path": "filename",
      "record_state": "active|inactive",
      "record_source": "tool_name",
      "cline_read_date": timestamp,
      "cline_edit_date": timestamp,
      "user_edit_date": timestamp
    }
  ],
  "model_usage": [
    {
      "ts": timestamp_ms,
      "model_id": "x-ai/grok-code-fast-1",
      "model_provider_id": "cline",
      "mode": "plan|act"
    }
  ],
  "environment_history": [
    {
      "ts": timestamp_ms,
      "os_name": "linux",
      "os_version": "6.14.0-36-generic",
      "os_arch": "x64",
      "host_name": "Cline CLI",
      "host_version": "1.0.7",
      "cline_version": "3.38.3"
    }
  ]
}
```

### Key Findings
1. **No explicit completion status**: Unlike the specification's `COMPLETED|RETRY|STUCK`, completion is inferred from inactivity timeout
2. **No direct token/cost fields**: Cost and token data is available through `cline task list` command
3. **No response.action enum**: Status is determined by monitoring activity patterns

### Task List Information
Token and cost data is available via:
```bash
cline task list --output-format json
```

Format example:
```
Task ID: 1764472800508
Message: Execute the simple test job...
Usage  : ↑ 11.4k ↓ 465 → 192 $0.0000
```

This provides usage statistics in the format: `↑ input ↓ output → total $ cost`

## Implementation Interfaces

### 1. Oneshot Start Interface (`logist/scripts/oneshot-start.py`)
- **Purpose**: Programmatic launch of oneshot tasks
- **Features**:
  - Command-line interface for task submission
  - Parameter support (model selection, interactive mode)
  - Task ID extraction via task list comparison
- **Limitations**: Task ID extraction depends on precise task list parsing

### 2. Oneshot Monitor Interface (`logist/scripts/oneshot-monitor.py`)
- **Purpose**: Poll for task completion and extract metadata
- **Completion Detection**: Uses inactivity timeout (default 10 minutes)
- **Metadata Extraction**: Combines file system metadata with task list usage data
- **Features**:
  - Configurable polling intervals and timeouts
  - Multiple output formats (human-readable, JSON)

### 3. Variance Analysis Tool (`logist/scripts/analyze-variance.py`)
- **Purpose**: Statistical analysis of execution metrics
- **Input Support**: Task list data, execution logs
- **Statistics Generated**: Mean, median, variance, ranges for tokens and costs
- **Usage Parsing**: Regular expression extraction from task list format

## Test Execution Results

### Simple Test Job
Created `logist/config/test-job-simple.py` - minimal deterministic job for variance testing:
```python
#!/usr/bin/env python3
"""Simple test job for variance analysis."""
import os

# Create predictable output file
with open('test-output.txt', 'w') as f:
    f.write('Test job completed successfully\n')
    f.write(f'Timestamp: {os.environ.get("TIMESTAMP", "unknown")}\n')
    f.write('Operations: file_creation, text_output\n')

print("Simple test job: COMPLETED")
```

### Execution Variance Data
Executed 3 simple test jobs with the following token consumption patterns:

- **Execution 1**: 12,300 tokens ($0.0000) - ↑ 11.8k ↓ 785 → 12.3k
- **Execution 2**: 34,800 tokens ($0.0000) - ↑ 2.6k ↓ 1.0k → 34.8k
- **Execution 3**: 25,700 tokens ($0.0000) - ↑ 12.0k ↓ 1.1k → 25.7k

**Variance Analysis Summary:**
- Token range: 12,300 → 34,800 tokens (2.8x variation)
- Mean token usage: 24,267 tokens
- All costs recorded as $0.0000 (free tier usage)
- Significant variance suggests inconsistent reasoning complexity for identical tasks

## Research Findings and Recommendations

### Current System Architecture
The Cline CLI uses a sophisticated task management system with:
- Persistent task state across sessions
- Rich metadata collection
- API usage tracking
- File system-based persistence

### Differences from Specification
The actual implementation diverges from the prompt specification:
1. **State Transitions**: No explicit `RUNNING → COMPLETED/RETRY/STUCK` states
2. **Metadata Location**: Cost/token data in CLI commands, not JSON fields
3. **Completion Detection**: Timeout-based rather than status-based

### Cost/Token Variance Patterns
**Cost Variance Analysis:**
- Current implementation shows $0.0000 costs across all test executions
- This indicates free tier usage or zero-cost API calls
- Cost variance cannot be analyzed until paid usage is encountered
- Token consumption shows 2.8x variation despite identical task inputs

**Implications:**
- Token usage estimates should include 2-3x variance buffer
- Cost projections should account for token consumption variability
- Statistical sampling essential for accurate estimation

---

## Oneshot Research Scripts: Setup and Usage Guide

## 🎯 Setup and Execution Workflow

### Available Scripts
- `oneshot-start.py` - Programmatic task launching
- `oneshot-monitor.py` - Completion monitoring with auto-restart
- `batch-executor.py` - Multiple task processing
- `analyze-variance.py` - Statistical analysis tool
- `test-job-simple.py` - Deterministic test job

### Complete Setup Process
```bash
# Navigate to project and make scripts executable
cd /path/to/logist
chmod +x scripts/oneshot-*.py config/test-job-simple.py

# Verify Cline configuration
cline --version && cline config list
```

### Key Features Demonstrated
- **Automatic task execution** with `--oneshot --yolo` modes
- **Inactivity detection** and restart capabilities
- **Batch processing** with individual monitoring
- **Process lifecycle management** with PID tracking
- **Cost/token variance analysis** for cost prediction

### Integration with Core Logist System
- Scripts integrate with `job poststep` command
- Cost data feeds into metrics system
- Task metadata supports monitoring requirements

---

## Historical Implementation Notes

This consolidated research document captures the foundational work that enabled Logist's Cline CLI integration. Key insights that influenced the final design:

### Core Interface Patterns
- Timeout-based completion detection
- File system polling for state changes
- CLI command parsing for usage data
- Process management with graceful termination

### Reliability Lessons
- Concurrent execution requires careful task ID handling
- Network interruptions demand robust retry mechanisms
- API quota limits need proactive monitoring
- Cost variance necessitates statistical sampling

### Architecture Decisions
- Stateless polling model over event-driven notifications
- Command-line data extraction over direct API integration
- Timeout heuristics over explicit status reporting
- External process management over direct API control

*Archived: December 1, 2025 - Research complete, findings integrated into production implementation*