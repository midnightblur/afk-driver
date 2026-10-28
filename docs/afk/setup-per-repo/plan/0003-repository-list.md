# 0003-repository-list — the machine-wide repository list and its short-name markers

## Goal
Add the repository list module: the machine-wide list of main checkouts in `~/.afk/repositories.json` and one short-name marker per entry in `<root>/<shortName>/.afk-repository`, written only through the safe writer. Its interface finds the entry for any path (main checkout, worktree, subfolder), lists all entries for setup only, adds, removes and repoints a short name.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "repository list (new)"
- SDD: SDD.md#§4 L3 — Data Architecture — "Repository list file (new)", "Short-name marker (new)", relations "list entry → marker" and "list entry → main checkout"
- SDD: SDD.md#§6 L5 — Domain Model — invariants owned by the repository list
- SDD: SDD.md#§7 L6 — Process & Coordination — row "add or remove a repository"; failure rows "run stops after marker, before entry" and "main checkout folder gone"
- ADR: adr/design/0005-shared-safe-writer.md — markers written under the list's lock
- ADR: adr/requirements/0005-two-clones-two-repositories.md — two clones are two entries

## Scope
- scripts/repo_list.py
- scripts/tests/test_repo_list.py

## Seams
- use: safe writer `_atomic_write_locked` from `install_block` — every list and marker write goes through the safe writer (INV-010)

## Acceptance
- [ ] A path to a main checkout is added; a path to a worktree or a subfolder adds that worktree's main checkout; the stored path is absolute with links resolved and compares without case on Windows (PRD §Repository list AC-003; SDD §4)
- [ ] A bare clone, a folder that is not a git repository, and a path already in the list are each refused with its reason (PRD §Repository list AC-004)
- [ ] Two clones of one remote are two entries with their own short names (PRD §Repository list AC-005; ADR-0005 requirements)
- [ ] An entry whose main checkout folder is gone is reported missing and is removed only on an explicit remove call (PRD §Repository list AC-006; SDD §7)
- [ ] The list lives in `~/.afk/repositories.json` with `schema` 1; a higher `schema` is refused with an update message; no entry is ever written to a repository file (PRD §Repository list AC-007; SDD §4)
- [ ] A short name is one folder name (letters, digits, dot, dash, underscore), unique in the list, defaulting to the main checkout folder name; a clash is refused so setup can ask for another (PRD §Catalog R R-05; SDD §4)
- [ ] Add writes the marker holding the normalized path first, then the entry, both under the list's lock, so no lock file sits in a folder under the root; an add stopped after the marker is completed by the next add, which reuses the marker (SDD §7 failure row "run stops after marker, before entry"; ADR-0005)
- [ ] A marker in a short name's folder holding a different path refuses that short name (PRD §Catalog R R-06)
- [ ] Remove deletes the marker and its folder only when the folder is empty; otherwise the marker stays (SDD §4 relation "list entry → marker")
- [ ] Repoint gives an entry a new main checkout path, for an entry whose folder is gone (PRD User Story 4)
- [ ] Finding the entry for a path reads only the list file; the all-entries call is the one only setup uses (PRD §Session scope AC-080; SDD §5 row "read another listed repository's settings")
- [ ] Implements the public interface in SDD §8 row "repository list (new)" unmodified: find entry for a path; all entries (setup only); add; remove; repoint a short name (SDD §8)
- [ ] Conforms to ADR-0005: every write goes through the safe writer (ADR-0005)

## Produces
- scripts/repo_list.py#def find_entry( — the list entry whose main checkout holds a path, or none
- scripts/repo_list.py#def all_entries( — every entry; called only by setup
- scripts/repo_list.py#def add_repository( — add a main checkout with its short name and marker
- scripts/repo_list.py#def remove_repository( — remove an entry; marker and folder deleted only when empty
- scripts/repo_list.py#def repoint_repository( — give an entry a new main checkout path

## Consumes
- 0001-safe-writer scripts/safe_write.py#def update_locked( — locked read-modify-write with change refusal

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `unit` tier; `scripts/tests/test_repo_list.py` against real temporary git repositories: main checkout, worktree, subfolder, bare clone, non-repository folder, duplicate, two clones, gone folder, higher schema, short-name clash, foreign marker, stopped add, remove with and without a worktree in the folder | list behaviour and invariants on real repositories |

## Context excerpts
> (SDD §8 row "repository list (new)") the list and its markers | find entry for a path; all entries (setup only); add; remove; repoint a short name | safe writer | repository list

> (SDD §4 Repository list file) `schema` | integer | 1 | must be 1; higher refused · `repositories` | list of entries | empty list | order is the order added · `entry.path` | absolute path of a main checkout, links resolved | a worktree path is stored as its main checkout | unique; compared without case on Windows · `entry.shortName` | one folder name: letters, digits, dot, dash, underscore | the main checkout's folder name | its folder under the root carries the matching marker | unique in the list

> (SDD §4 Short-name marker) `path` | the same normalized path as `entry.path` | written when setup takes the short name; written under the list's lock, so no lock file sits in the folder | one per folder | removed when the entry is removed and the folder holds no worktree

> (SDD §4 relations) list entry → marker | 1 to 1 | list module | marker kept while the folder holds a worktree; empty folder and marker deleted · list entry → main checkout | 1 to 1 | folder gone: entry reported missing; removed only on the developer's answer

> (SDD §6 invariants) a listed path is unique and is a main checkout | repository list | list module | setup · a short name is unique and its folder's marker holds that path | repository list | list module | setup, placement

> (SDD §7) add or remove a repository | developer in setup | single lock on the list file | read-after-write | list lock; safe writer refuses a changed file · run stops after marker, before entry | marker with this path, no entry | next add reuses the marker | list module

> (PRD §Repository list) AC-003 A path to a main checkout is added. A path to a worktree adds that worktree's main checkout. AC-004 A bare clone, a folder that is not a git repository, and a path already in the list are refused, each with its reason. AC-005 Two clones of one remote are two entries. AC-006 An entry whose folder is gone is reported, and setup offers remove or a new path. AC-007 The list survives a new session and a reboot. A list entry is never written to any repository file.

> (PRD §Catalog R) R-05 a repository's short name is its main checkout folder name | on a clash with another listed repository, setup asks for another short name · R-06 the short name's folder under the root is absent or was made by setup for that repository | setup asks for another short name

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0001-safe-writer

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
