# 🚦 Logist State Machine Semantics

This document defines the deterministic state machine used by the Logist workflow engine to manage the lifecycle of individual tasks (agent interactions) within a **Directed Acyclic Graph (DAG)** workflow. These state names will be used as constants and enumerated values in the JSON schema for inter-component communication and LLM responses.

---

## 1. ⚙️ Core Execution States (Automated Lifecycle)

These states describe the normal, automated execution path of a task.

* **DRAFT**
    * **Description:** The job has been created but is not yet configured for execution. Users can set objectives, details, acceptance criteria, and other properties before activation.
    * **Transition From:** *Initial State*, Creation.
    * **Next Automated States:** PENDING (via activation).

* **PENDING**
    * **Description:** The task is ready to run but is waiting for the scheduler or for its dependencies to complete.
    * **Transition From:** DRAFT (activated), SUSPENDED (resumed), DEPENDENCIES\_MET, RESUBMIT.
    * **Next Automated States:** RUNNING, CANCELED.

* **SUSPENDED**
    * **Description:** The task is intentionally paused by the scheduler or an external command (e.g., administrative intervention, resource constraints).
    * **Transition From:** Any active state (DRAFT, PENDING, RUNNING, etc.) via suspend command.
    * **Next Automated States:** PENDING (via resume command), CANCELED (via administrative action).
    * **Purpose:** Allows temporary exclusion from execution while preserving state for resumption.

* **RUNNING**
    * **Description:** An agent is actively executing.
    * **Transition From:** PENDING, PAUSED.
    * **Next Automated States:** REVIEW_REQUIRED (always - command-driven flow).

* **PAUSED**
    * **Description:** The task is intentionally suspended by the scheduler or an external command (e.g., rate limiting).
    * **Transition From:** RUNNING.
    * **Next Automated States:** RUNNING, CANCELED.

* **SUCCESS**
    * **Description:** The task completed execution and returned a valid, expected result.
    * **Transition From:** RUNNING, FORCE\_SUCCESS.
    * **Next State:** *End State*, Next Task PENDING.

* **FAILED** (Deprecated)
    * **Note:** In the command-driven model, RUNNING always transitions to REVIEW_REQUIRED. The FAILED state is no longer part of the primary workflow.

* **CANCELED**
    * **Description:** The task was terminated by an external command before completion.
    * **Transition From:** PENDING, RUNNING, PAUSED.
    * **Next State:** *End State*.

---

## 2. ✋ Command-Driven Intervention States (Actionable)

These states define **what command runs next** when `logist job step` is executed, rather than representing assessments of current status.

* **REVIEW\_REQUIRED**
    * **Description:** Review process is required to assess completed work.
    * **Semantic Role:** **Automated Quality Check:** System evaluates output and determines quality/recommendations.
    * **Next State:** REVIEWING.

* **REVIEWING**
    * **Description:** Review process is actively executing to assess results.
    * **Semantic Role:** **Active Assessment Execution:** Analogous to RUNNING but specifically for review operations.
    * **Next State:** APPROVAL_REQUIRED or INTERVENTION_REQUIRED.

* **INTERVENTION\_REQUIRED**
    * **Description:** Requires Steward (human) intervention for fixes, adjustments, or other changes before continuing workflow.
    * **Semantic Role:** **Human Problem-Solving:** Allows Steward to fix issues, provide guidance, or make workflow adjustments.
    * **Next States:** PENDING, REVIEW_REQUIRED, or CANCELED.

* **APPROVAL\_REQUIRED**
    * **Description:** Requires final Steward approval/rejection before the job can be marked SUCCESS and allow dependent jobs to proceed.
    * **Semantic Role:** **Final Human Gate:** Either auto-approve (if configured) or require explicit human sign-off.
    * **Next States:** SUCCESS or PENDING (if rejected).

---

## 3. 🔄 Error Handling and Agent Handoffs

Logist implements a structured error handling flow that cleanly separates concerns between agents while maintaining clear escalation paths.

### Agent Responsibility Model (Deprecated)
**Note:** The old agent-centric state ownership is deprecated in favor of the command-driven model above. States now define what command to run next, not which agent owns the state.

### Command-Driven Flow
1. **Job Creation**: Create job → `DRAFT` (initial state for configuration)
2. **Job Configuration**: `DRAFT` + `logist job config` commands → `DRAFT` (modified)
3. **Job Activation**: `DRAFT` + `logist job activate` → `PENDING` (added to execution queue)
4. **Agent Execution**: `PENDING` → `RUNNING` → `REVIEW_REQUIRED`
5. **Review Process**: `REVIEW_REQUIRED` → `REVIEWING` → `APPROVAL_REQUIRED` or `INTERVENTION_REQUIRED`
6. **Human Decisions**: Final gates where humans make approval/rejection/termination decisions

### System Health Monitoring
- **Automatic Recovery**: Stuck agents (marked RUNNING/REVIEWING but no active execution) auto-reset to safe pending states
- **Worker Recovery**: `RUNNING` (stuck) → `PENDING` (retry Worker)
- **Supervisor Recovery**: `REVIEWING` (stuck) → `REVIEW_REQUIRED` (retry Supervisor)
- **Timeout Detection**: No evidence of response/output after threshold triggers recovery

This design ensures resilience and prevents permanently blocked jobs while maintaining clear escalation paths.

## 4. ➡️ Continuation Commands (The Semantics of Resumption)

These are the commands that an external party (human or repair agent) issues to Logist to transition a task out of an Intervention State.

* **RESUBMIT** (human command)
    * **Transition From State(s):** INTERVENTION_REQUIRED (after human fixes).
    * **Action Semantics:** **Resumes:** After Steward intervention, restarts the workflow from PENDING.
    * **Next State:** PENDING.

* **APPROVE** (human command)
    * **Transition From State(s):** APPROVAL_REQUIRED.
    * **Action Semantics:** **Approves:** Marks job as complete, allows dependent jobs to proceed.
    * **Next State:** SUCCESS.

* **REJECT** (human command)
    * **Transition From State(s):** APPROVAL_REQUIRED.
    * **Action Semantics:** **Rejects:** Sends job back for more work (typically to Worker phase).
    * **Next State:** PENDING.

* **TERMINATE** (human command)
    * **Transition From State(s):** INTERVENTION_REQUIRED.
    * **Action Semantics:** **Aborts:** Steward determines workflow should end.
    * **Next State:** CANCELED.

---

## 5. 💾 State Persistence

The current state of a job is persisted to the filesystem to ensure that workflows can be resumed.

-   **Location**: The state is stored within the **`job_manifest.json`** file, which resides inside each job's specific directory.
-   **Mechanism**: A dedicated `"status"` field in the JSON manifest holds the current state value (e.g., `"PENDING"`, `"RUNNING"`, `"SUSPENDED"`). The Logist engine reads this field at the start of any operation and updates it upon every state transition.

### Example `job_manifest.json`

```json
{
  "job_id": "sample-implementation",
  "description": "Sample job demonstrating logist workflow...",
  "status": "SUSPENDED",
  "current_phase": "implementation",
  "metrics": {
    "cumulative_cost": 22,
    "cumulative_time_seconds": 310
  },
  "history": [
    {
      "phase": "requirements_analysis",
      "status": "SUCCESS",
      "summary": "Completed analysis of email validation rules."
    },
    {
      "phase": "implementation",
      "status": "SUSPENDED",
      "summary": "Job suspended for external review before continuing."
    }
  ]
}
```

---

## 6. 🔄 State Transition Matrix

| From State | To States | Trigger/Command |
|------------|-----------|-----------------|
| DRAFT | PENDING, SUSPENDED, CANCELED | `logist job activate`, `logist job suspend`, `logist job cancel` |
| PENDING | RUNNING, SUSPENDED, CANCELED | Scheduler trigger, `logist job suspend`, `logist job cancel` |
| SUSPENDED | PENDING, CANCELED | `logist job resume`, `logist job cancel` |
| RUNNING | REVIEW_REQUIRED, SUSPENDED, CANCELED | Agent completion, `logist job suspend`, `logist job cancel` |
| REVIEW_REQUIRED | REVIEWING, SUSPENDED, CANCELED | `logist job step`, `logist job suspend`, `logist job cancel` |
| REVIEWING | APPROVAL_REQUIRED, INTERVENTION_REQUIRED, SUSPENDED, CANCELED | Review completion, `logist job suspend`, `logist job cancel` |
| APPROVAL_REQUIRED | SUCCESS, PENDING, SUSPENDED, CANCELED | `logist job approve`, `logist job reject`, `logist job suspend`, `logist job cancel` |
| INTERVENTION_REQUIRED | PENDING, REVIEW_REQUIRED, SUSPENDED, CANCELED | Human intervention, `logist job suspend`, `logist job cancel` |
| SUCCESS | *Terminal State* | Job completed successfully |
| CANCELED | *Terminal State* | Job terminated by user |
| FAILED | *Terminal State* | Job failed (deprecated but kept for compatibility) |