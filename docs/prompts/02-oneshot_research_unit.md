# Oneshot Research Unit Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `oneshot_research_unit` (Phase 0.1) from the Logist master development plan. This unit researches and constructs the interface for iterative monitoring of Cline CLI oneshot execution outputs, including reliable state polling and cost/token variance analysis. Consult this prompts file throughout implementation to ensure every requirement is met - reference it explicitly after each major step to verify compliance.

## Critical Requirements - Cline Oneshot Interface Research

### Interface Construction
Build reliable external process interfaces to:
- Start oneshot executions programmatically
- Monitor completion via JSON state file polling
- Parse response states (COMPLETED/RETRY/STUCK)
- Extract metadata from task execution

### State File Polling Protocol
Implement monitoring protocol for `~/.cline/x/tasks/<ID>/task_metadata.json` files that:
- Polls for state transitions from RUNNING to completion states
- Parses response action enums (COMPLETED for success, RETRY for restart, STUCK for intervention)
- Extracts cost/token metadata for variance analysis
- Provides reliable completion detection

### Cost/Token Variance Research
Execute systematic testing to establish reliable cost expectations:
- Select deliberately simple test job (predictable operations)
- Run --oneshot 10-20 times to gather variance data
- Analyze token counts and API costs per execution
- Document findings for cost projections in future phases

## Deliverables - Exact Files to Create

### 1. Research Documentation
**File:** `logist/docs/oneshot-research.md` (new file)
**Contents:**
Comprehensive research findings including:
- Task metadata JSON schema documentation
- State transition protocols and timing expectations
- Cost/token variance analysis from 10-20 test executions
- Interface design patterns for oneshot monitoring
- Practical implementation guidance for future phases

### 2. Oneshot Start Interface
**File:** `logist/scripts/oneshot-start.py` (new file)
**Contents:**
Python wrapper script for programmatic oneshot execution:
- Command-line interface for starting oneshot tasks
- Parameter passing (model, prompts, context files)
- Task ID extraction and return
- Error handling for invalid parameters

### 3. Oneshot Monitor Interface
**File:** `logist/scripts/oneshot-monitor.py` (new file)
**Contents:**
Python polling interface for task completion:
- Task ID input parameter
- Continuous polling of `~/.cline/x/tasks/<ID>/task_metadata.json`
- State transition detection (RUNNING → COMPLETED/RETRY/STUCK)
- Metadata extraction (costs, tokens, completion status)
- Timeout and error handling

### 4. Simple Test Job
**File:** `logist/config/test-job-simple.py` (new file)
**Contents:**
Minimal, predictable test job for variance analysis:
- No external dependencies or LLM calls required
- Deterministic operations (file creation, text output)
- Consistent execution time and resource usage
- Suitable for 10-20 iteration variance testing

**Example test job operations:**
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

### 5. Variance Analysis Script
**File:** `logist/scripts/analyze-variance.py` (new file)
**Contents:**
Analysis tool for test execution results:
- Parse execution logs from 10-20 runs
- Calculate token/cost statistics (mean, variance, ranges)
- Generate variance analysis report
- Export data for future phase cost projections

## State Schema Documentation Requirements

**File:** `logist/docs/oneshot-research.md` must document:

### Task Metadata JSON Structure
```json
{
  "task_id": "unique-task-identifier",
  "status": "COMPLETED|RETRY|STUCK",
  "created_at": "ISO-timestamp",
  "completed_at": "ISO-timestamp",
  "model": "gpt-4-turbo",
  "tokens_used": 1234,
  "cost_usd": 0.012,
  "response": {
    "action": "COMPLETED|RETRY|STUCK",
    "evidence_files": ["output1.txt", "output2.log"],
    "summary_for_supervisor": "Task executed successfully",
    "job_manifest_url": "file://path/to/manifest"
  }
}
```

### State Transitions
- **STARTED** → **RUNNING**: Initial execution begins
- **RUNNING** → **COMPLETED**: Successful execution with valid response
- **RUNNING** → **RETRY**: Execution failed but can be retried
- **RUNNING** → **STUCK**: Execution blocked, requires human intervention

## Implementation Sequence

1. **Setup:** Create simple test job for variance research
2. **Interface Design:** Document Cline CLI parameters and task metadata schemas
3. **Start Interface:** Build programmatic oneshot execution wrapper
4. **Monitor Interface:** Implement polling interface for completion detection
5. **Testing Protocol:** Execute 10-20 test runs with comprehensive logging
6. **Analysis:** Calculate variance statistics and document findings
7. **Documentation:** Create complete research report with implementation guidance
8. **Verification:** Confirm interfaces work reliably and documentation is comprehensive

## Verification Standards

### Interface Functionality
- ✅ Oneshot start interface successfully launches tasks and returns task IDs
- ✅ Monitor interface correctly polls and detects all completion states
- ✅ Error handling for invalid task IDs and timeout scenarios
- ✅ Metadata extraction captures costs, tokens, and response data

### Research Completeness
- ✅ Minimum 10 test executions completed with full metrics
- ✅ Variance analysis shows clear patterns and ranges for simple operations
- ✅ Task metadata schemas documented with all known fields
- ✅ State transition timing documented (typical wait times)

### Documentation Quality
- ✅ `oneshot-research.md` provides complete implementation guidance
- ✅ Cost projections grounded in actual variance data
- ✅ Interface patterns clearly explained for future development
- ✅ Edge cases and error conditions documented

## Dependencies Check

- **After each step**, consult this prompts file to ensure all requirements are met
- **Cline CLI required** - must be installed and configured with API access
- **Python standard library** - no additional dependencies needed for basic interfaces
- **Internet connectivity** - required for API calls during testing
- **Test environment** - sufficient API quota for 10-20 test executions

Implement systematically, consulting this specification file at each milestone to maintain 100% requirements coverage.