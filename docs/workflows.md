# Project Workflows - Logist

This document describes development workflows specific to the Logist project.

## Core Agent Workflow

All AI agents working on this project must follow the **A-E workflow** defined in [AGENTS.md](../AGENTS.md):

- **A: Analyze** - Understand the request and declare intent
- **B: Build** - Create project plan
- **C: Code** - Implement the plan
- **D: Document** - Update documentation
- **E: Evaluate** - Verify against Definition of Done

For complete workflow documentation, see the [Agent Kernel Workflows](system-prompts/workflows/).

## Project-Specific Workflows

### Command Implementation Workflow
When adding a new CLI command:
1. Define the command in `src/logist/cli.py`
2. Implement core logic in `src/logist/job_processor.py` or separate service
3. Add the command to the demo script `scripts/test-demo.sh`
4. Update `docs/cli-reference.md`
5. Verify with `./scripts/test-demo.sh`

### Testing Workflow
We use `pytest` for unit and integration tests.
```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_core_engine.py
```

### Demo Script Workflow
The demo script provides a cumulative validation of the CLI.
```bash
# Run the demo script
./scripts/test-demo.sh
```

## See Also

- [AGENTS.md](../AGENTS.md) - Core A-E workflow
- [Definition of Done](definition-of-done.md) - Quality checklist
- [Architecture](architecture.md) - System design
- [Implementation Reference](implementation-reference.md) - Code patterns
- [Agent Kernel Workflows](system-prompts/workflows/) - Complete workflow documentation

---
Last Updated: 2026-02-01