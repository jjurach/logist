# Development Rules for Logist Project

> **Note for AI Agents:** This document contains MANDATORY instructions. Follow ALL rules precisely. When in doubt, ask the developer for clarification rather than making assumptions.

## Customization Guide

Before using this document, replace the following placeholders with your project-specific values:

- `Logist Project` - Your project's name (appears in title and throughout document)
- `logist/doc/project-status.md` - Your project status/punchlist file name
- `python` - Primary programming language (e.g., TypeScript, Python, Java)
- `Python` - Backend runtime (e.g., Node.js, Python, Java)

## AI Development Guidelines

This document establishes the rules and procedures for AI-assisted development on the Logist Project. These rules ensure consistent, trackable, and well-documented development practices.

**CRITICAL FOR AI AGENTS:** Follow these rules precisely. When in doubt, ask the developer for clarification rather than making assumptions.

---

## Decision Tree: When to Create a Project Plan

**AI AGENT INSTRUCTIONS:** Use this decision tree for EVERY user request:

```
User Request Received
    │
    ├─ Is it a question or information request only?
    │   ├─ YES → Answer directly, no plan needed
    │   └─ NO → Continue to next step
    │
    ├─ Does it modify existing code?
    │   ├─ YES → Create project plan (REQUIRED)
    │   └─ NO → Continue to next step
    │
    ├─ Does it create new files/features?
    │   ├─ YES → Create project plan (REQUIRED)
    │   └─ NO → Continue to next step
    │
    ├─ Does it modify database schema?
    │   ├─ YES → Create project plan (REQUIRED)
    │   └─ NO → Continue to next step
    │
    └─ Is it a trivial change? (see Trivial Changes section)
        ├─ YES → Use simplified change documentation only
        └─ NO → Create project plan (REQUIRED)
```

**If unsure, default to creating a project plan.**

---

## Trivial Changes Exception

**AI AGENT INSTRUCTIONS:** The following changes may skip the full project plan process but still require simplified change documentation:

### Qualifying Trivial Changes:
1. **Typo/Spelling Corrections**
   - Single word corrections
   - No functional impact
   - Example: Fixing "deprication" → "depreciation" in comments

2. **Formatting-Only Changes**
   - Whitespace adjustments
   - Indentation fixes
   - Line break adjustments
   - No code logic changes

3. **Single-Line Bug Fixes**
   - Obvious syntax errors
   - Missing semicolons, brackets, etc.
   - No dependencies affected
   - No architectural changes

4. **Documentation-Only Updates**
   - README updates
   - Comment improvements
   - No code changes

### Simplified Change Documentation for Trivial Changes:
```markdown
# Trivial Change: [Brief Description]

**Date:** YYYY-MM-DD HH:MM:SS  
**Type:** Trivial [Typo/Formatting/Bug Fix/Documentation]  
**Status:** Completed

## Change Made
Brief description of the trivial change.

## Files Modified
- `path/to/file.ext` - [Description]

## Notes
Any relevant context.
```

**AI AGENT INSTRUCTIONS:** For trivial changes, create the simplified documentation AFTER making the change, not before.

---

## Core Development Principles

### 1. **Documentation First**
**AI AGENT INSTRUCTIONS:** 
- **ALL changes must be documented** before implementation (except trivial changes - see above)
- Create a new markdown file for each change with detailed descriptions
- Track what files were modified and what changes were made
- Include before/after code snippets when applicable
- Use the exact template provided in this document

### 2. **Project Planning Required**
**AI AGENT INSTRUCTIONS:**
- **NO code changes without a project plan** (unless trivial - see exceptions above)
- Create a new detailed project plan for each requested change
- Include step-by-step implementation approach
- Define success criteria and testing requirements
- **WAIT for developer approval** before executing any plan
- Update project plan showing completed steps once complete

**What Counts as "Approval":**
- Explicit words: "approved", "proceed", "go ahead", "yes", "ok", "start"
- Implicit approval: User says "begin", "start", "implement"
- NOT approval: User asking questions, requesting clarification, or reviewing the plan

**AI AGENT INSTRUCTIONS:** If the user responds to your project plan with anything other than explicit approval, DO NOT proceed. Wait for clear approval.

### 3. **Change Tracking System**
**AI AGENT INSTRUCTIONS:**
- Store all change documentation in `dev_notes/` directory
- Use timestamp format: `YYYY-MM-DD_HH-MM-SS_description.md` (24-hour format, local timezone)
- Use descriptive, kebab-case filenames
- Maintain chronological order of changes
- Link related changes and project plans

**Timestamp Format Rules:**
- Format: `YYYY-MM-DD_HH-MM-SS`
- Use 24-hour time format
- Use local timezone
- Example: `2024-01-15_14-30-00`
- Get current timestamp using: `date +"%Y-%m-%d_%H-%M-%S"` (Unix) or equivalent

---

## File Organization

### Development Notes Structure
**AI AGENT INSTRUCTIONS:** Create this structure if it doesn't exist.

```
dev_notes/
├── changes/
│   ├── 2024-01-15_14-30-00_phase6-analytics-implementation.md
│   ├── 2024-01-15_15-45-00_dashboard-enhancement.md
│   └── ...
├── project_plans/
│   ├── 2024-01-15_14-25-00_analytics-dashboard-plan.md
│   ├── 2024-01-15_15-40-00_reporting-system-plan.md
│   └── ...
└── README.md
```

**AI AGENT INSTRUCTIONS:** 
- Create `dev_notes/` directory structure if it doesn't exist
- Use exact timestamp format: `YYYY-MM-DD_HH-MM-SS` (24-hour format)
- Use descriptive, kebab-case filenames

---

## Documentation Requirements

### Change Documentation Template
**AI AGENT INSTRUCTIONS:** Use this template for ALL non-trivial changes. Fill in ALL sections.

```markdown
# Change: [Brief Description]

**Date:** YYYY-MM-DD HH:MM:SS  
**Type:** [Feature/Enhancement/Bug Fix/Refactor]  
**Priority:** [High/Medium/Low]  
**Status:** [Planned/In Progress/Completed/Cancelled]  
**Related Project Plan:** `dev_notes/project_plans/YYYY-MM-DD_HH-MM-SS_project-name.md`

## Overview
Brief description of what was changed and why.

## Files Modified
- `path/to/file1.ts` - Description of changes
- `path/to/file2.tsx` - Description of changes

## Code Changes
### Before
```typescript
// Original code
```

### After
```typescript
// Modified code
```

## Testing
- [ ] Unit tests updated
- [ ] Integration tests updated
- [ ] Manual testing completed

## Impact Assessment
- Breaking changes: [Yes/No]
- Dependencies affected: [List]
- Performance impact: [None/Minor/Major]

## Notes
Additional context, decisions made, or future considerations.
```

### Project Plan Template
**AI AGENT INSTRUCTIONS:** Use this template for ALL project plans. Be thorough and specific.

```markdown
# Project Plan: [Project Name]

**Date:** YYYY-MM-DD HH:MM:SS  
**Estimated Duration:** [X hours/days]  
**Complexity:** [Low/Medium/High]  
**Status:** [Draft/Approved/In Progress/Completed/Cancelled]

## Objective
Clear statement of what needs to be accomplished.

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

## Implementation Steps
1. **Step 1:** [Description]
   - Files to modify: [List]
   - Files to create: [List]
   - Dependencies: [List]
   - Estimated time: [X hours]
   - Status: [ ] Not Started / [ ] In Progress / [ ] Completed

2. **Step 2:** [Description]
   - Files to modify: [List]
   - Files to create: [List]
   - Dependencies: [List]
   - Estimated time: [X hours]
   - Status: [ ] Not Started / [ ] In Progress / [ ] Completed

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Testing Strategy
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing
- [ ] Performance testing

## Risk Assessment
- **High Risk:** [Description and mitigation]
- **Medium Risk:** [Description and mitigation]
- **Low Risk:** [Description and mitigation]

## Dependencies
- [ ] Dependency 1
- [ ] Dependency 2
- [ ] Dependency 3

## Database Changes (if applicable)
- [ ] Schema changes required
- [ ] Migration script needed
- [ ] Data migration required

## API Changes (if applicable)
- [ ] New endpoints
- [ ] Modified endpoints
- [ ] Deprecated endpoints
- [ ] Documentation updates needed

## Notes
Additional context, assumptions, or considerations.
```

---

## Development Workflow

**AI AGENT INSTRUCTIONS:** Follow this workflow EXACTLY for every non-trivial request.

### Step 1: Request Analysis
**AI AGENT ACTIONS:**
1. Read and understand the user's request completely
2. Identify all components that need modification
3. Check for existing related code/files
4. Consider dependencies and potential impacts
5. Ask clarifying questions if ANY ambiguity exists

**AI AGENT CHECKLIST:**
- [ ] Request fully understood
- [ ] All affected components identified
- [ ] Dependencies mapped
- [ ] Potential impacts assessed
- [ ] Clarifying questions asked (if needed)

### Step 2: Project Plan Creation
**AI AGENT ACTIONS:**
1. Create a detailed project plan using the template above
2. Save to `dev_notes/project_plans/` with timestamp
3. Include ALL implementation steps with file lists
4. Define clear success criteria
5. **STOP - DO NOT EXECUTE ANY CODE**

**AI AGENT CHECKLIST:**
- [ ] Project plan created
- [ ] All steps detailed
- [ ] Files to modify/create listed
- [ ] Success criteria defined
- [ ] Plan saved with timestamp
- [ ] **NO CODE CHANGES MADE**

### Step 3: Developer Approval
**AI AGENT ACTIONS:**
1. Present the project plan to the developer
2. Wait for explicit approval (look for words like "approved", "proceed", "go ahead", "yes")
3. If feedback received, update the plan
4. **DO NOT PROCEED** until explicit approval

**AI AGENT CHECKLIST:**
- [ ] Plan presented to developer
- [ ] Explicit approval received
- [ ] Plan updated if feedback provided
- [ ] **READY TO PROCEED** flag set

### Step 4: Implementation
**AI AGENT ACTIONS:**
1. Execute the approved plan step by step
2. After EACH step:
   - Document the change immediately
   - Test the change (if possible)
   - Update project plan status
   - Verify no breaking changes
3. Only proceed to next step after current step is complete

**AI AGENT CHECKLIST (per step):**
- [ ] Step executed
- [ ] Change documented
- [ ] Code tested (if applicable)
- [ ] Project plan updated
- [ ] No breaking changes introduced
- [ ] Ready for next step

### Step 5: Change Documentation
**AI AGENT ACTIONS:**
1. Create change documentation for each modification
2. Save to `dev_notes/changes/` with timestamp
3. Include all relevant details and code changes
4. Link to the original project plan
5. Update project plan status to "Completed"

**AI AGENT CHECKLIST:**
- [ ] Change documentation created
- [ ] All files listed
- [ ] Code changes documented
- [ ] Linked to project plan
- [ ] Project plan marked complete

---

## Critical Rules

### **NEVER Execute Without Approval**
**AI AGENT INSTRUCTIONS:** This is the MOST IMPORTANT rule.

- All project plans MUST be approved before implementation
- No code changes without explicit developer consent
- If unsure, ask for clarification
- **Exception:** Trivial changes (see Trivial Changes section)

**AI AGENT DECISION POINT:** Before making ANY code change, ask yourself:
1. Is this a trivial change? → If yes, proceed with simplified docs
2. Do I have explicit approval? → If no, STOP and request approval
3. Am I certain about the approach? → If no, ask for clarification

### **Always Document Changes**
**AI AGENT INSTRUCTIONS:** Documentation is mandatory.

- Every file modification must be documented
- Include clear descriptions of what was changed
- Maintain chronological order of changes
- Link to project plans when applicable

### **Maintain Code Quality**
**AI AGENT INSTRUCTIONS:** Follow these quality standards.

- Follow existing code patterns and conventions
- Ensure python types are properly defined (e.g., TypeScript, Python type hints)
- Maintain consistent error handling
- Write clean, readable code
- Use meaningful variable and function names
- Add comments for complex logic
- Follow the existing code style (check other files first)

### **Test Before Proceeding**
**AI AGENT INSTRUCTIONS:** Verify changes work.

- Test each change before moving to the next step
- Verify that existing functionality still works
- Check for any breaking changes
- Run linters/type checkers if available
- If testing is not possible, clearly state this in documentation

---

## Database Changes

**AI AGENT INSTRUCTIONS:** Special procedures for database modifications.

### Schema Changes
1. **ALWAYS** create a migration script
2. Document the migration in project plan
3. Include rollback procedures
4. Test migration on sample data first

### Migration Script Format
```sql
-- Migration: [Description]
-- Date: YYYY-MM-DD
-- Related Project Plan: [plan-id]

-- Forward migration
BEGIN;
-- Your migration SQL here
COMMIT;

-- Rollback (if needed)
-- BEGIN;
-- Rollback SQL here
-- COMMIT;
```

**AI AGENT CHECKLIST for Database Changes:**
- [ ] Migration script created
- [ ] Rollback script included
- [ ] Migration documented in project plan
- [ ] Data integrity verified
- [ ] Backup strategy considered

---

## API Development

**AI AGENT INSTRUCTIONS:** Follow these practices for API endpoints.

### Endpoint Documentation
- Document all new/modified endpoints
- Include request/response examples
- Specify error codes and messages
- Document authentication requirements

### API Documentation Template
```markdown
## [Endpoint Name]

**Method:** [GET/POST/PUT/DELETE]  
**Path:** `/api/v1/[path]`  
**Authentication:** [Required/Optional]

### Request
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

### Response (Success)
```json
{
  "status": "success",
  "data": {}
}
```

### Response (Error)
```json
{
  "status": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```
```

**AI AGENT CHECKLIST for API Changes:**
- [ ] Endpoint documented
- [ ] Request/response examples provided
- [ ] Error handling implemented
- [ ] Authentication considered
- [ ] Validation added

---

## Project Status Tracking

### Development Notes
- All changes are tracked in `dev_notes/` directory
- Project plans are created before any implementation
- Developer approval is required for all changes
- Documentation is maintained for all modifications

### Project Structure (Planned/Current)
**AI AGENT INSTRUCTIONS:** These directories may not exist yet. Create them as needed.

- Documentation: `logist/doc/project-status.md` (to be created)

### Key Technologies
- Backend: Python, FastAPI

### Important Files (Planned)
- `logist/doc/project-status.md` - Overall project status (to be created)
- `project_plan_rules.md` - This file
- `dev_notes/` - All development documentation

---

## Best Practices

### Code Organization
**AI AGENT INSTRUCTIONS:** Follow these patterns.

- Keep related functionality together
- Use consistent naming conventions (camelCase for variables/functions, PascalCase for components/classes)
- Maintain proper python typing (avoid `any` when possible)
- Organize imports: external → internal, grouped by type

### Documentation
**AI AGENT INSTRUCTIONS:** Write clear documentation.

- Write clear, concise descriptions
- Include code examples when helpful
- Maintain chronological order
- Link related documents
- Use proper markdown formatting

### Testing
**AI AGENT INSTRUCTIONS:** Test thoroughly.

- Test each change individually
- Verify integration with existing code
- Check for performance impacts
- Ensure error handling works correctly
- Consider edge cases

### Communication
**AI AGENT INSTRUCTIONS:** Be clear and helpful.

- Ask questions when unclear
- Provide detailed explanations
- Be transparent about limitations
- Suggest improvements when appropriate
- Explain your reasoning for decisions

---

## Emergency Procedures

### If Something Goes Wrong
**AI AGENT INSTRUCTIONS:** Follow these steps immediately.

1. **STOP immediately** - Do not continue with changes
2. **Document the issue** - Create a change log entry explaining what happened
3. **Notify the developer** - Explain what happened clearly
4. **Wait for guidance** - Do not attempt to fix without approval

### Rollback Procedures
**AI AGENT INSTRUCTIONS:** Only execute with explicit approval.

1. **Identify the last working state** - Check git history or documentation
2. **Create a rollback plan** - Document what needs to be reverted
3. **Get developer approval** - Wait for explicit go-ahead
4. **Execute rollback carefully** - One step at a time
5. **Document the rollback process** - Create change documentation

---

## Support and Clarification

### When to Ask for Help
**AI AGENT INSTRUCTIONS:** Ask when:

- Requirements are unclear or ambiguous
- Technical limitations are encountered
- Breaking changes are detected
- Performance concerns arise
- Integration issues occur
- You're unsure about the approach

### How to Ask for Help
**AI AGENT INSTRUCTIONS:** Be specific and helpful.

- Be specific about the issue
- Provide relevant code snippets
- Include error messages (if any)
- Explain what you've tried
- Suggest potential solutions
- Reference related project plans or documentation

---

## AI Agent Quick Reference

### Before Making ANY Code Change, Ask:
1. ✅ Is this a trivial change? (If yes, use simplified docs)
2. ✅ Do I have a project plan? (If no, create one)
3. ✅ Do I have explicit approval? (If no, STOP and request)
4. ✅ Do I understand the requirements? (If no, ask questions)
5. ✅ Have I checked existing code patterns? (If no, check first)

### Mandatory Workflow:
```
Request → Analysis → Plan → Approval → Implementation → Documentation
```

### File Naming:
- Project Plans: `dev_notes/project_plans/YYYY-MM-DD_HH-MM-SS_description.md`
- Changes: `dev_notes/changes/YYYY-MM-DD_HH-MM-SS_description.md`
- Branches: `feature/YYYY-MM-DD-description` or `fix/YYYY-MM-DD-description`

### Commit Format:
```
[Type] Brief description - Related to project plan: [plan-id]
```

---

## Final Reminders

**AI AGENT INSTRUCTIONS:** 

- These rules exist to ensure high-quality, well-documented, and trackable development
- **Always follow them precisely**
- When in doubt, ask for clarification
- **Never execute code without approval** (except trivial changes)
- **Always document changes**
- **Test before proceeding**
- **Maintain code quality**

**Remember: It's better to ask for clarification than to make assumptions!**
