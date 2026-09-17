# Feature terms — agent-team-topology

Tooltip terms for this feature's lavish pages. Not a glossary: terms that outlive the feature graduate to the plugin `GLOSSARY.md`.

**herdr**: A terminal multiplexer for coding agents. It organizes terminals into workspaces, tabs and panes, recognizes the agent in each pane, and lets one agent start, message, wait for and close another through its command line.

**1DevTool**: A desktop developer workspace that can start other coding agents through its `1devtool-agent` command: single runs, named teams, parallel groups of workers, and a stop command that closes a team and its terminals.

**headless**: Running an agent as a single command-line process with no interactive screen, for example `claude -p` or `codex exec`. The process answers once and exits; its output goes to a file.

**planner-fable**: The Claude planner in this session's research phase, running on the Fable 5.1 model. It is closed; its findings are in FACTS-claude.md and PROPOSAL-claude.md.

**planner-astra**: The Codex planner in this session's research phase, running on the gpt-6-astra model. It is closed; its findings are in FACTS-codex.md and PROPOSAL-codex.md.

**relayer**: The herdr name of the contact agent in this session: the one agent the human talks to.

**auto mode**: A Claude Code permission mode in which a classifier approves safe tool calls, so the agent does not stop for a human approval on each command.

**approve-for-me**: A Codex command-line flag that sends each approval request to an automatic reviewer instead of the human, inside the workspace-write sandbox.

**review gate**: The independent review step after an implementation. Fresh reviewer agents, not the author, check the change and the loop repeats until nothing actionable remains.

**DISAGREE-FINAL**: A debater's verdict on a point that more discussion cannot settle, because the choice rests on a value, a cost trade or a policy only the human can set. Only these points reach the human in a grill.

**debater-fable**: The Claude debater of this session's converge round, on the Fable 5.1 model. It spoke for the Claude planner's proposal, worked only from files, and is now closed.

**debater-astra**: The Codex debater of this session's converge round, on the gpt-6-astra model. It spoke for the Codex planner's proposal, worked only from files, and is now closed.

**park**: To stop a role's work on purpose and record why and when it may continue, for example until a provider's usage limit resets. A parked role keeps its saved state.

**fallback list**: A list of other providers you write in advance for a role. The plugin may switch a role to a provider only when that provider is on its list or the role is set to automatic.

**catalog**: A repository-wide index of stored facts: their subjects, ids and file locations. It copies no claims and can be rebuilt from the per-feature stores at any time.

**wait horizon**: The longest time an unattended run may wait for a usage limit to reset before the plugin tells the human.

**weekly limit**: A provider usage limit measured over seven days. It can take days to reset and usually means the week's budget is spent.

**OS scheduled task**: A job registered with the operating system, such as the Windows task scheduler, that runs at a set time even when no agent session is open.

**effective config**: The configuration the plugin actually uses after defaults, repository settings and user overrides are merged, as printed by its config reader.

**run manifest**: The list the plugin keeps of everything it started for one run — each agent with its process, pane and directory, and each background process an agent started. Cleanup kills what the manifest names and reports what it could not.

**running checkpoint**: A file a role writes as it works, not at the end. It is what a replacement reads when the original agent dies, because a dying agent cannot be asked for a handoff.

**debate pattern**: Two agents or more, on different models, doing the same piece of thinking independently, then critiquing each other and recording a verdict each. Used for research, design, planning, review and audit work.

**talk edges**: The pairs of roles a pattern allows to message each other directly. Anything not listed relays through the contact agent.

**worktree**: A second working directory of the same repository, checked out on its own branch, sharing one copy of the repository's history.

**harness**: The program running an agent — the command-line tool or desktop app that owns its permissions, its tools and its sandbox.

**git hook**: A script git runs by itself at a set moment — before a commit, before a push — which can refuse the action. This plugin already ships one that refuses a branch name of the wrong shape.

**authentication check**: Asking a provider whether this machine is signed in and entitled to use it. It is not a usage-limit reading: it says whether the account works at all, not how much of the window is left.

**window share**: The part of a provider's usage window one agent or one pattern is expected to consume. Every session on one account draws from the same window.

**devil's-advocate pass**: A fresh agent briefed to attack a settled requirement set — never to agree with it. It reads the record only, not the conversation, so it cannot be led by how a decision was reached.

**brief**: The written instruction a spawned agent is started with. It carries quoted context instead of the human's conversation, so the agent starts with a small, deliberate context.
