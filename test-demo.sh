#!/bin/bash
# Logist CLI Implementation Demo & Test Suite
# Grows incrementally as units are implemented

set -e  # Exit on any error

DEMO_DIR="/tmp/logist-demo-$$"
export PURSER_JOBS_DIR="$DEMO_DIR/jobs"

cleanup() { rm -rf "$DEMO_DIR"; }
trap cleanup EXIT

echo "🧪 Logist CLI Implementation Demo"
echo "=================================="

# Source the virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
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

echo ""
echo "🎉 All implemented units passed!"
echo "✅ Demo script completed successfully"