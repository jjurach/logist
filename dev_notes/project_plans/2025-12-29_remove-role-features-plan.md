# Project Plan: Remove Role-Related Features

**Date:** 2025-12-29
**Complexity:** Medium
**Status:** Pending

## Objective

Remove all "role-related" features from the logist project as the architecture has evolved away from a "supervisor/worker" concept. The system now delegates role-switching responsibilities to the runner/agent layer, allowing dynamic mode changes (architect/editor) at harvest time.

## Background

The original logist design included a "programmable roles system" with Worker and Supervisor roles. This design has been superseded by the runner/agent architecture where:
- **Runners** handle WHERE code runs (container, host, cloud)
- **Agents** handle WHAT tool runs and can switch modes dynamically

The Worker/Supervisor distinction is no longer managed by logist core - agents handle their own mode switching internally.

## Files to DELETE

### Schema Files (src/logist/schemas/roles/)
1. `src/logist/schemas/roles/default-roles.json` - Default role definitions
2. `src/logist/schemas/roles/supervisor.json` - Supervisor role config
3. `src/logist/schemas/roles/supervisor.md` - Supervisor role instructions
4. `src/logist/schemas/roles/worker.json` - Worker role config
5. `src/logist/schemas/roles/worker.md` - Worker role instructions

### Service Files
6. `src/logist/services/role_manager.py` - RoleManagerService class

### Test Files
7. `tests/services/test_role_manager.py` - Role manager unit tests
8. `tests/test_init_roles.py` - Init command role tests

### Documentation Files (to be replaced/archived)
9. `doc/02_roles_overview.md` - Will be replaced with `doc/archive/legacy-roles.md`

## Files to MODIFY

### 1. src/logist/cli.py

**Changes required:**
- Remove import of `RoleManagerService` (line 41)
- Remove `role_manager = RoleManagerService()` instantiation
- Remove `roles_and_files_to_copy` list and loop copying worker/supervisor files (lines 56-77)
- Remove default roles configuration loading from `init_command` (lines 79-113)
- Remove `role_copied_count` tracking
- Remove `@cli.group()` `role()` command group (line 202-203)
- Remove `@role.command(name="list")` and `list_roles()` function (lines 1532-1547, 1692-1707)
- Remove `@role.command(name="inspect")` and `inspect_role()` function (lines 1711-1722)
- Remove `--role` flag from `poststep` command (lines 983-984)
- Remove role-related logic in `poststep()` function (lines 1031-1040)
- Remove role config loading in `preview()` function (lines 1801-1808)
- Remove role-related context assembly (line 1815)
- Remove role display in history/metrics commands (line 843, 853)

### 2. src/logist/services/__init__.py

**Changes required:**
- Remove `RoleManagerService` import and export (lines 10-12)

### 3. src/logist/job_state.py

**Changes required:**
- Rename `get_current_state_and_role()` to `get_current_state()` and remove role logic (lines 65-99)
- Update `transition_state()` to remove `agent_role` parameter or simplify (lines 102-166)
- Remove Worker/Supervisor-specific transitions from state machine
- Update docstrings to remove role references
- Consider simplifying state machine if supervisor-specific states can be removed

### 4. src/logist/job_context.py

**Changes required:**
- Update `assemble_job_context()` signature to remove `active_role` parameter (line 14)
- Remove role-specific instruction loading (lines 44-67)
- Remove role model selection logic (lines 74-82)
- Remove `role_name`, `role_instructions`, `role_model` from context dictionaries (lines 116-117, 127-129)
- Update `enhance_context_with_previous_outcome()` to remove role-specific instructions (lines 195-210)
- Update `format_llm_prompt()` to remove role references (line 153)

### 5. src/logist/job_processor.py

**Changes required:**
- Remove any role-related imports and logic
- Search for "role" references and remove them

### 6. src/logist/workspace_utils.py

**Changes required:**
- Remove any role-related logic (search for "role" references)

### 7. src/logist/metrics_utils.py

**Changes required:**
- Remove role tracking from metrics if present

### 8. src/logist/core_engine.py

**Changes required:**
- Remove any role-related imports and logic

### 9. src/logist/agents/mock_agent.py

**Changes required:**
- Remove role-related logic if present

### 10. src/logist/agents/mock_agent_processor.py

**Changes required:**
- Remove role-related logic if present

## Test Files to MODIFY

### 11. tests/test_agent_runtime_integration.py -> tests/test_agent_runner_integration.py

**Changes required:**
- Rename file from `test_agent_runtime_integration.py` to `test_agent_runner_integration.py`
- No content changes needed (file already uses runner terminology)

### 12. tests/test_core_engine.py

**Changes required:**
- Remove role-related test assertions and setup

### 13. tests/test_cli.py

**Changes required:**
- Remove role-related CLI tests
- Update tests that expect role files to be created on init

### 14. tests/test_job_context.py

**Changes required:**
- Remove role-related test cases
- Update test fixtures that include role data

### 15. tests/test_scenarios/mock_job_scenarios.py

**Changes required:**
- Remove role-related scenario data

### 16. tests/test_utils/mock_agent_utils.py

**Changes required:**
- Remove role-related mock utilities

### 17. tests/debug-test-run.py

**Changes required:**
- Remove role-related debug code if present

## Documentation Files to MODIFY

### 18. doc/01_architecture.md

**Changes required:**
- Remove references to Worker/Supervisor roles (line 12)
- Remove `RoleManagerService` section (lines 137-138)
- Update to reflect agent-agnostic architecture

### 19. doc/04_state_machine.md

**Changes required:**
- Remove Worker/Supervisor execution references (lines 89-90)
- Simplify state descriptions to remove role-specific language

### 20. doc/05_cli_reference.md

**Changes required:**
- Remove `--enhance` description mentioning "role instructions" (line 17)
- Remove role file copying from init command description (line 69)
- Remove entire "Role Management" section (lines 238-258)

### 21. doc/overview.md

**Changes required:**
- Remove "roles" from JSON example (line 130)
- Remove "Agent role execution system" feature (line 159)
- Remove role specialization from feature list (line 246)
- Update getting started section to remove role references (lines 260, 269, 297)

### 22. doc/problems.md

**Changes required:**
- Update Problem 7 about Worker/Supervisor vs Runner/Agent - mark as resolved by removal

### 23. doc/technical/logging-monitoring.md

**Changes required:**
- Remove role-related logging references if present

### 24. doc/technical/communication-protocol.md

**Changes required:**
- Remove role-related protocol references if present

## New File to CREATE

### doc/archive/legacy-roles.md

Create a document explaining the previous role implementation and why it was removed:

```markdown
# Legacy Roles System (Removed)

**Status:** Archived - Feature removed in December 2025

## Previous Implementation

Logist previously included a "programmable roles system" with:
- **Worker role**: Expert software development and implementation agent
- **Supervisor role**: Quality assurance and oversight specialist
- **System role**: System-level orchestration agent

### Role Manifest Architecture

Roles were defined with four mandatory attributes:
- `name`: Unique identifier
- `description`: Human-readable explanation
- `instructions`: Meta-prompt for behavior/constraints
- `llm_model`: Specific model for consistent role behavior

### CLI Commands (Removed)

- `logist role list` - Listed available agent roles
- `logist role inspect <role_name>` - Displayed role configuration
- `--role` flag on `job poststep` - Specified active role

### Configuration Files (Removed)

- `worker.json`, `worker.md` - Worker role configuration
- `supervisor.json`, `supervisor.md` - Supervisor role configuration
- `system.md` - System role configuration
- `default-roles.json` - Default role definitions

## Why Removed

The role system was removed because:

1. **Architecture Evolution**: The project evolved toward a runner/agent architecture where:
   - Runners handle execution environment (podman, docker, kubernetes, direct)
   - Agents handle tool execution (cline, aider, claude-code)

2. **Dynamic Mode Switching**: Modern AI coding agents (like Claude Code, Cline) support dynamic mode switching between "architect" and "editor" modes at runtime. This eliminates the need for pre-defined Worker/Supervisor roles.

3. **Simplification**: Removing the role layer reduces complexity and allows agents to manage their own behavioral modes internally.

4. **Harvest-time Flexibility**: The runner/agent architecture allows mode decisions to be made at harvest time rather than being fixed in configuration.

## Migration Notes

If you have existing jobs with role-specific configurations:
- The `active_agent` field in phase definitions is no longer used
- Role instructions were moved to agent-level configuration
- State transitions no longer depend on role type
```

## Implementation Order

### Phase 1: Test File Preparation
1. Rename `tests/test_agent_runtime_integration.py` to `tests/test_agent_runner_integration.py`

### Phase 2: Delete Obsolete Files
2. Delete schema files (`src/logist/schemas/roles/*`)
3. Delete `src/logist/services/role_manager.py`
4. Delete test files (`tests/services/test_role_manager.py`, `tests/test_init_roles.py`)

### Phase 3: Modify Source Files
5. Update `src/logist/services/__init__.py`
6. Update `src/logist/job_state.py`
7. Update `src/logist/job_context.py`
8. Update `src/logist/cli.py`
9. Update remaining source files (job_processor, workspace_utils, metrics_utils, core_engine, mock agents)

### Phase 4: Modify Test Files
10. Update test files to remove role expectations

### Phase 5: Documentation
11. Create `doc/archive/legacy-roles.md`
12. Update active documentation files
13. Move `doc/02_roles_overview.md` to archive

### Phase 6: Verification
14. Run `pytest` and ensure all tests pass
15. Verify no remaining references to "role", "Worker", "Supervisor" in active code (except archive)

## Success Criteria

- [ ] All role-related schema files deleted
- [ ] `RoleManagerService` removed
- [ ] Role-related CLI commands removed (`role list`, `role inspect`)
- [ ] `--role` flag removed from CLI
- [ ] Job state machine simplified (no role-dependent transitions)
- [ ] Job context assembly simplified (no role instructions)
- [ ] All tests pass
- [ ] `doc/archive/legacy-roles.md` explains the removed feature
- [ ] Active documentation updated to remove role references
- [ ] No "role"/"Worker"/"Supervisor" references in active code (grep verification)

## Risk Assessment

- **Medium Risk:** State machine changes may affect job execution flow
- **Medium Risk:** Tests may need significant updates
- **Low Risk:** Documentation changes are straightforward

## Notes

This removal aligns with the architectural direction documented in:
- `doc/07_runner_agent_architecture.md` - Runner/Agent separation
- `doc/problems.md` - Problem 7 about clarifying architecture layers

The three-layer architecture remains:
- **Runners** handle WHERE code runs
- **Agents** handle WHAT tool runs
- **Roles are removed** - agents handle their own modes internally
