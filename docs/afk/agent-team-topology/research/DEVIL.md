# Devil's-advocate pass — settled requirement set

Fresh agent, 2026-09-16, working only from `GRILL-LOG.md`, `research/BRIEF.md` and
`grill-requirements.round.json`. Briefed to attack, not to agree. 12 findings, ranked by
how likely each is to change a decision. Round 5 is built from what survives.

Status: none resolved yet. Three of them (F2, F3, F9) bear on cards open in round 4.

| # | Cards | Defect | Smallest fix proposed |
|---|---|---|---|
| F1 | PERM2 vs PERM1B, C5 | PERM2 forbids commit and push, but C5 removes the only mechanism that could stop it and PERM1B forbids enforcing anything. PERM2 is a wish. | Back it with a git pre-push/pre-commit hook keyed on an agent marker, the shape of the existing branch-name gate — or downgrade PERM2 to a brief instruction and say so. |
| F2 | H2 vs LIM1, BRIEF goal 5 | With no availability check at all, the plugin cannot know a role is unfillable until after it spawns and burns the agent — so LIM1's start-time offer cannot be built. Goal 5 asked for a real probe: installed is not subscribed. | Narrow H2 to no usage-limit prediction, and keep one cheap start-time authentication check per provider the pattern names. |
| F3 | ACC2 vs H1 | ACC2's recommended option blocks a replacement planner from reading its dead predecessor's checkpoint — which is the one thing H1 exists to provide. | Scope B2's blindness to live peer instances, not to the role: a replacement taking over a closed instance reads that instance's checkpoint. |
| F4 | PERM2 vs PAT1 | PAT1 promises a fuller pattern covers light work end to end, but PERM2 denies its builder the last three steps of end to end. | Make the commit and push grant a per-role field in the pattern data, granted to the builder role only. |
| F5 | P1, ledger | A pattern is priced in agents and messages, not in provider window. Every Claude session on one account shares one window, the contact agent included. | Price a pattern in window share per provider account, and refuse or resize one that leaves the contact agent no headroom. |
| F6 | L1 vs L2, H3 | A Codex debate planner on a weekly limit needs a park of up to seven days, which the 5-hour horizon forbids. | State the horizon per provider window, and name the action when a reset lies beyond it. |
| F7 | PERM1, PERM1B | One shared worktree plus no limits has no write arbitration: one agent's checkout or reset destroys another's uncommitted work. | Give each role an owned output path in the pattern data; an agent writes only there plus files its brief names. |
| F8 | PERM3, ACC1, T1 | The manifest has no owner when the contact session dies, and no feature key — so a second feature's cleanup can kill the first feature's agents by name. | Key the manifest, every agent name and every scheduled task by feature id and contact-session id; a new contact agent adopts by that key. |
| F9 | LIM3 | A killed process writes nothing, so LIM3's unfinished mark never gets written and the last complete-looking checkpoint stays on disk. | Invert the stamp: a checkpoint is born unfinished at every write, and only a clean exit stamps it finished. |
| F10 | C3, ENV2 vs S2 | Unattended, an agent that wakes into a detection-versus-config conflict blocks on a question nobody is there to answer. | Split C3 by human presence: ask when present, park with the conflict named when not. |
| F11 | S4 vs BRIEF goal 3 | The facts this feature produced are environment facts, not feature facts — quota windows, reset behaviour, spawn and kill behaviour. Dropping them makes every later run pay again. | Let the terminal sync-harness subtask promote environment-class rows into a durable register before deletion; feature-class rows stay disposable. |
| F12 | PERM3, LIM2, B2 | Nothing gives a live view of a running team, so a parked team and a hung team look identical. | Have the manifest carry each agent's role, model, state and park-until time, and name it as a read source for the read-only dashboard. |

Axis coverage: symptom-over-pain produced only F2; blocked-legitimate-scenario,
conflicting-pair and unaddressed-adjacent-pain each produced several.
