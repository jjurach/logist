# Git Commit Message Guidelines for Agents

To ensure clear and consistent commit history, agents should adhere to the following guidelines when crafting Git commit messages:

## Format

Commit messages should follow the conventional commit format:

```
<type>: <subject>

<body>
```

### Type

The `<type>` should be one of the following to categorize the nature of the change:

-   `feat`: A new feature
-   `fix`: A bug fix
-   `docs`: Documentation only changes
-   `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc.)
-   `refactor`: A code change that neither fixes a bug nor adds a feature
-   `perf`: A code change that improves performance
-   `test`: Adding missing tests or correcting existing tests
-   `build`: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
-   `ci`: Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)
-   `chore`: Other changes that don't modify src or test files
-   `revert`: Reverts a previous commit

### Subject

The `<subject>` should be a concise, imperative statement:

-   Start with a capital letter.
-   Do not end with a period.
-   Keep it brief (under 50-72 characters).

### Body (Optional)

The `<body>` should provide more detailed contextual information about the change:

-   Use the imperative mood.
-   Explain *what* and *why* the changes were made, not *how*.
-   Wrap lines at 72 characters.
-   Do not use special pretty characters. Just use simple outline format.


## Example

```
docs: add commit message guidelines

- Create AGENTS.md to document commit message conventions for automated agents.
- Explain the conventional commit format including type, subject, and body.
- Provide a clear example for agents to follow.
```

---

## Reliable Git Commits

When crafting commit messages, especially those containing special characters (like backticks for code snippets), the shell can misinterpret them, leading to errors like `command not found`. To ensure a reliable commit process, always write your commit message to a temporary file and use the `-F` flag with `git commit`.

To prevent conflicts when multiple processes might be creating temporary files in the same directory, append the process ID (`$$`) to the filename.

### Common Issues to Avoid

- **Process ID instability**: `$$` can change between command executions, creating multiple files
- **Directory context**: File references can break when cd'ing between directories during commits
- **File cleanup race conditions**: Multiple files can exist simultaneously
- **Path resolution**: Relative paths may not work correctly across directory changes
- **Python location**: Never just assume `python` is in your path. Always `source venv/bin/activate` in the project directory which needs python.

### Recommended Pattern

```bash
# 1. Work from project root to maintain consistent paths
cd /path/to/project/root

# 2. Create a unique temporary file with your full commit message
COMMIT_MSG_FILE=".git_commit_message-$$"
git_commit_message=$(cat <<EOF
<type>: <subject>

<body>
EOF
)
echo "$git_commit_message" > "$COMMIT_MSG_FILE"

# 3. Commit using the temporary file tab (stay in project root)
git commit -F "$COMMIT_MSG_FILE"

# 4. Clean up immediately after successful commit
rm "$COMMIT_MSG_FILE"
```

### Multi-Step Commit Pattern (for complex workflows)

For complex commit workflows involving directory changes, use this pattern to avoid path resolution issues:

```bash
# Always create and reference commit message files from repository root
REPO_ROOT="/path/to/repo"
COMMIT_MSG_FILE="$REPO_ROOT/.git_commit_message-$$"

# Write the commit message
cat << 'EOF' > "$COMMIT_MSG_FILE"
feat: implement core feature

- Add functionality A
- Implement logic B
- Add tests for coverage
EOF

# Stage files (cd into subdirectories as needed)
cd "$REPO_ROOT/subproject"
git add .

# Return to root and commit from there
cd "$REPO_ROOT"
git commit -F "$COMMIT_MSG_FILE"

# Cleanup from root directory
rm "$COMMIT_MSG_FILE"
```

### Recovery Pattern (when multiple commit message files exist)

```bash
# If you end up with multiple .git_commit_message-* files, use the latest one:
COMMIT_FILE="$(ls -t .git_commit_message-* | head -n1)"
git commit -F "$COMMIT_FILE"

# Clean up all remaining commit message files:
rm .git_commit_message-*
```

### Smooth Commit Workflow

For optimal commit reliability and cleanliness, use the following proven single-command workflow:

```bash
# Always work from project root
cd /path/to/project

# Create descriptive commit message file and execute commit chain in one go
COMMIT_MSG_FILE="feat-add-feature-$$.txt" && \
echo "feat: add new feature

- Implement core functionality
- Add supporting tests
- Update documentation" > "$COMMIT_MSG_FILE" && \
git add . && \
git commit -F "$COMMIT_MSG_FILE" && \
rm "$COMMIT_MSG_FILE"
```

**Benefits:**
- Descriptive temporary files (easier to identify if cleanup fails)
- Single chained command for atomic execution
- Immediate cleanup prevents file accumulation
- Clear, conventional commit messages with bullet-point bodies
- Ensures `git` receives exactly the intended message without shell interpretation issues

This approach has proven reliable across multiple projects and avoids common pitfalls like background job conflicts or incomplete cleanup.

This method avoids direct shell interpretation of commit message content, ensures that `git` receives messages exactly as intended, prevents filename collisions, and maintains reliable path resolution across directory changes.