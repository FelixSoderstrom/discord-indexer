---
description: Used to plan and implement a codechange. Supports concurrent execution.
argument-hint: "Desired result of a feature"
---

# Implementing changes

Follow the workflow for this user input:
**$ARGUMENTS**


# Workflow

1. Determine
2. Delegate
3. Response


## 1. Determine

Make sure you have sufficient knowledge about the area. If you have insufficient knowledge or context about the area mentioned in **$ARGUMENTS** you **must** stop this process and tell the user to run the "/gain-context"-command.
Go back and forth with the user discussing exactly *how* to implement change.
**Avoid** beeing agreeable for the sake of it and focus on **what's best for the codebasse**. It's better to shut the user down early if they present bad ideas.
User must explicitly state that you are in agreement before you are allowed to proceed to the next step.


## 2. Delegate

**Think hard** about:
- Which subagent is most appropriate for this task?
- How do I structure the instructions for the subagent?
- What information is essential for the instructions?

If there are multiple sessions of this command running concurrently, **Think hard** about:
- What effects does deploying these agents in paralell have?
- Should I deploy some of the agents sequentially? 

Onceyou have determined how to instruct and how to deploy the subagents you may deploy them.
Subagent should give you structured responses when it's done.


## 3. Response

Provide summary of what was done by the subagents.
Keepit technical and consice.
Mention if the agents failed with something.