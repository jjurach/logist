# Init Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `init_command` (Phase 1) from the Logist master development plan. This unit implements the `logist init` command that sets up jobs directory structure and copies default configurations. Consult this prompts file throughout implementation to ensure every requirement is met - reference it explicitly after each major step to verify compliance.

## Critical Requirements - Jobs Directory Setup

### Directory Structure Creation
The `logist init` command must:
- Create the configurable jobs directory (`~/.logist/jobs` by default)
- Set up the jobs index file structure
- Copy default role configurations to the jobs directory
- Enable flexible project organization

### Configuration File Management
Ensure proper initialization of:
- Jobs index JSON file (`jobs_index.json`)
- Default role configurations in `$JOBS_DIR/`
- Directory structure for job isolation
- Configuration validation and error handling

## Deliverables - Exact Files to Create

### 1. Command Implementation
**File:** `logist/logist/cli.py` (update existing file)
**Changes:** Add `init_command()` function and register with CLI group
**Contents:** Directory creation, file copying, configuration validation

### 2. Default Role Templates
**Files:** `$JOBS_DIR/*.json` (copied from `logist/schemas/roles/`)
- `worker.json`
- `supervisor.json`
- Any additional role configurations

### 3. Jobs Index Template
**File:** `$JOBS_DIR/jobs_index.json` (create new)
**Content:** Initial jobs index structure with current_job_id field

### 4. Directory Structure Validation
**Code:** Validation logic in CLI command to ensure proper setup

## Implementation Sequence

1. **Analyze:** Read `logist/schemas/roles/` for available configurations
2. **Design:** Plan directory structure and configuration copying logic
3. **CLI Integration:** Add command to existing CLI structure
4. **Template Copying:** Implement secure file copying from schemas to jobs dir
5. **Validation:** Add directory existence and permission checks
6. **Testing:** Create test cases for directory setup scenarios
7. **Documentation:** Update CLI help text and documentation

## Verification Standards

### Functionality Tests
- ✅ Creates `$JOBS_DIR` when it doesn't exist
- ✅ Copies all role JSON files from schemas to jobs directory
- ✅ Creates valid `jobs_index.json` structure
- ✅ Handles permission errors gracefully
- ✅ Provides clear success/error messages

### Integration Tests
- ✅ Subsequent commands can use the initialized jobs directory
- ✅ Role configurations are valid JSON and loadable
- ✅ Jobs index structure matches expected format
- ✅ No conflicts with existing files

## Dependencies Check

- **File System Access:** Must be able to create directories and copy files
- **Schema Files:** `logist/schemas/roles/` must contain valid configurations
- **CLI Framework:** Build upon existing Click CLI structure
- **Error Handling:** Secure file operations with proper permissions

Implement systematically, consulting this specification file at each milestone to maintain 100% requirements coverage.