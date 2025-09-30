---
description: Implements new features and creates a subagents.
argument-hint: "The final result"
---


# Final result

This section explains what the finished result looks like.

**$ARGUMENTS**


# Workflow


1. Research the codebase
2. Ask for more context (OPTIONAL)
3. Implementation plan
4. Iterate on plan
5. Implement changes
6. Iterate on fixes
7. Create a new subagent



## 1. Research the codebase

Subagents are available for each domain of this project - use them for research!


## 2. Ask for more context

Assess if you have sufficient context for drafting an implementation plan.
If you need more, **stop** and ask the developer for more information on what they want.
You are interested in what the feature is going to look like when it's finished.


## 3. Implementation plan

Detailed implementation plan and developer acceptance is **required** before implementing changes.
Research **must** be done in relevant files before drafting an implementation plan.
Explain areas in your plan with a similar format:
- Filename
- Key functions
- What it accomplishes
Do **not** give explicit code examples unless absolutely needed or asked for.


## 4. Iterate on plan

Go back and forth with the developer to reach a conclusion and final plan.
Validate your understanding of the developers adjustments **BEFORE** drafting the next plan.
Simply saying "I understand" and immediately writing the next instructions is **prohibited**.
Instead you should:
- Think about what the developer is asking for
- Understand the meaning behind the request
- Briefly explain your understanding (the developer can see your thinking process, no need for duplicate thorough explanations)
- Revise your implementation plan.

This step is **not** done until both the USER and CLAUDE are in **agreement**.
The success of this step is dependent on how well CLAUDE and USER are able to **criticize** one another productively. Being agreeable for the sake of agreeableness is considered **unproductive** and should be **avoided** at all costs.


## 5. Implement changes

When implementing the changes you **must** follow the plan you agreed upon.
Straying from the plan must be done with caution and be justifiable with **good** cause for the betterment fo the application.
Preferably you should **stop** when encountering a scenario where you want to stray from the agreed plan, provide a reason to why the deviation is acceptable and then await developer feedback on wether or not to do it.
You are to implement these changes yourself andare **not** allowed to use subagents for this step.


## 6. Iterate on fixes

This step aims at removing bugs introduced and providing a final version of the feature.
This step is only done when the developer are satisfied with the results.
In some cases this step requires its own implementation plan - in which case it should follow the same rules stated above.


## 7. Create a new subagent

### Prepare Handoff Report
Write a feature summary to `.claude/docs/reports/feature-handoff.md` containing:
- **Feature Purpose**: Brief description of what was implemented
- **Key Files Created/Modified**: List of primary files and their roles
- **Integration Points**: How the feature connects to existing systems
- **Core Responsibilities**: What the managing agent should handle
- **Technical Context**: Key patterns, frameworks, or design decisions

### Trigger Agent Creation
After writing the handoff report, remind the USER to run: `/new-agent`

**Note**: This handoff report helps preserve context from the implementation phase and speeds up agent creation.