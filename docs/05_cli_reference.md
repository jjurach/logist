# Logist CLI Reference

This document provides a comprehensive reference for all `logist` Command-Line Interface (CLI) commands. The CLI is built using the **Click** library, which allows for a clean, composable structure of nested commands.

## Global Options

These options can be used with the main `logist` command and affect all subcommands.

### `--jobs-dir <path>`
Specifies the root directory where the `jobs_index.json` file and all individual job subdirectories are stored. This allows for flexible project organization and development environments.

-   **Default**: `~/.logist/jobs`
-   **Environment Variable**: `PURSER_JOBS_DIR` can be set to override the default
-   **Development**: For development, you can use a local directory, e.g., `logist --jobs-dir ./jobs job list`.

### Environment Variables

**PURSER_JOBS_DIR**
: Override the default jobs directory (`~/.logist/jobs`).

**PURSER_JOB_ID**
: Specify the currently selected job ID when no job ID argument is provided. Takes precedence over the job selected in the jobs index.

---

## File Attachment with Cline Integration

Logist integrates with Cline's `--file` option to provide rich context for task execution:

### Single File Attachment
```bash
cline --oneshot --file task_spec.md "complete this task"
```

### Multiple File Attachments
```bash
cline --oneshot --file requirements.md --file guidelines.md --file examples.py "implement following all attached documents"
```

### Logist Enhanced Execution
The `scripts/oneshot.sh` script automatically attaches:
- `_meta_prompt_instructions.md` (common procedures)
- Specified prompt file (task-specific instructions)

This provides standardized context across all Logist executions while allowing task-specific customizations.

---

## Top-Level Commands

### `logist --version`
Displays the installed version of Logist.

### `logist --help`
Shows a help message for the main `logist` command, listing all available command groups.

---

## Job Management (`logist job`)

The `logist job` command group contains all subcommands for creating, inspecting, and executing jobs.

### `logist job create [DIRECTORY]`
Initializes a directory as a Logist job, or updates an existing one. This command is the entry point for registering a new workflow with Logist.

-   It finds or creates a `job_manifest.json` in the target directory.
-   It registers the directory's path in the `jobs_index.json` found in the configured `--jobs-dir`.
-   It automatically sets the newly created/registered job as the **currently selected job**.
-   **Arguments**:
    -   `[DIRECTORY]` (optional): The path to the job directory. Defaults to the current directory (`.`).
-   **Warning**: The command will warn you if the job directory is not located inside the configured `--jobs-dir`.
-   **Example**:
    ```bash
    # Initialize the current directory as a job
    logist job create .
    ```

### `logist job select <job_id>`
Sets a job as the currently selected one, allowing you to run subsequent commands without specifying the `job_id`.

-   **Arguments**:
    -   `<job_id>` (required): The ID of the job you want to select.
-   **Example**:
    ```bash
    logist job select my-other-job
    ```

### `logist job list`
Lists all active jobs registered in the `jobs_index.json`.

-   **Output**: A summary table showing the `Job ID`, `Status`, and a brief description for each job.
-   **Example**:
    ```bash
    logist job list
    ```

### `logist job status [JOB_ID]`
Displays the detailed current status of a specific job. If `JOB_ID` is omitted, it shows the status of the **currently selected job**.

-   **Arguments**:
    -   `[JOB_ID]` (optional): The identifier of the job to inspect.
-   **Example**:
    ```bash
    # Show status for the current job
    logist job status

    # Show status for a specific job
    logist job status my-first-job
    ```


### `logist job history [JOB_ID]`
*(New in future implementation)*

Displays a chronological history of all agent runs and Steward interventions for a specific job. Defaults to the **currently selected job** if `JOB_ID` is omitted.

-   **Arguments**:
    -   `[JOB_ID]` (optional): The identifier of the job.
-   **Example**:
    ```bash
    logist job history
    ```

### `logist job inspect [JOB_ID]`
*(New in future implementation)*

Dumps the full, raw `job_manifest.json` for a specific job to the console. Defaults to the **currently selected job** if `JOB_ID` is omitted.

-   **Arguments**:
    -   `[JOB_ID]` (optional): The identifier of the job.
-   **Example**:
    ```bash
    logist job inspect
    ```

### `logist job preview [JOB_ID]`
*(New in future implementation)*

Performs a **non-destructive preview** of the next agent interaction for a given job. Defaults to the **currently selected job** if `JOB_ID` is omitted.

-   **Arguments**:
    -   `[JOB_ID]` (optional): The identifier of the job to preview.
-   **Output**: The full, formatted prompt intended for the next agent.
-   **Example**:
    ```bash
    logist job preview
    ```

### Execution Commands

These commands control the lifecycle and execution flow of a job. If `JOB_ID` is omitted, they operate on the **currently selected job**.

-   **`logist job run [JOB_ID]`**: Executes a job continuously until it completes or requires human intervention.
-   **`logist job step [JOB_ID] [--dry-run]`**: Executes only the next single phase of a job and then pauses.
    -   **`--dry-run` (option)**: Simulates a full step without making real LLM calls or modifying state.
-   **`logist job rerun [JOB_ID]`**: Resets a job completely to its initial state.
-   **`logist job restep [JOB_ID]`**: Reverts a job to its previous checkpoint.


---

## Role Management (`logist role`)
*(New in future implementation)*

This new command group will provide utilities for managing the agent roles available to Logist.

### `logist role list`
Lists all available agent roles found in the global `roles.json` manifest, along with their descriptions.

-   **Example**:
    ```bash
    logist role list
    ```

### `logist role inspect <role_name>`
Displays the full configuration for a specific role, including its name, description, instructions, and designated LLM model.

-   **Arguments**:
    -   `role_name` (required): The name of the role to inspect.
-   **Example**:
    ```bash
    logist role inspect Worker
    ```