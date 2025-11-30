# Logist Project TODO and Future Work

This document serves as a backlog of proposed features, documentation improvements, and open questions for the Logist project.

## 🎯 High-Level Implementation Goals

-   **Transition from Placeholders**: Replace the current `PlaceholderLogistEngine` and `PlaceholderJobManager` in `logist/cli.py` with a functional implementation that can execute jobs.
-   **Core Data Models**: Implement the primary data structures (`Job`, `Role`, `JobManifest`) using Pydantic or dataclasses to ensure type safety and serialization.
-   **State Management**: Build the logic for creating, updating, and persisting job state to the filesystem (e.g., in `~/.logist/jobs/`).
-   **`cline` Integration**: Develop the mechanism for Logist to invoke the `cline` Node.js tool, pass it the required parameters, and parse its output.
-   **Git Commit Merging**: Design and implement the workflow for taking the agent-generated commits from the isolated Git environment and merging them into the main repository, potentially via a patch file or a human-approved pull request.
-   **Implement Jobs Index**: Define the schema and create the logic for managing the central `jobs_index.json` file, including adding, removing, and locating jobs.
-   **Implement `logist job preview` command**: Display the next agent prompt without execution.
-   **Implement `--dry-run` flag for `logist job step`**: Simulate a full execution cycle with mock responses.

## 📚 Documentation Tasks

-   **Create a Tutorial**: Write a new `06_tutorial.md` that walks a user through the entire lifecycle of the `sample-job.json`.
-   **Visualize State Machine**: ✅ Add Graphviz diagram (logist/docs/state-machine-fig1.gv) showing legal transitions and agent handoffs. Generate PNG with: `dot -Tpng state-machine-fig1.gv -o state-machine-fig1.png`
-   **Formalize Schemas in Docs**: Embed the JSON Schema for the `JobManifest` and `JSON Exit Command` directly into `02_roles_and_data.md` for clarity.
-   **Implement Full Role Instructions**: Create complete schema-aware role instructions in `logist/schemas/roles/` with proper JSON protocol understanding, acceptance criteria evaluation, and action selection guidance. Current files are placeholders with TODO markers.
-   **Add Troubleshooting Guide**: Create `07_troubleshooting.md` with common issues, error resolution, and debugging tips.
-   **Document Security Model**: Add security considerations including API key management, job isolation, and safe AI agent execution.
-   **Create Contributing Guide**: Expand development setup documentation with detailed coding standards, testing protocols, and PR checklist.
-   **Add Example Jobs Library**: Provide diverse job configurations for different use cases (web dev, data analysis, content creation, etc.).
-   **Document Monitoring & Observability**: Explain how to monitor job progress, set up alerts, and analyze performance metrics.
-   **Create Deployment Guide**: Document production deployment scenarios, Docker containerization, and operational considerations.

## ❓ Open Questions & Design Decisions



-   **Configuration Strategy**: Formalize the application's configuration. The `~/.logist/` directory is mentioned; we should define its structure and adopt the XDG Base Directory Specification for cross-platform compatibility.
-   **Testing Strategy**: Define a testing strategy for the functional implementation. This will require mocking `cline` calls, filesystem interactions, and LLM API responses.
-   **Structured Logging**: Implement structured logging (e.g., using Python's `logging` module with a JSON formatter) throughout the application to provide better traceability and debugging for complex jobs.
-   **Temporary Directory Cleanup**: A strategy for cleaning up the temporary `work/<timestamp>` directories created for Git isolation will be needed eventually.