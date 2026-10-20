midnightblur/afk-driver@cedb95982927650f83f340e01bd26a382ac1d76c · closed-with-frontier · boundaries 13/14 · unverified 3 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-078-transport-setup-dispatcher-ground/COVERAGE.json

## Answer

At head cedb959 the setup register and the dispatcher take a transport family and a C15 note edit with no code change outside them.

- **Dispatcher.** afk_adapter_kind loads the configuration once per shell, then reads AFK_CFG_<FAMILY>. For transport that is AFK_CFG_TRANSPORT, which only an empty `transport:` section sets, to ''. A caller that sets the kind after its own load keeps it; one that sets it before the load loses it. Plan D-43's premise ("no configuration ever sets AFK_CFG_TRANSPORT") is false.
- **Callers.** In code only the forge family is dispatched (gc-check.sh:136, forge_ledger.py:760). A cli kind runs as a subprocess and must load its own shell view.
- **Check E** walks every adapters/<family>/<kind>/ with no gate edit. CONFIG.md:136 already lists the four transport kinds.
- **Native-contract check A** scans ADAPTERS.md, every adapters/**/CONTRACT.md and MANIFEST.md for `Claude Code` and `Codex`.
- **Genericity gate** blocks an added ticket-shaped id such as the catalog id TR plus a number in plugin .md.
- **C15.** No code reads it. Check E reads its heading only when an adapter.json register names C15. The setup election is built by the agent from MANIFEST.md. install_block.py reads only marker blocks.
- **Setup statuses.** SKILL.md has no status for a row skipped with no human (inferred: the note is that rule's only home).

## Sites

- hooks/lib/adapter.sh:29-52, :108-113; hooks/lib/config.sh:17-33
- scripts/afk-config.py:273-280, :770-775, :1330-1358, :1443-1449; scripts/tests/test_afk_config.py:719-737
- hooks/lib/adapter_registry_check.py:41-147; CONFIG.md:136
- hooks/native-contract-gate.sh:90-152; hooks/genericity-gate.sh:114-168, :250-259; hooks/lib/sensitive-patterns.tsv:8-9
- skills/afk/setup/SKILL.md:26-37, :75-139; skills/afk/setup/MANIFEST.md:237-262, :597-622
- skills/afk/setup/scripts/install_block.py:53-363
- skills/afk/gc/scripts/gc-check.sh:85-136; skills/afk/review/scripts/forge_ledger.py:743-771
- ADAPTERS.md:186-188 (a README parity table that does not exist)

## Frontier

- B14: herdr's vendor installer and its uninstall, live herdr sessions, installed plugin copies, other repositories. These are outside this repository.

## Unverified (none load-bearing)

- c-6a8362f2: the hit set holds every reference over the name forms searched. This is the standard completeness caveat.
- c-32c9b5e0: herdr's own uninstall command and what it removes (vendor only; SDD §13 Q3).
- c-77711274: how committed docs/afk files carrying catalog ids passed the genericity gate.
