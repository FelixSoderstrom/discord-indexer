---
description: Used preemptively when a subagent is needed for implementing changes.
argument-hint: A subagent specialized in...
---

# Expected Result
A fully functional subagent specialized in: **$ARGUMENTS**

# Workflow

## 1. Research and Context Gathering

### Check for Feature Handoff
**IMPORTANT**: If you (the main agent) just implemented the feature via `/new-feature`:
- You already have the context in your memory - **skip reading the handoff report**
- Proceed directly to the research steps below using your existing knowledge
- The handoff report exists for cases where a different agent needs the context

If `.claude/docs/reports/feature-handoff.md` exists AND you don't have the context:
- Read the handoff report to understand what was just implemented
- Use it as foundation for your research
- Delete the file after reading: `rm .claude/docs/reports/feature-handoff.md`

### Git Analysis
- Run `git status` to identify uncommitted changes
- Run `git diff` to see recent modifications
- Run `git log --oneline -10` to understand recent commit context

### Codebase Analysis
- Read relevant feature files in the target area
- Identify key modules, classes, and functions
- Map integration points and dependencies

### Agent Ecosystem Review
- Read existing agent definitions in `.claude/agents/` that work in similar areas
- Read their instruction files in `.claude/docs/agents/`
- Identify coordination boundaries and potential overlaps

## 2. Write Comprehensive Report
Create a detailed report at `.claude/docs/reports/new-agent.md` with the following structure:

```markdown
# Agent Creation Report: [Agent-Name]

## Purpose Statement
[Clear one-paragraph description of why this agent is needed and what gap it fills]

## Core Responsibilities
- Primary responsibility 1
- Primary responsibility 2
- Primary responsibility 3
[High-level responsibilities, not implementation details]

## Technical Scope

### Key Files and Modules
- `src/path/to/file.py` - Role in system
- `src/path/to/module/` - Module purpose
- [List all relevant files the agent will work with]

### Integration Points
- **Interacts with**: [component/system]
- **Receives from**: [component/system]
- **Provides to**: [component/system]

## Agent Architecture Tips

### Naming Convention
- Suggested name: `[specific-name]` (kebab-case)
- Rationale: [why this name fits the domain]

### Delegation Trigger Phrases
- Primary trigger: "Use proactively for [specific scenarios]"
- Secondary triggers: "Specialist for [domain operations]"
- Keywords that should invoke this agent: [keyword1, keyword2]

### Tool Requirements

#### Essential Tools (must have)
- `Read`: [specific use case for this agent]
- `Edit`: [what files/patterns it will edit]
- `Write`: [if creating new files, what types]
- [Other tools with justification]

#### Optional Tools (consider including)
- `Bash`: [specific commands this agent might run]
- `Grep`: [if searching patterns is core to function]
- [Other tools that might be useful]

### Workflow Patterns
- Step 0 **MUST** be: "Read .claude/docs/agents/[agent-name]-instr.md"
- Typical workflow sequence: [Analysis → Planning → Implementation → Validation]
- Critical decision points: [where agent needs to branch logic]
- Output format expectations: [structured report, code changes, validation results]

### Domain-Specific Considerations

#### Technical Context
- Primary programming language/framework: [Python/Discord.py/etc.]
- Key design patterns to follow: [singleton, factory, etc.]
- Performance constraints: [if any]

#### Related Agents
- Agents in similar domain: [agent1, agent2]
- Potential parallel operations with: [agent3, agent4]

### Best Practices for This Domain
- Error handling: [specific exceptions to catch]
- Logging requirements: [what should be logged]
- Security considerations: [if applicable]
- Testing philosophy: [unit, integration, manual]

### Anti-Patterns to Avoid
- Do NOT: [specific things this agent shouldn't do]
- Avoid: [common pitfalls in this domain]
- Never: [hard boundaries]

### Success Metrics
- Primary success indicator: [what shows task completed]
- Quality checks: [how to validate good output]
- Performance targets: [if applicable]

### Model Selection Hint
- Recommended model: [claude-sonnet-4-5 for complex, haiku for simple]
- Reasoning: [complexity level, speed requirements]
```

**IMPORTANT:** If CLAUDE is unable to fill out the report above because of missing context they **MUST** deploy another instance of the general-purpose subagent to do more research.
Under **NO** circumstances should CLAUDE make up information in the report. All information in the report **MUST** be based on real research made by the general-purpose subagent.

## 3. Create Subagent Definition (Sequential)
**IMPORTANT: Run this synchronously - wait for completion before proceeding**

Deploy meta-agent with the report:
- Instruct meta-agent to read `.claude/docs/reports/new-agent.md`
- Meta-agent creates the agent definition at `.claude/agents/[agent-name].md`
- Verify the file was created successfully

## 4. Create Agent Instructions (Sequential)
**IMPORTANT: Run this AFTER meta-agent completes**

Deploy meta-instructions-writer with:
- The same report at `.claude/docs/reports/new-agent.md`
- Reference to the newly created agent definition
- Output location: `.claude/docs/agents/[agent-name]-instr.md`

The meta-instructions-writer will:
- Read the agent definition created by meta-agent
- Create detailed instructions following the template format
- Edit the agent definition to add "Step 0: Read instructions"

## 5. Validation
Verify both files were created correctly:
- Read `.claude/agents/[agent-name].md` - Check for proper frontmatter and structure
- Read `.claude/docs/agents/[agent-name]-instr.md` - Verify instructions follow template
- Confirm Step 0 references the instruction file

## 6. Cleanup
Delete the temporary report file:
```bash
rm .claude/docs/reports/new-agent.md
```

## 7. Report Success
Provide brief confirmation to user:
```
Created subagent: [agent-name]
  - Definition: .claude/agents/[agent-name].md
  - Instructions: .claude/docs/agents/[agent-name]-instr.md
  - Ready for use with delegation trigger: "[trigger phrase]"
```

# Important Notes

- **Sequential Execution**: Steps 3 and 4 MUST run sequentially, not in parallel
- **Report as Single Source**: The report file is the only context both meta-agents need
- **Validation Required**: Always verify files were created before cleanup
- **No Manual Creation**: Let meta-agents handle all file creation
- **Use valid data**: Fill out the report using real data from the research process.