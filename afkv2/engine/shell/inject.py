"""Add the tooltip layer to a rendered page.

The dictionary merges, later wins: the seed `tips.json`, the plugin `GLOSSARY.md`, the
repository glossaries with the page's own service last, then the feature's `PAGE-TIPS.md`.
The block sits between start and end markers and is replaced whole, so the same inputs
give the same bytes, and a file is rewritten only when its bytes differ.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parents[1]
SEED = HERE / "tips.json"
PLUGIN_GLOSSARY = PLUGIN_ROOT / "GLOSSARY.md"
FEATURE_TIPS = "PAGE-TIPS.md"

MARK_START = "<!-- afkv2-page-tips:start -->"
MARK_END = "<!-- afkv2-page-tips:end -->"
TIPS_BLOCK = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n?", re.DOTALL)
BODY_END = re.compile(r"</body\s*>", re.IGNORECASE)

ENTRY_RE = re.compile(r"(?:[-*+]\s+)?\*\*(.+?)\*\*\s*(?:\*\([^)]*\)\*\s*)?:\s*(.*)$")
META_LINE_RE = re.compile(r"[`_]*(Avoid|Code|Related)[`_]*\s*:")


class InjectError(Exception):
    """The page cannot be read or written as UTF-8 HTML."""


def clean(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "")
    text = re.sub(r"(\*\*|\*|__)", "", text)
    text = re.sub(r"(?<![\w])_|_(?![\w])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def keys_for(term: str) -> list[str]:
    """Dictionary keys of a term: each `a / b` part, its bare pre-dash head, a `(token)` inside it.

    Title-Case words lower so page-case usage matches; ALL-CAPS and mixed-case words keep their case.
    """
    raw = term.replace("`", "").strip()
    out: dict[str, None] = {}

    def add(part: str) -> None:
        part = part.strip()
        if part:
            out.setdefault(" ".join(w.lower() if len(w) > 1 and w[1:].islower() else w for w in part.split()))

    base = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    for part in re.split(r"\s*/\s*", base):
        add(part)
        head = re.split(r"\s+—\s+", part)[0]
        if head.strip() != part.strip():
            add(head)
    for match in re.finditer(r"\(([^)]*)\)", raw):
        inner = match.group(1).strip()
        if re.fullmatch(r"[\w.\-]+", inner):
            out.setdefault(inner)
    return list(out)


def parse_glossary(path: Path) -> dict[str, str]:
    """Entries of the glossary grammar: `**Term**:` then lines up to a blank one."""
    entries: dict[str, str] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return entries
    term, buffer = None, []

    def flush() -> None:
        definition = clean(" ".join(buffer)) if term and buffer else ""
        if definition:
            for key in keys_for(term):
                entries[key] = definition

    for line in lines:
        stripped = line.strip()
        match = ENTRY_RE.match(stripped)
        if match:
            flush()
            term, buffer = match.group(1), ([match.group(2)] if match.group(2) else [])
        elif not stripped or stripped.startswith("#") or META_LINE_RE.match(stripped):
            flush()
            term, buffer = None, []
        elif term is not None:
            buffer.append(stripped)
    flush()
    return entries


def repo_root(start: Path) -> Path | None:
    for folder in (start, *start.parents):
        if (folder / ".git").exists():
            return folder
    return None


def _seed(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("__") and isinstance(v, str) and v.strip()}


def _repo_glossaries(page: Path, top: Path) -> list[Path]:
    own = page.relative_to(top).parts[0] if page.is_relative_to(top) else ""
    try:
        names = sorted(entry.name for entry in os.scandir(top) if entry.is_dir())
    except OSError:
        names = []
    others = [top / name / "GLOSSARY.md" for name in names if name != own]
    return [top / "GLOSSARY.md", *others, top / own / "GLOSSARY.md"] if own else [top / "GLOSSARY.md", *others]


def load_dictionary(page: Path) -> dict[str, str]:
    tips = _seed(SEED)
    tips.update(parse_glossary(PLUGIN_GLOSSARY))
    page = Path(os.path.abspath(page))
    top = repo_root(page.parent)
    if top:
        for glossary in _repo_glossaries(page, top):
            tips.update(parse_glossary(glossary))
    tips.update(parse_glossary(page.parent.parent / FEATURE_TIPS))
    return tips


def _asset(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def tips_block(tips: dict[str, str]) -> str:
    dictionary = json.dumps(tips, ensure_ascii=False).replace("</", "<\\/")
    return (f'{MARK_START}\n<style>\n{_asset("tips.css")}</style>\n'
            f'<script id="afkv2-tips-dict" type="application/json">{dictionary}</script>\n'
            f'<script>\n{_asset("tips.js")}</script>\n{MARK_END}\n')


def inject(html: str, tips: dict[str, str]) -> str:
    """`html` with its tooltip block replaced; a pure function of its arguments."""
    html = TIPS_BLOCK.sub("", html)
    if not tips:
        return html
    block = tips_block(tips)
    match = BODY_END.search(html)
    if match:
        return html[: match.start()] + block + html[match.start():]
    return html + ("" if html.endswith("\n") else "\n") + block


def write_if_changed(path: Path, data: bytes) -> bool:
    """Atomically replace `path` with `data` only when its bytes differ; True when written."""
    try:
        if path.read_bytes() == data:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=".page-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return True


def inject_file(path: str | Path) -> bool:
    """Add the tooltip layer to the page at `path`; True when its bytes changed."""
    target = Path(path)
    try:
        html = target.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as problem:
        raise InjectError(f"cannot read {target} as UTF-8: {problem}") from problem
    try:
        return write_if_changed(target, inject(html, load_dictionary(target)).encode("utf-8"))
    except OSError as problem:
        raise InjectError(f"cannot write {target}: {problem}") from problem
