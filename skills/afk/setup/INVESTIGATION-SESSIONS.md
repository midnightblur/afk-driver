# INVESTIGATION-SESSIONS.md — the opt-in code-question default

One home for the block `MANIFEST.md · H10` installs into the user-global
steering file(s) — targets + copy command live in that entry. Everything
between the sentinel lines lands verbatim; edit here.

Deliberately carries no scope guard: a wrong answer about existing code costs
the same in a repository the plugin never touches.

<!-- afk:investigation:start -->
## Code questions: investigate to closure

A question or claim about existing code — how X works, what calls or depends on
X, what breaks if X changes, what edge cases exist, whether Y exists — is
answered by running `/afk:investigate`, never from a partial read. Every
session, every repository, plugin skill running or not. State facts only from
its ledger, and list its `unverified` and `frontier` items in the reply. An
absence claim with no closed ledger behind it is written `unverified: <reason>`.
Doctrine, reference only: `INVESTIGATION.md` at the installed plugin root.
<!-- afk:investigation:end -->
