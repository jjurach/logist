# Project Plan: Mock Agent Development for Unit Testing

**Date:** 2025-12-26 14:13:00
**Estimated Duration:** 2-3 weeks
**Complexity:** Medium
**Status:** Draft

## Executive Summary

Develop a comprehensive mock agent system to enable proper unit testing of Logist job execution flows without requiring actual LLM service calls. This will allow testing of success/failure interpretation, state transitions, and lifecycle management in isolation, while reserving real LLM interactions for integration testing only.

## Objective

Create a mock agent framework that can:
1. Emulate various LLM response patterns (success, failure, errors, timeouts)
2. Test state machine transitions and lifecycle management
3. Validate job execution flows without external dependencies
4. Eventually replace all unit tests that currently make real LLM calls
5. Maintain clean separation between unit testing and integration testing

## Requirements
- [ ] Mock agent can emulate Worker and Supervisor roles
- [ ] Support configurable response patterns and failure modes
- [ ] Proper state transition testing for all job lifecycles
- [ ] Comprehensive test coverage for success/failure scenarios
- [ ] Clean integration with existing test infrastructure
- [ ] Eventually remove all unmocked LLM tests from unit test suite

## Implementation Steps

### Phase 1: Core Mock Agent Framework
1. **Design Mock Agent Architecture**
    - Files to create: `src/logist/agents/mock_agent.py`
    - Define: Mock agent interface and base classes
    - Dependencies: None
    - Estimated time: 2 hours
    - Status: [ ] Not Started

2. **Implement Basic Response Emulation**
    - Files to modify: `src/logist/agents/mock_agent.py`
    - Add: Configurable response patterns (success, failure, errors)
    - Dependencies: Phase 1.1
    - Estimated time: 3 hours
    - Status: [ ] Not Started

3. **Add State Transition Testing Support**
    - Files to modify: `src/logist/agents/mock_agent.py`
    - Add: State-aware response generation based on job context
    - Dependencies: Phase 1.2
    - Estimated time: 2 hours
    - Status: [ ] Not Started

### Phase 2: Lifecycle Testing Integration
4. **Create Mock Agent Test Utilities**
    - Files to create: `tests/test_utils/mock_agent_utils.py`
    - Define: Helper functions for mock agent setup and validation
    - Dependencies: Phase 1.3
    - Estimated time: 2 hours
    - Status: [ ] Not Started

5. **Implement Job Lifecycle Mock Scenarios**
    - Files to create: `tests/test_scenarios/mock_job_scenarios.py`
    - Add: Predefined mock scenarios for different job lifecycles
    - Dependencies: Phase 2.1
    - Estimated time: 4 hours
    - Status: [ ] Not Started

6. **Add Mock Agent to Test Configuration**
    - Files to modify: `tests/conftest.py`
    - Add: Mock agent fixtures and configuration
    - Dependencies: Phase 2.2
    - Estimated time: 1 hour
    - Status: [ ] Not Started

### Phase 3: Comprehensive Testing Coverage
7. **Replace Unit Tests with Mock Agent**
    - Files to modify: Various test files in `tests/`
    - Replace: Real LLM calls with mock agent in unit tests
    - Dependencies: Phase 2.3
    - Estimated time: 6 hours
    - Status: [ ] Not Started

8. **Add Mock-Specific Test Cases**
    - Files to create: `tests/test_mock_agent_integration.py`
    - Add: Tests specifically for mock agent functionality
    - Dependencies: Phase 3.1
    - Estimated time: 4 hours
    - Status: [ ] Not Started

9. **Validate State Machine Coverage**
    - Files to modify: `tests/test_state_machine.py` (enhance)
    - Add: Mock agent integration for comprehensive state testing
    - Dependencies: Phase 3.2
    - Estimated time: 3 hours
    - Status: [ ] Not Started

### Phase 4: Cleanup and Optimization
10. **Audit and Remove Unmocked Tests**
    - Files to check: All `tests/*.py` files
    - Remove: Unit tests that make real LLM calls
    - Dependencies: Phase 3.3
    - Estimated time: 3 hours
    - Status: [ ] Not Started

11. **Update Test Documentation**
    - Files to modify: `README.md`, test files
    - Update: Documentation to reflect mock agent usage
    - Dependencies: Phase 4.1
    - Estimated time: 2 hours
    - Status: [ ] Not Started

12. **Final Integration Test**
    - Files to run: Full test suite with mock agents
    - Verify: All unit tests pass without LLM service dependencies
    - Dependencies: Phase 4.2
    - Estimated time: 1 hour
    - Status: [ ] Not Started

## Success Criteria
- [ ] Mock agent can emulate all Worker and Supervisor response patterns
- [ ] All state transitions testable without real LLM calls
- [ ] Unit test suite runs in <30 seconds without network dependencies
- [ ] Zero unit tests making actual LLM service calls
- [ ] Comprehensive coverage of success/failure scenarios
- [ ] Clean separation between unit and integration testing
- [ ] Mock agent framework extensible for future test scenarios

## Testing Strategy
- **Unit Tests**: Mock agent response patterns and state transitions
- **Integration Tests**: Real LLM calls (reserved for integration suite)
- **Mock Validation**: Ensure mock responses match expected LLM behavior
- **Performance Tests**: Mock agent response times and resource usage
- **Coverage Tests**: Validate all code paths exercised by mock scenarios

## Risk Assessment
- **Medium Risk:** Mock responses may not accurately reflect real LLM behavior
  - Mitigation: Regular validation against real LLM responses in integration tests
- **Low Risk:** Performance impact from mock framework overhead
  - Mitigation: Optimize mock response generation and caching
- **Low Risk:** Difficulty maintaining mock scenarios as LLM behavior evolves
  - Mitigation: Modular mock design with easy scenario updates

## Dependencies
- [ ] Existing agent runtime framework
- [ ] Current test infrastructure
- [ ] State machine implementation (completed)
- [ ] Job lifecycle management

## Database Changes (if applicable)
- [ ] No database changes required

## API Changes (if applicable)
- [ ] New mock agent interface for testing
- [ ] Updated test configuration fixtures

## Notes
- Start with simple mock responses, then expand to complex scenarios
- Maintain clear distinction between mock and real agent behavior
- Use mock agents exclusively in unit tests, real agents in integration tests
- Ensure mock framework doesn't introduce test-only dependencies
- Focus on deterministic, fast test execution without external services

## Timeline & Milestones

**Week 1:**
- Phase 1: Core mock agent framework development
- Phase 2: Lifecycle testing integration

**Week 2:**
- Phase 3: Comprehensive testing coverage
- Phase 4: Cleanup and optimization

**Final Milestone:** ✅ MOCK AGENT FRAMEWORK COMPLETE - UNIT TESTS LLM-INDEPENDENT

## ✅ FINAL STATUS SUMMARY

- **Phase 1**: Core Mock Agent Framework - 🔄 READY FOR EXECUTION
- **Phase 2**: Lifecycle Testing Integration - 🔄 READY FOR EXECUTION
- **Phase 3**: Comprehensive Testing Coverage - 🔄 READY FOR EXECUTION
- **Phase 4**: Cleanup and Optimization - 🔄 READY FOR EXECUTION

**Goal: Enable fast, reliable unit testing without LLM service dependencies**