# Job List Command Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `job_list_command` (Phase 2) from the Logist master development plan. Implement \`logist job list\` Command Consult this prompts file throughout implementation to ensure every requirement is met - reference it explicitly after each major step to verify compliance.

## Critical Requirements
Display all jobs in the configured jobs directory

## Deliverables - Exact Files to Create

### 1. Functional Job List Command
**File:** `logist/cli.py` (modified)
**Changes:**
- Implemented `PlaceholderJobManager.list_jobs()` method to read `jobs_index.json`
- Added proper file parsing and error handling for jobs manifest files
- Updated CLI `list_jobs` command to format and display job information in tabular format
- Added colored status indicators based on job state
- Added current job marker (`👈`) for selected job

### 2. Documentation Updates
**File:** `docs/prompts/04-job_list_command.md` (this file)
**Changes:**
- Marked ✅ verification standards as completed
- Updated deliverables section with actual implementation details
- Documented technical implementation decisions

### 3. Testing Verification
**Files:** Temporary test job (`/tmp/test-job/`) for verification
**Changes:**
- Created test job manifest to verify list functionality
- Verified command displays job ID, status, and description correctly

## Implementation Sequence
1. **Analyze:** Read master plan requirements for this phase
2. **Design:** Plan the implementation approach
3. **Build:** Create the required files
4. **Test:** Verify functionality
5. **Document:** Update documentation
6. **Verify:** Ensure requirements are met
7. **Commit:** Follow the Git Status and Commit protocol in `_meta_prompt_instructions.md`

## Verification Standards
- ✅ All required functionality implemented
- ✅ Tests pass
- ✅ Documentation updated
- ✅ Backward compatibility maintained

## Dependencies Check
- **Master Plan:** Reference this specific phase requirements
- **Dependencies:** Verify all prerequisite phases are complete
- **Testing:** Run appropriate test suites

Implement systematically, consulting this specification file at each milestone to maintain 100% requirements coverage.