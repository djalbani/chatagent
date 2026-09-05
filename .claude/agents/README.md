# Your Agent Team

This folder is your **team of AI specialists**. Each `.md` file below is one agent —
a worker with its own job, its own instructions, its own tools, and its own memory.

When you run Claude Code in this repo, the "lead" agent (the one you chat with) reads
the `description:` line of each file and automatically hands work to the right
specialist — or you can call one by name: *"use the proposal-writer to draft a
proposal for this lead."*

## The team

| Agent | Job | Needs |
|-------|-----|-------|
| `lead-qualifier` | Reads an inbound client inquiry, scores it, tells you if it's worth your time | nothing (works on pasted text) |
| `proposal-writer` | Turns a qualified lead into a tailored project proposal in your voice | your `docs/` folder |
| `inbox-triage` | Sorts client email, flags what's urgent, drafts replies in your persona | **Gmail** connector |
| `discovery-scheduler` | Proposes discovery-call time slots and books them | **Google Calendar** connector |
| `project-kickoff` | Spins up a full task list for a new web project | **ClickUp** connector |
| `code-reviewer` | Reviews changes to your code (like this repo) before you ship | nothing (reads the repo) |

## How to use them

- **Automatic:** just describe what you want. *"A new lead just emailed asking for a
  Shopify store — is it worth pursuing?"* → the lead-qualifier gets pulled in.
- **By name:** *"Use the code-reviewer to check my latest changes."*
- **In sequence (a pipeline):** *"Qualify this lead, then if it's a good fit, draft a
  proposal."* The lead-qualifier runs first, its result feeds the proposal-writer.

## Anatomy of an agent file

Every file has two parts:

```markdown
---
name: lead-qualifier          # what you call it
description: When to use it    # how the lead agent decides to delegate
tools: Read, Grep, Glob        # what it's allowed to touch (omit = inherit all)
model: sonnet                  # brain size: haiku (fast/cheap) → sonnet → opus (deepest)
---

Everything below the dashes is the agent's system prompt — its job description,
personality, rules, and step-by-step method.
```

## Editing your team

- Change any agent by editing its file. Restart Claude Code to pick up changes.
- Add a new specialist by copying a file and rewriting it.
- The connector-based agents (Gmail, Calendar, ClickUp) only work when that
  connector is enabled in your Claude environment. If it isn't, the agent will
  ask you to paste the info instead — nothing breaks.

Start small: run one agent, watch what it does, then adjust its instructions.
That feedback loop is the whole skill.
