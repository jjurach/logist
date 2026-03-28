# Project Plan: Core Engine Refactor for Better Separation of Concerns

**Date:** 2025-12-26 21:38:48
**Estimated Duration:** 4-6 hours
**Complexity:** High
**Status:** Draft

## Objective
Refactor core_engine.py to improve separation of concerns, testability, and extensibility by removing direct dependencies on workspace_utils and execute_llm_with_cline, and instead injecting runner and agent dependencies that handle these operations.

## Requirements
- [ ] Remove all workspace_utils calls from core_engine.py
- [ ] Remove execute_llm_with_cline() calls from core_engine.py
- [ ] Modify core_engine.py to accept runner and agent as constructor dependencies
- [ ] Define clean interfaces between engine, runner, and agent
- [ ] Move git operations (provision/harvest) to runner/agent methods
- [ ] Move direct Cline execution to a "direct command" runner
- [ ] Ensure mock agent can emulate success/failure without needing mock runner
- [ ] Maintain backward compatibility for existing functionality
- [ ] Update tests to work with new architecture

## Implementation Steps
1. **Analyze Current Architecture**
   - Review current core_engine.py dependencies and method calls
   - Identify all workspace_utils and execute_llm_with_cline usage
   - Document current interaction patterns between engine, runners, and agents
   - Files to modify: `src/logist/core_engine.py`
   - Files to create: None
   - Dependencies: Current runner/agent base classes
   - Estimated time: 1 hour
   - Status: [ ] Not Started

2. **Define Runner Interface Extensions**
   - Add provision() and harvest() methods to Runtime base class
   - Define interface for workspace preparation and git operations
   - Ensure mock runtime can provide no-op implementations
   - Files to modify: `src/logist/runtimes/base.py`
   - Files to create: None
   - Dependencies: Base runtime interface
   - Estimated time: 1 hour
   - Status: [ ] Not Started

3. **Create Direct Command Runner**
   - Implement new runner for direct Cline execution
   - Handle execute_llm_with_cline functionality
   - Integrate with existing agent system
   - Files to modify: None
   - Files to create: `src/logist/runtimes/direct.py`
   - Dependencies: Runtime base class, job_processor
   - Estimated time: 2 hours
   - Status: [ ] Not Started

4. **Refactor Core Engine Constructor**
   - Modify LogistEngine.__init__ to accept runner and agent parameters
   - Update method signatures to use injected dependencies
   - Remove direct imports of workspace_utils and job_processor
   - Files to modify: `src/logist/core_engine.py`
   - Files to create: None
   - Dependencies: Updated runtime/agent interfaces
   - Estimated time: 1.5 hours
   - Status: [ ] Not Started

5. **Refactor Job Execution Methods**
   - Update step_job() to use runner.provision() and runner.harvest()
   - Replace execute_llm_with_cline() with runner.execute_job_step()
   - Update restep_single_step() with new execution pattern
   - Files to modify: `src/logist/core_engine.py`
   - Files to create: None
   - Dependencies: New runner interface methods
   - Estimated time: 2 hours
   - Status: [ ] Not Started

6. **Update CLI Integration**
   - Modify CLI code to instantiate engine with appropriate runner/agent
   - Ensure backward compatibility for existing commands
   - Update any hardcoded engine instantiations
   - Files to modify: `src/logist/cli.py`
   - Files to create: None
   - Dependencies: Refactored core_engine.py
   - Estimated time: 1 hour
   - Status: [ ] Not Started

7. **Update Tests**
   - Modify unit tests to work with dependency injection
   - Update integration tests for new architecture
   - Ensure mock agent works without mock runner
   - Files to modify: `tests/test_core_engine.py`, `tests/test_integration_e2e.py`
   - Files to create: None
   - Dependencies: Refactored core components
   - Estimated time: 2 hours
   - Status: [ ] Not Started

## Success Criteria
- [ ] core_engine.py no longer imports or calls workspace_utils directly
- [ ] core_engine.py no longer calls execute_llm_with_cline() directly
- [ ] LogistEngine accepts runner and agent in constructor
- [ ] Git operations handled through runner.provision() and runner.harvest()
- [ ] Direct Cline execution moved to dedicated runner
- [ ] All existing functionality preserved
- [ ] Unit tests pass with new architecture
- [ ] Integration tests pass with new architecture
- [ ] Mock agent can emulate behavior without mock runner

## Testing Strategy
- [ ] Unit tests for new runner interface methods
- [ ] Unit tests for dependency injection in core engine
- [ ] Integration tests for end-to-end job execution
- [ ] Mock agent behavior verification tests
- [ ] Backward compatibility tests for existing CLI commands

## Risk Assessment
- **High Risk:** Breaking existing job execution flow - Mitigation: Comprehensive testing before deployment
- **Medium Risk:** Interface changes affecting other components - Mitigation: Update all dependent code simultaneously
- **Low Risk:** Mock agent behavior changes - Mitigation: Ensure mock implementations match expected interfaces

## Dependencies
- [ ] Current Runtime base class must support new methods
- [ ] Agent base class compatibility with new execution patterns
- [ ] CLI integration must be updated to provide dependencies
- [ ] Test suite must be updated for new architecture

## Database Changes (if applicable)
- [ ] No database changes required

## API Changes (if applicable)
- [ ] LogistEngine constructor API changed (now requires runner/agent parameters)
- [ ] Runtime interface extended with provision()/harvest() methods
- [ ] New DirectCommandRunner added to runtime options

## Notes
This refactor improves testability by allowing mock injection and better separation of concerns. The engine becomes a pure orchestrator that delegates execution details to specialized runners and agents. Mock agents can now simulate behavior without needing complex mock runners.

The proposed interaction pattern:
1. Engine receives Runner and Agent instances
2. For job execution: engine calls runner.provision() → agent execution → runner.harvest()
3. For direct commands: engine uses DirectCommandRunner which handles Cline execution
4. Runners handle environment-specific operations (git, workspace prep)
5. Agents handle command generation and environment setup