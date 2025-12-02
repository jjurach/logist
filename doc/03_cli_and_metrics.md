# CLI Interface and Metrics

## Logist Execution Commands

### Command Overview
The Logist provides four core CLI commands for managing job execution, each with specific state transition behavior. All commands follow the pattern `logist job <command> <job_id>` with optional parameters.

### logist job run <job_id>
**Purpose**: Continuous execution from current state until completion or halt

**State Transitions**:
- PENDING → RUNNING → [Worker→Supervisor→Steward loop] → SUCCESS/FAILED/HALTED
- Automatically handles RETRY actions without human intervention
- Stops on STUCK status requiring Steward review

**Usage**: `logist job run my-job --resume`

**Parameters**:
- `--resume`: Continue from last successful state (default: start fresh)
- `--model <model>`: Override default LLM model

### logist job step <job_id>
**Purpose**: Execute single phase and pause for inspection

**State Transitions**:
- Execute one Worker→Supervisor iteration
- Stop after Supervisor review for Steward checkpoint
- Maintains job state for subsequent commands

**Usage**: `logist job step my-job`

**Parameters**: None

### logist job rerun <job_id>
**Purpose**: Complete job reset to initial state

**State Transitions**:
- **FORCE_RESET** → Initializes fresh Job Manifest
- Deletes all evidence files and execution history
- Returns to planning phase

**Usage**: `logist job rerun my-job`

**Parameters**:
- `--clean-git`: Reset Git branch to baseline hash
- `--keep-files`: Preserve evidence files in archive directory

### logist job restep <job_id>
**Purpose**: Revert to previous phase checkpoint and retry

**State Transitions**:
- Reverts Job Manifest to state before last execution
- Allows parameter adjustment after failure
- Re-executes current phase with fresh start

**Usage**: `logist job restep my-job`

**Parameters**:
- `--phase <phase>`: Revert to specific phase instead of previous

## Metric Guardrails

### Metric Tracking System
The Logist continuously monitors resource utilization across all Agent Runs in a job, enforcing configurable thresholds to prevent runaway costs or infinite loops.

### Required Metrics

#### cumulative_cost
- **Definition**: Total USD cost accumulated from all Agent Runs in the current job
- **Calculation**: Sum of API costs from each LLM call plus any infrastructure charges
- **Precision**: Tracked in cents (e.g., 125 represents $1.25)
- **Reset**: Zero on job rerun, preserved on job restep

#### cumulative_time_seconds
- **Definition**: Total wall-clock time elapsed during Agent Run execution
- **Calculation**: Active execution time only (excludes idle/waiting)
- **Precision**: Whole seconds
- **Reset**: Zero on job rerun, preserved on job restep

#### current_action_count
- **Definition**: A running total of the number of actions (tool calls, shell executions) taken by the agent within the current job.
- **Calculation**: Incremented each time the agent successfully executes a tool or command.
- **Precision**: Integer
- **Reset**: Zero on job rerun.

### Threshold Enforcement

#### cost_threshold
- **Type**: Integer (USD cents)
- **Default**: 1000 ($10.00)
- **Validation Point**: Checked before every Agent Run begins
- **Action on Violation**: Immediately set job status to `HALTED_COST`
- **Configuration**: Set in job specification or global config

#### time_threshold_minutes
- **Type**: Integer (minutes)
- **Default**: 60 minutes
- **Validation Point**: Checked before every Agent Run begins
- **Action on Violation**: Immediately set job status to `HALTED_TIME`
- **Configuration**: Set in job specification or global config

#### max_allowed_iterations
- **Type**: Integer
- **Default**: 50
- **Validation Point**: Checked before every Agent Run begins.
- **Action on Violation**: Immediately set job status to `HALTED_ITERATION`.
- **Purpose**: Acts as a hard safety cap to prevent infinite loops or runaway execution, even if time and cost thresholds have not been met.
- **Configuration**: Set in job specification or global config.

### Halt States

#### HALTED_COST
- **Trigger**: Cost threshold exceeded before Agent Run
- **Description**: Job budget depleted - requires cost threshold increase or job redesign
- **Recovery**: Increase cost_threshold and use `logist job restep`
- **Prevention**: Monitor early and adjust thresholds proactively

#### HALTED_TIME
- **Trigger**: Time threshold exceeded before Agent Run
- **Description**: Job timeout reached - may indicate infinite loop or excessive scope
- **Recovery**: Increase time_threshold_minutes or break job into smaller units
- **Prevention**: Use shorter time limits for initial exploration phases

### Configuration Examples
```json
{
  "job_spec": {
    "cost_threshold": 5000,    // $50.00 maximum
    "time_threshold_minutes": 120,  // 2 hours maximum
    "default_model": "grok-code-fast-1"
  }
}
```

### Metric Reporting
All metrics are logged to the Job Manifest and can be queried via `logist job status`. Threshold violations are highlighted in red with suggested recovery actions.