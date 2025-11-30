# Oneshot Research Scripts: Setup and Usage Guide

This guide provides complete instructions for setting up and using the Logist oneshot research scripts for testing Cline CLI batch execution with automatic restart capabilities.

## 🎯 Overview

The oneshot research tools enable:
- **Automatic task execution** with Cline CLI `--oneshot --yolo` mode
- **Inactivity detection** and automatic restart of stuck tasks
- **Batch processing** of multiple tasks with individual monitoring
- **Cost/token variance analysis** across multiple executions
- **Process lifecycle management** with PID tracking and graceful termination

## 📋 Prerequisites

### Required Software
```bash
# Node.js and npm (for Cline CLI)
node --version  # Should be 18+
npm --version   # Should be 9+

# Python 3.8+ (for research scripts)
python3 --version  # Should be 3.8+
```

### Cline CLI Installation
```bash
# Install Cline CLI globally
npm install -g @cline/cli

# Verify installation
cline --version  # Should show version 3.38.3 or higher

# Configure API access (choose one)
# OpenAI
cline config set openai.key sk-your-openai-key-here
cline config set openai.model gpt-4-turbo

# Anthropic
cline config set anthropic.key sk-your-anthropic-key-here
cline config set anthropic.model claude-3-opus-20240229
```

### Python Dependencies
```bash
# Install required Python packages
pip install jsonschema requests  # If not already installed via requirements.txt

# The scripts use only standard library + jsonschema for JSON validation
```

## 🏗️ Script Files and Their Purposes

### 1. `logist/scripts/oneshot-start.py`
**Purpose**: Programmatic launch of oneshot tasks with parameter control
**Executable**: ✅ Yes
```bash
chmod +x logist/scripts/oneshot-start.py
```

**Usage Examples:**
```bash
# Basic oneshot execution
./oneshot-start.py --prompt "Create a hello world script in Python" --verbose

# With custom model and context
./oneshot-start.py --prompt "Analyze this data" --model gpt-4 --context data.json --json-output

# Background execution with monitoring PID
PID=$(./oneshot-start.py --prompt "Long running task..." 2>&1 | grep -o "PID: [0-9]*" | cut -d' ' -f2)
echo "Task launched with PID: $PID"
```

### 2. `logist/scripts/oneshot-monitor.py`
**Purpose**: Monitor task completion with automatic restart of stuck tasks
**Executable**: ✅ Yes

**Key Features:**
- Inactivity detection via metadata polling
- Automatic restart using `cline task open $task_id --oneshot --yolo`
- Process termination before restart
- Retry limits and anti-loop protection

**Usage Examples:**
```bash
# Basic monitoring (no restart)
./oneshot-monitor.py 1734567890123 --verbose

# With auto-restart capability
./oneshot-monitor.py 1734567890123 --auto-restart --pid 12345 --max-retries 3 --verbose

# Long-running task monitoring
./oneshot-monitor.py 1734567890123 --timeout 60 --poll-interval 10 --auto-restart

# JSON output for scripting
./oneshot-monitor.py 1734567890123 --json --timeout 30
```

### 3. `logist/scripts/batch-executor.py`
**Purpose**: Execute multiple tasks in batch with individual monitoring and restart
**Executable**: ✅ Yes (after writing, needs `chmod +x`)

**Features:**
- Process multiple tasks from JSON file or single command-line task
- Individual monitoring for each task
- Automatic restart capabilities per task
- Comprehensive result reporting

**Usage Examples:**
```bash
# Execute single task
./batch-executor.py --prompt "Create a bash script that lists files" --name "list-task" --auto-restart

# Execute from JSON file
./batch-executor.py tasks.json --auto-restart --verbose --output results.json

# Custom timeout and model
./batch-executor.py --prompt "Analyze this code" --model gpt-4 --timeout 30 --json-output
```

### 4. `logist/scripts/analyze-variance.py`
**Purpose**: Statistical analysis of execution metrics across multiple runs
**Executable**: ✅ (after writing, needs `chmod +x`)

**Features:**
- Analyze token consumption patterns
- Calculate variance in costs and execution times
- Generate research reports for cost projections

### 5. `logist/config/test-job-simple.py`
**Purpose**: Predictable test job for oneshot variance research
**Executable**: ✅ Yes

**Features:**
- Deterministic operations for consistent testing
- JSON schema compliant output
- Error handling with graceful failure responses

## 🚀 Complete Setup and Execution Workflow

### Step 1: Initial Setup
```bash
# Navigate to project directory
cd /path/to/logist

# Make scripts executable
chmod +x scripts/oneshot-start.py
chmod +x scripts/oneshot-monitor.py
chmod +x scripts/batch-executor.py
chmod +x scripts/analyze-variance.py
chmod +x config/test-job-simple.py

# Verify Cline CLI access
cline --version
cline config list  # Should show API keys configured
```

### Step 2: Test Individual Components

#### Test Basic Oneshot Launch
```bash
# Simple task execution
./scripts/oneshot-start.py --prompt "Create a hello world script in Python" --verbose

Expected output:
Launching task: cline --oneshot --no-interactive --model gpt-4 [...command...]
✅ Oneshot execution completed successfully
Output: [JSON response with COMPLETED/STUCK/RETRY status]
```

#### Test Monitoring (Manual Task ID)
```bash
# First launch a task to get its ID
# (Note: Get real task ID from ~/.cline/data/tasks/ directory)
TASK_ID=$(ls -t ~/.cline/data/tasks/ | head -1)
./scripts/oneshot-monitor.py $TASK_ID --timeout 15 --verbose

Expected output:
Monitoring task 1734567890123456 (auto_restart=disabled)...
Task 1734567890123456 status: ACTIVE, waiting 5s...
Task 1734567890123456 completed: TIMEOUT_COMPLETE
```

#### Test Enhanced Monitoring with Auto-Restart
```bash
# Launch task and capture PID (in production, you'd script this)
# For now, manually get task ID and PID
TASK_ID="1734567890123456"
PROCESS_PID="12345"

./scripts/oneshot-monitor.py $TASK_ID --auto-restart --pid $PROCESS_PID --max-retries 2 --verbose

Expected output (if task gets stuck):
Monitoring task 1734567890123456 (auto_restart=enabled)...
Task 1734567890123456 appears stuck (inactive > 10min), attempting restart...
Gracefully terminated process 12345
Restarting task with: cline task open 1734567890123456 --oneshot --yolo
Successfully restarted task 1734567890123456
Restart #1 completed for task 1734567890123456
[continues monitoring...]
```

### Step 3: Create Task Configuration for Batch Execution

#### Create a JSON task file:
```bash
# Create tasks.json
cat > tasks.json << 'EOF'
[
  {
    "name": "script-generator",
    "prompt": "Create a Python script that generates random passwords",
    "context_files": []
  },
  {
    "name": "data-analyzer",
    "prompt": "Analyze this dataset and generate summary statistics",
    "context_files": ["data/sample.csv"]
  },
  {
    "name": "error-handler",
    "prompt": "Create error handling patterns for file operations",
    "context_files": []
  }
]
EOF
```

### Step 4: Execute Batch Processing
```bash
# Run batch with auto-restart
./scripts/batch-executor.py tasks.json --auto-restart --verbose --timeout 20 --output batch-results.json

# Expected output:
Starting batch execution of 3 tasks...

--- Executing script-generator (1/3) ---
Launching task: cline --oneshot --no-interactive --model gpt-4 [...script-generator prompt...]
Monitoring script-generator (ID: task_1734567890123)...
Task task_1734567890123 completed: TIMEOUT_COMPLETE
Restart Attempts: 2

--- Executing data-analyzer (2/3) ---
[...similar output...]

📊 Batch Execution Summary
==================================================
Tasks Processed: 3
Successful Tasks: 3
Total Restarts: 1

📋 Task Details:
  ✅ script-generator: TIMEOUT_COMPLETE (restarts: 2)
  ✅ data-analyzer: TIMEOUT_COMPLETE (restarts: 0)
  ✅ error-handler: TIMEOUT_COMPLETE (restarts: 0)
```

### Step 5: Variance Analysis (Multiple Runs)

#### Execute multiple test runs:
```bash
# Run simple test job multiple times
for i in {1..10}; do
  echo "=== Run $i ==="
  ./config/test-job-simple.py
  sleep 2
done > variance-test.log
```

#### Analyze results:
```bash
# (Note: analyze-variance.py would parse the log and generate statistics)
# For manual analysis, extract metrics from logs
grep -E "(tokens_used|cost_usd|duration)" variance-test.log
```

## 📊 Expected Outputs and Behavior

### Successful Task Completion
```json
{
  "task_id": "1734567890123456",
  "status": "TIMEOUT_COMPLETE",
  "model": "gpt-4-turbo",
  "api_calls": 3,
  "cost_usd": 0.0000,
  "restart_attempts": 1,
  "created_at": 1734567890,
  "completed_at": 1734567900
}
```

### Failed/Stuck Task with Auto-Restart
```
Monitoring task 1734567890123456 (auto_restart=enabled)...
Task 1734567890123456 appears stuck (inactive > 10min), attempting restart...
Gracefully terminated process 12345
Restarting task with: cline task open 1734567890123456 --oneshot --yolo
Successfully restarted task 1734567890123456
Restart #1 completed for task 1734567890123456
[Monitoring continues...]
```

### Batch Execution Results
```json
[
  {
    "task_name": "script-generator",
    "task_id": "task_001",
    "status": "TIMEOUT_COMPLETE",
    "restart_attempts": 2,
    "model": "gpt-4",
    "evidence_files": ["output.py", "test-output.txt"]
  }
]
```

## 🔧 Troubleshooting and Common Issues

### Issue: "cline command not found"
```bash
# Check installation
which cline
npm install -g @cline/cli

# Verify version
cline --version
```

### Issue: "Could not find Cline task metadata directory"
```bash
# Check Cline data directory
ls -la ~/.cline/
ls -la ~/.cline/data/tasks/

# Override directory if needed
export CLINE_TASKS_DIR=/custom/path/to/tasks
```

### Issue: "Task monitoring timeout"
- Increase `--timeout` value (default 10 minutes)
- Check if task is actually running: `ps aux | grep cline`
- Verify API key limits and quota

### Issue: "JSON parse error"
- The metadata file might be mid-update
- Script handles this gracefully with retries
- Check file permissions on task directory

### Issue: "Restart command failed"
```bash
# Manual restart test
cline task open <task_id> --oneshot --yolo

# Check task exists
cline task list | grep <task_id>
```

### Issue: "PID termination failed"
- Process may have already exited
- Script will continue with restart attempt
- Check process table: `ps aux | grep <pid>`

## 🔄 Integration with Logist Workflow

### In Job Poststep Processing
```bash
# After oneshot completion, validate response
logist job poststep --task-id $TASK_ID --response-file ~/.cline/data/tasks/$TASK_ID/response.json
```

### Cost Threshold Enforcement
```bash
# Extract cost from completed task
COST=$(./oneshot-monitor.py $TASK_ID --json | jq -r '.cost_usd')

# Check against threshold
if (( $(echo "$COST > 0.50" | bc -l) )); then
  echo "Cost threshold exceeded: $COST"
  exit 1
fi
```

### Automated Testing Integration
```bash
#!/bin/bash
# Automated test pipeline

# Launch test tasks
./batch-executor.py test-tasks.json --auto-restart --output test-results.json

# Validate results
python3 validate_results.py test-results.json

# Generate reports
./analyze-variance.py test-results.json > test-report.md
```

## 📝 Development Notes

### Adding New Monitoring Features
1. Extend `monitor_task()` function with new parameters
2. Add corresponding CLI arguments to `main()`
3. Update documentation with new examples
4. Test with various task scenarios

### Custom Polling Strategies
- Modify `poll_interval` for different update frequencies
- Add custom timeout calculations based on task complexity
- Implement exponential backoff for retries

### Integration Points
- These scripts integrate with `logist job poststep` for response validation
- Cost data feeds into `metrics_cost_tracking_system` for budget enforcement
- Task metadata provides monitoring data for dashboard implementations

---

*Document compiled for Logist Phase 0.1: Oneshot Research Unit*
*Last updated: November 29, 2025*