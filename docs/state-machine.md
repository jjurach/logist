# Logist State Machine Semantics

This document defines the deterministic state machine used by the Logist workflow engine to manage job lifecycle. State names are used as constants in the JSON schema for inter-component communication.

---

## 1. Core Concept: The Step

A **step** is the atomic unit of execution in Logist. One step:
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
- `logist job run` - Cycles through PENDING jobs, executing steps until no PENDING jobs remain

After a step completes, the **next step may be for a different job** in the queue.

---

## 2. State Categories

### Resting States (Job waits here)

These are states where a job remains until an external action occurs.

| State | Description | Human Action Required? |
|-------|-------------|------------------------|
| **DRAFT** | Being configured | No (user is configuring) |
| **PENDING** | Ready for next step | No (scheduler picks it up) |
| **SUCCESS** | Complete | No (terminal) |
| **APPROVAL_REQUIRED** | Needs sign-off | **Yes** - approve or reject |
| **INTERVENTION_REQUIRED** | Needs fix | **Yes** - fix and resubmit |
| **SUSPENDED** | Paused | **Yes** - resume |
| **CANCELED** | Terminated | No (terminal) |

### Transient States (Job passes through during step execution)

These states occur during step execution and transition automatically.

| State | Description | Duration | Runner Method |
|-------|-------------|----------|---------------|
| **PROVISIONING** | Setting up workspace | Seconds to minutes | `provision()` |
| **EXECUTING** | Agent running | Minutes to hours | `spawn()`, `is_alive()`, `get_logs()` |
| **RECOVERING** | Restarting stuck agent | Seconds | `recover()` |
| **HARVESTING** | Collecting results | Seconds | `harvest()` |

**Note:** RECOVERING quickly returns to EXECUTING with updated inputs. HARVESTING quickly transitions to a resting state based on the agent's exit signal.

---

## 3. State Diagram

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

---

## 4. State Definitions

### DRAFT
- **Description:** The job has been created but is not yet configured for execution. Users can set objectives, details, acceptance criteria, and other properties before activation.
- **Transition From:** Initial State (job creation)
- **Transitions To:** PENDING (via `activate`), SUSPENDED (via `suspend`), CANCELED (via `cancel`)

### PENDING
- **Description:** The job is ready for execution and waiting to be picked up by `logist job step` or scheduler.
- **Transition From:** DRAFT (activated), SUSPENDED (resumed), INTERVENTION_REQUIRED (resubmitted), APPROVAL_REQUIRED (rejected)
- **Transitions To:** PROVISIONING (step begins), SUSPENDED, CANCELED

### PROVISIONING (Transient)
- **Description:** Runner is setting up the workspace - cloning git repository, creating job branch, copying attachments.
- **Runner Method:** `provision()`
- **Transition From:** PENDING
- **Transitions To:** EXECUTING (success), INTERVENTION_REQUIRED (failure), CANCELED

### EXECUTING (Transient)
- **Description:** Agent is actively running the task.
- **Runner Methods:** `spawn()`, `is_alive()`, `get_logs()`, `wait()`
- **Transition From:** PROVISIONING, RECOVERING
- **Transitions To:** HARVESTING (agent signals completion), RECOVERING (timeout/stuck), CANCELED

### RECOVERING (Transient)
- **Description:** Runner is attempting to restart a stuck execution.
- **Runner Method:** `recover()`
- **Transition From:** EXECUTING (timeout detected)
- **Transitions To:** EXECUTING (recovery succeeds, with updated inputs)
- **Note:** If recovery fails, the job transitions to INTERVENTION_REQUIRED via HARVESTING.

### HARVESTING (Transient)
- **Description:** Runner is collecting outputs, committing changes to the job branch, and determining the final state based on the agent's exit signal.
- **Runner Method:** `harvest()`
- **Transition From:** EXECUTING
- **Transitions To:** SUCCESS, APPROVAL_REQUIRED, or INTERVENTION_REQUIRED (based on agent exit signal)

### INTERVENTION_REQUIRED
- **Description:** Requires human intervention before the job can continue. The job stays in this state **indefinitely** until a human acts.
- **Transition From:** PROVISIONING (failure), HARVESTING (agent signaled stuck/error)
- **Transitions To:** PENDING (via `resubmit`), CANCELED (via `cancel`)
- **Human Action:** Fix issues, then run `logist job resubmit`

### APPROVAL_REQUIRED
- **Description:** Work is complete but requires human approval before marking as SUCCESS.
- **Transition From:** HARVESTING (agent signaled needs approval)
- **Transitions To:** SUCCESS (via `approve`), PENDING (via `reject`), CANCELED (via `cancel`)
- **Human Action:** Review work, then run `logist job approve` or `logist job reject`

### SUSPENDED
- **Description:** Job is intentionally paused.
- **Transition From:** Any non-terminal state via `suspend`
- **Transitions To:** PENDING (via `resume`), CANCELED (via `cancel`)

### SUCCESS (Terminal)
- **Description:** The job completed successfully.
- **Transition From:** HARVESTING (goal achieved), APPROVAL_REQUIRED (approved)
- **Transitions To:** None (terminal state)

### CANCELED (Terminal)
- **Description:** The job was terminated by user action.
- **Transition From:** Any non-terminal state via `cancel`
- **Transitions To:** None (terminal state)

---

## 5. State Transition Matrix

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

---

## 6. CLI Commands and State Transitions

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
| `logist job suspend` | Any non-terminal | → SUSPENDED |
| `logist job resume` | SUSPENDED | → PENDING |

---

## 7. State Persistence

The current state of a job is persisted in the `job_manifest.json` file within each job's directory.

```json
{
  "job_id": "sample-implementation",
  "description": "Sample job demonstrating logist workflow...",
  "status": "PENDING",
  "current_phase": "implementation",
  "metrics": {
    "cumulative_cost": 22,
    "cumulative_time_seconds": 310
  },
  "history": [
    {
      "phase": "implementation",
      "status": "PENDING",
      "summary": "Job activated and ready for execution."
    }
  ]
}
```

---

## 8. Deprecated States

The following states are deprecated and should not be used in new code:

| State | Replacement | Notes |
|-------|-------------|-------|
| RUNNING | PROVISIONING, EXECUTING, HARVESTING | Split into runner lifecycle phases |
| PAUSED | SUSPENDED | Consolidated pause semantics |
| REVIEW_REQUIRED | Removed | No separate review phase; agents self-evaluate |
| REVIEWING | Removed | No separate review phase; agents self-evaluate |
| FAILED | INTERVENTION_REQUIRED or CANCELED | Use appropriate error state |

For backward compatibility, existing job manifests with deprecated states should be migrated:
- RUNNING → INTERVENTION_REQUIRED (stuck) or re-execute
- REVIEW_REQUIRED → INTERVENTION_REQUIRED
- REVIEWING → INTERVENTION_REQUIRED
- PAUSED → SUSPENDED
- FAILED → CANCELED
