# Common Meta-Prompt Instructions for All Logist Prompts

## Success/Failure Communication Protocol
When completing any Logist implementation task:

### Success Reporting
When the goal of the prompt has been fully met and all verification standards satisfied:
```
🎉 =============== SUCCESS =============== 🎉
🎯 All requirements completed successfully!
📋 Verification standards: ✅ ✅ ✅ ✅
🏆 Implementation complete and working as expected
```

### Failure/Error Communication
If the task cannot be completed or issues are encountered:
```
❌ =============== FAILURE ================ ❌
⚠️  Issue: [Clear description of the problem]
🔍 Investigation: [What was checked/tried]
💡 Solution needed: [What is required to proceed]
```

### Key Requirements
- **Clear banners**: Use prominent banners with emojis for immediate visibility
- **Specific details**: Explain exactly what worked or what failed
- **Actionable information**: Provide context for next steps or fixes
- **Truthful reporting**: Accurately represent completion status without exaggeration

---

Read and interpret ../../../AGENTS.md especially for git expectations.

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

### Testing and Validation
After completing implementation, validate with the demo script:
```bash
cd /home/phaedrus/AiSpace/logist
source venv/bin/activate && chmod +x test-demo.sh && ./test-demo.sh
```

**Expected Output:**
- ✅ Virtual environment activated
- ✅ Jobs directory created successfully
- ✅ Job created successfully
- ✅ Job status command executed
- ✅ Job selected successfully
- 🎉 All implemented units passed!

**If demo script fails:**
- Check venv activation (run `which python3` after activation)
- Verify package installation (`pip list | grep click`)
- Debug specific failing unit and fix implementation
- Re-run demo script until all units pass

### 3. Move to Completed Directory
Move this file from `doc/prompts/` to `doc/prompts/completed/` and prepare for commit:
```bash
cd /home/phaedrus/AiSpace/logist
mv doc/prompts/XX-task_name.md doc/prompts/completed/
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
