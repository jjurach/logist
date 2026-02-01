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
   - Runners handle WHERE code runs (container, host, cloud)
   - Agents handle WHAT tool runs (cline, aider, claude-code)

2. **Dynamic Mode Switching**: Modern AI coding agents (like Claude Code, Cline) support dynamic mode switching between "architect" and "editor" modes at runtime. This eliminates the need for pre-defined Worker/Supervisor roles.

3. **Simplification**: Removing the role layer reduces complexity and allows agents to manage their own behavioral modes internally.

4. **Harvest-time Flexibility**: The runner/agent architecture allows mode decisions to be made at harvest time rather than being fixed in configuration.

## Migration Notes

If you have existing jobs with role-specific configurations:
- The `active_agent` field in phase definitions is no longer used
- Role instructions were moved to agent-level configuration
- State transitions no longer depend on role type