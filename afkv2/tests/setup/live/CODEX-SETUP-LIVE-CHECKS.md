# Codex setup live checks (owner-run)

These checks change the global Codex config on the owner's machine (PLAN.md
decision D-S-8), so the owner runs them. Run them from a test repository, not
from a work repository. Record each result in `docs/afk/afkv2/plan-s3/JOURNAL.md`.

## 1. Hook trust review gives a fired record

1. Enable afkv2 in Codex next to v1.
2. Start a new Codex session in the test repository. Trust the afkv2 hooks in
   Codex's hook trust review.
3. Expect: `%LOCALAPPDATA%\afkv2\hook-fired-codex.txt` exists, with a time
   after this session started.
4. Expect: the session context holds `afkv2-core-behaviors end <sha12>`.

## 2. Takeover from a Codex session

1. In the Codex session of check 1, run `/afkv2:setup`.
2. Expect: `takeover` answers `"ok": true`; `proof.required` names `codex` and
   every other provider that still has a v1 block.
3. Expect: `codex plugin list` shows `afk@afk-toolkit` disabled and
   `afkv2@afk-toolkit` enabled; `%LOCALAPPDATA%\afkv2\backup\codex\config.toml`
   holds the config from before.
4. Start a new Codex session. Expect: the afkv2 end marker is in context and no
   v1 rule text is.

## 3. Untrusted hook keeps the v1 block

1. Before check 1, with the afkv2 hooks not trusted, run `/afkv2:setup` from a
   Claude session on a machine where `~/.codex/AGENTS.md` holds the v1 block.
2. Expect: `takeover` answers `"ok": false`, `v1_block` is `kept`, and a reason
   names the Codex hook trust review. Both instruction files are unchanged.

## 4. Switch back

1. Run `/afkv2:setup switch-back`.
2. Expect: `codex plugin list` shows only `afk@afk-toolkit` enabled; the v1 block
   is back in both instruction files; `npm ls -g lavish-axi` shows the version
   from before setup.
