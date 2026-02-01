# Enhanced Job Lifecycle Implementation

Apply instructions from `_meta_prompt_instructions.md`.

## Implementation Status: ⏳ PENDING

## Task Overview
Implement enhanced job lifecycle management (Phase 4+) from the Logist development plan, adding DRAFT state, job configuration, activation commands, and queue management to prevent premature job execution.

## Critical Requirements ⏳
Implement job lifecycle improvements discussed in planning session: DRAFT initial state, job config commands, activation with queue positioning, and documentation updates.

## Deliverables - Exact Files Created/Modified ⏳
- **logist/schemas/job_config.json**: JSON schema for job configuration properties
- **logist/logist/cli.py**: Add `DRAFT` state constant and state machine updates
- **logist/logist/job_processor.py**: Modify job creation to start in DRAFT state
- **logist/logist/cli.py**: Add `job config` subcommand with --objective/--details/--acceptance/--prompt/--files options
- **logist/logist/cli.py**: Add `job activate --rank` subcommand for DRAFT→PENDING transition with queue positioning
- **logist/logist/cli.py**: Add queue array to jobs_index.json structure and queue management logic
- **logist/logist/cli.py**: Modify `job run` to consume from queue[0] instead of arbitrary selection
- **logist/logist/cli.py**: Modify `job list` to show queue positions
- **logist/logist/job_processor.py**: Add prompt.md generation from config during activation
- **logist/docs/04_state_machine.md**: Update to show DRAFT as initial state, ACTIVATION transitions
- **logist/docs/05_cli_reference.md**: Add job config and job activate command documentation
- **logist/docs/state-machine-fig1.gv**: Update GraphViz diagram with new DRAFT→ACTIVATE→PENDING flow

## Implementation Summary ⏳
1. **State Machine Changes**: Add DRAFT state as initial job state, preventing premature execution
2. **Job Configuration**: Implement `logist job config` command for setting job properties (objective, details, acceptance, prompt)
3. **Job Activation**: Implement `logist job activate [--rank N]` command to transition DRAFT→PENDING with queue positioning
4. **Queue Management**: Add ordered queue array to jobs_index.json for processing order control
5. **Prompt Generation**: Create prompt.md from configuration during activation with XML-tagged sections
6. **Documentation Updates**: Update state machine docs, CLI reference, and GraphViz diagrams
7. **Testing**: Comprehensive testing of new commands and queue behavior

## State Machine Changes ⏳
- Add `DRAFT` constant to state definitions
- Modify job creation to initialize in DRAFT state instead of PENDING
- Update state transition logic to allow only DRAFT→PENDING via activate command
- Maintain backward compatibility for existing job states

## Job Configuration System ⏳
**Schema Structure** (`schemas/job_config.json`):
```json
{
  "type": "object",
  "properties": {
    "files": {
      "type": "array",
      "items": {"type": "string"}
    },
    "objective": {"type": "string"},
    "details": {"type": "string"},
    "acceptance": {"type": "string"},
    "prompt": {"type": "string"}
  }
}
```

**CLI Commands**:
- `logist job config --objective 'what to accomplish' [JOB_ID]`
- `logist job config --details 'specific requirements' [JOB_ID]`
- `logist job config --acceptance 'completion criteria' [JOB_ID]`
- `logist job config --prompt 'task description' [JOB_ID]`
- `logist job config --files 'file1.md,file2.py' [JOB_ID]`

## Job Activation & Queue Management ⏳
**Command**: `logist job activate [--rank <position>] [JOB_ID]`

**Jobs Index Structure Updates**:
```json
{
  "current_job_id": "job-123",
  "jobs": {"job-123": "/path/to/job"},
  "queue": ["urgent-job", "job-123", "normal-job"]
}
```

**Rank Parameter Behavior**:
- `logist job activate` - append to queue end
- `logist job activate --rank 0` - insert at queue position 0 (highest priority)
- `logist job activate --rank 2` - insert at position 2
- `logist job activate --rank 99` - append if queue shorter than 99

## Prompt.md Generation ⏳
**When activating (DRAFT→PENDING), if prompt.md doesn't exist:**

1. Write prompt from `config.prompt` as first line
2. Append `<objective>` + newline + `config.objective` + `</objective>` (if present)
3. Append `<details>` + newline + `config.details` + `</details>` (if present)
4. Append `<acceptance>` + newline + `config.acceptance` + `</acceptance>` (if present)

**Example Output**:
```
Create a Python email validator function
<objective>
Validate email addresses according to RFC standards
</objective>
<details>
Include comprehensive error handling and type hints
</details>
<acceptance>
Function passes all unit tests and handles edge cases
</acceptance>
```

## Documentation Updates ⏳
**logist/docs/04_state_machine.md**:
- Add DRAFT state description
- Rename "Initial State" to DRAFT in transition descriptions
- Add ACTIVATION transition from DRAFT→PENDING
- Update state machine semantics section

**logist/docs/05_cli_reference.md**:
- Add `logist job config` command documentation with all options
- Add `logist job activate [--rank <num>]` command documentation
- Update job lifecycle descriptions to mention DRAFT state

**logist/docs/state-machine-fig1.gv**:
- Change initial state from PENDING to DRAFT
- Add ACTIVATE transition arrow from DRAFT to PENDING
- Add rank parameter notation to transition label

## Files Written ⏳
- `logist/schemas/job_config.json`: JSON schema for job configuration
- `job/config.json`: Created during job config commands
- `job/prompt.md`: Generated during activation if missing
- `jobs_index.json`: Updated with queue array structure

## Verification Standards ⏳
- ✅ `logist job create` initializes jobs in DRAFT state
- ✅ `logist job config` commands update job configuration without state changes
- ✅ `logist job activate` requires DRAFT state and creates PENDING + queue position
- ✅ `logist job run` processes queue[0] preferentially
- ✅ `logist job list` shows queue positions alongside job statuses
- ✅ prompt.md generation includes proper XML tagging and ordering
- ✅ State machine diagrams and docs accurately reflect new flow
- ✅ Backward compatibility maintained for existing job operations

## Dependencies Check ⏳
- **Phase 1.3 (job_create_command)**: ✅ Required - provides base job creation
- **Phase 2.1 (job_status_command)**: ✅ Required - job status inspection needed
- **Phase 3.7 (job_preview_command)**: ✅ Required - may need job config context
- **Master Plan Requirements**: Ready for Phase 4 implementation

## Testing Performed ⏳
- Create job in DRAFT state verification
- Job config command testing with all properties
- Activate with various rank positions testing
- Queue order preservation and consumption testing
- Prompt.md generation with configuration testing
- Error handling for invalid state transitions testing
- Documentation accuracy verification

Implement systematically, maintaining requirement compliance and testing at each milestone.
