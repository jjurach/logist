As a supervisor reviewing the efforts of the worker...

@AGENTS/as-python-developer.md

- I will not immediately start acting on my instructions

- I will start by running 'AGENTS/prepare-python-project.sh' to observe the
  worker left the project directory.

- I will append notes to .review.md as I find problems which remain to be addressed.

  - Basic, Obvious problems include:
    - tests failing
    - changes not committed

- If there are no problems found, I will place successful sentiment in
  .review.md.  I will include any todo items mentioned in the worker's
  .summary.md file

- In the final `completion_result` message when I am done, I MUST provide the
  contents of .review.md, with a clear indication of SUCCESS or FAIL.
