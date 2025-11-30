# Common Meta-Prompt Instructions for All Logist Prompts

## Git Status and Commit Protocol
After completing the implementation for any Logist prompt:

### 1. Check Status
Run `cd /home/phaedrus/AiSpace/logist && git status` to see all changes
- Review modified files, added files, and untracked files
- Ensure no unintended changes are included

### 2. Document Changes
Update this prompt file to reflect completed deliverables and any deviations:
- Mark verification standards as completed ✅
- Update deliverables section with actual files created
- Document any implementation decisions or design changes
- Note any prerequisites that proved incomplete or incorrect
- Document the completion date at the bottom of the file

### 3. Move to Completed Directory
Move this file from `docs/prompts/` to `docs/completed/` and prepare for commit:
```bash
cd /home/phaedrus/AiSpace/logist
mv docs/prompts/XX-task_name.md docs/completed/
```

### 4. Stage and Commit Changes
Use conventional commit format following AGENTS.md guidelines:
```bash
cd /home/phaedrus/AiSpace/logist
git add .

# Use appropriate commit type and message:
git commit -m "feat: implement [task name]

- Add [function_name]() and register with CLI
- [Brief summary of core functionality implemented]
- [Additional technical details]
"
```

### Commit Type Selection (from AGENTS.md):
- `feat`: New feature implementation
- `fix`: Bug fix or correction
- `docs`: Documentation changes
- `style`: Code style/formatting
- `refactor`: Code restructuring without behavior change
- `test`: Testing infrastructure
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Maintenance tasks

### Commit Message Format:
```
<type>: <concise imperative subject>

- <bullet point detailing what changed>
- <additional technical details>
- <mention of breaking changes if any>
```

### Important Notes:
- Subject should be imperative and under 72 characters
- Body should explain what changed and why, not how
- Move prompt to `completed/` directory as part of commit
- Ensure clean commit history following project conventions

---

*This meta-prompt file provides consistent instructions for all Logist implementation tasks. Reference this file from each prompt file instead of duplicating instructions.*