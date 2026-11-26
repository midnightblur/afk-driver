"""The prototype guides: SKILL.md and its canvas rules MOCKUP.md (SDD §5, §6, §8; ticket 207 VR-004, VR-005, VR-006,
VR-016).

A static row proves the rule is written in the file that owns it: the plan lowered these rows to static, and the
quality of the rules is proved by the owner's live check. Each check finds the section that owns the rule and compares
on normalized text (lowercase, whitespace collapsed, backticks and quotes removed), so a change of case, line wrap or
quoting keeps it green. Every verb the guides name must exist in its script. Each failure names the file, the section,
the expected phrase and the actual section text.
"""

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
HOME = PLUGIN / "skills" / "prototype"
SKILL_MD = HOME / "SKILL.md"
MOCKUP_MD = HOME / "MOCKUP.md"
QUOTES = str.maketrans("", "", "`\"'\u2018\u2019\u201c\u201d")


def _norm(text):
    """Lowercase, quotes and backticks removed, whitespace collapsed to 1 space."""
    return " ".join(text.translate(QUOTES).lower().split())


def _text(path):
    assert path.is_file(), f"input: {path}\nexpected: the file exists\nactual: no file"
    return path.read_text("utf-8")


def _section(path, heading):
    """The normalized text under `heading` up to the next heading of the same or a higher level."""
    text = _text(path)
    level, title = heading.split(" ", 1)
    headings = re.findall(r"^(#+ +.*?)[ \t]*$", text, re.M)
    found = next((m for m in re.finditer(rf"^{level} +(.*?)[ \t]*$", text, re.M)
                  if _norm(m.group(1)) == _norm(title)), None)
    assert found, f"file: {path.name}\nexpected: heading {heading!r}\nactual headings: {headings}"
    rest = text[found.end():]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.M)
    return _norm(rest[:stop.start()] if stop else rest)


def _states(path, heading, phrase, present=True):
    """Assert that section `heading` of `path` holds `phrase` (or lacks it when `present` is false)."""
    section = _section(path, heading)
    held = _norm(phrase) in section
    assert held is present, (f"file: {path.name}\nsection: {heading}\n"
                             f"expected: {'holds' if present else 'lacks'} {phrase!r}\nactual: {section[:600]!r}")


# --- VR-005 (PRD AC-001): a PRD with no screen story stops with no_ui and writes nothing

def test_no_screen_story_stops_with_no_ui():
    gate = "## No screen, no mockup"
    _states(SKILL_MD, gate, "`no_ui`")
    _states(SKILL_MD, gate, "no story adds or changes a screen")
    _states(SKILL_MD, gate, "writes no file")
    _states(SKILL_MD, gate, "leaves the `INDEX.md` Prototype row as it is")


# --- VR-006 (PRD AC-014): "chat only", at any time, ends lavish and takes every later note in chat

def test_chat_only_ends_lavish_for_the_run():
    chat_only = "### Chat only"
    _states(SKILL_MD, chat_only, '"chat only"')
    _states(SKILL_MD, chat_only, "at any time")
    _states(SKILL_MD, chat_only, '"chat only", at any time: run `end` when lavish shows a mockup')
    _states(SKILL_MD, chat_only, "every later note of this run in chat")
    _states(SKILL_MD, chat_only, "never shows the mockup in lavish again")
    _states(SKILL_MD, "## Notes loop", "Show the mockup in lavish only when the developer did not ask for chat only.")
    _states(SKILL_MD, "### In lavish", "chat only", present=False)


# --- VR-016 (PRD AC-007, AC-013): clickable from the entry screen, and each note gets an edit or a reply

def test_each_note_gets_an_edit_or_a_reply_and_a_new_show():
    loop, lavish, chat = "## Notes loop", "### In lavish", "### In chat"
    _states(SKILL_MD, loop, "Give each note an edit of the mockup or a reply, never neither.")
    _states(SKILL_MD, loop, "names its element by the `selector`, the `tag` and the `text`")
    _states(SKILL_MD, lavish, "Show the edited mockup: lavish reloads the saved file in the open session")
    _states(SKILL_MD, lavish, "first give each note of the notes file an edit of the mockup or a reply")
    _states(SKILL_MD, chat, "`file://` path")
    _states(SKILL_MD, chat, "an edit of the mockup or a reply")
    _states(SKILL_MD, chat, "reload the mockup after each edit")
    _states(SKILL_MD, lavish, "`status` `user-ended`")
    _states(SKILL_MD, lavish, 'go on by "In chat"')
    # the Codex Stop hook clears the waiting record after each wait, and only `show` writes it
    _states(SKILL_MD, lavish, "On Codex, run `show` before you end each turn")
    # `show` reuses the open tab by its tab record; only `end` forgets the record when the Stop hook saw the end
    _states(SKILL_MD, lavish, "To show it again, run `end`, then `show`: lavish then opens a new tab.")
    _states(SKILL_MD, lavish, "`notes-unwritten` | the notes are in the `notes` field of the refusal")
    _states(SKILL_MD, lavish, "When the developer does not see the mockup, run `end`, then `show`.")


def test_mockup_is_clickable_from_the_entry_screen_inside_the_shell():
    shell = "## App shell and neighbours"
    _states(MOCKUP_MD, shell, "clickable from the entry screen")
    _states(MOCKUP_MD, shell, "inside the app shell")
    _states(MOCKUP_MD, shell, "stub")
    _states(MOCKUP_MD, shell, "neighbour")


# lavish (0.1.86) annotates only the file it opened, refuses a load with a changed query, and drops the hash when it
# reloads after an edit; window.name survives that reload (proved in a scratch lavish session)

def test_the_mockup_is_1_file_that_routes_by_its_hash():
    routes = "## Screens and routes"
    _states(MOCKUP_MD, "# Mockup rules", "1 self-contained HTML file in the `prototype/` folder")
    _states(MOCKUP_MD, "# Mockup rules", "per screen in the", present=False)
    _states(MOCKUP_MD, routes, "Route each screen by the hash: `#/<screen>`")
    _states(MOCKUP_MD, routes, "Never read or write `location.search` or `location.pathname`.")
    _states(MOCKUP_MD, routes, "Never link to another file")
    _states(MOCKUP_MD, routes, "Keep the route in `window.name` at each render")
    _states(MOCKUP_MD, routes, "An unknown route shows the entry screen.")
    _states(MOCKUP_MD, "## Regions", "Start each `id` with its screen")
    _states(MOCKUP_MD, "## Variants", "`variant=<name>` parameter of the hash route")
    _states(SKILL_MD, "## Steps", "merge the screens and their edits into 1 file")
    _states(SKILL_MD, "## Notes loop", "all in the 1 file")
    _states(HOME / "PROTOTYPE-FORMAT.md", "## Screens table", "`prototype/orders.html#/detail`")
    _states(HOME / "PROTOTYPE-FORMAT.md", "## Checks at settle", "`page-leave`")


def test_every_verb_the_guides_name_exists():
    """Each `<script> <verb>` the guides name is a `cmd_<verb>` of that script; the notes loop calls `wait`."""
    scripts = HOME / "scripts"
    named = re.findall(r"(\w+)\.py\"? (\w+)", _text(SKILL_MD) + _text(MOCKUP_MD))
    assert ("mockup_show", "wait") in named, (f"input: SKILL.md + MOCKUP.md\nexpected: names mockup_show.py wait\n"
                                              f"actual: {sorted(set(named))}")
    for script, verb in named:
        source = _text(scripts / f"{script}.py")
        assert re.search(rf"^def cmd_{verb}\(", source, re.M), (f"input: {script}.py\nexpected: def cmd_{verb}(\n"
                                                                f"actual: {re.findall(r'^def (cmd_\w+)', source, re.M)}")


# --- VR-004 (PRD AC-008, AC-020; SDD §8): only made-up rows, at most 50 per screen, an id on each region

def test_only_made_up_rows_at_most_50_per_screen():
    data = "## Made-up data"
    _states(MOCKUP_MD, data, "every row is made up")
    _states(MOCKUP_MD, data, "Use at most 50 rows per screen.")
    _states(MOCKUP_MD, data, "1 JSON script")
    _states(MOCKUP_MD, data, "never a record copied from the live app or its database")
    _states(MOCKUP_MD, "## Regions", "an `id` on every region the developer may note")
    _states(SKILL_MD, "## Steps", "made-up data")
    _states(SKILL_MD, "## Steps", "never copy a record")


# --- the live app: the run starts it only on a free address, and stops only what it started (SDD §7; D-7)

def test_live_app_starts_on_a_free_address_and_stops_only_what_the_run_started():
    _states(SKILL_MD, "## Steps", "already answers before the start: start no app")
    _states(SKILL_MD, "## Steps", "Stop only an app that step 2 of this run started")


def test_the_screen_check_comes_before_a_frontend_refusal():
    steps = _section(SKILL_MD, "## Steps")
    start = steps.split(_norm("2. **Anchor.**"))[0]
    gate, refusal = _norm('by "No screen, no mockup"'), _norm("`no-frontend`")
    message = (f"file: {SKILL_MD.name}\nsection: ## Steps, before step 2\n"
               f"expected: {gate!r} before {refusal!r}\nactual: {start[:600]!r}")
    assert gate in start, message
    assert refusal in start, message
    assert start.index(gate) < start.index(refusal), message
    cells = [cell.strip() for cell in start.split("|")]
    check, stop = _norm("first check for a screen"), _norm("Then")
    for code in ("no-frontend", "pick-frontend"):
        row = cells[cells.index(code) + 1] if code in cells else ""
        row_message = (f"file: {SKILL_MD.name}\nsection: ## Steps, step 1 refusal row {code}\n"
                       f"expected: {check!r} before {stop!r}\nactual: {row!r}")
        assert check in row and row.index(check) < row.index(stop), row_message
