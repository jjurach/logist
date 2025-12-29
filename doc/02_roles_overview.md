# Roles Overview

## Programmable Roles System

### Role Manifest Architecture
The **Role Manifest** system enables flexible AI agent specialization within Logist's orchestration framework. Roles provide programmable templates for different aspects of job execution, allowing customized behavior patterns and expertise areas. Each role encapsulates specific skills, constraints, and decision-making frameworks tailored to distinct workflow phases.

### Role Definition Structure
Every role requires exactly four mandatory attributes that define its complete operational profile:

- **`name`**: Unique identifier for role-based specialization
- **`description`**: Human-readable explanation of role expertise and responsibilities
- **`instructions`**: Complete meta-prompt defining behavior, constraints, and decision-making framework
- **`llm_model`**: Specific LLM model identifier for consistent role behavior

### Core Role Types

```json
{
  "Worker": {
    "name": "Worker",
    "description": "Expert software development and implementation agent specializing in code generation, debugging, and technical problem-solving",
    "instructions": "You are an expert software engineer...",
    "llm_model": "grok-code-fast-1"
  },
  "Supervisor": {
    "name": "Supervisor",
    "description": "Quality assurance and oversight specialist focused on reviewing outputs, identifying issues, and providing constructive feedback",
    "instructions": "You are a senior technical reviewer...",
    "llm_model": "gemini-2.5-flash"
  }
}
```

### Role Specialization Benefits
- **Expertise Isolation**: Different models excel at different tasks (creation vs. evaluation)
- **Behavioral Consistency**: Configurable behavior patterns across job types
- **Workflow Flexibility**: Mix and match roles for different project needs
- **Quality Assurance**: Specialized roles for specific verification tasks

## Structured Communication

### JSON Exit Command Protocol
Every agent execution must terminate with a machine-readable **JSON Exit Command** that informs the Logist how to proceed. This standardized format, formally defined in `schemas/llm-chat-schema.json`, ensures reliable automation. Logist initiates the interaction by sending a `request` object, and the agent must return a `response` object compliant with this schema.

### Required JSON Structure
```json
{
  "action": "COMPLETED|STUCK|RETRY",
  "evidence_files": ["path/to/file1", "path/to/file2"],
  "summary_for_supervisor": "Brief description of work completed and current state"
}
```

### Field Specifications

#### action (Required)
- **Type**: String (enumerated)
- **Allowed Values**:
  - `"COMPLETED"`: Job phase successfully finished, ready for next phase
  - `"STUCK"`: Unable to proceed, requires human clarification
  - `"RETRY"`: Current approach unsuccessful, suggest restarting with different parameters
- **Purpose**: Controls Logist's flow logic and determines next execution step

#### evidence_files (Required)
- **Type**: Array of strings
- **Format**: Relative paths from job working directory
- **Purpose**: Lists all files modified, created, or analyzed during execution
- **Usage**: Logist uses this list to track job artifacts and prepare context for subsequent agents

#### summary_for_supervisor (Required)
- **Type**: String
- **Purpose**: Concise explanation for the next agent about what was accomplished and current project state
- **Length**: 2-3 sentences maximum
- **Tone**: Professional, factual, focused on outcomes and decisions

### Agent Output Requirements
All agents must:
1. Perform their specialized work using the configured AI coding agent (Cline, Aider, Claude Code, etc.)
2. Generate any required output files in the job directory
3. Output exactly one valid JSON exit command
4. Not include any text outside the JSON structure

### Example Output
```json
{
  "action": "COMPLETED",
  "evidence_files": ["src/main.py", "tests/test_main.py", "docs/spec.md"],
  "summary_for_supervisor": "Successfully implemented the main application structure with comprehensive tests and updated documentation. The implementation follows best practices and includes error handling for edge cases."
}
```

## Job History Tracking

### History Archive File (`jobHistory.json`)

Each job directory maintains a **`jobHistory.json`** file that captures the complete audit trail of all `--oneshot` interactions. This persistent archive serves dual purposes: debugging failed executions and providing reusable fixtures for automated testing.

#### History Entry Structure
```json
{
  "interactions": [
    {
      "sequence": 1,
      "timestamp": "2025-01-29T14:30:45Z",
      "state_before": "PENDING",
      "workspace_path": "${JOB_DIR}/workspace",
      "request": {
        "prompt": "Full constructed prompt sent to LLM...",
        "files_context": ["evidence1.md", "config.json", "source.py"],
        "metadata": {
          "role": "Worker",
          "phase": "PENDING",
          "model": "grok-code-fast-1",
          "temperature": 0.7
        }
      },
      "response": {
        "status": "SUCCESS",
        "actions": ["COMPLETED"],
        "evidence_files": ["results.py", "tests/test_results.py"],
        "summary_for_supervisor": "Successfully implemented feature X with test coverage",
        "raw_response": "{ \"action\": \"COMPLETED\", \"evidence_files\": [...], ... }"
      }
    }
  ]
}
```

#### History Entry Fields

##### sequence (Required)
- **Type**: Integer
- **Purpose**: Chronological ordering of interactions
- **Usage**: Enables resumption from specific points

##### timestamp (Required)
- **Type**: ISO 8601 string
- **Purpose**: Precise timing for debugging and analysis
- **Format**: `YYYY-MM-DDTHH:MM:SSZ`

##### state_before (Required)
- **Type**: String (JobState enum)
- **Purpose**: Job state prior to this interaction
- **Values**: `PENDING`, `RUNNING`, `REVIEWING`, `REVIEW_REQUIRED`, etc.

##### workspace_path (Required)
- **Type**: String
- **Purpose**: Absolute path to isolated workspace for this interaction
- **Usage**: Enables verification of workspace state with archived context

##### request.prompt (Required)
- **Type**: String
- **Purpose**: Complete prompt text sent to LLM
- **Usage**: Debugging prompt construction and agent decision-making

##### request.files_context (Required)
- **Type**: Array of strings
- **Purpose**: Files included in LLM context during this interaction
- **Format**: Relative paths from workspace root

##### request.metadata (Optional)
- **Type**: Object
- **Purpose**: Additional parameters (model, temperature, role assignments)
- **Usage**: Reproduce exact conditions for testing

##### response.* (Required)
- **Type**: Complete --oneshot response object
- **Purpose**: Full record of agent execution outcome
- **Usage**: `job poststep` replay for testing, state transition analysis

### Usage Contexts

#### Debugging Failed Jobs
- **Historical Context**: Compare prompts across failed interaction sequences
- **State Transitions**: Trace how responses led to different outcomes
- **Workspace Verification**: Confirm file context matches archived state

#### Automated Testing
- **Fixture Library**: Extract `response.raw_response` for `job poststep` testing
- **Regression Prevention**: Ensure state transition logic remains consistent
- **Integration Testing**: Replay entire interaction sequences

#### Machine Learning & Analytics
- **Response Pattern Analysis**: Study agent decision-making trends
- **Performance Tracking**: Monitor success rates by prompt complexity
- **Behavior Auditing**: Create datasets for agent behavior analysis

### Maintenance Guidelines

- **Automatic Recording**: Every `job step` appends new interaction to history
- **Disk Management**: Consider rotation/compression for long-running jobs
- **Privacy Consideration**: Contains full prompts and responses - secure accordingly
- **Non interference**: History reading should never affect job execution state

## Logist Flow Control Integration

The Logist reads and validates each JSON exit command to determine next actions:
- **COMPLETED**: Advances workflow and prepares next phase
- **STUCK**: Pauses execution for Steward review
- **RETRY**: Automatically restarts current phase with fresh parameters

Invalid JSON or missing required fields are treated as STUCK status.