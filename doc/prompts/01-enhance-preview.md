
read and interpret `_prompt_instructions.md`

- add --debug switch to logist to be more chatty about what preview and step and run are doing.

- preview should accumulate all relevant information, write it to timestamped `preview*.md` file in the job directory, and preview should always output the name of this file.  step and run should also create these timestamped `preview*.md` files within the job directory.

- this preview dump should clearly list attachments and any files being passed into the cline task

- the step and run commands should write the response from the llm to the timestamped `result*.md` file.

- the step and run commands should output cost metrics when --debug flag is set: input/output tokens, costs, elapsed time.
