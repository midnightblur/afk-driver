"""The v1 strings the setup tests write and expect, in one place.

Literals, not imports of `setup_v1_facts`: a changed name there must fail a test.
"""

V1_ID = "afk@afk-toolkit"
NEW_ID = "afkv2@afk-toolkit"
V1_PLUGIN_NAME = "afk"
V1_CONFIG_FOLDER = ".afk"

BEHAVIORS_START = "<!-- afk:behaviors:start -->"
BEHAVIORS_END = "<!-- afk:behaviors:end -->"
INVESTIGATION_START = "<!-- afk:investigation:start -->"
INVESTIGATION_END = "<!-- afk:investigation:end -->"

PRECOMMIT_MARKER = "afk-precommit-gates"
BRANCH_GATE_MARKER = "afk-branch-name-gate"
STUB_INSTALL_NOTE = "(installed by afk-toolkit install-git-hooks.sh)."
STUB_ROOT_LINE = "# afk-plugin-root: /v1"

NEW_ID_ENABLED_LINE = rb'("afkv2@afk-toolkit"\]\r?\nenabled = )true'

CODEX_LIST_MARKETPLACE = ("Marketplace `afk-toolkit`\n"
                          "C:\\cache\\afk-toolkit\\marketplace.json\n")
CODEX_LIST_ROWS = ("afk@afk-toolkit    installed, disabled  1.16.0   C:\\cache\\afk\n"
                   "afkv2@afk-toolkit  installed, enabled   0.1.0    C:\\cache\\afkv2\n")
