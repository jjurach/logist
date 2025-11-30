# Understanding Asynchronous Batch Execution in Cline

This document describes the strategy for running `cline` in asynchronous batch execution mode, where the `--oneshot` command is detached from the terminal and monitored externally via JSON state file polling. This enables robust, automated deployment workflows without terminal constraints.

## Asynchronous Execution Strategy

The `--oneshot` flag triggers full autonomous mode, but to enable batch processing, executions must be run asynchronously using standard shell tools:

- **Detachment**: Use `nohup &` to run `cline --oneshot` in the background, detached from the controlling terminal.
- **Process Management**: Capture the process ID (PID) for potential termination/restart operations.
- **State Monitoring**: Do not attempt to parse live log output; instead, poll persistent JSON state files for status updates.

Example shell invocation:
```bash
nohup cline --oneshot -t "task description" &
PID=$!
echo "Started PID: $PID"
```

## Status Monitoring via State File Polling

The preferred monitoring mechanism is polling the internal JSON state files that `cline` maintains at `~/.cline/x/tasks/<ID>/task_metadata.json`. These files contain completion signals and error indicators:

### Polling Criteria

Monitor the following fields in the state file:

- **Completion Signal**: Check `is_goal_achieved` field set to `true` or `final_stop_reason` set to "Goal achieved via completion tool."
- **Stuck/Failure Detection**:
  - **Inactivity Check**: Detect when the task file's last modified timestamp exceeds a threshold (e.g., 20 minutes) without updates.
  - **Loop Detection**: Monitor `current_action_count` approaching or exceeding `max_allowed_iterations` (currently hardcoded to 6 consecutive mistakes).

### External Watchdog Implementation

Implement a Python watchdog script to poll state files every 30-60 seconds:

```python
import time
import json
import os
from pathlib import Path

def monitor_task(task_id, inactivity_threshold=1200):  # 20 minutes
    task_file = Path.home() / '.cline' / 'x' / 'tasks' / task_id / 'task_metadata.json'

    while True:
        if task_file.exists():
            try:
                stat = task_file.stat()
                if time.time() - stat.st_mtime > inactivity_threshold:
                    return "STUCK"  # Escalates to INTERVENTION_REQUIRED

                with open(task_file, 'r') as f:
                    data = json.load(f)
                    if data.get('is_goal_achieved'):
                        return "COMPLETED"  # Ready for supervisor review
                    # Additional checks for RETRY conditions
            except:
                pass  # File may be updating

        time.sleep(60)  # Poll every minute
```

## Poststep Processing and Response Validation

After `--oneshot` execution completes, the result undergoes poststep processing by the `logist job poststep` command:

- **JSON Schema Validation**: Responses are validated against `logist/schemas/llm-chat-schema.json` to ensure structural compliance
- **State Mapping**: Validated response metadata triggers corresponding `logist job` state transitions
- **Schema Rejection**: If the LLM response does not match the required JSON schema, the system fails with INTERVENTION_REQUIRED status, including descriptive text about all available information from the malformed LLM response

## System Instructions for LLM Compliance

Prior to early testing, system instructions must be developed that explicitly command LLMs to produce valid JSON responses according to the schema:

- **Response Format Requirements**: Include explicit instructions that "your response must be valid JSON matching the following schema..."
- **Fallback Handling**: If malformed output is detected, provide mechanism to retry or flag for human review
- **Validation Integration**: System prompts should reference the JSON validation unit (Phase 0.0) to ensure consistent formatting

## Recovery and Restart Logic

The watchdog should implement automatic recovery:

- **Detection**: When STUCK or inactivity detected, kill the running process using the captured PID.
- **Restart/Resumption**: Use `cline task new --resume-or-new <ID>` or `cline task open <ID>` to resume the task with the same ID.
- **Iteration Limits**: Track restart attempts to prevent infinite loops (e.g., max 3-5 retries).

## Output Format Definitions

When `--oneshot` completes, the agent's JSON response (after validation) indicates the outcome:

- **response.action = "COMPLETED"**: Task goal achieved successfully. Transitions to APPROVAL_REQUIRED for supervisor review.
- **response.action = "RETRY"**: Execution should be restarted using resume commands. Trigger watchdog auto-recovery via `cline task open`.
- **response.action = "STUCK"**: Unresolvable issue requiring human intervention. Transitions to INTERVENTION_REQUIRED state.

## Integration with Logist Workflow

- The `cost_threshold` and `time_threshold_minutes` from job manifests become critical since `cline` provides no internal control.
- External monitoring enables reliable batch processing, with automatic retry logic handling transient failures.
- Human intervention is preserved for complex issues (STUCK state) while maintaining autonomous operation for routine tasks.

This approach ensures `cline` operates as a pure task execution engine, with all orchestration (monitoring, retry, lifecycle management) handled by external systems.