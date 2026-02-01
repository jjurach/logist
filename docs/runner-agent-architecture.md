# Logist Runner and Agent Architecture

This document defines the fundamental architectural separation between **runners** and **agent providers** in Logist. These concepts guide future development and may require refactoring existing implementations to align with this design.

## Architectural Overview

Logist separates execution behaviors behind two primary interfaces:

1. **Runner Interface** - Controls *where* and *how* code executes (environment management)
2. **Agent Provider Interface** - Controls *what* CLI tool executes the coding task (tool abstraction)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Logist Core Engine                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐           ┌─────────────────────────┐     │
│   │  Runner         │           │  Agent Provider         │     │
│   │  Interface      │           │  Interface              │     │
│   ├─────────────────┤           ├─────────────────────────┤     │
│   │ - podman        │           │ - cline-cli             │     │
│   │ - docker        │           │ - aider-chat            │     │
│   │ - kubernetes    │           │ - claude-code           │     │
│   │ - direct        │           │ - gemini-cli            │     │
│   │                 │           │ - openai-codex          │     │
│   │                 │           │ - mock                  │     │
│   └─────────────────┘           └─────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Non-Interactive Execution Principle

**Logist and its runners are fundamentally non-interactive.** The system manages execution autonomously and is not designed to prompt the user for input at any point during a job's lifecycle.

- Job creation, configuration, and activation are the only user interaction points
- Once a job step begins execution, it runs to completion without user prompts
- Human intervention states (INTERVENTION_REQUIRED, APPROVAL_REQUIRED) occur *between* executions, not during
- Agents must be configured for one-shot, non-interactive mode

## Configuration Hierarchy

### logist.yml Configuration File

A `logist.yml` configuration file in the project root defines default runner and agent settings:

```yaml
# logist.yml - Project-level configuration
runner: docker          # Default runner (podman, docker, kubernetes, direct)
agent: claude-code      # Default agent provider

# Runner-specific configuration
runners:
  docker:
    image: logist/agent-runner:latest
    network: host
  podman:
    image: logist/agent-runner:latest
  direct:
    timeout: 3600

# Agent-specific configuration
agents:
  claude-code:
    model: claude-sonnet-4-20250514
  aider-chat:
    model: gpt-4
```

### Job-Level Overrides

Jobs can override default configurations via attributes in the job manifest:

```json
{
  "job_id": "my-job",
  "runner": "podman",
  "agent": "aider-chat",
  "prompt": "Implement the new feature..."
}
```

CLI options also override defaults:
```bash
logist job create --runner podman --agent aider-chat --prompt "Do this thing"
```

## Runner Interface

### Runner Responsibilities

The runner subclass determines behaviors related to:

1. **Process Lifecycle Management**
   - Spawning one-shot processes in the background
   - Monitoring process state and health
   - Recovering/restarting stuck processes
   - Cleaning up after job step completion

2. **Workspace Provisioning**
   - Setting up isolated workspace for the job
   - Managing git repository cloning and branch setup
   - Delivering source tree to the agent execution environment
   - Handling attachments and context files

3. **Execution Monitoring**
   - Providing timestamped logs to the agent instance
   - Determining completion status for a job step
   - Managing timeouts and resource limits

4. **Results Harvesting**
   - Collecting execution outputs and evidence files
   - Committing changes to the job branch
   - Preparing results for the next phase

### Docker Runner Specifics

The Docker runner needs to:

- Run `docker run` to start executing a container task
- Run `docker ps -a` and similar commands to reconcile logist state information
  - Know the state that logist thinks is currently executing (container IDs)
- Run `docker logs` and similar commands to pull the latest chat state of the CLI execution
- Run `docker kill` and `docker rm` to clean up after a logist step completes
- Run `docker exec` in recovery mode to restart a session using its state

The Docker runner passes the latest log to the agent instance for the agent to determine whether the log indicates completion of the task. The agent instance may pass information back into a "replay" of the execution to recover/restart it.

### Podman Runner

The Podman runner performs the same operations using Podman equivalents:
- `podman run`, `podman ps`, `podman logs`, `podman kill`, `podman rm`, `podman exec`

### Kubernetes Runner

The Kubernetes runner manages jobs as Kubernetes pods/jobs:
- Create pods/jobs for execution
- Query pod status via kubectl or API
- Stream logs from running pods
- Handle pod lifecycle and cleanup

### Direct Runner

The Direct runner executes commands directly on the host:
- Spawn background processes
- Monitor process status via PID
- Capture stdout/stderr output
- Handle process termination and cleanup

## Agent Provider Interface

### Agent Responsibilities

The agent subclass concerns itself with:

1. **Prompt Delivery**
   - Delivering attached files and context to the CLI tool
   - Cleaning up and formatting the prompt for the specific agent
   - Scanning for and including references to relevant source files

2. **Command Generation**
   - Generating the appropriate CLI command for the agent tool
   - Configuring one-shot/non-interactive mode flags
   - Setting up API keys and model configurations

3. **Completion Detection**
   - Parsing execution logs to detect completion
   - Identifying success/failure/stuck states from output
   - Extracting structured responses (JSON exit commands)

4. **Environment Setup**
   - Providing required environment variables
   - Configuring tool-specific settings

### Supported Agent Providers

| Agent | Description |
|-------|-------------|
| `cline-cli` | Cline CLI for one-shot coding tasks |
| `aider-chat` | Aider for AI pair programming |
| `claude-code` | Claude Code CLI for direct Claude interaction |
| `gemini-cli` | Google Gemini CLI tool |
| `openai-codex` | OpenAI Codex for code generation |
| `mock` | Mock agent for testing and development |

## Required Job Attributes

### status Attribute

The status of a job is stored according to the state sequence defined in `doc/04_state_machine.md`. Valid states include:

**Resting States:** DRAFT, PENDING, SUCCESS, CANCELED, SUSPENDED, APPROVAL_REQUIRED, INTERVENTION_REQUIRED

**Transient States (during step execution):** PROVISIONING, EXECUTING, RECOVERING, HARVESTING

### prompt Attribute

Every job must have a `prompt` attribute containing the text to be executed with the job:

```bash
# Create job with inline prompt
logist job create --prompt 'Implement user authentication'

# Create job from file
logist job create --file prompt.md
```

If created with `--file`, the file contents populate the required prompt attribute.

### gitSourceRepo Attribute

An important attribute is `gitSourceRepo`, which specifies where the source code comes from:

- **Typical usage**: Logist is executed from a terminal in a git-cloned workspace
- **Auto-detection**: Logist consults `./.git`, `./../.git`, etc. until it finds the `.git` directory
- **Explicit override**: `--gitSourceRepo` flag on command-line
- **Error handling**: If logist cannot find a git directory and `--gitSourceRepo` is not provided, the create/update operation fails with an error message and `exit(1)`

This git directory or URL is used by the runner/agent provider to construct an isolated workspace for the job.

## Optional Job Attributes

Jobs can override many default behaviors. While `logist.yml` provides configuration defaults, the CLI (and API) provides options during job creation to override them:

```bash
# Override default runner
logist job create --runner podman --prompt "Do this"

# Override default agent
logist job create --agent aider-chat --prompt "Do this"

# Override both
logist job create --runner docker --agent claude-code --prompt "Do this"
```

These overrides are stored in the job manifest and persist across job operations.

## Runner Lifecycle Operations

The Runner interface defines a complete lifecycle for job execution. Each phase maps to specific runner methods and job states (see `doc/04_state_machine.md`):

### Lifecycle Phases and State Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Runner Lifecycle with Job States                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Job State: PENDING                                                          │
│       │                                                                      │
│       ▼                                                                      │
│  1. PROVISION ─────────────────────────────────────────────────────────────  │
│  Job State: PROVISIONING                                                     │
│  ┌──────────────────┐                                                        │
│  │ provision()      │                                                        │
│  │ - Clone repo     │                                                        │
│  │ - Setup branch   │                                                        │
│  │ - Copy files     │                                                        │
│  └────────┬─────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  2. SPAWN ─────────────────────────────────────────────────────────────────  │
│  Job State: EXECUTING                                                        │
│  ┌──────────────────┐                                                        │
│  │ spawn()          │                                                        │
│  │ - Start process  │                                                        │
│  │ - Return PID     │                                                        │
│  │ - Configure env  │                                                        │
│  └────────┬─────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  3. MONITOR ───────────────────────────────────────────────────────────────  │
│  Job State: EXECUTING                                                        │
│  ┌──────────────────┐                                                        │
│  │ is_alive()       │                                                        │
│  │ get_logs()       │◀─────────────────┐                                     │
│  │ wait()           │                  │ Loop                                │
│  └────────┬─────────┘                  │                                     │
│           │                            │                                     │
│           ├────────────────────────────┘                                     │
│           │                                                                  │
│           ├──────────────────────────────────────────────────────────────┐   │
│           │ (timeout/stuck)                                              │   │
│           ▼                                                              │   │
│  3b. RECOVER ──────────────────────────────────────────────────────────  │   │
│  Job State: RECOVERING                                                   │   │
│  ┌──────────────────┐                                                    │   │
│  │ recover()        │                                                    │   │
│  │ - Restart agent  │──────────────────────────────────────────────────▶ │   │
│  │ - Update inputs  │  (success: return to EXECUTING)                    │   │
│  └──────────────────┘                                                    │   │
│           │                                                              │   │
│           │ (agent completes)                                            │   │
│           ▼                                                                  │
│  4. HARVEST ───────────────────────────────────────────────────────────────  │
│  Job State: HARVESTING                                                       │
│  ┌──────────────────┐                                                        │
│  │ harvest()        │                                                        │
│  │ - Commit changes │                                                        │
│  │ - Collect files  │                                                        │
│  │ - Record results │                                                        │
│  │ - Determine exit │                                                        │
│  └────────┬─────────┘                                                        │
│           │                                                                  │
│           ├──────────────▶ SUCCESS (goal achieved)                           │
│           ├──────────────▶ APPROVAL_REQUIRED (needs sign-off)                │
│           └──────────────▶ INTERVENTION_REQUIRED (error/stuck)               │
│                                                                              │
│  5. CLEANUP ───────────────────────────────────────────────────────────────  │
│  ┌──────────────────┐                                                        │
│  │ terminate()      │                                                        │
│  │ cleanup()        │                                                        │
│  │ - Kill process   │                                                        │
│  │ - Free resources │                                                        │
│  └──────────────────┘                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. Provision Phase

The `provision()` method prepares the workspace for job execution:

```python
def provision(self, job_dir: str, workspace_dir: str) -> Dict[str, Any]:
    """
    Provision workspace for job execution.

    Responsibilities:
    - Clone git repository to isolated workspace
    - Create job-specific branch
    - Copy attachments and context files
    - Setup environment for agent execution

    Returns:
        {
            "success": True/False,
            "attachments_copied": ["file1.md", "file2.py"],
            "discovered_files": ["src/main.py"],
            "file_arguments": ["--file", "file1.md"],
            "error": None or "error message"
        }
    """
```

### 2. Spawn Phase

The `spawn()` method starts the agent process:

```python
def spawn(self, cmd: List[str], env: Dict[str, str],
          labels: Optional[Dict[str, str]] = None) -> str:
    """
    Start a new process/container with the given command.

    Responsibilities:
    - Execute agent command in isolated environment
    - Configure environment variables
    - Apply resource limits (CPU, memory, timeout)
    - Return unique process identifier

    Returns:
        Unique process_id string for tracking
    """
```

### 3. Monitor Phase

Multiple methods support process monitoring:

```python
def is_alive(self, process_id: str) -> bool:
    """Check if process is still running."""

def get_logs(self, process_id: str, tail: Optional[int] = None) -> str:
    """Get current stdout/stderr from process."""

def wait(self, process_id: str, timeout: Optional[float] = None) -> Tuple[int, str]:
    """Wait for process completion, return (exit_code, logs)."""
```

### 3b. Recover Phase

The `recover()` method attempts to restart a stuck execution:

```python
def recover(self, process_id: str, job_context: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Attempt to recover a stuck execution.

    This method is called when an execution times out or becomes stuck.
    It attempts to restart the agent with updated inputs derived from
    the current execution state.

    Args:
        process_id: The identifier of the stuck process
        job_context: Current job context including logs and state

    Returns:
        Tuple of (success, updated_inputs):
        - (True, {"new_prompt": "...", ...}) - Recovery succeeded, continue EXECUTING
        - (False, {}) - Recovery failed, transition to INTERVENTION_REQUIRED

    Notes:
        - RECOVERING state is transient; it quickly returns to EXECUTING
        - The runner may use logs to determine recovery strategy
        - Docker runner uses `docker exec` to restart sessions
        - Direct runner may spawn a new process with updated context
    """
```

Recovery strategies vary by runner:

| Runner | Recovery Strategy |
|--------|-------------------|
| Docker | `docker exec` to restart session using saved state |
| Podman | `podman exec` equivalent |
| Direct | Spawn new process with updated context from logs |
| Kubernetes | Create new pod with recovery configuration |

### 4. Harvest Phase

The `harvest()` method collects results after execution:

```python
def harvest(self, job_dir: str, workspace_dir: str,
            evidence_files: List[str], summary: str) -> Dict[str, Any]:
    """
    Harvest results from completed job execution.

    Responsibilities:
    - Commit changes to job branch
    - Collect evidence files and artifacts
    - Record execution metrics
    - Prepare results for next phase

    Returns:
        {
            "success": True/False,
            "commit_hash": "abc123...",
            "timestamp": 1234567890.0,
            "files_committed": ["file1.py", "file2.py"],
            "error": None or "error message"
        }
    """
```

### 5. Cleanup Phase

Cleanup methods handle resource deallocation:

```python
def terminate(self, process_id: str, force: bool = False) -> bool:
    """Terminate running process (SIGTERM or SIGKILL)."""

def cleanup(self, process_id: str) -> None:
    """Free resources associated with process."""
```

## Mapping CLI Commands to Runner Operations

| CLI Command | Runner Methods | Job State Transitions |
|-------------|----------------|----------------------|
| `logist job create` | (None) | → DRAFT |
| `logist job activate` | (None) | DRAFT → PENDING |
| `logist job step` | `provision()` → `spawn()` → `wait()` → `harvest()` → `cleanup()` | PENDING → PROVISIONING → EXECUTING → HARVESTING → [resting state] |
| `logist job run` | Multiple `step` cycles | Cycles through PENDING jobs |
| `logist job status` | `is_alive()`, `get_logs()` | (No transition) |
| `logist workspace cleanup` | `cleanup()` | (No transition) |
| `logist job approve` | (None) | APPROVAL_REQUIRED → SUCCESS |
| `logist job reject` | (None) | APPROVAL_REQUIRED → PENDING |
| `logist job resubmit` | (None) | INTERVENTION_REQUIRED → PENDING |

## Error Handling

Each lifecycle phase should handle errors gracefully:

```python
try:
    process_id = runner.spawn(cmd, env)
    exit_code, logs = runner.wait(process_id, timeout=3600)
except TimeoutError:
    runner.terminate(process_id, force=True)
    # Handle timeout...
except RuntimeError as e:
    # Handle spawn failure...
finally:
    runner.cleanup(process_id)
```
