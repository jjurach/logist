Follow `docs/prompts/_meta_prompt_instructions.md` when executing this prompt.

# 00-16-role_list_command: Implement `logist role list` Command

## Task Description
Implement the `logist role list` CLI command to dynamically display all available agent roles configured within Logist. This command should replace the current placeholder implementation in `logist/cli.py` with functionality that reads role definitions from JSON files stored in the `jobs_dir`.

## Command Intention
The `logist role list` command provides an overview of all programmable agent roles, including their names and descriptions. This allows users to quickly understand which roles are available for job execution and to reference them when configuring job phases or inspecting specific roles.

## Implementation Advice and Source Code Paths

### Primary Source File
-   `logist/cli.py`: This file contains the `role` Click group and the `list_roles` command. The `PlaceholderRoleManager` class and its `list_roles` method will be updated.

### Detailed Implementation Steps

1.  **Modify `PlaceholderRoleManager.list_roles` in `logist/cli.py`:**
    *   The `list_roles` method needs to be enhanced to dynamically scan for role definition files.
    *   **Determine Role File Location:** Role definition files (e.g., `worker.json`, `supervisor.json`) are copied into the `jobs_dir` during the `logist init` process. The `jobs_dir` path needs to be accessible within this method. It is best to pass `jobs_dir` as an argument to the `list_roles` method.
    *   **Scan for Role Files:** Iterate through the files within the `jobs_dir`. Identify JSON files that represent role definitions. A simple heuristic could be to check if the file name ends with `.json` and contains `name` and `description` fields.
    *   **Parse Role Definitions:** For each identified JSON file, read its content.
    *   **Extract Role Information:** From each parsed JSON, extract the `name` and `description` of the role.
    *   **Handle Errors:** Implement robust error handling for cases where JSON files are malformed, unreadable, or do not contain the expected `name` and `description` fields. These files should be skipped with a warning message (e.g., using `click.secho` with `fg="yellow"`).
    *   **Return Formatted List:** The method should return a list of dictionaries, where each dictionary has keys like `"name"` and `"description"` corresponding to an available role.

2.  **Update `role.command(name="list")` in `logist/cli.py`:**
    *   Modify the `list_roles` function that is decorated with `@role.command(name="list")` to accept the `jobs_dir` from the Click context (`ctx.obj["JOBS_DIR"]`) and pass it to the `role_manager.list_roles()` call.

### Example Role File Structure (from `config/default-roles.json` and `docs/02_roles_and_data.md`)
```json
{
  "name": "Worker",
  "description": "Expert software development and implementation agent specializing in code generation, debugging, and technical problem-solving",
  "instructions": "You are an expert software engineer...",
  "llm_model": "grok-code-fast-1"
}
```
The implementation should primarily focus on extracting `name` and `description`.

## Unit Tests and Demo Features

### Unit Tests (`tests/test_cli.py`)
Add test cases to `tests/test_cli.py` to cover the `logist role list` command:
1.  **Test `list_roles` after `init`:**
    *   Ensure that after `logist init` is run (which copies default role files), `logist role list` correctly displays the "Worker" and "Supervisor" roles.
    *   Verify that the output contains the expected names and descriptions.
2.  **Test with no roles:**
    *   Create a temporary `jobs_dir` without any role JSON files.
    *   Verify that `logist role list` correctly reports no roles or an empty list.
3.  **Test with malformed role file:**
    *   Create a temporary `jobs_dir` with a malformed JSON file (e.g., incomplete JSON, missing `name` or `description`).
    *   Verify that the command handles this gracefully (e.g., skips the file with a warning) and still lists other valid roles.
4.  **Test with custom roles:**
    *   Add a new valid role JSON file to a temporary `jobs_dir`.
    *   Verify that `logist role list` includes this new role in its output.

### Demo Features (`test-demo.sh`)
Update `test-demo.sh` to include a verification step for `logist role list`:
1.  **Add execution step:** After `logist init`, add a command to execute `logist role list`.
2.  **Assert output:** Verify that the output of `logist role list` contains the expected default roles (e.g., "Worker" and "Supervisor"). This can be done by piping the output to `grep` or similar tools and checking the exit code.

## Verification Standards
-   [ ] `logist role list` command is implemented and correctly lists default roles after `logist init`.
-   [ ] The command gracefully handles scenarios with no role files, malformed role files, and custom role files.
-   [ ] Relevant unit tests are added to `tests/test_cli.py` and pass.
-   [ ] `test-demo.sh` includes a step to verify `logist role list` output.
-   [ ] This prompt file has been updated with implementation details, testing guidance, and a reference to `_meta_prompt_instructions.md`.