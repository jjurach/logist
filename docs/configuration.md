# Logist Configuration

This document describes the configuration options available in Logist, including project-level configuration via `logist.yml` and job-level overrides.

## Configuration Hierarchy

Logist uses a layered configuration hierarchy where each layer can override the previous:

1. **Project Configuration (`logist.yml`)** - Base defaults for the project
2. **Job Manifest** - Job-specific overrides stored in `job_manifest.json`
3. **CLI Flags** - Runtime overrides via command-line options

## Project Configuration: `logist.yml`

Place a `logist.yml` file in your project root to define default runner and agent settings.

### Minimal Configuration

```yaml
# logist.yml - Minimal configuration
runner: direct          # Default runner (podman, docker, kubernetes, direct)
agent: mock             # Default agent provider for testing
```

### Full Configuration Example

```yaml
# logist.yml - Full configuration example
runner: docker          # Default runner
agent: claude-code      # Default agent provider

# Runner-specific configuration
runners:
  docker:
    image: logist/agent-runner:latest
    network: host
    timeout: 3600
  podman:
    image: logist/agent-runner:latest
    rootless: true
  kubernetes:
    namespace: logist-jobs
    service_account: logist-runner
  direct:
    timeout: 3600
    working_dir: ./workspace

# Agent-specific configuration
agents:
  cline-cli:
    model: grok-code-fast-1
    temperature: 0.7
  aider-chat:
    model: gpt-4
    auto_commits: false
  claude-code:
    model: claude-sonnet-4-20250514
    dangerously_skip_permissions: true
  mock:
    mode: success  # success, hang, api_error, context_full, auth_error

# Resource limits
limits:
  cost_threshold: 10.00        # Max spend per job (USD)
  time_threshold_minutes: 60   # Max execution time per job
  max_iterations: 50           # Max steps before requiring intervention
```

## Runner Configuration

### Available Runners

| Runner | Description |
|--------|-------------|
| `direct` | Execute commands directly on the host system |
| `docker` | Run agents in Docker containers |
| `podman` | Run agents in Podman containers (rootless supported) |
| `kubernetes` | Run agents as Kubernetes pods/jobs |

### Direct Runner

The `direct` runner executes agent commands directly on the host system. This is the simplest configuration and is ideal for development and testing.

```yaml
runner: direct
runners:
  direct:
    timeout: 3600          # Command timeout in seconds
    working_dir: ./workspace  # Working directory for execution
```

### Docker Runner

The Docker runner executes agents in isolated Docker containers.

```yaml
runner: docker
runners:
  docker:
    image: logist/agent-runner:latest
    network: host          # Network mode
    volumes:               # Additional volume mounts
      - /path/to/data:/data:ro
    environment:           # Additional environment variables
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
```

### Podman Runner

The Podman runner provides rootless container execution.

```yaml
runner: podman
runners:
  podman:
    image: logist/agent-runner:latest
    rootless: true
    userns: keep-id
```

## Agent Configuration

### Available Agent Providers

| Agent | Description |
|-------|-------------|
| `cline-cli` | Cline CLI for one-shot coding tasks |
| `aider-chat` | Aider for AI pair programming |
| `claude-code` | Claude Code CLI for direct Claude interaction |
| `gemini-cli` | Google Gemini CLI tool |
| `mock` | Mock agent for testing and development |

### Mock Agent (Testing)

The mock agent simulates agent behavior for testing without incurring API costs.

```yaml
agent: mock
agents:
  mock:
    mode: success  # Simulation mode
```

**Available modes:**
- `success` - Simulates successful task completion
- `hang` - Simulates a hanging process (for timeout testing)
- `api_error` - Simulates API rate limiting (429 error)
- `context_full` - Simulates token limit exceeded
- `auth_error` - Simulates authentication failure

## Testing Configuration

For testing, use the `direct` runner with the `mock` agent:

```yaml
# logist.yml - Testing configuration
runner: direct
agent: mock

runners:
  direct:
    timeout: 30  # Short timeout for tests

agents:
  mock:
    mode: success
```

This configuration:
- Executes commands directly without container overhead
- Uses mock responses instead of real API calls
- Provides fast, deterministic test execution
- Avoids API costs during development

## Job-Level Overrides

Jobs can override project defaults via the job manifest or CLI:

### Via CLI

```bash
# Override runner and agent for a specific job
logist job create --runner podman --agent aider-chat --prompt "Implement feature X"

# Create job with specific git source
logist job create --git-source-repo /path/to/repo --prompt "Fix bug Y"
```

### Via Job Manifest

```json
{
  "job_id": "my-custom-job",
  "runner": "podman",
  "agent": "aider-chat",
  "prompt": "Implement the new feature",
  "gitSourceRepo": "/path/to/source"
}
```

## Environment Variables

Logist respects the following environment variables:

| Variable | Description |
|----------|-------------|
| `LOGIST_JOBS_DIR` | Default jobs directory |
| `LOGIST_CONFIG` | Path to logist.yml configuration |
| `ANTHROPIC_API_KEY` | API key for Claude-based agents |
| `OPENAI_API_KEY` | API key for OpenAI-based agents |

## Configuration Validation

Logist validates configuration at startup and provides helpful error messages for invalid settings:

```bash
# Validate configuration
logist config validate

# Show effective configuration
logist config show
```
