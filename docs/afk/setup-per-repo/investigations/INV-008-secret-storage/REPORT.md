midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-008-secret-storage/COVERAGE.json

## Answer

The plugin keeps one Jira credential set per home folder, in plain text, and cannot tell two sets apart. `setup_secrets.py` writes the three `JIRA_*` values only into `~/.claude.json` `mcpServers.tracker.env` and sets no file mode. Its only agent-shell gate is a non-empty the `claude` session marker; it reads no `codex` marker, makes no terminal check, and no hook blocks the script. Forge tokens stay in the `gh`/`glab` login store; only the branch-protection read takes a token from the environment.

## Sites

- `skills/afk/setup/scripts/setup_secrets.py:147-148`: the one gate, the `claude` session marker. No `CODEX_*`, the `codex` session marker or `isatty` read. Run under a `codex`-like environment with a temp home folder: passes preflight; closed stdin gives an `EOFError` traceback at `input()` (`:80-92`); with piped answers, `getpass` (`:215`) waits on the Windows console; nothing written.
- `setup_secrets.py:199-252`: asks base URL and email, reads the token with `getpass`, checks `{base}/rest/api/3/myself`, then writes `env` into `mcpServers.tracker` via `tracker_registration.register` (`tracker_registration.py:59-78`, one key `tracker`, replaced whole, no site or account key).
- `setup_secrets.py:105-109`: `write_text` to `.claude.json.afk-tmp`, then `os.replace`. No chmod, `os.open` mode or umask. `0o600`/`0o700`: 0 hits in code.
- `setup_secrets.py:243-246`: `shutil.copy2` to `~/.claude.json.bak-<stamp>` on every run; the copy keeps the old token; no code deletes it.
- `setup_secrets.py:258-278`: `gh`/`glab auth login`, no `--hostname`; the CLI keeps the token.
- `skills/afk/setup/scripts/codex_marketplace_ref.py:44,94,112,136`: rewrites `${CODEX_HOME:-~/.codex}/config.toml`, keeps its mode, leaves a plain-text `config.toml.bak-<UTC>` copy. No setup code writes the Jira block to `config.toml`.
- `adapters/tracker/jira/api.py:107-127` `resolve_creds_env`: fixed `CRED_KEYS`; per field, process env, then the first `tracker` env block at any depth in `~/.claude.json` (`:74-87`), then `~/.codex/config.toml` (`:93`, ignores `CODEX_HOME`). Takes no argument; fields from two sources can mix (probe with fake values confirmed).
- `api.py:130-136,464,649`: `load_creds` on every tracker call and `--check-creds`; no write, no print of a value. Other callers: `publish_bug.py:299`, `publish_prd.py:267`, `publish_meeting.py:128`, `scripts/afk-config.py:955`, `developer_values.py:116`.
- `adapters/tracker/jira/adapter.json:25`, `scripts/afk-config.py:656-659`: `jira.credentials-env` declared and type-checked; no code reads its value.
- `.mcp.json`, `.mcp.codex.json`: no env block; the secret lives only in the user-scope entry.
- `adapters/forge/branch_protection.py:183,189,260`: `GH_TOKEN`/`GITHUB_TOKEN`, `GITLAB_TOKEN`, else `gh auth token` for github.com; token in memory only. `forge.sh` and github-issues use the CLI login.
- `hooks/hooks.json:56-79`, `hooks/hooks.codex.json:56-79`: PreToolUse runs the repository handlers and `protected-branch-guard.py`; neither names `setup_secrets`.
- `hooks/lib/provider.sh:24-62`, `provider_facts.py:15-31`: the shared detector treats the `codex` session marker as the `codex` marker; `setup_secrets.py` does not use it.
- Tests: `test_tracker_jira.py:130-265`, `test_tracker_registration.py:135-219`. Unguarded: the the `claude` session marker refusal, prompts, write and file mode, `.bak` copy, `--check-creds`, a non-afk `tracker` entry used as a source.
- Documents the code refutes: `skills/afk/setup/SKILL.md:122-124` (refusal by "no tty"), `MANIFEST.md:977`, `CONFIG.md:294`, `adapters/tracker/jira/CONTRACT.md:29-34`, `GLOSSARY.md:333`, `mcp-servers/tracker/server.py:16-19`.
- Inference: on POSIX with no controlling terminal, `getpass` reads stdin, so an agent shell without the `claude` session marker could pipe a token through and the script would write it. Not run.
- Inference: the rewritten `~/.claude.json` gets the default mode (typically 0644 on POSIX), not owner-only.

## Frontier

- B14, 6 nodes: harness env injection and scope choice for the `tracker` entry (`server.py:18`); gh/glab token store, file mode and host choice (`branch_protection.py:140,184`, `gitlab/forge.sh:380`, `github-issues/api.py:101`); Jira Cloud token reach across sites (`api.py:142`).

## Unverified

- Seed claim that the name set reaches every reference (not load-bearing): the effect-primitive counter-search found 97 code sites outside it, now in the ledger.
