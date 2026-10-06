"""The H6 `developer:` values `setup_secrets.py` asks for, and the file each goes to.

Split out of `setup_secrets.py` (which runs on import) so a test can drive it.
A run writes only the keys it asked about: a key this repository has no use
for may be another repository's answer, so it is never removed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

DEVELOPER_KEYS = ("trackerAssignee", "mrReviewer", "mrAssignee", "worktreeBasePath", "ideBinary")


def read_block(p: Path) -> dict:
    """The `developer:` mapping of a config file, or an empty dict.

    Deliberately small: one flat block of `key: value` lines under one heading,
    which is all this block is ever allowed to be.
    """
    if not p.is_file():
        return {}
    out, inside = {}, False
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[:1].isspace():
            inside = line.strip() == "developer:"
            continue
        if inside and ":" in line:
            key, _, value = line.strip().partition(":")
            value = value.strip().strip("'\"")
            if key.strip() in DEVELOPER_KEYS and value:
                out[key.strip()] = value
    return out


def write_block(p: Path, values: dict) -> None:
    """Replace the `developer:` block, leaving every other line untouched.

    The file may hold keys this script knows nothing about, so it is edited
    rather than rewritten.
    """
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
    kept, skipping = [], False
    for line in lines:
        if not line[:1].isspace() and line.strip():
            skipping = line.strip() == "developer:"
            if skipping:
                continue
        elif skipping:
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()

    block = ["developer:"]
    for key in DEVELOPER_KEYS:
        value = values.get(key)
        if value:
            needs_quotes = any(c in str(value) for c in ":#") or str(value).strip() != str(value)
            block.append("  %s: %s" % (key, ('"%s"' % value) if needs_quotes else value))

    body = "\n".join(kept + ([""] if kept else []) + block) + "\n"
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(p)


def configure(*, repo: Path, machine: Path, shared: Path | None,
              tracker_kind: str, forge_kind: str, account_id: str | None,
              ask: Callable, yes: Callable, ok: Callable, skip: Callable, warn: Callable,
              resolve: Callable[[str], str | None],
              forge_user: Callable[[str], str | None],
              ide_guess: str | None = None) -> list[Path]:
    """Ask for this developer's values and write them. Returns the files written.

    `resolve(key)` is the effective value now; it pre-fills each prompt, so a
    machine-wide answer is offered again rather than retyped.
    """
    overlay = repo / ".afk" / "config.local.yaml"
    if read_block(overlay):
        skip(f"This checkout already has its own developer block in {overlay} — keeping it there.")
        target = overlay
    elif shared is not None and read_block(shared):
        skip(f"This repository already has its developer block in {shared} — keeping it there.")
        target = shared
    elif shared is None:
        warn("this repository has no git directory to share a file from — using the machine file")
        target = machine
    elif yes(f"Write these answers for this repository and all its worktrees, to {shared}? "
             f"No writes them to {machine}, the default for every repository"):
        target = shared
    else:
        target = machine
    cfg = read_block(target)
    if cfg:
        skip("Existing values — Enter keeps each current value.")

    def current(key: str) -> str | None:
        return cfg.get(key) or resolve(key)

    # These name a PERSON, so nothing defaults them: each developer answers for
    # themselves, and an empty answer is re-asked rather than quietly meaning someone else.
    if tracker_kind == "none":
        skip("tracker: none — no assignee asked for; other repositories' values are kept")
    else:
        # Pre-filled with the account this developer is: the validated Jira
        # accountId, else the GitHub login `gh` is authenticated as.
        prefill = current("trackerAssignee") or account_id
        if not prefill and tracker_kind == "github-issues":
            prefill = forge_user("github")
        cfg["trackerAssignee"] = ask(
            "assignee account id or email (yours, unless work goes to someone else)", prefill)

    if forge_kind == "none":
        skip("forge: none — no reviewer or assignee asked for; other repositories' values are kept")
    else:
        # No pre-fill beyond an earlier answer: nobody else may pick who reviews your work.
        answer = ask("reviewer (forge username, or `none` to leave it unset)", current("mrReviewer"))
        if answer.strip().lower() == "none":
            # Recorded, not dropped: a recorded answer tells the doctor this
            # developer was asked, and every consumer reads it as "no reviewer".
            cfg["mrReviewer"] = "none"
            skip("reviewer recorded as none — the change Ready flip will fail closed")
        else:
            cfg["mrReviewer"] = answer

        # Recorded as `none` too, so it overrides an assignee a broader file sets.
        answer = ask("MR/PR assignee (forge username, or `none` for no assignee)",
                     current("mrAssignee") or forge_user(forge_kind))
        cfg["mrAssignee"] = "none" if answer.strip().lower() == "none" else answer
        if cfg["mrAssignee"] == "none":
            skip("assignee recorded as none — every MR/PR opens with no assignee")

    # A location belongs to one repository, so it never goes to the machine file.
    wt_target = shared if target == machine and shared is not None else target
    wt_cfg = cfg if wt_target == target else read_block(wt_target)
    machine_wt = read_block(machine).get("worktreeBasePath")
    wt_effective = resolve("worktreeBasePath")
    if wt_cfg.get("worktreeBasePath"):
        wt = ask("worktree base path for this repository", wt_cfg["worktreeBasePath"]).replace("\\", "/")
        wt_cfg["worktreeBasePath"] = wt
    elif machine_wt and wt_effective == machine_wt:
        warn(f"{machine} sets worktreeBasePath for every repository: {machine_wt}")
        wt = ask("worktree base path for this repository", machine_wt).replace("\\", "/")
        if wt != machine_wt:
            wt_cfg["worktreeBasePath"] = wt
    elif wt_effective:
        ok(f"worktree base path resolves to {wt_effective} — leaving it unset")
        wt = wt_effective
    else:
        wt = ask("worktree base path (cannot be derived here)", "").replace("\\", "/")
        if wt:
            wt_cfg["worktreeBasePath"] = wt
    if wt and not Path(wt).exists() and yes(f"{wt} does not exist. Create it?"):
        Path(wt).mkdir(parents=True, exist_ok=True)
        ok(f"created {wt}")

    ide_default = current("ideBinary") or ide_guess
    if ide_default:
        cfg["ideBinary"] = ask("IDE binary (optional)", ide_default).replace("\\", "/")

    written = [target]
    write_block(target, cfg)
    ok(f"wrote the developer block in {target}")
    if wt_target != target and wt_cfg.get("worktreeBasePath"):
        write_block(wt_target, wt_cfg)
        ok(f"wrote this repository's worktree base path in {wt_target}")
        written.append(wt_target)
    return written
