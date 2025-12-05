# Logist

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A sophisticated agent orchestration tool that manages persistent, multi-step jobs using Cline CLI as the execution primitive. Inspired by maritime operations, Logist provides safe, structured workflows with comprehensive oversight and resource management.

---

## 🧪 Testing

### Logist CLI Testing

Logist is an AI agent orchestration tool with Git isolation and safety features. It has a comprehensive test suite with 86+ tests covering CLI commands, core functionality, and integrations.

#### Prerequisites

1. **Python Environment**: Python 3.8+ required
2. **Development Dependencies**: This project uses `pip install -e .` and `requirements-dev.txt`
3. **Virtual Environment**: Strongly recommended to avoid dependency conflicts

#### Quick Start - Run All Tests

1. **Activate your virtual environment** (recommended):
   ```bash
   # Create venv if it doesn't exist
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install the Logist package**:
   ```bash
   pip install -e .
   pip install -r requirements-dev.txt
   ```

3. **Run the complete test suite**:
   ```bash
   # Run all tests with verbose output
   pytest tests/ -v

   # Run all tests but stop on first failure
   pytest tests/ -x

   # Run tests with coverage report
   pytest tests/ --cov=logist --cov-report=html
   ```

#### Running Specific Test Categories

```bash
# Run only CLI tests
pytest tests/test_cli.py -v

# Run only core engine tests
pytest tests/test_core_engine.py -v

# Run only validation tests
pytest tests/test_validation.py -v

# Run a specific test function
pytest tests/test_cli.py::TestCLICommands::test_job_create_command -v
```

#### Test Output Options

```bash
# Quiet mode (minimal output)
pytest tests/ -q

# No traceback for failed tests
pytest tests/ --tb=no

# Show output even for passing tests
pytest tests/ -s

# Time-based performance info
pytest tests/ --durations=10
```

#### Troubleshooting Common Issues

**Tests appear to hang (no output for a long time)**:
- Some tests may wait for external resources or file operations
- Try running with timeout: `timeout 60 pytest tests/test_cli.py -v`
- Use the diagnostic script: `python3 debug-test-run.py`
- Run in parallel threads: `pytest tests/ -n auto`
- Stop on first failure: `pytest tests/ -x`

**Import errors or "Module not found"**:
```bash
# Clean reinstall
pip uninstall logist -y
pip install -e . --force-reinstall
```

**Permission or file access errors**:
- Ensure you're in the correct directory (`pwd` should show `.../logist`)
- Check if the `venv` directory exists and is activated
- Try running as user with proper write permissions

**Virtual environment issues**:
```bash
# Deactivate and reactivate
deactivate
source venv/bin/activate
```

**Environment-specific failures**:
- Some tests depend on specific Python versions or system libraries
- Check Python version: `python3 --version`
- Ensure all system dependencies are installed

#### Test Structure Overview

```
logist/tests/
├── test_cli.py           # 15 CLI command tests (job, role, rerun commands)
├── test_core_engine.py   # Core LogistEngine functionality tests
├── test_job_context.py   # Job context assembly tests
├── test_validation.py    # JSON schema and validation tests
└── services/            # Service layer tests
    ├── test_job_manager.py
    └── test_role_manager.py
```

**Current Status**: 87 tests passing, 5 skipped (94.6% success rate). All tests are currently passing with high test coverage.

#### Advanced Testing

**Debugging hanging tests**:
```bash
# Run with debugging output
pytest tests/test_cli.py -v -s --pdb

# Time individual tests
pytest tests/test_cli.py --durations=0
```

**Continuous Integration**:
```bash
# Run tests like CI would
pytest tests/ --tb=short --strict-markers

# Check code coverage
pytest tests/ --cov=logist --cov-fail-under=85
```

## 🏗️ Installation

### Virtual Environment Setup (Recommended)

It's highly recommended to use a Python virtual environment to isolate dependencies:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Deactivate when done:
# deactivate
```

### From Source (Development)

#### Option 1: Modern Python Packaging (Recommended)
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

#### Option 2: Traditional Requirements Files
```bash
git clone <repository-url>
cd logist

# Install runtime dependencies only
pip install -r requirements.txt

# Or install with development tools (pytest, black, etc.)
pip install -r requirements-dev.txt
```

### For Users
```bash
pip install logist
```

## 📋 Prerequisites

### Cline CLI Setup

Logist requires the **[Cline CLI](https://github.com/cline/cline)** tool as its execution primitive. Cline is a Node.js-based command-line interface that provides structured AI agent execution.

#### Installation
```bash
npm install -g @cline/cli
```

#### Configuration
Cline must be configured with access to your preferred LLM providers:

1. **Obtain API keys** from your LLM providers (OpenAI, Anthropic, Google, etc.)
2. **Configure Cline**:
   ```bash
   cline config set openai.key sk-your-key-here
   cline config set openai.model grok-code-fast-1
   ```
3. **Verify setup**:
   ```bash
   cline --version
   cline config list
   ```

**Note**: Cline is maintained as a separate project and is not included in Logist's Python dependencies. Users are responsible for installing and configuring Cline appropriately.

## 🚀 Quick Start

1. **Set environment variables (optional but recommended):**
   ```bash
   # Set custom jobs directory
   export LOGIST_JOBS_DIR="./my-jobs"

   # Set current job ID
   export LOGIST_JOB_ID="demo-job"
   ```

2. **Create a job specification:**
   ```json
   {
     "job_spec": {
       "job_id": "demo",
       "description": "Sample job",
       "cost_threshold": 1000,
       "time_threshold_minutes": 30
     }
   }
   ```

3. **Run your first job:**
   ```bash
   logist job run demo
   ```

4. **Monitor progress:**
   ```bash
   logist job status demo
   ```

   **Or omit job ID if LOGIST_JOB_ID is set:**
   ```bash
   logist job status  # Uses value from LOGIST_JOB_ID
   ```

## 📋 Testing Procedure

### 🧪 Run Tests

#### 1. Install Test Dependencies
```bash
cd logist
pip install -e .[dev]
```

#### 2. Execute All Tests
```bash
# From project root
pytest

# With verbose output
pytest -v

# With coverage
pytest --cov=logist --cov-report=html
```

#### 3. CLI Functionality Tests
```bash
# Test CLI installation
logist --version
logist --help

# Test core commands (prints placeholder actions)
logist job list
logist job run demo-job
logist job step demo-job
logist job status demo-job
```

#### 4. Individual Test Suites
```bash
# Engine placeholder tests
pytest tests/test_cli.py::TestPlaceholderLogistEngine -v

# Job manager placeholder tests
pytest tests/test_cli.py::TestPlaceholderJobManager -v

# CLI command integration tests
pytest tests/test_cli.py::TestCLICommands -v
```

### 🔍 Test Coverage

Current **do-little tests** verify:
- ✅ CLI commands accept valid arguments
- ✅ Placeholder functions print expected intentions
- ✅ JSON parsing works for job specifications
- ✅ Command-line help and versioning
- ✅ Click framework integration
- ✅ Placeholder state management

### 🎭 Do-Nothing-But-Print Philosophy

This initial implementation follows a **print-based scaffolding** pattern:

- **Prints Actions**: All functions describe what they _would_ do instead of executing
- **Validates Structure**: Ensures command parsing and data flow work correctly
- **Safe Testing**: No actual file system or external service modifications
- **Rapid Iteration**: Fast feedback loop for CLI design refinement

### 🔧 Development Testing

```bash
# Install in development mode
pip install -e .

# Run with demo job
logist job create config/sample-job.json
logist job step sample-implementation
```

## 🏛️ Architecture

**Core Components:**
- **Logist**: Orchestration engine managing job lifecycles
- **Steward**: Human checkpoint interface
- **Worker**: Implementation agent executing tasks
- **Supervisor**: Quality assurance and oversight agent

**Workflow Pattern:**
1. **Planning** (Logist analyzes objectives)
2. **Execution** (Worker builds solutions)
3. **Review** (Supervisor validates quality)
4. **Intervention** (Steward provides guidance via checkpoints)

## 📚 Documentation

This documentation follows a progressive learning path:

### [`01_architecture.md`](docs/01_architecture.md) - Core Concepts
- Project terminology (Logist, Job, Agent Run, Steward)
- Execution philosophy and job isolation
- Iterative Worker→Supervisor→Steward loop
- Git safety practices and rollback mechanisms

### [`02_roles_and_data.md`](docs/02_roles_and_data.md) - Roles and Communication
- Programmable role system and manifest structure
- JSON exit command protocol for agent communication
- Structured output requirements and validation
- Flow control integration

### [`03_cli_and_metrics.md`](docs/03_cli_and_metrics.md) - CLI Interface and Guardrails
- Four core logist commands (run, step, rerun, restep)
- Metric tracking system (cost, time)
- Threshold enforcement and halt states
- Configuration options and recovery strategies

### [`04_state_machine.md`](docs/04_state_machine.md) - Advanced Workflows
- DAG-based task execution and state machine
- Parallel task dependencies and failure handling
- Intervention states and human gates
- Reference implementation for future enhancements

### Key Design Principles

- **Safety First**: Git isolation prevents workspace corruption
- **Structured Communication**: JSON protocols eliminate ambiguity
- **Human Control**: Steward checkpoints maintain oversight
- **Resource Aware**: Cost and time thresholds prevent runaway execution
- **Composable**: Roles and jobs can be mixed and matched

## 🛡️ Safety Features

- **Git Isolation**: Jobs run in separate branches with baseline commits
- **Threshold Enforcement**: Automatic halting on cost/time limits
- **State Persistence**: Complete rollback capability
- **Structured Communication**: JSON protocols prevent ambiguity

## 💻 Development Workflow

### Code Quality & Formatting

This project uses **Ruff** for lightning-fast linting and formatting, replacing flake8, isort, and black:

```bash
# Format code automatically
ruff format .

# Check for linting issues
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Run both formatting and checking
ruff format . && ruff check --fix .
```

### Running Tests

```bash
# Run all tests
pytest

# Verbose output with coverage
pytest -v --cov=logist --cov-report=html
```

### Pre-commit Setup (Optional)

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files  # Manual run
```

## 🤝 Contributing

1. Install development dependencies: `pip install -e .[dev]`
2. Run code quality checks: `ruff format . && ruff check --fix .`
3. Run tests: `pytest`
4. Create feature branch and submit PR

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Inspiration

The name 'logist' draws from nautical history, where logistics originated from the work of pursers who managed material distribution and supplies aboard ships. Combining 'logistics' for systematic resource management with the maritime tradition of purser's oversight, Logist provides structured orchestration for complex AI workflows.

Drawing from maritime traditions where a ship's logist manages finances and logistics while stewards coordinate operations, this tool provides structured oversight for complex AI workflows.