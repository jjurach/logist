# Project Plan: Agent/Runtime Abstraction & Robust Execution

**Date:** 2025-12-26 13:01:52
**Estimated Duration:** 4-5 weeks
**Complexity:** High
**Status:** Draft

## Objective
Implement a robust Logist system with decoupled Agent/Runtime architecture, persistent job management, intelligent log analysis, and automated hang detection. This will enable reliable execution of AI agents across diverse environments while providing crash recovery and concurrent job management.

## Requirements
- [ ] Provider Pattern implementation with Agent and Runtime interfaces
- [ ] MockAgent for cost-effective testing without external dependencies
- [ ] Persistent job management with filesystem-based tracking
- [ ] Regex-based log analysis for intelligent state detection
- [ ] Execution Sentinel for automatic hang detection and cleanup
- [ ] Comprehensive unit test coverage using pytest fixtures
- [ ] Crash recovery and job re-attachment capabilities
- [ ] Concurrent job execution with advisory locking

## Implementation Steps

### Phase 1: Core Architecture (Provider Pattern)
1. **Create Agent Base Interface**
   - Files to create: `src/logist/agents/base.py`
   - Files to modify: None
   - Dependencies: None
   - Estimated time: 2 hours
   - Status: [x] Completed

2. **Create Runtime Base Interface**
   - Files to create: `src/logist/runtimes/base.py`
   - Files to modify: None
   - Dependencies: Phase 1.1
   - Estimated time: 2 hours
   - Status: [x] Completed

3. **Implement HostRuntime**
   - Files to create: `src/logist/runtimes/host.py`
   - Files to modify: None
   - Dependencies: Phase 1.2
   - Estimated time: 3 hours
   - Status: [x] Completed

### Phase 2: Mock Agent & Testing Infrastructure
4. **Implement MockAgent**
   - Files to create: `src/logist/agents/mock.py`
   - Files to modify: None
   - Dependencies: Phase 1.1
   - Estimated time: 4 hours
   - Status: [x] Completed

5. **Create Pytest Fixtures**
   - Files to modify: `tests/conftest.py` (create if doesn't exist)
   - Files to create: `tests/test_mock_agent.py`
   - Dependencies: Phase 2.1
   - Estimated time: 3 hours
   - Status: [x] Completed

6. **Implement Core Test Cases**
   - Files to create: `tests/test_agent_runtime_integration.py`
   - Files to modify: None
   - Dependencies: Phase 2.2
   - Estimated time: 4 hours
   - Status: [x] Completed

### Phase 3: Persistent Job Management
7. **Create Job Directory Structure Management**
   - Files to create: `src/logist/core/job_directory.py`
   - Files to modify: `src/logist/job_state.py` (extend existing)
   - Dependencies: None
   - Estimated time: 3 hours
   - Status: [ ] Not Started

8. **Implement Advisory File Locking**
   - Files to create: `src/logist/core/locking.py`
   - Files to modify: None
   - Dependencies: Phase 3.1
   - Estimated time: 2 hours
   - Status: [ ] Not Started

9. **Job Recovery Logic**
   - Files to create: `src/logist/core/recovery.py`
   - Files to modify: `src/logist/recovery.py` (extend existing)
   - Dependencies: Phase 3.1, 3.2
   - Estimated time: 4 hours
   - Status: [ ] Not Started

### Phase 4: Logist Intelligence (Regex Dictionary)
10. **Implement Observer Module**
    - Files to create: `src/logist/core/observer.py`
    - Files to modify: None
    - Dependencies: None
    - Estimated time: 3 hours
    - Status: [ ] Not Started

11. **State Detection Integration**
    - Files to modify: `src/logist/core_engine.py`
    - Files to create: None
    - Dependencies: Phase 4.1
    - Estimated time: 2 hours
    - Status: [ ] Not Started

### Phase 5: Execution Sentinel
12. **Implement Hang Detection**
    - Files to create: `src/logist/core/sentinel.py`
    - Files to modify: None
    - Dependencies: Phase 1.2, 4.1
    - Estimated time: 4 hours
    - Status: [ ] Not Started

13. **Integrate Sentinel with Core Engine**
    - Files to modify: `src/logist/core_engine.py`
    - Files to create: None
    - Dependencies: Phase 5.1
    - Estimated time: 2 hours
    - Status: [ ] Not Started

### Phase 6: CLI Integration & Commands
14. **Extend CLI for Job Attach/Recovery**
    - Files to modify: `src/logist/cli.py`
    - Files to create: None
    - Dependencies: Phase 3.3, 5.2
    - Estimated time: 3 hours
    - Status: [ ] Not Started

15. **Add Job Status Dashboard Command**
    - Files to modify: `src/logist/cli.py`
    - Files to create: `src/logist/commands/dashboard.py`
    - Dependencies: Phase 3.1
    - Estimated time: 2 hours
    - Status: [ ] Not Started

### Phase 7: Integration Testing & Validation
16. **End-to-End Integration Tests**
    - Files to create: `tests/test_integration_e2e.py`
    - Files to modify: None
    - Dependencies: All previous phases
    - Estimated time: 4 hours
    - Status: [ ] Not Started

17. **Performance & Concurrency Testing**
    - Files to create: `tests/test_concurrency.py`
    - Files to modify: None
    - Dependencies: Phase 7.1
    - Estimated time: 3 hours
    - Status: [ ] Not Started

## Success Criteria
- [ ] All Agent and Runtime interfaces implemented and functional
- [ ] MockAgent passes all test scenarios (success, hang, error)
- [ ] Job directory structure properly created and managed
- [ ] File locking prevents concurrent access to same job
- [ ] Regex dictionary correctly identifies all specified states
- [ ] Execution Sentinel properly detects and handles hangs
- [ ] Crash recovery successfully re-attaches to running jobs
- [ ] All unit tests pass with >90% coverage
- [ ] Integration tests demonstrate end-to-end functionality

## Testing Strategy
- **Unit Tests**: Individual components (Agent, Runtime, Observer, Sentinel)
- **Integration Tests**: Full job lifecycle with MockAgent
- **Concurrency Tests**: Multiple jobs running simultaneously
- **Recovery Tests**: Simulating crashes and re-attachment
- **Performance Tests**: Hang detection timing and resource usage

## Risk Assessment
- **High Risk:** Complex concurrency and file locking implementation
  - Mitigation: Extensive testing with race condition scenarios
- **Medium Risk:** Regex patterns may not cover all real-world cases
  - Mitigation: Start with comprehensive patterns, add more as needed
- **Low Risk:** Directory structure changes may affect existing code
  - Mitigation: Careful integration testing before deployment

## Dependencies
- [ ] Python filelock library for advisory locking
- [ ] Existing Logist core modules (job_state.py, core_engine.py)
- [ ] pytest-asyncio for concurrent testing
- [ ] fcntl module for Unix file locking

## Database Changes (if applicable)
- [ ] No database changes required - using filesystem-based persistence

## API Changes (if applicable)
- [ ] New CLI commands: `logist attach <job_id>`, `logist dashboard`
- [ ] Extended job status reporting with detailed state information

## Notes
- This implementation follows the Provider Pattern to ensure extensibility
- MockAgent enables cost-effective testing without external API calls
- Filesystem-based persistence ensures portability and simplicity
- Regex-based intelligence allows for flexible log analysis
- Execution Sentinel prevents resource waste from hung processes
- Advisory locking enables safe concurrent job management

## Future Roadmap Items (from prompt)
- [ ] Auto-cleanup of job directories after successful PR merge
- [ ] Podman runtime provider support
- [ ] Enhanced dashboard with live status updates