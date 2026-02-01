
read and interpret `_prompt_instructions.md`

- add --debug switch to logist to be more chatty about what preview and step and run are doing.

- preview, run, and step should write all relevant information to jobHistory.json.

- these commands with --debug switch should be verbose about the information going into the jobHistory.json file, including cost metrics: input/output tokens, costs, elapsed time.

## Completion Verification

### Verification Standards
- ✅ --debug switch implemented and functional
- ✅ preview command writes jobHistory.json entries
- ✅ step command writes jobHistory.json entries
- ✅ run command writes jobHistory.json entries
- ✅ Debug output shows detailed metrics (costs, tokens, timing)

### Files Modified
- `logist/src/logist/cli.py`: Added LogistEngine class with history writing methods, updated context to include engine instance, modified commands to use engine for history logging
- `pyrightconfig.json`: Updated Python version to match environment (3.12)

### Implementation Details
- Added `_write_job_history_entry()` method to LogistEngine for structured history logging
- Added `_show_debug_history_info()` method for verbose debug output with metrics display
- Made LogistEngine instance available in Click context for all commands
- Updated preview_job command to access engine methods via context
- History entries include comprehensive metadata: operation details, metrics, evidence files, and timing

**Completion Date:** December 1, 2025