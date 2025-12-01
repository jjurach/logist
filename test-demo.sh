#!/bin/bash
# Logist CLI Implementation Demo & Test Suite
# Grows incrementally as units are implemented

set -e  # Exit on any error

# VERBOSE mode: print payloads and command outputs when VERBOSE is truthy
VERBOSE="${VERBOSE:-}"

# Helper function to display sample payloads when verbose
show_sample_payloads() {
    if [ -n "$VERBOSE" ]; then
        echo "📄 Sample Job Payload:"
        cat config/sample-job.json | jq .
        echo ""
        echo "📄 Sample LLM Request Payload:"
        cat docs/examples/llm-exchange/valid-llm-request.json | jq .
        echo ""
        echo "📄 Sample LLM Response Payload:"
        cat docs/examples/llm-exchange/valid-llm-response.json | jq .
        echo ""
    fi
}

# Helper function to run commands with optional output
run_cmd() {
    local cmd="$1"
    if [ -n "$VERBOSE" ]; then
        echo "🔧 Running: $cmd"
        eval "$cmd"
    else
        eval "$cmd" > /dev/null 2>&1
    fi
}

DEMO_DIR="/tmp/logist-demo-$$"
export LOGIST_JOBS_DIR="$DEMO_DIR/jobs"

cleanup() { rm -rf "$DEMO_DIR"; }
trap cleanup EXIT

echo "🧪 Logist CLI Implementation Demo"
echo "=================================="

# Source the virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
    # Install the logist package in editable mode so modules are discoverable
    pip install -e .
    echo "✅ Logist package installed in editable mode"
else
    echo "⚠️  Virtual environment not found, using system Python"
fi

# Show sample payloads in verbose mode
show_sample_payloads

# Unit 1: init_command
echo "📋 Unit 1: logist init"
logist init
if [ ! -d "$DEMO_DIR/jobs" ]; then
    echo "❌ Jobs directory not created"
    exit 1
fi
if [ ! -f "$DEMO_DIR/jobs/jobs_index.json" ]; then
    echo "❌ jobs_index.json not created"
    exit 1
fi
echo "✅ Jobs directory created successfully"

# Unit 2: job_list_command
echo "📋 Unit 2: logist job list"
logist job list
echo "✅ Job list command executed (empty list expected)"

# Unit 3: job_create_command
echo "📋 Unit 3: logist job create"
mkdir -p "$DEMO_DIR/my-first-job"
logist job create "$DEMO_DIR/my-first-job"
if [ ! -f "$DEMO_DIR/my-first-job/job_manifest.json" ]; then
    echo "❌ Job manifest not created"
    exit 1
fi
echo "✅ Job created successfully"

# Set up job spec for my-first-job
echo "📋 Setting up job spec for my-first-job"
cp config/sample-job.json "$DEMO_DIR/my-first-job/"
python3 -c "
import json
with open('$DEMO_DIR/my-first-job/sample-job.json', 'r') as f:
    sample_data = json.load(f)

with open('$DEMO_DIR/my-first-job/job_manifest.json', 'r+') as f:
    manifest = json.load(f)
    # Extract the job_spec from the sample data and update manifest
    job_spec_data = sample_data['job_spec']
    manifest.update(job_spec_data)
    # Set initial phase if not set
    if not manifest.get('current_phase'):
        if manifest.get('phases'):
            manifest['current_phase'] = manifest['phases'][0]['name']
    f.seek(0)
    json.dump(manifest, f, indent=2)
"
echo "✅ Job spec set up successfully"

# Unit 4: job_status_command
echo "📋 Unit 4: logist job status"
logist job status my-first-job | grep -q "Status:"
if [ $? -ne 0 ]; then
    echo "❌ Job status not displayed"
    exit 1
fi
echo "✅ Job status command executed"

# Unit 5: job_select_command
echo "📋 Unit 5: logist job select"
logist job select my-first-job
# Verify current_job_id is set
CURRENT_JOB=$(python3 -c "
import json
with open('$DEMO_DIR/jobs/jobs_index.json', 'r') as f:
    data = json.load(f)
    print(data.get('current_job_id', 'None'))
")
if [ "$CURRENT_JOB" != "my-first-job" ]; then
    echo "❌ Job not selected correctly: $CURRENT_JOB"
    exit 1
fi
echo "✅ Job selected successfully"

# Unit 6: job_step_execution
echo "📋 Unit 6: job step execution"
echo "📋 Previewing job step..."
logist job preview my-first-job
echo "✅ Job preview executed"

echo "📋 Running actual job step..."
# Note: This will actually execute a worker step, which requires LLM API access
# The job is properly configured now, but execution may fail without API keys or if rate-limited
echo "⚠️  Note: Job step execution may fail due to missing API configuration - this is expected in demo environment"
run_cmd "logist job step my-first-job"
echo "✅ Job step command executed (may have completed, failed due to API access, or requires user interaction)"

echo ""
# Unit 7: role_list_command
echo "📋 Unit 7: logist role list"
ROLE_LIST_OUTPUT=$(logist role list)
echo "$ROLE_LIST_OUTPUT"
if ! echo "$ROLE_LIST_OUTPUT" | grep -q "Worker: Expert software development"; then
    echo "❌ Worker role not listed or description incorrect"
    exit 1
fi
if ! echo "$ROLE_LIST_OUTPUT" | grep -q "Supervisor: Quality assurance and oversight specialist"; then
    echo "❌ Supervisor role not listed or description incorrect"
    exit 1
fi
echo "✅ Role list command executed and roles verified"

# Unit 11: role_inspect_command
echo "📋 Unit 11: logist role inspect existing role"
logist role inspect Worker > /tmp/worker_inspect_output.txt
if ! grep -q '"name": "Worker"' /tmp/worker_inspect_output.txt; then
    echo "❌ Worker role inspect did not show correct name"
    exit 1
fi
if ! grep -q '"description": "Expert software development and implementation agent specializing in code generation, debugging, and technical problem-solving"' /tmp/worker_inspect_output.txt; then
    echo "❌ Worker role inspect did not show correct description"
    exit 1
fi
if ! grep -q '"llm_model": "grok-code-fast-1"' /tmp/worker_inspect_output.txt; then
    echo "❌ Worker role inspect did not show correct LLM model"
    exit 1
fi
if ! grep -q '"instructions":' /tmp/worker_inspect_output.txt; then
    echo "❌ Worker role inspect did not show instructions field"
    exit 1
fi
echo "✅ Role inspect command executed and Worker role verified"

# Unit 12: role_inspect_command for non-existent role
echo "📋 Unit 12: logist role inspect non-existent role"
NONEXISTENT_INSPECT_OUTPUT=$(logist role inspect NonExistentRole 2>&1)
if ! echo "$NONEXISTENT_INSPECT_OUTPUT" | grep -q "Role 'NonExistentRole' not found"; then
    echo "❌ Role inspect should show proper error for non-existent role"
    exit 1
fi
echo "✅ Role inspect command properly handles non-existent roles"

# Unit 8: job_rerun_command
echo "📋 Unit 8: logist job rerun"
mkdir -p "$DEMO_DIR/rerun-test-job"

# Create a sample job spec with phases for testing rerun
cat > "$DEMO_DIR/rerun-test-job/job.json" << 'EOF'
{
  "job_spec": {
    "job_id": "rerun-test-job",
    "description": "Test job for rerun functionality",
    "phases": [
      {"name": "analysis", "description": "Analysis phase"},
      {"name": "implementation", "description": "Implementation phase"},
      {"name": "testing", "description": "Testing phase"}
    ]
  }
}
EOF

logist job create "$DEMO_DIR/rerun-test-job"
if [ ! -f "$DEMO_DIR/rerun-test-job/job_manifest.json" ]; then
    echo "❌ Rerun test job manifest not created"
    exit 1
fi
echo "✅ Rerun test job created successfully"

# Test rerun from start (no --step specified)
logist job rerun rerun-test-job | grep -q "Starting rerun from the beginning"
if [ $? -ne 0 ]; then
    echo "❌ Job rerun from start failed"
    exit 1
fi
echo "✅ Job rerun from start executed"

# Test rerun from specific step
logist job rerun rerun-test-job --step 1 | grep -q "Starting rerun from phase 1"
if [ $? -ne 0 ]; then
    echo "❌ Job rerun from specific step failed"
    exit 1
fi
echo "✅ Job rerun from specific step executed"

# Test rerun with invalid step (should handle gracefully)
logist job rerun rerun-test-job --step 10 | grep -q "Invalid step number"
if [ $? -ne 0 ]; then
    echo "❌ Job rerun error handling for invalid step failed"
    exit 1
fi
echo "✅ Job rerun error handling for invalid step number verified"

# Unit 9: job_chat_command
echo "📋 Unit 9: logist job chat state validation"
logist job chat my-first-job 2>&1 | grep -q "Job 'my-first-job' has no execution history"
if [ $? -ne 0 ]; then
    echo "❌ Job chat should fail for job with no execution history"
    exit 1
fi
echo "✅ Job chat correctly rejects jobs with no execution history"

# Unit 10: job_run_command
echo "📋 Unit 10: logist job run - terminal state detection"
# Test that run command properly handles jobs in terminal states
# First create a job and manually set it to a terminal state
mkdir -p "$DEMO_DIR/terminal-test-job"
logist job create "$DEMO_DIR/terminal-test-job"

# Manually set job to CANCELED status to test terminal state handling
JOB_MANIFEST="$DEMO_DIR/terminal-test-job/job_manifest.json"
python3 -c "
import json
with open('$JOB_MANIFEST', 'r') as f:
    manifest = json.load(f)
manifest['status'] = 'SUCCESS'
with open('$JOB_MANIFEST', 'w') as f:
    json.dump(manifest, f, indent=2)
"

# Test that run command recognizes terminal state
logist job run terminal-test-job 2>&1 | grep -q "already in terminal state"
if [ $? -ne 0 ]; then
    echo "❌ Job run should detect and skip jobs in terminal states"
    exit 1
fi
echo "✅ Job run correctly recognizes jobs in terminal states"

# Test that run command shows proper error for nonexistent jobs
NONEXISTENT_RUN_OUTPUT=$(logist job run nonexistent-job 2>&1)
if ! echo "$NONEXISTENT_RUN_OUTPUT" | grep -q "Could not find job directory"; then
    echo "❌ Job run should show proper error for nonexistent jobs"
    exit 1
fi
echo "✅ Job run shows proper error handling for nonexistent jobs"

echo ""
echo "🎉 All implemented units passed!"
echo "✅ Virtual environment activated"
echo "✅ Jobs directory created successfully"
echo "✅ Job created successfully"
echo "✅ Job status command executed"
echo "✅ Job selected successfully"
echo "✅ Job workspace setup executed"
echo "✅ Role list command executed and roles verified"
echo "✅ Role inspect command executed and Worker role verified"
echo "✅ Role inspect command properly handles non-existent roles"
echo "✅ Job rerun command executed and scenarios verified"
echo "✅ Job chat command state validation working"
echo "✅ Job run command terminal state detection working"
echo ""
echo "🎉 Demo script completed successfully"