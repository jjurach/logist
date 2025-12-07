As an expert coder who is calculating and commiting some change...

@AGENTS/as-python-developer.md

In addition to the tasks presented in your prompt, you will need to add these
items to the end of your .checklist.md

[ ] commit your code changes
[ ] scan through doc for relevant keywords, then describe/summarize any changes
    you made with your commit files in this doc directory. If there was a potential
    conflict or something about the requirements you couldn't complete, add items
    to doc/todo.md to reflect this.

[ ] commit your doc changes

[ ] create .summary.json to summarize these changes you made in JSON format. be sure to include
    todo items for subtests which could not be completed.

[ ] run AGENTS/prepare-python-project.sh one more time in order to:
    - see that all tests succeed
    - see that all files are committed

In the final completion_result message, you must print the contents of .summary.json in JSON format
