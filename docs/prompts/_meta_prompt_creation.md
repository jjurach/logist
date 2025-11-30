
When reviewing and populating details and acceptance criteria for a prompt,
start by searching logist/docs for elements of the prompt filename and/or the
name of the prompt to find out more about the intention of the prompt.  Examine
the previous task or any dependent tasks for details which were provided to
that task to this task under consideration.

Add any advice or information on how to implement the feature, and which source
code paths are likely to be used by the implementation.

Describe the unit tests and demo features to be added for this prompt.

Add a reference to the prompt file under consideration to follow
docs/prompts/_meta_prompt_instructions.md when executing this prompt.

Only modify the identified prompt file and any related documents in logist/docs
associated with or referenced by the prompt file.  Do not execute these
instructions.

Follow the instructions in AGENTS.md when committing these logist/docs changes. Read `../../AGENTS.md` for specific commit message guidelines.

### Move to Completed Directory and Commit
After completing the implementation and verification for a prompt, the prompt file must be moved to the `docs/prompts/completed/` directory and committed using Git with a meaningful commit message.

**Steps:**
1.  **Move the prompt file:** Move the *original* prompt file (e.g., `docs/prompts/00-task_name.md` or `docs/prompts/XX-task_name.md` where XX is the phase number) to the `docs/prompts/completed/` directory.
    ```bash
    cd /home/phaedrus/AiSpace/logist
    mv docs/prompts/XX-task_name.md docs/prompts/completed/XX-task_name.md
    ```
2.  **Stage changes:** Add the moved file and any other modified files to the Git staging area.
    ```bash
    cd /home/phaedrus/AiSpace/logist
    git add .
    ```
3.  **Commit changes:** Create a meaningful commit message following the guidelines in `AGENTS.md`. The commit message should clearly describe the completion of the prompt and the move of the file.
    ```bash
    # Example commit message:
    # feat: complete 00-task_name prompt documentation

    # - Updated the 00-task_name prompt with implementation guidance and testing details.
    # - Moved 00-task_name.md to docs/prompts/completed/.
    ```
    To ensure reliable commits, especially with special characters, use the temporary file method:
    ```bash
    COMMIT_MSG_FILE=".git_commit_message-$$"
    git_commit_message=$(cat <<EOF
    feat: complete XX-task_name prompt documentation

    - Updated the XX-task_name prompt with implementation guidance and testing details.
    - Moved XX-task_name.md to docs/prompts/completed/.
    EOF
    )
    echo "$git_commit_message" > "$COMMIT_MSG_FILE"
    git commit -F "$COMMIT_MSG_FILE"
    rm "$COMMIT_MSG_FILE"
    ```