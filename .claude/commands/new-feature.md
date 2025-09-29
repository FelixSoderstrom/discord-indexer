---
description: Implements new features and creates a subagents.
argument-hint: "The final result"
---


# Final result

This section explains what the finished result looks like.

**$ARGUMENTS**


# Workflow


1. Research the codebase
2. OPTIONAL: Ask for more context if insufficient for step 3
3. Draft an implementation plan
4. Iterate with developer on plan
5. Implement the changes
6. Iterate on bugfixes and improvements
7. Create specialized subagent for future implementations



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
Simply saying "I understand" and immediately writing the next instructions are **prohibited**.
Instead you should:
- Think about what the developer is asking for
- Understand the meaning behind the request
- Briefly explain your understanding (the developer can see your thinking process, no need for duplicate thorough explanations)
- Revise your implementation plan.

Only once the developer clearly states that you should proceed are you allowed to.


## 5. Implementing the changes

When implementing the changes you **must** follow the plan you agreed upon.
Straying from the plan must be done with caution and be justifiable with **good** cause for the betterment fo the application.
Preferably you should **stop** when encountering a scenario where you want to stray from the agreed plan, provide a reason to why the deviation is acceptable and then await developer feedback on wether or not to do it.
You are to implement these changes yourself andare **not** allowed to use subagents for this step.


## 6. Iterate on fixes

This step aims at removing bugs introduced and providing a final version of the feature.
This step is only done when the developer are satisfied with the results.
In some cases this step requires its own implementation plan - in which case it should follow the same rules stated above.



## 7. Creating the subagent

Once the implementation is in place and the developer is satisfied you should create a specialized subagent for this feature that can handle future implementations or changes regarding this feature.
To do this you must first read the meta-agent definition in `.claude/agents/meta-agent.md`
Then deploy it, providing detailed instructions on what the subagent is responsible for.
