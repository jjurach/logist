# Project Plan: Clarify Logist Job Attributes and Architecture

**Date:** 2025-12-28 15:30:39
**Complexity:** Medium
**Status:** Completed

## Objective

Define fundamental concepts around runner/agent architecture and job attributes. This project plan focuses on documenting intended architecture and identifying contradictions with current implementation. Future project plans will address the implementation fixes.

## Background

The logist architecture separates execution behaviors behind two interfaces:
- **Runner interface**: Capable of running podman, docker, kubernetes, or direct commands
- **Agent provider interface**: Capable of interacting with cline, aider, claude, gemini, codex to execute one-shot non-interactive coding sessions

A `logist.yml` configuration file defines default runner and agent, but jobs can override these defaults via attributes in the job manifest.

## Completed Tasks

### 1. Write Fundamental Concepts Document
- **Status:** Completed
- **Output:** `doc/07_runner_agent_architecture.md`
- **Content:**
  - Architectural overview with Runner/Agent separation diagram
  - Non-interactive execution principle
  - Configuration hierarchy (logist.yml -> job manifest -> CLI flags)
  - Runner interface responsibilities (Docker, Podman, Kubernetes, Direct)
  - Agent provider responsibilities (cline-cli, aider-chat, claude-code, etc.)
  - Required job attributes (status, prompt, gitSourceRepo)
  - Optional job attributes (runner/agent overrides)

### 2. Scan Documentation for Contradictions
- **Status:** Completed
- **Files Reviewed:**
  - `doc/01_architecture.md`
  - `doc/02_roles_overview.md`
  - `doc/04_state_machine.md`
  - `doc/overview.md`
  - `doc/workspace.md`
  - `src/logist/runtimes/base.py`
  - `src/logist/agents/base.py`

### 3. Document Contradictions
- **Status:** Completed
- **Output:** `doc/problems.md`
- **Issues Identified:**
  1. Runner vs Runtime terminology mismatch
  2. Cline-centric vs agent-agnostic documentation
  3. Missing `prompt` attribute in job schema
  4. Missing `gitSourceRepo` attribute
  5. Missing `logist.yml` configuration file support
  6. Git operations ownership (workspace_utils vs runners)
  7. Worker/Supervisor vs Runner/Agent model clarification
  8. DRAFT state and job activation workflow
  9. Missing runner backends (docker, podman, kubernetes)

## Future Implementation Tasks

These tasks should be addressed in subsequent project plans:

### Phase 1: Core Attribute Implementation (High Priority)

#### Task 1.1: Add prompt Attribute to Job Schema
- Modify job manifest schema to require `prompt` field
- Update job creation to accept `--prompt` and `--file` flags
- Validate prompt exists before job activation
- **Files to modify:** Job schema, CLI commands, job creation logic

#### Task 1.2: Add gitSourceRepo Attribute
- Add `gitSourceRepo` field to job manifest
- Implement auto-detection of git root from current directory
- Support explicit `--gitSourceRepo` CLI flag
- Fail gracefully with error message if git repo not found
- **Files to modify:** Job schema, CLI commands, workspace_utils

#### Task 1.3: Implement logist.yml Configuration
- Create configuration file parser for `logist.yml`
- Define schema for runner/agent defaults
- Implement configuration hierarchy (defaults -> job -> CLI)
- **Files to create:** `src/logist/config.py`
- **Files to modify:** CLI initialization, core engine

### Phase 2: Architecture Alignment (Medium Priority)

#### Task 2.1: Resolve Runner/Runtime Terminology
- Decide on canonical term (recommend: keep "Runtime" in code, use "Runner" in docs)
- Update either code OR documentation for consistency
- **Files affected:** Potentially all runtime files or all documentation

#### Task 2.2: Move Git Operations to Runners
- Implement `provision()` in runtime subclasses
- Implement `harvest()` in runtime subclasses
- Migrate logic from workspace_utils to appropriate runners
- Update core_engine to use runner methods
- **Files to modify:** All runtime implementations, core_engine.py

#### Task 2.3: Implement Missing Runner Backends
- Docker runtime (using docker CLI)
- Podman runtime (using podman CLI)
- Kubernetes runtime (using kubectl or k8s API)
- **Files to create:** `src/logist/runtimes/docker.py`, `podman.py`, `kubernetes.py`

### Phase 3: Documentation Cleanup (Low Priority)

#### Task 3.1: Update Cline-Centric Documentation
- Modify `doc/overview.md` to describe multiple agent providers
- Update `doc/01_architecture.md` to reflect agent abstraction
- Revise role documentation to be agent-agnostic
- **Files to modify:** Multiple documentation files

#### Task 3.2: Clarify Architecture Layers
- Add section explaining Runner/Agent (infrastructure) vs Worker/Supervisor (roles)
- Update diagrams to show both layers
- **Files to modify:** `doc/01_architecture.md`

## Success Criteria

- [x] `doc/07_runner_agent_architecture.md` created with complete architectural description
- [x] `doc/problems.md` created documenting all contradictions
- [ ] Future: Job schema includes required `prompt` attribute
- [ ] Future: Job schema includes optional `gitSourceRepo` attribute
- [ ] Future: `logist.yml` configuration file support implemented
- [ ] Future: All contradictions in `doc/problems.md` resolved

## Dependencies

- None for documentation tasks (completed)
- Future implementation tasks depend on this documentation being approved

## Risk Assessment

- **Low Risk:** Documentation-only changes do not affect runtime behavior
- **Medium Risk:** Future schema changes may require migration of existing jobs
- **Medium Risk:** Moving git operations to runners requires careful testing

## Notes

This project plan is primarily about defining what we want. The `doc/problems.md` file serves as a roadmap for future implementation work. Each contradiction should be addressed in a focused project plan that tackles related issues together.

The architecture separates concerns clearly:
- **Runners** handle WHERE code runs (container, host, cloud)
- **Agents** handle WHAT tool runs (cline, aider, claude-code)
- **Roles** handle WHO is responsible (Worker, Supervisor)

These three dimensions are orthogonal and can be mixed independently.
