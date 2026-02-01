# Implementation Reference

This document provides practical implementation patterns and reference implementations for Logist.

## Key Technologies
- **Backend:** Python 3.12+
- **CLI Framework:** `argparse` (via `logist/cli.py`)
- **Job Processing:** `logist/job_processor.py`
- **Testing:** `pytest`

## Core Patterns

### Job Context Management
Use `JobContext` to manage job-specific state and files.
```python
from logist.job_context import JobContext

with JobContext(job_id) as ctx:
    # Perform work within job context
    pass
```

### State Machine Transitions
Jobs follow a strict state machine. Transitions are managed by `JobProcessor`.
See [State Machine](state-machine.md) for details.

## Testing Patterns

### Integration Tests
Integration tests should use the mock agent system to simulate LLM responses.
See `tests/test_agent_runner_integration.py` for examples.

## See Also

- [Architecture](architecture.md) - System design
- [Workflows](workflows.md) - Development workflows
- [Definition of Done](definition-of-done.md) - Quality standards

---
Last Updated: 2026-02-01
