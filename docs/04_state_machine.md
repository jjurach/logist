# 🚦 Logist State Machine Semantics

This document defines the deterministic state machine used by the Logist workflow engine to manage the lifecycle of individual tasks (agent interactions) within a **Directed Acyclic Graph (DAG)** workflow. These state names will be used as constants and enumerated values in the JSON schema for inter-component communication and LLM responses.

---

## 1. ⚙️ Core Execution States (Automated Lifecycle)

These states describe the normal, automated execution path of a task.

* **PENDING**
    * **Description:** The task is ready to run but is waiting for the scheduler or for its dependencies to complete.
    * **Transition From:** *Initial State*, DEPENDENCIES\_MET, RESUBMIT.
    * **Next Automated States:** RUNNING, CANCELED.

* **RUNNING**
    * **Description:** An agent is actively executing (Worker by default, but may be Supervisor depending on state transitions).
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
    * **Description:** Run the Supervisor in --oneshot mode to assess the Worker's completed task.
    * **Semantic Role:** **Automated Quality Check:** Supervisor evaluates Worker output and determines quality/recommendations.
    * **Next State:** REVIEWING.

* **REVIEWING**
    * **Description:** Supervisor is actively executing in --oneshot mode to review Worker results.
    * **Semantic Role:** **Active Assessment Execution:** Analogous to RUNNING but specifically for Supervisor operations.
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
1. **Worker Execution**: `PENDING` → `RUNNING` (worker) → `REVIEW_REQUIRED`
2. **Supervisor Review**: `REVIEW_REQUIRED` → `REVIEWING` (supervisor) → `APPROVAL_REQUIRED` or `INTERVENTION_REQUIRED`
3. **Human Decisions**: Final gates where humans make approval/rejection/termination decisions

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
-   **Mechanism**: A dedicated `"status"` field in the JSON manifest holds the current state value (e.g., `"PENDING"`, `"RUNNING"`, `"STUCK"`). The Logist engine reads this field at the start of any operation and updates it upon every state transition.

### Example `job_manifest.json`

```json
{
  "job_id": "sample-implementation",
  "description": "Sample job demonstrating logist workflow...",
  "status": "STUCK",
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
      "status": "STUCK",
      "summary": "The generated code has a syntax error that I cannot resolve."
    }
  ]
}
```