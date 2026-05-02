# What I want

## Context
- i want a personal AI assistant with many features inspired from [openclaw](ref-openclaw/). 
- but the key difference is i do not want an AI agent with complete autonomy within my OS, computer and files. Its too risk.
- **Also, openclaw is so bloated, with many client interfaces, many features and typescript. I prefer Python (because i am very familiar with) or Rust (for performance gains).**
- i want to be the owner of the memory layer (my memories, agent learning, conversations logs and history)
- i want to choose between different LLM providers
- i want to be able to extend the assistant capabilities using plugins, MCP servers, tools, custom commands, skills, etc.

## My vision
- i find the current, thread-style UI from chatgpt and all other big chatbots abhorent. Who wants to go through hundreds of chats?
- it will be better if the UI aligns with the fact the agent is a personal assistant, a consigliere like Bruce Wayne's Alfred Pennyworth or Iron Man's **Jarvis**.
- this means just one chat, continuous, chat. A telegram bot would fit well.

## Architecture
<suggestions>

## Security
- beware of ssh-key exploits
- no public exposing ports (i have Tailscale set on my mac-mini, iphone and linux notebook)
- consider how to limit damage if the UI (telegram) is compromised
- no write privileges for anything unless in the allowlist
- no root access to host (usually my personal computer)
- agent should not message or be messaged anyone besides the user

## Observability
- structured logs
- use correlation ID in all logs
- important: Log statements are anti-pattern: "transaction started, movement calculated," learn to use debug mode to avoid cluttering your logs.

## Commom use-cases
- **Deep Research**: i want a detailed technical report about the current research about some topic using only thrustworth sources (not reddit).
  - We could use this hierarchy for grouding sources: attached files > thrustworth websites (wikipedia, arxiv, other academic research portals, universities websites, etc) > big websites > reddit, blogs, substack, medium.
- i want to ask for personal counselling like if the agent is "Alfred Pennyworth", Bruce Wayne's butler. I like the tone from Alfred from Christopher Nolan's trilogy: a fatherly tone.
- i want to ask random/general question (like chatgpt)
- i want to work on my personal software engineering projects, primarily in my personal computer shell (linux or macos) but sometimes remotely (using telegram). Currently i use [OpenCode](https://github.com/anomalyco/opencode).
- i want the option to ask **private** questions which should not be recorded.
