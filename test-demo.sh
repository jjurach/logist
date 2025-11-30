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

# Unit 6: isolation_env_setup
echo "📋 Unit 6: isolation_env_setup workspace creation"
logist job step my-first-job --dry-run  # Use --dry-run to test setup without execution
if [ ! -d "$DEMO_DIR/my-first-job/workspace" ]; then
    echo "❌ Workspace directory not created"
    exit 1
fi
if [ ! -d "$DEMO_DIR/my-first-job/workspace/.git" ]; then
    echo "❌ Workspace is not a valid git repository"
    exit 1
fi
echo "✅ Workspace directory created with working git clone"

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


echo ""
echo "🎉 All implemented units passed!"
echo "✅ Virtual environment activated"
echo "✅ Jobs directory created successfully"
echo "✅ Job created successfully"
echo "✅ Job status command executed"
echo "✅ Job selected successfully"
echo "✅ Job workspace setup executed"
echo "✅ Role list command executed and roles verified"
echo "✅ Job rerun command executed and scenarios verified"
echo ""
echo "🎉 Demo script completed successfully"