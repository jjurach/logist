# Project Plan: State Machine Redesign for Runner-Aligned Architecture

**Date:** 2025-12-29
**Complexity:** High
**Status:** Proposed

## Objective

Redesign the job state machine to:
1. Remove legacy Worker/Supervisor role dependencies
2. Align states with runner lifecycle operations (`provision`, `spawn`, `monitor`, `harvest`, `cleanup`)
3. Add `RECOVERING` state for runner recovery operations
4. Emphasize **step** as the atomic unit of execution
5. Clarify transient vs resting states

## Background

### Previous State Flow (With Roles)

```
DRAFT → PENDING → RUNNING → REVIEW_REQUIRED → REVIEWING → APPROVAL_REQUIRED → SUCCESS
                     ↑                              ↓
                     └──────────────────────────────┘
                              (retry)
```

The old flow assumed:
- **RUNNING** = Worker agent executing
- **REVIEW_REQUIRED/REVIEWING** = Supervisor agent reviewing
- Role-dependent transitions between states

### Problems After Role Removal

1. **REVIEW_REQUIRED/REVIEWING are orphaned** - No Supervisor role to trigger them
2. **Runner lifecycle not represented** - States don't map to `provision()`, `spawn()`, etc.
3. **Recovery operations undefined** - No state for stuck execution recovery
4. **Step concept not explicit** - The atomic unit of work is unclear

## Core Concept: The Step

A **step** is the atomic unit of execution in logist. One step:
1. Takes a job from PENDING
2. Executes through PROVISIONING → EXECUTING → HARVESTING
3. Lands the job in a **resting state** (SUCCESS, INTERVENTION_REQUIRED, APPROVAL_REQUIRED, etc.)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ONE STEP                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PENDING ──▶ PROVISIONING ──▶ EXECUTING ──▶ HARVESTING ──▶ [resting state]  │
│                                    │                                         │
│                               (timeout)                                      │
│                                    ▼                                         │
│                               RECOVERING ──▶ EXECUTING (with updated inputs) │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Step Execution Model

- `logist job step` - Executes one step on a PENDING job (explicit or next in queue)
- `logist job step JOB_ID` - Executes one step on a specific PENDING job
- `logist job run` - Cycles through PENDING jobs, executing steps until no PENDING jobs remain or a limit is reached

After a step completes, the **next step may be for a different job** in the queue.

### Parallel Execution (Future)

When multiple jobs run concurrently, `logist job run` cycles through them:
```
Job A: PENDING → step → SUCCESS
Job B: PENDING → step → INTERVENTION_REQUIRED (stuck)
Job C: PENDING → step → APPROVAL_REQUIRED
Job D: PENDING → step → SUCCESS
...
```

Each job reaches its own resting state independently. The scheduler picks up the next PENDING job for the next step.

## Proposed State Machine

### New State Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Job Lifecycle State Machine                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────┐     activate      ┌──────────┐                                 │
│  │  DRAFT  │──────────────────▶│  PENDING │◀─────────────────────┐          │
│  └─────────┘                   └────┬─────┘                      │          │
│                                     │                            │          │
│                              `logist job step`                   │          │
│                                     │                            │          │
│                                     ▼                            │          │
│                            ┌──────────────┐                      │          │
│                            │ PROVISIONING │ (transient)          │          │
│                            └───────┬──────┘                      │          │
│                                    │                             │          │
│                                    ▼                             │          │
│  ┌────────────┐             ┌───────────┐                        │          │
│  │ RECOVERING │◀──timeout───│ EXECUTING │                        │          │
│  │(transient) │             └─────┬─────┘                        │          │
│  └─────┬──────┘                   │                              │          │
│        │                          │                              │          │
│        │ recovered           agent signals                       │          │
│        │ (updated inputs)    completion                          │          │
│        │        │                 │                              │          │
│        │        ▼                 ▼                              │          │
│        │   ┌───────────┐   ┌─────────────┐                       │          │
│        └──▶│ EXECUTING │   │  HARVESTING │ (transient)           │          │
│            └───────────┘   └──────┬──────┘                       │          │
│                                   │                              │          │
│                     agent exit signal determines state           │          │
│                                   │                              │          │
│              ┌────────────────────┼────────────────────┐         │          │
│              │                    │                    │         │          │
│              ▼                    ▼                    ▼         │          │
│     ┌─────────────┐    ┌──────────────────┐    ┌────────────┐    │          │
│     │   SUCCESS   │    │   INTERVENTION   │    │  APPROVAL  │    │          │
│     │ (terminal)  │    │    REQUIRED      │    │  REQUIRED  │    │          │
│     └─────────────┘    └────────┬─────────┘    └──────┬─────┘    │          │
│                                 │                     │          │          │
│                                 │ human               │ approve  │          │
│                                 │ resubmits           │          │          │
│                                 │                     ▼          │          │
│                                 │              ┌───────────┐     │          │
│                                 │              │  SUCCESS  │     │          │
│                                 │              └───────────┘     │          │
│                                 │                                │          │
│                                 │                     reject     │          │
│                                 └────────────────────────────────┘          │
│                                                                              │
│  Any State ──suspend──▶ SUSPENDED ──resume──▶ PENDING                       │
│  Any State ──cancel───▶ CANCELED                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### State Categories

#### Resting States (Job waits here)

| State | Description | Human Action Required? |
|-------|-------------|------------------------|
| **DRAFT** | Being configured | No (user is configuring) |
| **PENDING** | Ready for next step | No (scheduler picks it up) |
| **SUCCESS** | Complete | No (terminal) |
| **APPROVAL_REQUIRED** | Needs sign-off | **Yes** - approve or reject |
| **INTERVENTION_REQUIRED** | Needs fix | **Yes** - fix and resubmit |
| **SUSPENDED** | Paused | **Yes** - resume |
| **CANCELED** | Terminated | No (terminal) |

#### Transient States (Job passes through quickly)

| State | Description | Duration | Notes |
|-------|-------------|----------|-------|
| **PROVISIONING** | Setting up workspace | Seconds to minutes | |
| **EXECUTING** | Agent running | Minutes to hours | |
| **RECOVERING** | Restarting stuck agent | Seconds | Quickly returns to EXECUTING with updated inputs |
| **HARVESTING** | Collecting results | Seconds | Quickly transitions to resting state |

### State Definitions

| State | Description | Runner Method | Exit Condition |
|-------|-------------|---------------|----------------|
| **DRAFT** | Job created, being configured | - | `logist job activate` |
| **PENDING** | Ready for step, waiting for scheduler | - | `logist job step` |
| **PROVISIONING** | Runner cloning repo, setting up workspace | `provision()` | Workspace ready |
| **EXECUTING** | Agent actively running | `spawn()`, `is_alive()`, `get_logs()` | Agent signals completion or timeout |
| **RECOVERING** | Runner restarting stuck execution | `recover()` | Returns to EXECUTING with updated inputs |
| **HARVESTING** | Collecting outputs, committing changes | `harvest()` | Transitions to resting state |
| **INTERVENTION_REQUIRED** | Human must fix issues | - | Human runs `resubmit` → PENDING |
| **APPROVAL_REQUIRED** | Human must approve result | - | `approve` → SUCCESS, `reject` → PENDING |
| **SUCCESS** | Job completed successfully | - | *Terminal* |
| **CANCELED** | Job terminated by user | `terminate()`, `cleanup()` | *Terminal* |
| **SUSPENDED** | Temporarily paused | - | `logist job resume` → PENDING |

### State Transition Matrix

| From State | To States | Trigger |
|------------|-----------|---------|
| DRAFT | PENDING, SUSPENDED, CANCELED | `activate`, `suspend`, `cancel` |
| PENDING | PROVISIONING, SUSPENDED, CANCELED | `step`, `suspend`, `cancel` |
| PROVISIONING | EXECUTING, INTERVENTION_REQUIRED, CANCELED | Success, Failure, `cancel` |
| EXECUTING | HARVESTING, RECOVERING, CANCELED | Complete, Timeout, `cancel` |
| RECOVERING | EXECUTING | Recovery succeeds (with updated inputs) |
| HARVESTING | SUCCESS, APPROVAL_REQUIRED, INTERVENTION_REQUIRED | Based on agent exit signal |
| INTERVENTION_REQUIRED | PENDING, CANCELED | `resubmit`, `cancel` |
| APPROVAL_REQUIRED | SUCCESS, PENDING, CANCELED | `approve`, `reject`, `cancel` |
| SUSPENDED | PENDING, CANCELED | `resume`, `cancel` |
| SUCCESS | *Terminal State* | - |
| CANCELED | *Terminal State* | - |

### Mapping CLI Commands to States

| CLI Command | Precondition | Effect |
|-------------|--------------|--------|
| `logist job create` | - | Creates job in DRAFT |
| `logist job activate` | DRAFT | → PENDING |
| `logist job step` | PENDING | Executes step → resting state |
| `logist job step JOB_ID` | Job in PENDING | Executes step on specific job |
| `logist job run` | PENDING jobs exist | Cycles steps until no PENDING jobs |
| `logist job approve` | APPROVAL_REQUIRED | → SUCCESS |
| `logist job reject` | APPROVAL_REQUIRED | → PENDING |
| `logist job resubmit` | INTERVENTION_REQUIRED | → PENDING |
| `logist job cancel` | Any non-terminal | → CANCELED |
| `logist job suspend` | Any active | → SUSPENDED |
| `logist job resume` | SUSPENDED | → PENDING |

## Changes Required

### Phase 1: Documentation Updates

#### 1.1 Update doc/04_state_machine.md
- Replace current state diagram with new runner-aligned diagram
- Update state definitions to remove REVIEW_REQUIRED, REVIEWING
- Add PROVISIONING, EXECUTING, HARVESTING, RECOVERING states
- Replace RUNNING with split states (PROVISIONING, EXECUTING, HARVESTING)
- Emphasize step as atomic unit
- Document transient vs resting state distinction
- Add runner method mapping

#### 1.2 Update doc/07_runner_agent_architecture.md
- Add `recover()` method to runner interface
- Update lifecycle diagram to show state transitions
- Add mapping between runner methods and job states
- Clarify that RECOVERING quickly returns to EXECUTING

#### 1.3 Update doc/01_architecture.md
- Update "Iterative Loop Structure" section (lines 79-92)
- Remove Worker Run/Supervisor Run/Steward Checkpoint terminology
- Replace with step-centric terminology: Provision → Execute → Harvest
- Update "Flow Control Logic" section (lines 88-92)
- Add step concept explanation

#### 1.4 Update doc/05_cli_reference.md
- Update state references throughout
- Add PROVISIONING, EXECUTING, HARVESTING to state list
- Document `logist job resubmit` command
- Remove REVIEW_REQUIRED, REVIEWING references

#### 1.5 Update doc/problems.md
- Mark Problem 7 (Worker/Supervisor vs Runner/Agent) as RESOLVED
- Add note about state machine redesign completing the role removal

### Phase 2: Source Code Evaluation

#### 2.1 Evaluate src/logist/job_state.py
- Current states likely include: DRAFT, PENDING, RUNNING, PAUSED, REVIEW_REQUIRED, REVIEWING, APPROVAL_REQUIRED, INTERVENTION_REQUIRED, SUCCESS, FAILED, CANCELED, SUSPENDED
- Changes needed:
  - Add: PROVISIONING, EXECUTING, HARVESTING, RECOVERING
  - Remove: REVIEW_REQUIRED, REVIEWING, RUNNING, PAUSED
  - Keep: DRAFT, PENDING, SUCCESS, CANCELED, SUSPENDED, INTERVENTION_REQUIRED, APPROVAL_REQUIRED
- Update `transition_state()` with new valid transitions
- Update `get_current_state()` with new state handling

#### 2.2 Evaluate src/logist/core_engine.py
- Update `step_job()` method to transition through new states:
  - PENDING → PROVISIONING (before `provision()`)
  - PROVISIONING → EXECUTING (before `spawn()`)
  - EXECUTING → HARVESTING (after `wait()` or completion signal)
  - HARVESTING → [resting state] (based on agent exit signal)
- Handle timeout → RECOVERING → EXECUTING flow

#### 2.3 Evaluate src/logist/cli.py
- Update status displays to show new states
- Update `step` command to handle new state transitions
- Add `logist job resubmit` command if not present
- Remove any REVIEW_REQUIRED/REVIEWING references

#### 2.4 Evaluate src/logist/runners/base.py
- Add `recover()` method to Runner interface:
```python
def recover(self, process_id: str, job_context: Dict) -> Tuple[bool, Dict]:
    """
    Attempt to recover a stuck execution.

    Returns:
        (True, updated_inputs) - Recovery succeeded, continue EXECUTING with updated inputs
        (False, {}) - Recovery failed, transition to INTERVENTION_REQUIRED
    """
    raise NotImplementedError
```

#### 2.5 Evaluate test files
- tests/test_job_state.py - Update for new states
- tests/test_core_engine.py - Update for new transitions
- tests/test_cli.py - Update for resubmit command

### Phase 3: Implementation Priority

**High Priority (Breaking Changes):**
1. Update JobState enum in job_state.py
2. Update transition_state() with new valid transitions
3. Update core_engine.py to use new states during step execution
4. Update CLI status displays

**Medium Priority (New Features):**
5. Add recover() to Runner interface
6. Implement recover() in DirectRunner (basic implementation)
7. Ensure `logist job resubmit` works correctly

**Low Priority (Documentation):**
8. Update all documentation files

## Impact Analysis

### Breaking Changes

1. **State Enum Changes** - Code checking for RUNNING, REVIEW_REQUIRED, REVIEWING will break
2. **Transition Logic** - Any code with hardcoded transitions needs updates
3. **Status Display** - CLI output will show different state names

### Backward Compatibility

- Existing DRAFT, PENDING, SUCCESS, CANCELED, SUSPENDED states are unchanged
- INTERVENTION_REQUIRED, APPROVAL_REQUIRED remain semantically similar
- Job manifests with old states may need migration script

### Migration Strategy

1. Add new states to enum while keeping old ones (deprecated)
2. Map old states to new states in a migration function:
   - RUNNING → EXECUTING (or INTERVENTION_REQUIRED if stuck)
   - REVIEW_REQUIRED → INTERVENTION_REQUIRED
   - REVIEWING → INTERVENTION_REQUIRED
   - PAUSED → SUSPENDED
3. Remove deprecated states after migration period

## Success Criteria

- [ ] doc/04_state_machine.md updated with new diagram and definitions
- [ ] doc/07_runner_agent_architecture.md includes recover() method
- [ ] doc/01_architecture.md removes Worker/Supervisor terminology
- [ ] doc/05_cli_reference.md documents new states
- [ ] doc/problems.md marks relevant problems as resolved
- [ ] JobState enum includes new states (without REVIEW_REQUIRED, REVIEWING)
- [ ] core_engine.py transitions through new states during step
- [ ] Runner interface includes recover() method signature
- [ ] CLI displays new state names correctly
- [ ] All tests pass with new state machine

## Risk Assessment

- **High Risk:** State enum changes affect many files
- **Medium Risk:** Migration of existing job manifests
- **Medium Risk:** Test coverage for all new state transitions
- **Low Risk:** Documentation updates are straightforward

## Notes

### Key Design Decisions

1. **No AWAITING_DECISION state** - The agent's exit signal (parsed during HARVESTING) directly determines the next resting state. There is no intermediate decision state.

2. **RECOVERING is transient** - It quickly returns to EXECUTING with updated inputs (e.g., new context from recovery attempt). If recovery fails, job goes to INTERVENTION_REQUIRED.

3. **HARVESTING is transient** - It quickly transitions to a resting state (SUCCESS, APPROVAL_REQUIRED, or INTERVENTION_REQUIRED) based on what harvest discovers from the agent's output.

4. **INTERVENTION_REQUIRED is sticky** - A job stays in this state indefinitely until a human runs `logist job resubmit` to move it back to PENDING.

5. **Step-centric execution** - The step is the atomic unit. After a step completes, the next step may operate on a different PENDING job in the queue.

### Alignment with Architecture

This redesign aligns the state machine with:
- Runner lifecycle operations (`provision`, `spawn`, `monitor`, `harvest`, `cleanup`, `recover`)
- Agent-agnostic architecture (no Worker/Supervisor roles)
- Non-interactive execution principle (agents run to completion without user prompts during execution)
- Future parallel job execution (each job independently reaches resting states)
