Follow `docs/prompts/_meta_prompt_instructions.md` when executing this prompt.

# 00-17-role_inspect_command: Implement `logist role inspect` Command

## Task Description
Implement the `logist role inspect <role_name>` CLI command to display the full configuration of a specific agent role dynamically. This command should replace the current placeholder implementation in `logist/cli.py` with functionality that reads role definitions from JSON files stored in the `jobs_dir`.

## Command Intention
The `logist role inspect <role_name>` command provides a detailed view of a specified agent role's configuration, including its name, description, instructions, and designated LLM model. This is critical for users needing to understand the exact parameters of a role, debug role definitions, or verify custom role configurations.

## Implementation Advice and Source Code Paths

### Primary Source File
-   `logist/cli.py`: This file contains the `role` Click group and will house the `inspect_role` command.

### Detailed Implementation Steps

1.  **Modify `inspect_role` function in `logist/cli.py`:**
    *   This function will be decorated with `@role.command(name="inspect")` and will accept `role_name` as a required argument.
    *   The `jobs_dir` path will be accessible via the Click context (`ctx.obj["JOBS_DIR"]`).
    *   Construct the full path to the role's JSON definition file, typically `f"{jobs_dir}/schemas/roles/{role_name.lower()}.json"`.
    *   Use `pathlib` for robust path handling.
    *   Attempt to read and parse the JSON file.
    *   Implement error handling for `FileNotFoundError` (role not found) and `json.JSONDecodeError` (malformed JSON).
    *   If successful, pretty-print the JSON content to the console using `json.dumps(role_data, indent=2)`.
    *   Use `click.secho` for colored output (e.g., red for errors, green for success).

### Example Role File Structure (from `config/default-roles.json` and `docs/02_roles_and_data.md`)
```json
{
  "name": "Worker",
  "description": "Expert software development and implementation agent specializing in code generation, debugging, and technical problem-solving",
  "instructions": "You are an expert software engineer...",
  "llm_model": "grok-code-fast-1"
}
```

## Unit Tests and Demo Features

### Unit Tests (`tests/test_cli.py`)
Add test cases to `tests/test_cli.py` to cover the `logist role inspect` command:
1.  **Test `inspect_role` for existing role:**
    *   Ensure that after `logist init` is run (which copies default role files), `logist role inspect Worker` correctly displays the "Worker" role's full JSON configuration.
    *   Verify that the output contains the expected fields like `name`, `description`, `instructions`, and `llm_model`.
2.  **Test `inspect_role` for a non-existent role:**
    *   Create a temporary `jobs_dir` environment where `logist role inspect NonExistentRole` is called.
    *   Verify that the command returns an appropriate "role not found" error message and exits with a non-zero status code.
3.  **Test `inspect_role` with a malformed role file:**
    *   Create a temporary `jobs_dir` with a custom role JSON file that is intentionally malformed.
    *   Verify that `logist role inspect MalformedRole` handles this gracefully by reporting a JSON parsing error.
4.  **Test `inspect_role` with a valid custom role:**
    *   Add a new valid custom role JSON file to a temporary `jobs_dir`.
    *   Verify that `logist role inspect CustomRole` correctly displays its full configuration.

### Demo Features (`test-demo.sh`)
Update `test-demo.sh` to include verification steps for `logist role inspect`:
1.  **Add execution step for existing role:** After `logist init`, add a command to execute `logist --jobs-dir ./jobs role inspect Worker`.
2.  **Assert output for existing role:** Verify that the output of `logist role inspect Worker` contains expected elements of the Worker role (e.g., "Worker", "Expert software development"). This can be done using `grep`.
3.  **Add execution step for non-existent role (negative test):** Include a command to execute `logist --jobs-dir ./jobs role inspect NonExistentRole`.
4.  **Assert output for non-existent role:** Verify that the output indicates the role was not found and that the command exits with a non-zero status code (e.g., `! grep "Role 'NonExistentRole' not found"`, or check exit status).

## Verification Standards
-   [ ] `logist role inspect <role_name>` command is implemented and correctly displays the full configuration of an existing role after `logist init`.
-   [ ] The command gracefully handles scenarios where the specified role does not exist or its definition file is malformed.
-   [ ] Relevant unit tests are added to `tests/test_cli.py` and pass.
-   [ ] `test-demo.sh` includes steps to verify `logist role inspect` output for both existing and non-existent roles.
-   [ ] This prompt file has been updated with implementation details, testing guidance, and a reference to `_meta_prompt_instructions.md`.