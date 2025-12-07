## Virtual Environment Setup and Python Execution

# `timeout 30 AGENTS/prepare-python-project.sh`

python, pytest, pip, and other python-related commands have been configured to
observe/require a local ./venv directory. If a python-related command fails
with `Error: VENV interpreter not found`, then the project needs to be
initialized with `timeout 30 AGENTS/prepare-python-project.sh`

prepare-python-project.sh does the following:

- checks if the directory is a python project
- initializes $project/.checklist.md file for agent task tracking
- initializes and activates venv environment
- runs `pytest -x` and writes its output to $project/.prepare-pytest-x.out
  - indicates if at least one test is failing
- runs `get status` and save this to $project/.prepare-git-status.out
  - indicates if there are local modifications in this playground.

## The script outputs clearly the steps it takes.

- If you have run the script, and it says that all pytest tests pass, then
  there is no reason for you as the agent to execute the pytest command again.
  - When you see all "All pytests appeared to succeed", then do not run `pytest -v`
    or other pytest commands to see if tests succeed, because now you know.
  - Also, avoid `pytest -v` or save to file and only read first 10 lines of the
    file -- in order to reduce number of needless input tokens.consider
- If you have run this script, and it says there are no local modifications, then
  there is no reason for you to run any further git commands to deal with
  cleaning up commits.

## When to use the AGENTS/prepare-python-project.sh script?

- at the beginning of task execution to normalize the directory
- after you have created a new installable script
- when you need to run tests
- just before you commit your work
