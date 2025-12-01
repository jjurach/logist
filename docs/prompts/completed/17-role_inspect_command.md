# Role Inspect Command Implementation - Cline Oneshot Prompt

Follow `docs/prompts/_meta_prompt_instructions.md` when executing this prompt.

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

## Implementation Sequence
1. **Analyze:** Read master plan requirements for this task and verify prerequisite phases complete
2. **Design:** Plan the implementation approach considering path resolution and error scenarios
3. **Build:** Create the inspection functionality with proper file handling and JSON parsing
4. **Test:** Verify functionality with various role files and error conditions
5. **Document:** Update documentation and this prompt file
6. **Verify:** Ensure requirements are met and output is properly formatted
7. **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`

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
-   [x] `logist role inspect <role_name>` command is implemented and correctly displays the full configuration of an existing role after `logist init`.
-   [x] The command gracefully handles scenarios where the specified role does not exist or its definition file is malformed.
-   [x] Relevant unit tests are added to `tests/test_cli.py` and pass.
-   [x] `test-demo.sh` includes steps to verify `logist role inspect` output for both existing and non-existent roles.
-   [x] This prompt file has been updated with implementation details, testing guidance, and a reference to `_meta_prompt_instructions.md`.

## Dependencies Check
- **Master Plan:** Reference this specific task requirements from the Logist development plan
- **Dependencies:** Requires role files to be present and accessible (typically after `logist init`)
- **Prerequisites:** File system read access and JSON parsing capabilities
- **Testing:** Test both positive and negative scenarios for comprehensive coverage

## Additional Considerations

### Edge Cases and Constraints
*   **Case Sensitivity:** Role names should be handled case-insensitively for file lookup but preserve the original case in display, ensuring `worker` and `WORKER` both resolve to the Worker role.
*   **File Path Assumptions:** The implementation assumes role files are located at `jobs_dir/{role_name}.json`, so changes to this convention would require corresponding updates.
*   **Security Considerations:** When displaying role configurations, ensure no sensitive information (like API keys) is ever stored in role definition files.
*   **Performance for Large Roles:** Role files with extensive instructions should be displayed efficiently without truncating content.
*   **Internationalization:** Consider how role descriptions might be localized or formatted for different display contexts.

### Success Criteria for Implementation
-   [x] `logist role inspect <role_name>` command is implemented and correctly displays the full configuration of an existing role after `logist init`.
-   [x] The command gracefully handles scenarios where the specified role does not exist or its definition file is malformed.
-   [x] Relevant unit tests are added to `tests/test_cli.py` and pass.
-   [x] `test-demo.sh` includes steps to verify `logist role inspect` output for both existing and non-existent roles.
-   [x] This prompt file has been updated with implementation details, testing guidance, and a reference to `_meta_prompt_instructions.md`.

### Implementation Quality Guidelines

**Pre-Implementation Checklist:**
- [ ] Review role file format and location conventions
- [ ] Analyze error handling patterns for file operations and JSON parsing
- [ ] Plan output formatting strategy for clear, readable configuration display
- [ ] Consider security implications of exposing role configuration details
- [ ] Design fallback mechanisms for missing or corrupted role files

**Code Quality Requirements:**
- Implement robust file system operations with comprehensive error handling
- Follow existing CLI patterns for consistent command behavior
- Add proper logging for troubleshooting configuration access issues
- Include input validation and sanitization for role name parameters
- Ensure graceful degradation when role files are inaccessible

**Testing Strategy:**
- Unit tests for path resolution, file reading, and JSON parsing logic
- Integration tests with real role files in various states
- Error condition testing for missing files and malformed JSON
- Performance testing for large role configuration files
- Security testing to ensure no sensitive data leakage

## Meta-Prompt Instructions
This prompt follows the guidelines in `docs/prompts/_meta_prompt_instructions.md` for execution, success/failure reporting, and Git commit protocols.

## Implementation Complete ✅
**Completed:** November 30, 2025

**Note:** Upon analysis, the `logist role inspect <role_name>` command was already fully implemented. Added comprehensive unit tests and demo script verification to ensure robust functionality for both existing and non-existent roles.