# Adversary report — 0003-manifest-module

- Verdict: `findings` — probed=187, crit=0 high=0 med=0 low=5
- Target: `cli:C:/Users/mvu/PersonalProjects/afk-driver-agent-teams`. `scripts/team/` copied to a scratch folder and imported as `from team import manifest`.
- Platforms: Windows 11, and WSL Linux on a `/tmp` folder. Date: 2026-10-19.
- Promise sources: contract `## Goal / Scope / Acceptance / Context excerpts`, SDD §4 field tables, SDD §6 table A1-A7, plan decisions D-48 and D-49.
- Written by the executor from the adversary's returned body: the harness refused the adversary's own file write.

## Information diet

- Read: the contract; SDD §4 and §6; `plan/DECISIONS.md` D-48 to D-50; the module's `help()` output and public constants; `LANGUAGE.md`; `REPORTING.md`.
- Entered without a read: the harness git status block (branch name, the file list of `plan/review/`, 5 commit subject lines of this branch); D-50 names review finding ids and `.claude/wiring-ious.md`, not their content.
- Not read: module source, `scripts/tests/`, any diff, any commit body, any review report, `.claude/wiring-ious.md`, the earlier copy of this report.
- Ruling: not tainted. No diff, test or finding content entered; every lock scenario comes from SDD §7 row "Manifest write collision" and ADR-0003. If "any commit of this branch" includes subject lines, read the verdict as `tainted`.

## Findings (most severe first)

### F1 — On Linux, a writer that meets a stale lock among 8 or more writers raises instead of waiting
- class `robustness`, severity `low`
- Breaks: Acceptance "while the mutex is held the losing writer waits, a stale lock is stolen atomically" (SDD §7, ADR-0003).
- Observed on WSL Linux only, all writers released at one instant onto a lock folder 120 s old: 8 writers × 1 entry, 2 of 60 trials; 8 × 2, 2 of 100; 16 × 1, 9 of 50 had 1 failed writer.
- The failing call raises `ManifestError: cannot write the manifest of adv-steal-14: [Errno 2] No such file or directory: '<W>/runs/p8/adv-steal-14/manifest.lock/owner'`; its entry is not recorded. No silent loss: lost entries equal raised errors in every trial.
- 0 failures with 2 or 3 writers, with no stale lock, and on Windows (25 trials of 16 writers).
- Impact: the caller gets the generic `ManifestError`, not `ManifestBusy`, so it cannot tell "retry" from "bad data" (inferred from the class docstrings).
- Repro (Linux):
```python
import os, time, multiprocessing as mp
from team import manifest as m
BASE = {'role': 'r', 'model': 'x', 'stage': 's', 'pattern_step': 'p', 'lifespan': 'Turn'}

def worker(root, f, wid, go, q):
    while time.time() < go:
        pass
    try:
        m.record_entry(root, f, dict(BASE, agent_id=f'p{wid}'))
        q.put(None)
    except Exception as e:
        q.put(f'{type(e).__name__}: {e}')

def trial(root, f, procs=16):
    m.adopt_manifest(root, f, 'S1')
    lock = os.path.join(os.path.dirname(m.manifest_path(root, f)), 'manifest.lock')
    os.mkdir(lock)
    old = time.time() - 120
    os.utime(lock, (old, old))
    q, go = mp.Queue(), time.time() + 1.0
    ps = [mp.Process(target=worker, args=(root, f, w, go, q)) for w in range(procs)]
    for p in ps:
        p.start()
    errors = [e for e in (q.get() for _ in ps) if e]
    for p in ps:
        p.join()
    return errors  # expected []; observed in 9 of 50 trials: one ManifestError naming manifest.lock/owner
```

### F2 — A calendar-impossible timestamp passes validation and is stored
- class `spec`, severity `low`
- Breaks: SDD §4 agent entry rows `started-at` and `park-until time` ("UTC, ISO 8601, to the second"); Acceptance "Manifest validation is hand-written inside the module" (SDD §9).
- Actual: `record_entry(root, f, {..., 'agent_id': 'a', 'started_at': '2026-02-30T25:61:61Z', 'park_until': '0000-00-00T00:00:00Z'})` succeeds and `read_manifest` returns both values unchanged; `park_until='2026-13-45T99:99:99Z'` also succeeds.
- Expected: `ManifestError` naming the field, as for `'2026-10-19 10:00'`.
- Impact (inferred): the earliest park-until time decides when the wait job ends (SDD §6 A3); a later parser fails or orders it wrongly.

### F3 — A format version of `1.0` is read as known, and the file is rewritten
- class `spec`, severity `low`
- Breaks: SDD §4 row "format version" (integer, known versions only, unknown → foreign file); Acceptance "A manifest with an unknown format version is treated as a foreign file: not read, not deleted, reported once".
- Repro: write `{"format_version": 1.0, "feature": "adv-foreign-vfloat", "owning_session": "X", "owner_generation": 1, "agents": [], "processes": []}` to `manifest_path(root, 'adv-foreign-vfloat')`, then call `adopt_manifest(root, 'adv-foreign-vfloat', 'S9')`.
- Actual: no `ForeignManifest`, no stderr line; the file is rewritten with `owning_session` `S9` and `owner_generation` 2, `format_version` stays `1.0`. The string `"1"` and boolean `true` are refused as foreign.
- Expected: `ForeignManifest` with the file byte-identical, or a `ManifestError` for a non-integer version.

### F4 — `remove_process` answers False for an existing process entry when the id is not an integer
- class `robustness`, severity `low`
- Breaks: D-48 `remove_process` — "False when no entry holds it"; the process entry is keyed by process identifier (SDD §4).
- Repro: `record_entry(root, f, {'pid': 4242, 'owner': 'S1', 'label': 'L', 'started_at': 't'})`, then `remove_process(root, f, '4242')` → `False`, entry still present; `remove_process(root, f, True)` → `False`, entry still present; `remove_process(root, f, 4242.0)` → `True`, removed.
- Expected: `ManifestError` for a non-integer id, as `record_entry` raises for `'pid': '104'`.
- Impact (inferred): a cleanup caller that passes the id as text concludes "no entry" while the line stays.

### F5 — A stale lock path that is a regular file blocks every write on Linux, but is stolen on Windows
- class `robustness`, severity `low`
- Breaks: Acceptance "a stale lock is stolen atomically" (SDD §7).
- Repro: `adopt_manifest(root, f, 'S1')`; create a regular file `<run folder>/manifest.lock` with an mtime 60 s old; set `m.LOCK_WAIT = 3.0`; call `record_entry`.
- Actual: Windows — the write succeeds and the file is removed. Linux — `ManifestBusy: manifest of adv-lock-f stayed busy past 3s`, the file is kept and every later write fails the same way.
- The module never creates a regular file at that path (inferred from the docstring "lock folder"), so the trigger is disk damage or a foreign tool.

## Promises that held

| Promise (source) | Scenarios | Result |
|---|---|---|
| Lifecycle table A1-A7, refusal names the move (SDD §6, ADR-0002) | all 49 from/to pairs on Windows and Linux; unknown, `None`, int, case and space variants of the target; unknown agent-id | 0 mismatches; refusal names agent, from and to; unknown agent gives `ManifestError` |
| New entry starts in starting; state changes only through move (SDD §4, §6) | new entry with `state` cleaned or working; update with `state` | refused |
| Cleaned is terminal; resume is a new entry (SDD §6, AC-056) | lost → starting; re-record a cleaned id; new entry with the same session id | refused; new entry accepted in starting |
| Adoption (AC-015) | same session twice; S1 → S2 → S1; 4 sessions racing, 20 trials per system | same session keeps the generation; each takeover adds 1; the race ends at generation 5 every time |
| Owner generation copied into the entry (SDD §4) | entry after 2 takeovers; caller-given `owner_generation` | copies the header value; caller value refused |
| Foreign file (SDD §4, D-49) | versions 2, 0, `"1"`, `true`, missing, JSON list; 7 calls each | every call raises `ForeignManifest`; file byte-identical; 1 stderr line per process |
| Malformed version-1 file | bad JSON, empty file, bad header, wrong feature, bad agent | `ManifestError`, file untouched |
| Hand-written validation (SDD §9) | 20 bad agent and process entries | `ManifestError` naming the field |
| Checkpoint path (AC-024, SDD §4) | 2 features × 2 roles; `..`, separators, absolute path, empty | `<root>/<feature>/checkpoints/<role>.json`; unsafe names refused |
| No lost update; the losing writer waits (SDD §7, I10) | 6 writers × 40 + 2 movers + 4 readers per system; 8 and 16 writers on a stale lock on Windows | 0 lost, 0 errors |
| No half-written read (ADR-0003) | 33,288 reads on Windows and over 19,000 on Linux during writes; writer killed mid-write, 8 trials per system | every read parses |
| Busy and stale lock (SDD §7) | fresh lock, 3 s wait; live holder refreshing for 14 s; lock released after 2 s; abandoned lock; non-empty stale lock folder | `ManifestBusy`, nothing written; writer waits; lock stolen at 10 s; lock stolen at once |

## Observations (no promise broken)

- A writer killed mid-write leaves `manifest.json.<pid>.<hex>.tmp` in the run folder (4 of 8 trials on Windows, 6 of 8 on Linux); the next writer does not remove it. The cleanup step owns the run folder (SDD §4; unverified: that cleanup removes unknown files).
- On Windows, features `adv-dot.` and `adv-dot` share one folder, as do `adv-Case` and `adv-case`; the second call raises `ManifestError ... malformed header` and changes nothing, but the message does not name the collision.

## Earlier run (verdict tainted, not the gate verdict)

The first run reported `tainted` because the same git status block held commit subjects; it probed 231 scenarios and found 0 critical, 0 high, 3 medium, 6 low. Its medium findings, for the feature gate to weigh:
- correctness — a lock holder that stalls 10 s or more between its last lock check and its rename (reproduced by patching `os.replace` to sleep 15 s) overwrites a write published by a writer that took the stale lock; both calls report success.
- robustness — under WSL with the run directory on a Windows drive (`/mnt/c`), `read_manifest` returned `None` during a concurrent write in 15 of 4628 reads; no update was lost.
- robustness — `pid=0` is accepted for agent and process entries while `-1` is refused (inferred risk: on POSIX, `kill(0)` signals the caller's own process group).

ADVERSARY: findings — probed=187 crit=0 high=0 med=0 low=5 report: docs/afk/agent-team-topology/plan/review/0003-manifest-module-adversary.md
In plain terms: The module that tracks a team run's agents held up on all its main promises, including its state rules and writes that happen at the same time, but it has 5 small gaps; none of them blocks shipping.
