
Follow instructions in `./_meta_prompt_instructions.md` to implement this
feature and to clean up locally modified files into one or more git commits.

<objective>

- review/improve cline oneshot batch execution preparation
- introduce some rules/conventions for workspace

<details>

- During batch execution, the current project git HEAD is cloned to the
  "workspace" subdirectory of the logist job directory
- The `cline --oneshot` process should chdir to this workspace directory before
  executing.

- at initial step (or run) time during prepare/preview:
  - the workspace directory is cloned from original local checkout
  - any "attachments" subdirectory of the jobs directory should be recursively
    copied into the workspace directory during activate so that they are
    available to the running cline process.
  - all attachments are added to cline --file arguments.
  - the prompt.md file is scanned for any existing paths within workspace,
    which when present, are added to --file options.
- devise tests which place the answer to a question in attachment files, so the
  oneshot test can only provide the correct answer if the `cline --file`
  feature worked correctly. for example:
  - consider attachments: cat-alive.md and cat-dead.md, where
    only one of them is attached, and the result is examined.
  - the prompt can read, if Jon's cat is alive, then post a successful
    schemas/llm-chat-schema.json response JSON explaining that the cat is
    alive. Otherwise, post an intervention required response explaining
    that the cat is dead.  Then, test with different file arguments.

- in the preview case, all the discovered --file arguments are output along
  with the text of the initial prompt going to the oneshot process.

- move logist/logist/schemas/roles/system.md to logist/schemas/roles/system.md
  and correct any logic which depended on this weird directory structure.

- confirm python is able to locate and copy these json role source files from
  an "egg" distribution and just from a checked out source tree.  If special
  care is necessary to either to copy these files to the python install
  library path, or else, maybe a build step has to wrap these files in a python
  source file or similar.  Please try to solve this problem one way or another.

- verify from `logist job preview` that both system and the correct role files
  are added to the initial cline context.

- step (or run) should print a clear display of details from the
  llm-chat-schema.json response when this is detected.
  - step (or run) should fail if oneshot terminates, but no response json is
    detected.
  - step (or run) may need to look at `cline task view` output or maybe the
    `api_conversation_history.json` within the .cline/data/tasks to determine
    this final outcome.
  - this final outcome is required, and its JSON is written to
    latest-outcome.json of the job directory
  - the previous-outcome.json is copied to workspace/attachments and is added to
    --file arguments, along with worker-instructions.md or
    supervisor-instructions.md.
    - test if better to attach ../latest-outcome.json etc. instead of copying
      to attachments subdirectory.
    - does cline have a problem accessing files in ".." parent dir (e.g.
      "../latest-outcome.json") ? -- if not, it would be better to leave these
      files in place and not have to copy to attachments directory.

  - The supervisor and worker roles will be given different instructions for
    interpreting this previous outcome:
    - the worker will summarize what all it did and if it had any struggles.
    - the supervisor will read this and consider this against the objectives
      and acceptance of the task
    - the supervisor will place any concerns, criticisms, additional research,
      in its response
    - the worker will read this with the hope that the additional information
      will make something easier than it would have been.

- update any logist/docs which will be affected by or will want to communicate
  this context preparation.

- enhance preview output to report all of these details

- commit some easy example job directories which should hard-code a different
  llm response outcome for further testing purposes.

- prepare test situation where a job prompt expresses a condition, for example,
  "if the sum of the purple number (expressed in an attachment) and red number
  (which defaults to zero) is even, then succeed, but if it is odd, then fail
  with intervention required and in the llm response structure, ask for an odd
  red number to allow the sum to be even."

<acceptance>

- units tests, or integration tests, or demo script demonstrates
  that attached files affect the llm computation

