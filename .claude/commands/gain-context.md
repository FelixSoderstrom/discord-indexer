---
description: Used to gain context on a given feature or area of the codebase.
argument-hint: "Description of a feature in the codebase and any perticular aspects of it."
---

# Gaining context

I want you to investigate the following feature using appropriate subagents:
**$ARGUMENTS**


# Workflow

1. Think
2. Delegate
3. Response


## 1. Think

Think about what the user is describing, which subagent(s) this relates to and how you should structure the prompt for the subagent(s).
If insufficient context was given for the feature you should stop and tell the user to be more descriptive.


## 2. Delegate

Delegate the research to the subagent(s) and await response.
Make sure to include any questions mentioned in **$ARGUMENTS** in your prompt.
**IMPORTANT:** Prompt to subagents must explicitly state to not alter any code and only report back.


## 3. Response

Respond to the user with a brief summary.
Make sure to answer any questions that were defined in **$ARGUMENTS**