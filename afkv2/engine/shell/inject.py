"""Add the tooltip layer to a rendered page.

Shared terms merge the seed, plugin glossary and repository glossaries, own service last.
Pages without a durable source also load legacy `PAGE-TIPS.md`. The shared terms appear once, in the
dictionary block; page-owned terms and IDs stay in separate maps of the payload for the browser resolver.
The block sits between start and end markers and is replaced whole, so the same inputs
give the same bytes, and a file is rewritten only when its bytes differ.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from html.parser import HTMLParser
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


CONNECTORS = frozenset({"a", "an", "and", "for", "in", "of", "on", "or", "the", "to"})
COMMON_WORD = re.compile(r"[a-z]+")


def _initials(words: list[str]) -> set[str]:
    """The initialisms of `words`: every word, and every word but the connectors."""
    content = [w for w in words if w.lower() not in CONNECTORS]
    return {"".join(w[0] for w in group).upper() for group in (words, content) if group}


def _alias(inner: str, base: str) -> bool:
    """A `(token)` is an alias of its term when it is code (backticks) or the initialism of the base words.

    Any other `(token)` is a qualifier, such as `Enrich (action)` or `Currency (GL)`: it narrows the
    meaning and is no name of the term, so it gives no key.
    """
    token = inner.replace("`", "").strip()
    if not re.fullmatch(r"[\w.\-]+", token):
        return False
    if inner.startswith("`") and inner.endswith("`"):
        return True
    words = [w for w in re.split(r"[\s\-]+", base) if w]
    return len(words) > 1 and re.sub(r"(?<=[A-Z])s$", "", token).upper() in _initials(words)


def keys_for(term: str) -> list[str]:
    """Dictionary keys of a term: each `a / b` part, its bare pre-dash head, and a `(token)` alias.

    Title-Case words lower so page-case usage matches; ALL-CAPS and mixed-case words keep their case.
    A term with a qualifier `(token)` (see `_alias`) gives no key for a bare common word, such as
    `open` from `Open (workspace)`: that word on a page rarely carries the qualified meaning.
    """
    stripped = term.strip()
    raw = stripped.replace("`", "")
    out: dict[str, None] = {}
    base = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    inners = [m.group(1).strip() for m in re.finditer(r"\(([^)]*)\)", stripped)]
    qualified = any(not _alias(inner, base) for inner in inners)

    def add(part: str) -> None:
        part = part.strip()
        if not part:
            return
        key = " ".join(w.lower() if len(w) > 1 and w[1:].islower() else w for w in part.split())
        if qualified and COMMON_WORD.fullmatch(key):
            return
        out.setdefault(key)

    for part in re.split(r"\s*/\s*", base):
        add(part)
        head = re.split(r"\s+—\s+", part)[0]
        if head.strip() != part.strip():
            add(head)
    for inner in inners:
        if _alias(inner, base):
            out.setdefault(inner.replace("`", "").strip())
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


class _Source(HTMLParser):
    """Read the durable JSON script without treating markup inside other scripts as HTML."""

    def __init__(self, html: str):
        super().__init__()
        self.blocks: list[str] = []
        self.active = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = dict(attrs).get("id") == "afkv2-page-tip-source"
            if self.active:
                self.blocks.append("")

    def handle_data(self, data):
        if self.active:
            self.blocks[-1] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def _page_maps(html: str) -> tuple[dict[str, str], dict[str, str]]:
    blocks = _Source(html).blocks
    if len(blocks) != 1:
        return {}, {}
    try:
        source = json.loads(blocks[0])
        maps = []
        for kind, key, value in (("ids", "id", "title"), ("terms", "term", "definition")):
            entries = source.get(kind, [])
            if not isinstance(entries, list):
                return {}, {}
            result = {}
            for entry in entries:
                if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) and entry[k]
                                                          for k in (key, value)):
                    return {}, {}
                result[entry[key]] = entry[value]
            maps.append(result)
        return maps[0], maps[1]
    except (ValueError, AttributeError):
        return {}, {}


def load_dictionary(page: Path, html: str = "") -> dict[str, str]:
    tips = _seed(SEED)
    tips.update(parse_glossary(PLUGIN_GLOSSARY))
    page = Path(os.path.abspath(page))
    top = repo_root(page.parent)
    if top:
        for glossary in _repo_glossaries(page, top):
            tips.update(parse_glossary(glossary))
    if not _Source(html).blocks:
        tips.update(parse_glossary(page.parent.parent / FEATURE_TIPS))
    return tips


def _asset(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def tips_block(tips: dict[str, str], page_ids: dict[str, str] | None = None,
               page_terms: dict[str, str] | None = None) -> str:
    # The shared terms sit once, in the dictionary block; the payload holds only the page-owned maps.
    dictionary = json.dumps(tips, ensure_ascii=True).replace("</", "<\\/").replace("<", "\\u003c").replace("\\u003c\\/", "<\\/")
    payload = json.dumps({"page_ids": page_ids or {}, "page_terms": page_terms or {}},
                         ensure_ascii=True, sort_keys=True).replace("<", "\\u003c")
    return (f'{MARK_START}\n<style>\n{_asset("tips.css")}</style>\n'
            f'<script id="afkv2-tips-dict" type="application/json">{dictionary}</script>\n'
            f'<script id="afkv2-tips-payload" type="application/json">{payload}</script>\n'
            f'<script>\n{_asset("tips.js")}</script>\n{MARK_END}\n')


def inject(html: str, tips: dict[str, str]) -> str:
    """`html` with its tooltip block replaced; a pure function of its arguments."""
    html = TIPS_BLOCK.sub("", html)
    page_ids, page_terms = _page_maps(html)
    if not tips and not page_ids and not page_terms:
        return html
    block = tips_block(tips, page_ids, page_terms)
    match = BODY_END.search(html)
    if match:
        return html[: match.start()] + block + html[match.start():]
    return html + ("" if html.endswith("\n") else "\n") + block


# Windows refuses a replace while another process holds the target open, as a scanner does a new file briefly.
REPLACE_TRIES = 10
REPLACE_WAIT_S = 0.05


def _replace(source, target) -> None:
    for attempt in range(1, REPLACE_TRIES + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES:
                raise
            time.sleep(REPLACE_WAIT_S * attempt)


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
        _replace(temp, path)
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
        return write_if_changed(target, inject(html, load_dictionary(target, html)).encode("utf-8"))
    except OSError as problem:
        raise InjectError(f"cannot write {target}: {problem}") from problem
