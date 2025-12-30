# Project Plan: Fix Job ID Generation and Simplify Directory Structure

**Date:** 2025-12-30 00:26:56
**Complexity:** Medium
**Status:** Completed

## Objective

Fix the `logist job create` command to properly generate job IDs and simplify the job directory structure by removing all subdirectories and the prompt.md file. Job directories should contain only `job_manifest.json`.

## Requirements

- [x] When no `--name` is specified, generate a random job ID instead of using "."
- [x] When `--name` is specified, use that value as the job ID
- [x] Remove ALL subdirectories from job creation (logs, temp, workspace, backups)
- [x] Remove prompt.md file support entirely - prompt is only stored in job_manifest.json
- [x] Update tests to reflect new behavior

## Implementation Steps

### 1. Add `--name` Option to CLI

- Files to modify: `src/logist/cli.py`
- Dependencies: None
- Status: [x] Completed

**Details:**
Add new option to `create_job` command around line 207:
```python
@click.option("--name", "-n", "job_name", help="Job name/ID (auto-generated if not specified)")
```

Pass `job_name` parameter to `manager.create_job()`.

### 2. Update Job Manager to Handle Job ID Generation

- Files to modify: `src/logist/services/job_manager.py`
- Dependencies: Step 1
- Status: [x] Completed

**Details:**

a) Import uuid at top of file:
```python
import uuid
```

b) Modify `create_job()` method signature to accept `job_name` parameter:
```python
def create_job(self, job_dir: str, jobs_dir: str, prompt: str = None,
               git_source_repo: str = None, runner: str = None, agent: str = None,
               job_name: str = None) -> str:
```

c) Add job ID resolution logic after line 45:
```python
# Determine job_id
if job_name:
    # Explicit name provided - use it
    job_id = job_name
    job_dir_abs = os.path.join(jobs_dir_abs, job_id)
elif job_dir == "." or os.path.basename(os.path.normpath(job_dir)) == ".":
    # Current directory or "." - generate random ID
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    job_dir_abs = os.path.join(jobs_dir_abs, job_id)
else:
    # Use existing behavior - directory name as job_id
    if os.path.isabs(job_dir):
        job_dir_abs = job_dir
        job_id = os.path.basename(job_dir_abs)
    else:
        job_id = job_dir
        job_dir_abs = os.path.join(jobs_dir_abs, job_id)
```

### 3. Remove All Subdirectories from Job Creation

- Files to modify: `src/logist/services/job_manager.py`, `src/logist/core/job_directory.py`
- Dependencies: None (can be done in parallel with Step 2)
- Status: [x] Completed

**Details:**

In `src/logist/services/job_manager.py` around line 73, remove the entire subdirectory creation block:
```python
# DELETE THIS BLOCK:
# Create standard subdirectories
subdirs = ["workspace", "logs", "backups", "temp"]
for subdir in subdirs:
    subdir_path = os.path.join(job_dir_abs, subdir)
    os.makedirs(subdir_path, exist_ok=True)
```

In `src/logist/core/job_directory.py` line 92, apply same removal if this code path is still used.

### 4. Remove prompt.md File Support

- Files to modify:
  - `src/logist/services/job_manager.py`
  - `src/logist/cli.py`
  - `src/logist/core_engine.py`
  - `src/logist/workspace_utils.py`
- Dependencies: None
- Status: [x] Completed

**Details:**

#### 4a. job_manager.py - Remove prompt.md creation (lines 113-116)
Remove:
```python
# Also write prompt to prompt.md file
prompt_file_path = os.path.join(job_dir_abs, "prompt.md")
with open(prompt_file_path, 'w') as f:
    f.write(prompt)
```

#### 4b. job_manager.py - Remove prompt.md fallback reading (lines 595-601)
Remove the fallback that reads from prompt.md file. The prompt must be in manifest:
```python
# DELETE THIS BLOCK:
# Also check for prompt.md file
prompt_file_path = os.path.join(job_dir, "prompt.md")
if os.path.exists(prompt_file_path):
    with open(prompt_file_path, 'r') as f:
        prompt = f.read().strip()
    if prompt:
        manifest["prompt"] = prompt
```

#### 4c. cli.py - Remove prompt.md generation during activation (lines 2326-2361)
Remove the entire block that generates prompt.md from config.json:
```python
# DELETE THIS BLOCK:
# Generate prompt.md if config exists
config_path = os.path.join(job_dir, "config.json")
prompt_path = os.path.join(job_dir, "prompt.md")
# ... all related code through line 2361
```

#### 4d. core_engine.py - Remove prompt.md copy to workspace (lines 295-306)
Remove the block that copies prompt.md to workspace/tmp/:
```python
# DELETE THIS BLOCK:
# 8. Copy prompt.md to workspace/tmp/ for Apply command
import shutil
prompt_file_src = os.path.join(job_dir, "prompt.md")
# ... through line 306
```
Update to read prompt from manifest instead if needed for the workflow.

#### 4e. workspace_utils.py - Update discover_file_arguments function (lines 1040-1077)
The function `discover_file_arguments` scans prompt.md for file references. Update to:
- Accept prompt content as a parameter instead of reading from file
- Or read prompt from job_manifest.json instead

### 5. Update Tests

- Files to modify: `tests/services/test_job_manager.py`
- Dependencies: Steps 1-4
- Status: [x] Completed

**Details:**
- Remove tests that check for subdirectory creation
- Remove tests that check for prompt.md file
- Add test for random job ID generation when no name specified
- Add test for explicit job ID with `--name` option
- Verify job directory contains only job_manifest.json

## Success Criteria

- [x] `logist job create --prompt 'test'` generates a random job ID like `job-a1b2c3d4`
- [x] `logist job create --name my-job --prompt 'test'` creates job with ID `my-job`
- [x] Job directories contain ONLY `job_manifest.json` (no subdirectories, no prompt.md)
- [x] Prompt is stored only in job_manifest.json `prompt` attribute
- [x] All existing tests pass (after updating for new expectations)
- [x] New tests pass for added functionality (4 new tests added, 115 total tests pass)

## Testing Strategy

- [ ] Unit tests for job ID generation logic
- [ ] Integration tests for CLI command
- [ ] Manual testing of both scenarios
- [ ] Verify no prompt.md files are created

## Risk Assessment

- **Low Risk:** Backward compatibility - existing jobs with subdirectories and prompt.md will still exist but won't break anything
- **Medium Risk:** Code that reads prompt.md needs to be updated to read from manifest instead

## Files Summary

| File | Changes |
|------|---------|
| `src/logist/cli.py` | Add `--name` option; Remove prompt.md generation |
| `src/logist/services/job_manager.py` | Add `job_name` param; Random ID generation; Remove subdirs; Remove prompt.md creation/reading |
| `src/logist/core/job_directory.py` | Remove subdirs creation |
| `src/logist/core_engine.py` | Remove prompt.md copy to workspace |
| `src/logist/workspace_utils.py` | Update discover_file_arguments to not use prompt.md |
| `tests/test_job_manager.py` | Update tests |

## Notes

### prompt.md Usage Found in Codebase

1. **job_manager.py:113-116** - Creates prompt.md when job is created with prompt
2. **job_manager.py:595-601** - Reads prompt.md as fallback if prompt not in manifest
3. **cli.py:2326-2361** - Generates prompt.md from config.json during job activation
4. **core_engine.py:295-306** - Copies prompt.md to workspace/tmp/ during execution
5. **workspace_utils.py:1040-1074** - Scans prompt.md for file references

All of these need to be removed or updated to use manifest instead.

### Expected Directory Structure After Implementation

```
jobs/
├── jobs_index.json
└── test-job/
    └── job_manifest.json
```

The `job_manifest.json` contains all job metadata including the `prompt` attribute:
```json
{
  "job_id": "test-job",
  "prompt": "just say yes",
  "status": "draft",
  ...
}
```
