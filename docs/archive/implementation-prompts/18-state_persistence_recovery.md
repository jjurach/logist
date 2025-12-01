# State Persistence Recovery Implementation - Cline Oneshot Prompt

## Task Overview
You are implementing the `state_persistence_recovery` from the Logist master development plan. Consult this prompts file throughout implementation to ensure every requirement is met - reference it explicitly after each major step to verify compliance.

## Implementation Sequence
1. **Analyze:** Read master plan requirements for this task
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
- ✅ Job state survives restarts
- ✅ Detects hung processes
- ✅ Auto-recovery works correctly
- ✅ Backup/restore functionality verified

## Implementation Details
### Files Created/Modified
- **New:** `logist/logist/recovery.py` - Core recovery logic with backup management, hung process detection, and automatic recovery
- **Modified:** `logist/logist/job_state.py` - Added backup creation before manifest updates
- **Modified:** `logist/logist/cli.py` - Integrated recovery validation into job status and step commands

### Key Features Implemented
1. **Backup Manifest System**: Automatic timestamped backups before state changes with cleanup
2. **Hung Process Detection**: Timeout-based detection for jobs stuck in RUNNING/REVIEWING states
3. **Automatic Recovery**: Safe state transitions for hung processes (RUNNING→PENDING, REVIEWING→REVIEW_REQUIRED)
4. **Recovery Validation**: Integrated validation performed before job operations
5. **CLI Integration**: Recovery status display and validation in job status command

### Testing Results
- ✅ Demo script passes all units (no regressions)
- ✅ Recovery module imports and functions correctly
- ✅ Hung process detection triggers automatic recovery
- ✅ Backup creation and restore functionality verified
- ✅ Integration with existing error handling maintains backward compatibility

All verification standards satisfied. Implementation complete.

## Dependencies Check
- **Master Plan:** Reference this specific task requirements
- **Dependencies:** Verify all prerequisite phases are complete
- **Testing:** Run appropriate test suites

Implement systematically, consulting this specification file at each milestone to maintain 100% requirements coverage.