# Logist Testing Strategy & Demo Script

## Overview

Logist implements a **progressive testing methodology** using living demo scripts that grow with implementation. This approach ensures **iterative validation**, **cumulative correctness**, and **repeatable testing** without LLM API dependencies.

## Core Testing Components

### 1. Incremental Demo Script (`logist/test-demo.sh`)

The demo script serves as both implementation validation and feature showcase:

```bash
#!/bin/bash
# Logist CLI Implementation Demo & Test Suite
# Grows incrementally as units are implemented

set -e  # Exit on any error

DEMO_DIR="/tmp/logist-demo-$$"
export LOGIST_JOBS_DIR="$DEMO_DIR/jobs"

cleanup() { rm -rf "$DEMO_DIR"; }
trap cleanup EXIT

echo "🧪 Logist CLI Implementation Demo"
echo "=================================="
```

### 2. Progressive Feature Validation

#### Phase 1: Foundation Commands (Units 1-5)
```bash
# Unit 1: init_command
echo "📋 Unit 1: logist init"
logist init
assert_directory "$DEMO_DIR/jobs"
assert_job_index_exists

# Unit 2: job_list_command
echo "📋 Unit 2: logist job list"
logist job list
assert_empty_job_list

# Unit 3: job_create_command
echo "📋 Unit 3: logist job create"
logist job create my-first-job
assert_job_created my-first-job
assert_job_status my-first-job PENDING

# Unit 4: job_status_command
echo "📋 Unit 4: logist job status"
logist job status my-first-job
assert_job_status my-first-job PENDING

# Unit 5: job_select_command
echo "📋 Unit 5: logist job select"
logist job select my-first-job
assert_job_selected my-first-job
```

#### Phase 2: Execution Infrastructure (Units 6-10)
```bash
# Unit 6: isolation_env_setup
echo "📋 Unit 6: logist job step (workspace setup)"
# Note: isolation happens during first job step
logist job step my-first-job  # Creates workspace automatically
assert_workspace_directory my-first-job
assert_git_repository my-first-job

# Unit 7: job_step_command (with actual LLM)
echo "📋 Unit 7: logist job step (actual LLM execution)"
logist job step my-first-job
assert_job_status my-first-job RUNNING
assert_job_history_contains my-first-job 1

# Unit 8: job_preview_command
echo "📋 Unit 8: logist job preview"
logist job preview my-first-job
# Preview shows prompt without changing state
assert_job_status my-first-job RUNNING

# Unit 9: job_poststep_command (mock testing)
echo "📋 Unit 9: logist job poststep (with historical response)"
# Use response from jobHistory for repeatable testing
logist job poststep my-first-job 0  # Use first historical interaction
assert_job_status my-first-job COMPLETED
assert_job_history_validated my-first-job 1

# Unit 10: job_run_command
echo "📋 Unit 10: logist job run"
logist job create run-test-job
logist job run run-test-job
# job run uses internal loops of job step until completion
assert_job_completed run-test-job
```

### 3. Mock Testing Infrastructure

#### Job History as Test Fixtures

The `jobHistory.json` provides deterministic test inputs:

```bash
# Extract and reuse historical responses
test_with_mock_response() {
    local job_id=$1
    local interaction_seq=$2

    # Extract input file from history
    extract_response_fixture "$job_id" "$interaction_seq" > temp_response.json

    # Use job poststep instead of actual LLM call
    logist job poststep "$job_id" temp_response.json

    # Verify state transitions are deterministic
    assert_job_deterministic_transition "$job_id"
}
```

#### Regression Test Suite
```bash
run_regression_tests() {
    echo "🧪 Running regression tests with historical fixtures"

    # Use all historical jobHistory entries as test cases
    for job_dir in "$LOGIST_JOBS_DIR"/*/ ; do
        [ -f "$job_dir/jobHistory.json" ] || continue
        test_job_history_fixtures "$job_dir"
    done
}
```

## Testing Architecture

### 4. Command Testing Patterns

#### State Validation Assertions
```bash
assert_job_status() {
    local job_id=$1
    local expected_status=$2

    local actual_status=$(logist job status "$job_id" 2>/dev/null | grep "Status:" | cut -d: -f2 | tr -d ' ')

    if [[ "$actual_status" != "$expected_status" ]]; then
        echo "❌ Status assertion failed: expected $expected_status, got $actual_status"
        exit 1
    fi
    echo "✅ Status assertion passed: $job_id is $expected_status"
}
```

#### File System Assertions
```bash
assert_workspace_directory() {
    local job_id=$1

    if [[ ! -d "$LOGIST_JOBS_DIR/$job_id/workspace" ]]; then
        echo "❌ Workspace directory missing for job: $job_id"
        exit 1
    fi
    if [[ ! -d "$LOGIST_JOBS_DIR/$job_id/workspace/.git" ]]; then
        echo "❌ Git repository not initialized in workspace for job: $job_id"
        exit 1
    fi
    echo "✅ Workspace and Git repo verified for: $job_id"
}
```

#### Job History Assertions
```bash
assert_job_history_contains() {
    local job_id=$1
    local expected_count=$2

    local history_file="$LOGIST_JOBS_DIR/$job_id/jobHistory.json"
    if [[ ! -f "$history_file" ]]; then
        echo "❌ Job history missing for: $job_id"
        exit 1
    fi

    local actual_count=$(jq '.interactions | length' "$history_file" 2>/dev/null || echo "0")

    if [[ "$actual_count" -lt "$expected_count" ]]; then
        echo "❌ Job history missing entries: expected >=$expected_count, got $actual_count"
        exit 1
    fi
    echo "✅ Job history verified: $job_id has $actual_count interactions"
}
```

### 5. Implementation Unit Testing Guidelines

For each master plan unit implementation:

#### 1. **Add Commands to Demo Script**
```bash
# Unit X: {unit_snake_case_name}
echo "📋 Unit X: logist {subcommand}"
# Implementation-specific commands and assertions
logist {subcommand} {args}
assert_{specific_validation}()
```

#### 2. **Mode Selection Strategy**
- **Real LLM calls**: Use in `job step` and `job run` commands
- **Mock responses**: Use `job poststep` for unit tests, regression tests, and CI/CD
- **Historical fixtures**: Leverage `jobHistory.json` for deterministic testing

#### 3. **Assertion Coverage**
- **File system changes**: Directory creation, Git operations, file generation
- **State transitions**: Job status changes, phase progression
- **Configuration validation**: Role loading, manifest parsing, schema compliance
- **Error handling**: Invalid inputs, missing dependencies, edge cases

#### 4. **Test Data Management**
- **Clean temp directories**: Fresh environments for each test run
- **Fixture reuse**: Historical responses as basis for regression tests
- **Non-destructive tests**: Read-only state tests don't modify existing jobs

### 6. Integration Testing Patterns

#### Real vs Mock Execution Paths
```bash
# Production execution (uses live LLM)
job_step_with_llm() {
    logist job preview "$job_id"  # No state change
    logist job step "$job_id"     # preview + LLM call + poststep
}

# Testing execution (uses historical fixtures)
job_step_with_mock() {
    logist job preview "$job_id"      # No state change
    logist job poststep "$job_id" 0   # Use first historical interaction
}
```

#### Cumulative Validation
```bash
# Run all phases in sequence
run_full_integration_test() {
    # Phase 1: Foundation
    test_foundation_commands

    # Phase 2: Job management
    test_job_lifecycle

    # Phase 3: Execution engine
    test_execution_engine

    # Phases 4-7: Advanced features
    test_advanced_features

    echo "✅ Full integration test passed"
}
```

### 7. Continuous Testing Workflow

#### Development Phase
1. **Unit implementation**: Add commands and assertions to demo script
2. **Local testing**: Run `./test-demo.sh` validates implementation
3. **Historical fixtures**: Save responses to `jobHistory.json` for regression testing

#### Quality Assurance Phase
1. **Regression testing**: Verify all historical responses still produce same results
2. **Integration testing**: Run complete workflow with mix of real/mock execution
3. **Performance validation**: Check resource usage, timing, and scalability

#### Deployment Phase
1. **Production validation**: Full real-LLM execution test suite
2. **Monitoring**: Establish baselines for metrics and error rates
3. **Rollback testing**: Verify state restoration and job recovery

### 8. Benefits of This Approach

#### For Developers
- **Immediate feedback**: Each unit's correctness is immediately demonstrable
- **Deterministic testing**: Historical fixtures enable reliable automation
- **Incremental validation**: Cumulative testing catches integration issues early

#### For Quality Assurance
- **Reproducible results**: Same inputs produce same outputs across runs
- **Comprehensive coverage**: Mock testing enables edge case exploration
- **Performance baseline**: Historical data tracks system behavior over time

#### For Stakeholders
- **Visible progress**: Demo script showcases available functionality
- **Confidence in correctness**: Comprehensive test suite validates implementation
- **Risk mitigation**: Thorough testing prevents production issues

This testing strategy transforms development from a risky, uncertain process into a structured, validated progression with continuous quality assurance and stakeholder visibility.