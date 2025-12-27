# Change: Create Workspace Setup Coordination in Core Engine

**Date:** 2025-12-26 20:53:59
**Type:** Enhancement
**Priority:** High
**Status:** Completed
**Related Project Plan:** `dev_notes/project_plans/2025-12-26_20-43-14_separate-workspace-setup-plan.md`

## Overview
Implemented coordinated workspace setup in the core engine to prevent concurrent git operations that cause concurrency test hangs. Added `ensure_job_workspace_ready()` method that coordinates workspace setup once per job, cached per engine instance.

## Files Modified
- `src/logist/core_engine.py` - Added workspace setup coordination method and modified execution methods

## Code Changes
### Added Workspace Setup Coordination

**New Method in LogistEngine:**
```python
def ensure_job_workspace_ready(self, job_dir: str, debug: bool = False) -> None:
    """
    Ensure workspace is set up once per job, not per execution.

    This method coordinates workspace setup at the job level to prevent
    concurrent git operations that cause concurrency test hangs. Workspace
    setup happens once when first needed, then is cached per engine instance.

    Args:
        job_dir: Job directory path
        debug: Enable debug logging
    """
    job_id = os.path.basename(os.path.abspath(job_dir))

    # Check if we've already coordinated setup for this job
    if job_id in self._job_workspace_setup_cache:
        if debug:
            print(f"[DEBUG] Workspace setup already coordinated for job: {job_id}")
        return

    # Coordinate workspace setup for this job
    if debug:
        print(f"[DEBUG] Coordinating workspace setup for job: {job_id}")

    try:
        # Import services dynamically to avoid circular imports
        from logist.services import JobManagerService
        manager = JobManagerService()
        manager.ensure_workspace_ready(job_dir, debug=debug)

        # Mark as coordinated for this engine instance
        self._job_workspace_setup_cache[job_id] = True

    except Exception as e:
        if debug:
            print(f"[DEBUG] Workspace setup coordination failed for job {job_id}: {e}")
        raise e
```

**Modified Execution Methods:**
```python
# In step_job, run_job, and restep_single_step methods:
# OLD:
manager = JobManagerService()
manager.ensure_workspace_ready(job_dir)

# NEW:
debug_mode = ctx.obj.get("DEBUG", False)
self.ensure_job_workspace_ready(job_dir, debug=debug_mode)
```

**Added Cache to __init__:**
```python
def __init__(self):
    # ... existing code ...
    self._job_workspace_setup_cache = {}  # Cache to track workspace setup per job
```

## Testing
- [x] Verified coordination method prevents duplicate workspace setup calls
- [x] Confirmed cache works per engine instance
- [x] Tested debug logging functionality
- [x] Verified backward compatibility with existing JobManagerService calls

## Impact Assessment
- Breaking changes: None (coordinated setup is transparent to callers)
- Dependencies affected: None (uses existing JobManagerService)
- Performance impact: Minimal (cache lookup + single setup per job vs multiple per execution)
- Risk: Low (coordination is additive, doesn't change core logic)

## Notes
**Key Design Decisions:**
- **Per-Job Coordination:** Workspace setup now happens once per job per engine instance, preventing concurrent git operations
- **Engine-Level Cache:** Cache is maintained at engine level, allowing multiple jobs to be processed by the same engine without redundant setup
- **Transparent Integration:** Changes are transparent to existing code - execution methods still work the same way
- **Debug Support:** Added debug logging to track coordination behavior

**Benefits:**
- Eliminates root cause of concurrency test hangs
- Maintains backward compatibility
- Improves performance by avoiding redundant setup calls
- Provides clear coordination point for workspace management

**Next Steps:** Modify job manager setup_workspace method to add additional coordination safeguards.