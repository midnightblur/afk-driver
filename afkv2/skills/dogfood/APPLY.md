# Apply a milestone note

You are the main agent. Apply only a note that `check-note` answered ok, by step 3 of [SKILL.md](SKILL.md); from a note that fails the check, apply nothing. The note fields are in [NOTE-FORMAT.md](NOTE-FORMAT.md).

Apply each `changed` row of the note at once, by its change kind, with no question to the developer. Nothing is released, installed or reloaded: the installed plugin does not change, and each apply lasts only for this session. Write no plugin file, in a worktree or in the installed plugin.

## The change kinds

1. **CK-1, a skill.** From now on, read that skill from its worktree path in place of the installed copy, for the rest of this session. "This skill's folder" in its text is its folder in the worktree. A skill that you are running now: follow the new text at once, from the current step of the run on, and say so to the developer.
2. **CK-2, a script of a skill.** Run the script from its worktree path. The skill text of CK-1 gets you there: a skill read from the worktree runs its scripts from the worktree. A script whose skill the note does not change: read that skill from the worktree too, by CK-1.
3. **CK-3, the core behaviors.** Read the changed text from its worktree path. Follow it as a session instruction, in place of the core behaviors that the session start printed.
4. **CK-4, a hook or the hook registration.** Hooks run from the installed plugin, so this part is best effort: it may not apply in this session. Tell the developer so, with the `best-effort` line of the note for that path.

A `removed` row of CK-1 to CK-3: from now on, act as if the file is gone. Do not use the removed skill, script or text, and do not fall back to its installed copy. A removed CK-4 row is best effort, as each CK-4 row: the installed hook can still run.

## The redo

The note names a delta in `redo`: the work that you already did under the old text and that comes out differently under the new text. Redo that delta at once, under the new text, with no question to the developer. Then tell the developer what you redid. `redo: none`: there is nothing to redo.

## Tell the developer

After the apply, tell the developer in 1 message:

- what you applied: each row, its path and its change kind;
- how to try it: the `use` text of the note;
- each part that is best effort (CK-4), and that it may not apply in this session;
- a skill that you switched to the new text while it ran;
- what you redid;
- that the applied changes last only for this session, and the installed plugin does not change.
