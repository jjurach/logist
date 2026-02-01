# Definition of Done - Logist

**Referenced from:** [AGENTS.md](../AGENTS.md)

This document defines the "Done" criteria for the Logist project. It extends the universal Agent Kernel Definition of Done with project-specific requirements.

## Agent Kernel Definition of Done

This project follows the Agent Kernel Definition of Done. **You MUST review these documents first:**

### Universal Requirements

See **[Universal Definition of Done](system-prompts/principles/definition-of-done.md)** for:
- Plan vs Reality Protocol
- Verification as Data
- Codebase State Integrity
- Agent Handoff
- Status tracking in project plans
- dev_notes/ change documentation requirements

### Python Requirements

See **[Python Definition of Done](system-prompts/languages/python/definition-of-done.md)** for:
- Python environment & dependencies (pyproject.toml, requirements.txt)
- Testing requirements (pytest)
- Code quality standards (PEP 8, type hints)
- File organization

## Project-Specific Extensions

The following requirements are specific to Logist and extend the Agent Kernel DoD:

### 1. CLI Integrity
- [ ] New commands are registered in `logist/cli.py`
- [ ] Commands handle `--jobs-dir` correctly
- [ ] Help text is provided for all commands and options
- [ ] Commands use `click` for argument/option parsing

### 2. Job State Consistency
- [ ] All state transitions are valid according to `docs/state-machine.md`
- [ ] `job_manifest.json` is updated correctly after each operation
- [ ] Metrics (cost, time, actions) are updated and thresholds enforced

### 3. Safety & Isolation
- [ ] Workspace setup uses Git isolation (dedicated branch)
- [ ] Baseline resets are handled correctly
- [ ] No changes are made to the main branch during job execution

## Pre-Commit Checklist

Before committing, verify:

**Code Quality:**
- [ ] Python type hints are present for all new functions
- [ ] Docstrings follow the project style
- [ ] `ruff check .` passes (if configured) or generic linting is clean

**Testing:**
- [ ] All unit tests pass: `pytest tests/ -v`
- [ ] Demo script passes: `./scripts/test-demo.sh`
- [ ] Integration tests for new features are added to `tests/`

**Documentation:**
- [ ] `AGENTS.md` is updated if new workflows are introduced
- [ ] `docs/architecture.md` is updated for design changes
- [ ] `docs/cli-reference.md` is updated for new commands

## See Also

- [AGENTS.md](../AGENTS.md) - Core A-E workflow
- [Universal DoD](system-prompts/principles/definition-of-done.md) - Agent Kernel universal requirements
- [Python DoD](system-prompts/languages/python/definition-of-done.md) - Agent Kernel Python requirements
- [Architecture](architecture.md) - System design
- [CLI Reference](cli-reference.md) - Command reference

---
Last Updated: 2026-02-01