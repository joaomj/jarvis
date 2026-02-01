# What I want

## Context
- i want an AI assistant with many features inspired from [openclaw](https://github.com/openclaw/openclaw). See also [openclaw docs](https://docs.openclaw.ai/)
  - openclaw was previously named "clawdbot"
- but the key difference is i do not want an AI agent with complete autonomy within my OS, computer and files. Its too risk.
- i want to be the owner of my memories, of the agent learnings, of the conversation logs/history.
  - they should be easily portable and synced. What about using **Syncthing** for this? Look at their repo: https://github.com/syncthing/syncthing
    - this way i would avoid dependency with Google Drive (my current backup tool). Perhaps we could leverage git for this, too.

## My vision
- i find the current, thread-style UI from chatgpt and all other big chatbots abhorent. Who wants to go through hundreds of chats?
- it will be better if the UI aligns with the fact the agent is a personal assistant, a consigliere, a butler
- this means just one chat, continuous, chat.
- all the chat management should happen in the background, away from the user view: chat history organization, memories organization, choosing what "conversation mode" or tool to use, etc etc.
- the agent must have the ability to self-improve itself and passively learn from its user
- 

## Agents and the memory problem
- agents are bad at retrieval
- there are 03 common solutions:
  - put everything in the context ("AGENTS.md"): this is great until you context get full and the agent get lost in it ("context poisoning").
  - offload something and retrieve when needed: this is the "skills" approach pioneered by [Anthropic](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) in october 2025. The problem is: agents are [really bad at deciding when to call a skill](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals). Also there is another problem: what kind of offloading architecure? A filesystem? An sqlite database?
  - make the context an index: this is the recent [Vercel](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) approach. They compress the context file and make it act like an index to the detailed instructions. I am using this method right now.

## Agents and the decision problem
- agents are bad at following instructions
- also, they are non-deterministic
- this makes instructions to agents not very reliable
- how could we make agents reliably follow instructions?

## Interface
- should be easier to use, to build upon it, cheap or free, mobile-adapted
- Telegram or Discord?
- i want to talk to the agent even when i am away from home, using my cellphone.

## Architecture

### Hardware
- i am not a know-all about systems design
- i want the simplest and cheaper arch, but without sacrificing security
- i have a Mac Mini M4 (16gb RAM, 256gb SSD), an Iphone 16 and a VPS subscription (very basic, only 4GB RAM 50gb hd, but could upgrade if necessary and justifiable)
- i am familiar with Tailscale and Cloudflare tunnels
- my home network runs on an ISP-provided router (i have no admin access to it)

### Software
- i want to avoid vendor lock-in
- i prefer opensource solutions
- i want to be able to select which LLM provider to use (currently i use Google Antigravity, OpenAI, OpencodeZen, Z.AI GLM)
- what if our agent runs on [opencode](https://github.com/anomalyco/opencode)? Its an opensource harness i like to use. Openclaw is opensource, too, but i find it too complex and with many things running with i dont really grasp.
  - opencode allows for provider selection, agent selection, i can use my own custom agents with it (they have 2 native agents: "plan" and "build"), has a webserver mode, etc

## Security
- beware of ssh-key exploits
- no public exposing ports
- consider how to limit damage if the UI (telegram) is compromised
- no write privileges for anything unless in the allowlist
- agent should not write or delete emails
- agent should not change anything in the user X account (remove saved posts, etc)
- agent should not message or be messaged anyone besides the user

## Observability
- structured logs
- use correlation ID in all logs
- consider using Langfuse for agent traceability
- we must log all agent actions and messages
- correlation ID is always passed forward in requests
- all apps send logs to stdout/stderr
- some agent collects (FluentBit, for example)
- the agent sends it to some backend (Elastic, DataDog, NewRelic, etc.)
- the final tool has the entire indexing structure configured, retention time, etc.
- important: Log statements are anti-pattern: "transaction started, movement calculated," learn to use debug mode to avoid cluttering your logs.

## Commom use-cases
- i want to chat about some topic about History or Economics
- i want a detailed technical report about the current research about some topic using only thrustworth sources (not reddit), like Perplexity or Gemini Deep Research.
- i want to analyze the reliability/robustness of a research paper following scientific research methdology best practices (statistical tests, etc)
- i want to ask for personal counselling like if the agent is "Alfred Pennyworth", Bruce Wayne's butler. I like the one from Christopher Nolan's trilogy.
- i want to ask about some random/general question
- i want to work on my personal software engineering projects, opening and commanding opencode remotely
- **Priority/Very High Pain:** i want the agent to summarize my emails, substack newsletters (only the ones i specify) and specially saved X (formerly Twitter) articles. Also i want the option to ask the agent to copy the article/blogpost/email to markdown file for me to store locally.
- i want to be warned about incoming weather events for the day
- i want to be warned about my Google Calendar events for the day and week.
- i want the option to talk to the agent using my VOICE, but i want the agent to only responde with text, not audio.
- i want to send to the agent some text (e.g., PDF, markdown) files (books, research articles, etc) and ask it to summarize them for me or chat with me using only them as sources (like Google's NotebookLM). For example: i want the agent to analyze Tocqueville's "Democracy in America"; i send the PDF and start to discuss the book with the agent, like in a book club meeting.
- i want the option to ask **private** questions: they should not be recorded
- i would not ask the agent to generate video, images, etc. So no need to be multimodal.

From all those cases, the most urgent i want to solve is the one about summarizing X articles and substack articles. I have a ton of saved ones, but do not have the time to read them all. This should be the first feature we must implement, before or right after the Telegram connection.

## Open questions
- what kind of memory management we should use, considering this is only a personal-use agent i do not intend to publish?
- could we take advantage of opencode as the harness for our agent?
- telegram or discord?
- what approach would we use for "converting" messages between the client (e.g. telegram) and our "host" (the ai agent, e.g. opencode)? A gateway, like openclaw?
- what approach should we use for the agent to not forget?
- what approach for the agent to learn?
- what approach for the agent to relaibly know when to use skills/tools?
- how could the agent conver user voice messages to text commands? Can this be made locally using a small STT model? Or even whisper?
- how to integrate opencode when the user wants to work on his software engineering projects?

## To study for inspiration

### Memory
- [How we built Agent Builder’s memory system](https://x.com/hwchase17/article/2011814697889316930)
- [Agent Skills vs. Rules vs. Commands vs. Subagents](https://x.com/tempoimmaterial/status/2014054104658526645)
- [WTF is a Context Graph? A Guide to the Trillion-Dollar Problem](https://x.com/parcadei/status/2013713799719559480?s=20)
- [Towards a Disaggregated Agent Filesystem on Object Storage](https://x.com/penberg/status/2010360708253274513?s=20)
- [Memory as reasoning](https://blog.plasticlabs.ai/blog/Memory-as-Reasoning)
- [A knowledge management system inspired by plain-text accounting](https://thalo.rejot.dev/blog/plain-text-knowledge-management)
- [Securely indexing large codebases](https://cursor.com/blog/secure-codebase-indexing)
- [Dynamic context discovery](https://cursor.com/blog/dynamic-context-discovery)
- [How to build agents with filesystems and bash](https://vercel.com/blog/how-to-build-agents-with-filesystems-and-bash)
- [qmd - mini cli search for docs and knowledge bases](https://github.com/tobi/qmd)
- [building the brain logic of ai agents : a beginner's guide](https://x.com/sharpeye_wnl/status/2017110571460784451)
- [Build Agents That Learn](https://x.com/ashpreetbedi/status/2016318096772936159)
- [Agents Need a Database](https://x.com/ashpreetbedi/status/2015935966268018823)
- [Nothing new under the sun: everything is a file](https://turso.tech/blog/nothing-new-under-the-sun)
- [agentic memory: filesystem vs database](https://x.com/helloiamleonie/status/2013256958535401503)
- [How Clawdbot Remembers Everything](https://x.com/manthanguptaa/status/2015780646770323543)
- [The Three-Layer Memory System Upgrade for Clawdbot](https://x.com/spacepixel/status/2015967798636556777)
- [How to make your agent learn and ship while you sleep](https://x.com/ryancarson/status/2016520542723924279)

### Mysc
- [how to read technical books (the right way)](https://x.com/oprydai/status/2012694785111552379?s=20)
- [system design for starters](https://x.com/AvinashSingh_20/status/2015075875193340319?s=20)
- [Understanding the differences between LangChain, LangGraph, and DeepAgents (and when to use each one)](https://x.com/masondrxy/status/2014917523263954990)
- [Langchain - why multiagents?](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/multi-agent/index.mdx)
- [Skill - logging best practices](https://gist.github.com/jsadoski-rockhall/4e3450c1c633902a49c0a7d8d857bd91)
- [the engineering behind clawdbot](https://x.com/Hesamation/status/2017038553058857413)

### Books and Scientific Papers for free
- [Annas Archive API](https://annas-archive.li/faq#api): 
  *We have one stable JSON API for members, for getting a fast download URL: [/dyn/api/fast_download.json](https://annas-archive.li/dyn/api/fast_download.json) (documentation within JSON itself). For other use cases, such as iterating through all our files, building custom search, and so on, we recommend [generating](https://software.annas-archive.li/AnnaArchivist/annas-archive/-/blob/main/data-imports/README.md) or [downloading](https://annas-archive.li/torrents#aa_derived_mirror_metadata) our ElasticSearch and MariaDB databases. The raw data can be manually explored through JSON files](https://annas-archive.li/db/aarecord_elasticsearch/md5:8336332bf5877e3adbfb60ac70720cd5.json.html). Our raw torrents list can be downloaded as [JSON](https://annas-archive.li/dyn/torrents.json) as well.*
- [Semantic Scholar API](https://www.semanticscholar.org/product/api/tutorial): if we use an API key, we get 1 rate per second limit. For our use its sufficient.