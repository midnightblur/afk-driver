# A milestone applies ad hoc, with no release, reinstall or reload

> Layer: Requirements
> Context ticket: 211

The main agent applies each milestone by reading the changed files from the plugin worktree and following them in place of the installed copy, for the rest of its session. Nothing is released, reinstalled or reloaded. Hooks run from the installed plugin, so a hook change is best effort; a critical one gets a reinstall for that session, worked out case by case. The developer chose this because afkv2 changes favour instructions over scripts.

## Considered Options

- Load the plugin from the worktree for the session and reload it at each milestone. Rejected by the developer before the grill: "Draft works don't need to be released and installed as plugin to be reloaded."
- Reinstall the plugin from a local marketplace at each milestone. Rejected for the same reason; on Codex it also changes the plugin for every session on the machine.
