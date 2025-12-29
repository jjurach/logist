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

The status of a job is stored according to the state sequence defined in `doc/04_state_machine.md`. Valid states include: DRAFT, PENDING, RUNNING, REVIEW_REQUIRED, REVIEWING, APPROVAL_REQUIRED, INTERVENTION_REQUIRED, SUCCESS, CANCELED.

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
