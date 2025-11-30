
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

### Move to Completed Directory
After completing the implementation and verification for a prompt, move the prompt file from `docs/prompts/` to `docs/prompts/completed/` before committing.

```bash
cd /home/phaedrus/AiSpace/logist
mv docs/prompts/00-task_name.md docs/prompts/completed/
```