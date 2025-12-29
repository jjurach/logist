# Documentation and Implementation Contradictions

This document identifies contradictions between the intended architecture (as defined in `07_runner_agent_architecture.md`) and the current documentation and implementation. These issues should be addressed in future project plans.

## Terminology Contradictions

### 1. Runner vs Runtime Naming

**New Architecture**: Uses "Runner" terminology (docker runner, podman runner, direct runner)

**Current Implementation**: Uses "Runtime" as the base class (`src/logist/runtimes/base.py`)

**Files Affected**:
- `src/logist/runtimes/base.py` - Class named `Runtime`
- `src/logist/runtimes/direct.py`, `host.py`, `mock.py` - All inherit from `Runtime`
- `doc/01_architecture.md` - Refers to "runtime" in some contexts

**Resolution Required**: Decide on consistent terminology. Either:
- Rename `Runtime` class to `Runner` throughout codebase, or
- Update architecture document to use "Runtime" terminology

---

## Agent Provider Contradictions

### 2. Cline-Centric vs Agent-Agnostic Design

**New Architecture**: Describes agent provider interface supporting multiple CLI tools:
- cline-cli, aider-chat, claude-code, gemini-cli, openai-codex, mock

**Current Documentation**:
- `doc/overview.md` line 10-11: "uses **Cline CLI** as the fundamental execution primitive"
- `doc/01_architecture.md` line 6: "uses a Node.js-based tool, **`cline`**, as the fundamental execution primitive"
- `doc/02_roles_overview.md`: All examples reference Cline-specific behavior

**Files Affected**:
- `doc/overview.md` - Cline is described as THE execution primitive
- `doc/01_architecture.md` - Heavy Cline terminology throughout
- `doc/02_roles_overview.md` - Cline-specific output requirements

**Resolution Required**: Update documentation to describe Cline as ONE of the supported agent providers, not the only one.

---

## Job Attribute Contradictions

### 3. Missing "prompt" Attribute in Job Schema

**New Architecture**: Jobs MUST have a `prompt` attribute containing execution text

**Current Implementation**: Job manifest (`doc/01_architecture.md` lines 21-31) shows:
- `job_id`, `description`, `status`, `current_phase`, `metrics`, `history`
- No explicit `prompt` field defined

**Files Affected**:
- Job manifest schema/validation
- `doc/01_architecture.md` - Job manifest structure
- Job creation logic

**Resolution Required**: Add `prompt` as a required field in job manifest schema.

### 4. Missing "gitSourceRepo" Attribute

**New Architecture**: Jobs should have `gitSourceRepo` attribute for source location

**Current Implementation**: Workspace setup assumes current directory is within a git repo:
- `doc/workspace.md` describes setup from current git working directory
- No mechanism for specifying external git URL

**Files Affected**:
- `src/logist/workspace_utils.py` - Assumes local git repo
- Job manifest schema
- CLI job creation commands

**Resolution Required**: Add `gitSourceRepo` attribute and support for external git URLs.

---

## Configuration Contradictions

### 5. Missing logist.yml Configuration File

**New Architecture**: Describes `logist.yml` for project-level configuration of default runner/agent

**Current Implementation**: No `logist.yml` exists. Current configuration uses:
- `jobs_index.json` - For job registry
- `job_manifest.json` - Per-job configuration
- No project-level defaults file

**Files Affected**:
- Configuration loading logic
- CLI initialization
- Documentation

**Resolution Required**: Implement `logist.yml` configuration file support.

---

## Responsibility Contradictions

### 6. Git Operations Ownership

**New Architecture**: Runner is responsible for:
- Workspace provisioning (git clone, branch setup)
- Results harvesting (committing changes)
- Methods: `provision()`, `harvest()`

**Current Implementation**:
- `workspace_utils.py` handles all git operations independently
- `Runtime.provision()` and `Runtime.harvest()` exist but raise `NotImplementedError`
- Git operations are NOT delegated to runners

**Files Affected**:
- `src/logist/workspace_utils.py` - Contains git logic
- `src/logist/runtimes/base.py` - Has stub methods
- `src/logist/core_engine.py` - Calls workspace_utils directly

**Resolution Required**: Move git operations from workspace_utils into runner implementations, or clarify architecture to explain current separation.

---

## Workflow Contradictions

### 7. Worker/Supervisor Model vs Runner/Agent Model

**New Architecture**: Focuses on Runner (environment) + Agent (CLI tool) separation

**Current Documentation**: Heavily emphasizes Worker/Supervisor role model:
- `doc/01_architecture.md`: Three-phase loop (Worker -> Supervisor -> Steward)
- `doc/02_roles_overview.md`: Worker and Supervisor role definitions
- `doc/04_state_machine.md`: States tied to Worker/Supervisor execution

**Clarification Needed**: These are orthogonal concepts:
- Runner/Agent = Infrastructure layer (HOW to run)
- Worker/Supervisor = Role layer (WHAT roles exist)

**Resolution Required**: Documentation should clarify that Runner/Agent is infrastructure; Worker/Supervisor are logical roles that USE the infrastructure.

---

## State Machine Contradictions

### 8. DRAFT State and Job Activation

**New Architecture**: Mentions job creation with prompt attribute

**Current State Machine** (`doc/04_state_machine.md`):
- DRAFT state exists for configuration before activation
- `logist job activate` command transitions DRAFT -> PENDING

**Alignment Check**: These are consistent but documentation should clarify:
- Job creation creates DRAFT state
- `prompt` attribute set during DRAFT phase
- Activation validates required attributes before transitioning

---

## Runner Backend List

### 9. Supported Runners Mismatch

**New Architecture**: Lists supported runner backends as:
- podman, docker, kubernetes, direct

**Current Implementation**: Has runtimes:
- `base.py` (abstract)
- `direct.py`
- `host.py`
- `mock.py`

**Missing**:
- docker runtime
- podman runtime
- kubernetes runtime

**Resolution Required**: Implement missing runner backends or document them as planned/future.

---

## Priority Resolution Order

1. **High Priority** (Blocking new features):
   - Add `prompt` attribute to job schema (#3)
   - Add `gitSourceRepo` attribute (#4)
   - Implement `logist.yml` configuration (#5)

2. **Medium Priority** (Architecture alignment):
   - Resolve Runner vs Runtime terminology (#1)
   - Move git operations to runners (#6)
   - Implement docker/podman runners (#9)

3. **Low Priority** (Documentation cleanup):
   - Update Cline-centric documentation (#2)
   - Clarify Worker/Supervisor vs Runner/Agent (#7)
   - Verify DRAFT state workflow (#8)
