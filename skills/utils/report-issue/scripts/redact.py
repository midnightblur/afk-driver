#!/usr/bin/env python3
"""Strip everything but plugin-side context from outgoing issue text.

    redact.py --plugin-root P [--repo-root R] [--keep-repo OWNER/NAME]
              [--check] [-o OUT] [IN]

Reads IN (default stdin), writes the redacted text to OUT (default stdout).
Two passes:

1. Replace every sensitive shape with a placeholder: private keys, auth headers
   (anywhere on a line), token and cloud-key shapes, secret assignments (`.env`
   lines), URL credentials, addresses, account ids, handles, home paths,
   addresses and host names, URLs outside the target repository, tracker ticket
   ids, the consuming repository's identity (root path, remote hosts, and every
   remote path segment: owner, group, name), and the git user's handles.
   Identity is an ALLOWLIST: a path-shaped token survives only when it resolves
   inside the plugin root (or is a generic run-artifact path); a source-file
   name only when the plugin ships a file of that name; a PascalCase word only
   when the plugin's own text uses it. Everything else is a placeholder. The
   ticket, account, address, and source-file shapes are the ones
   `hooks/lib/sensitive-patterns.tsv` owns for the genericity gate.
2. Scan the result for RESIDUAL shapes: any first-pass shape that survived,
   high-entropy blobs, and secret keywords bound to a value.

`--check` skips pass 1 and only scans. Exit codes:
    0  clean
    1  residual hits — each printed to stderr as `redact: line N: <class>`
    2  usage error
"""
from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PLUGIN_ROOT = HERE.parents[3]

TOKEN_SHAPES = [
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"glpat-[A-Za-z0-9_-]{20,}",
    r"xox[abprs]-[A-Za-z0-9-]{10,}",
    r"(?:AKIA|ASIA|AIDA|AROA|AGPA|ANPA|ANVA|AIPA|APKA)[0-9A-Z]{16}",
    r"sk-[A-Za-z0-9_-]{20,}",
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}",
]
SECRET_NAME = r"[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY|CREDENTIALS?)[A-Za-z0-9_]*"
TLDS = (
    "com|net|org|io|dev|app|cloud|co|ai|biz|info|xyz|tech|site|online|us|uk|de|fr|"
    "jp|cn|in|au|ca|nl|se|no|fi|dk|ch|at|be|es|it|pl|ru|br|mx|vn|sg|hk|kr|tw|nz|"
    "ie|il|za|eu|gov|edu|mil|int|internal|local|corp|lan|intra|intranet|"
    "localdomain|arpa|test|invalid"
)
PUBLIC_HOSTS = {
    "github.com", "api.github.com", "raw.githubusercontent.com", "gitlab.com",
    "anthropic.com", "docs.anthropic.com", "claude.ai", "claude.com",
    "example.com", "example.org", "example.net",
}
KEPT_IPS = {"127.0.0.1", "0.0.0.0"}
GENERIC_PATHS = re.compile(
    r"^(?:plan/[A-Z][A-Z-]*\.md|plan/review/INDEX\.md|\.afk/config(?:\.local)?\.yaml"
    r"|\.claude/afk-issues(?:/<[a-z-]+>\.md)?)$"
)
TEXT_SUFFIXES = {".md", ".sh", ".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".tsv"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", "tests", ".pytest_cache"}
PATH_TOKEN = r"[^\s\"'`()\[\],;|]*[\\/][^\s\"'`()\[\],;|]*"
PLACEHOLDER_SEGMENT = re.compile(r"^(?:<[^>]*>|\{[^}]*\}|.*\*.*)$")


def load_patterns(plugin_root: Path) -> dict[str, str]:
    path = plugin_root / "hooks" / "lib" / "sensitive-patterns.tsv"
    patterns: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, _, regex = line.partition("\t")
        patterns[name.strip()] = regex.strip()
    for need in ("ticket-id", "notation-prefixes", "account-id", "email", "source-file"):
        if need not in patterns:
            raise SystemExit(f"redact: {path} has no `{need}` pattern")
        try:
            re.compile(patterns[need])
        except re.error as problem:
            raise SystemExit(f"redact: {path} `{need}` does not compile: {problem}")
    return patterns


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _path_forms(path: str) -> list[str]:
    """Every spelling a path can take in tool output on this machine."""
    if not path:
        return []
    p = path.rstrip("/\\")
    forms = {p, p.replace("\\", "/"), p.replace("/", "\\")}
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    if m:
        rest = m.group(2).replace("\\", "/")
        forms.add(f"/{m.group(1).lower()}/{rest}")
        forms.add(f"/mnt/{m.group(1).lower()}/{rest}")
    return sorted((f for f in forms if len(f) > 3), key=len, reverse=True)


def _remote_parts(url: str) -> tuple[str | None, list[str]]:
    """The host and every path segment of a git remote URL."""
    text = url.strip()
    m = re.match(r"^(?:[a-z+]+://)?(?:[^@/\s]+@)?([^/:\s]+)[:/](.+?)(?:\.git)?/?$", text)
    if not m:
        return None, []
    return m.group(1), [s for s in m.group(2).split("/") if s]


def _plugin_inventory(plugin_root: Path) -> tuple[set[str], set[str], set[str]]:
    """Basenames the plugin ships, and the PascalCase words and lowercase words
    its own text uses — the allowlists identity redaction keeps."""
    basenames: set[str] = set()
    pascal: set[str] = set()
    words: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(plugin_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            basenames.add(name)
            if Path(name).suffix not in TEXT_SUFFIXES:
                continue
            try:
                text = (Path(dirpath) / name).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            pascal.update(re.findall(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+\b", text))
            words.update(w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z0-9-]*\b", text))
    return basenames, pascal, words


class Redactor:
    def __init__(self, plugin_root: Path, repo_root: Path | None, keep_repo: str | None):
        self.pat = load_patterns(plugin_root)
        self.plugin_root = plugin_root.resolve()
        self.keep_repo = (keep_repo or "").strip("/").lower()
        self.keep_parts = set(self.keep_repo.split("/")) if self.keep_repo else set()
        self.basenames, self.pascal, self.words = _plugin_inventory(self.plugin_root)
        self.rules: list[tuple[str, re.Pattern, object]] = []
        self._build(repo_root)

    def _add(self, cls: str, regex: str, repl, flags: int = 0) -> None:
        self.rules.append((cls, re.compile(regex, flags), repl))

    def _literal(self, cls: str, values, repl: str) -> None:
        values = sorted({v for v in values if v and len(v) >= 3}, key=len, reverse=True)
        if values:
            alt = "|".join(re.escape(v) for v in values)
            self._add(cls, rf"(?<![A-Za-z0-9_])(?:{alt})(?![A-Za-z0-9_])", repl, re.I)

    def _build(self, repo_root: Path | None) -> None:
        a = self._add
        a("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "<private-key>")
        a("auth-header", r"(?i)\b((?:proxy-)?(?:authorization|x-api-key|cookie|set-cookie|private-token)\s*:[ \t]*)(?!<redacted>)\S[^\n]*", r"\1<redacted>")
        a("bearer", r"(?i)\b(bearer|basic)\s+(?=[A-Za-z0-9._~+/=-]*\d)[A-Za-z0-9._~+/=-]{12,}", r"\1 <redacted>")
        a("token", "|".join(TOKEN_SHAPES), "<token>")
        a("url-credential", r"(://)[^/\s:@<]+:[^/\s@]+@", r"\1<redacted>@")
        a("secret-assignment", rf"(?i)\b({SECRET_NAME})(\s*[=:]\s*)(\"[^\"\n]*\"|'[^'\n]*'|[^\s<][^\s]*)", r"\1\2<redacted>")

        # Roots first: the plugin root is shown as the variable skills use, the
        # consuming repository as a placeholder, a home directory as `~`.
        for form in _path_forms(str(self.plugin_root)):
            a("plugin-path", re.escape(form), "${AFK_PLUGIN_ROOT}", re.I)
        identity: set[str] = set()
        handles: set[str] = set()
        self.product_classes: set[str] = set()
        if repo_root is not None:
            repo_root = repo_root.resolve()
            if repo_root != self.plugin_root:
                for form in _path_forms(str(repo_root)):
                    a("repo-path", re.escape(form), "<repo>", re.I)
                identity.add(repo_root.name)
                for line in _git(repo_root, "remote", "-v").splitlines():
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    host, segments = _remote_parts(parts[1])
                    if "/".join(segments).lower() == self.keep_repo:
                        continue
                    identity.add(parts[1])
                    if host and host.lower() not in PUBLIC_HOSTS:
                        identity.add(host)
                    identity.update(s for s in segments if s.lower() not in self.keep_parts)
                    if len(segments) >= 2:
                        identity.add("/".join(segments[-2:]))
                for name in _git(repo_root, "ls-files").splitlines():
                    base = name.rsplit("/", 1)[-1]
                    if re.fullmatch(self.pat["source-file"], base):
                        self.product_classes.add(base.rsplit(".", 1)[0])
            for key in ("user.name", "user.email"):
                value = _git(repo_root, "config", key).strip()
                if key == "user.email":
                    value = value.split("@")[0]
                handles.update(t for t in re.split(r"[^A-Za-z0-9]+", value) if len(t) >= 3)
        home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
        for form in _path_forms(home):
            a("home-path", re.escape(form), "~", re.I)
        a("home-path", r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+", "~")
        a("home-path", r"(?<![\w.~])/(?:home|Users)/[^/\s]+", "~")
        self._literal("repo-identity", identity, "<repo>")

        a("email", self.pat["email"], "<email>")
        a("account-id", self.pat["account-id"], "<account-id>")
        a("handle", r"(?<![\w.@/<])@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\b", "<handle>")
        a("url", r"\b(?:https?|ssh|git)://[^\s)>\]\"'`]+", self._url)
        a("ip", r"\b(?:\d{1,3}\.){3}\d{1,3}\b", lambda m: m.group(0) if m.group(0) in KEPT_IPS else "<ip>")
        a("host", rf"(?i)(?<![\w.@/-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:{TLDS})(?![\w-]|\.\w)", self._host)
        a("ticket-id", rf"(?<![A-Za-z0-9_]){self.pat['ticket-id']}(?![A-Za-z0-9_])", self._ticket)
        a("product-symbol", r"`([A-Z][A-Za-z0-9]*)`", lambda m: "`<product-symbol>`" if m.group(1) in self.product_classes else m.group(0))
        a("path", PATH_TOKEN, self._path)
        a("product-file", rf"(?<![A-Za-z0-9_.<-]){self.pat['source-file']}(?![A-Za-z0-9_])", self._product_file)
        a("pascal-case", r"(?<![\w$<])[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+(?![\w])", lambda m: m.group(0) if m.group(0) in self.pascal else "<symbol>")
        self._literal("user-handle", handles, "<user>")

    def _url(self, m: re.Match) -> str:
        url = m.group(0)
        if self.keep_repo and re.match(rf"(?i)https://github\.com/{re.escape(self.keep_repo)}(?:[/#?]|$)", url):
            return url
        return "<url>"

    def _host(self, m: re.Match) -> str:
        host = m.group(0).lower()
        if host in PUBLIC_HOSTS or host.endswith((".example.com", ".example.org", ".example.net", ".test", ".invalid")):
            return m.group(0)
        return "<host>"

    def _ticket(self, m: re.Match) -> str:
        prefix = m.group(0).split("-")[0]
        return m.group(0) if re.fullmatch(self.pat["notation-prefixes"], prefix) else "<ticket>"

    def _product_file(self, m: re.Match) -> str:
        return m.group(0) if m.group(0) in self.basenames else "<product-file>"

    def _path(self, m: re.Match) -> str:
        token = m.group(0)
        if "://" in token or token.startswith("</") or not re.search(r"[A-Za-z0-9]", token):
            return token
        core = token.rstrip(".:,;!?")
        tail = token[len(core):]
        core = re.sub(r"(?::\d+){1,2}$", "", core)
        if self.keep_repo and core.lower().split("#")[0] == self.keep_repo:
            return token
        segments = [s for s in re.split(r"[\\/]", core) if s]
        rooted = bool(re.match(r"^(?:[\\/]|\.{1,2}[\\/]|~|\$|[A-Za-z]:)", core))
        has_ext = bool(re.search(r"\.[A-Za-z0-9]{1,8}$", segments[-1])) if segments else False
        if not rooted and not has_ext and len(segments) == 2:
            if all(s.isdigit() for s in segments) or all(s.lower() in self.words or s.startswith("<") for s in segments):
                return token
        return token if self._plugin_path(core) else "<path>" + tail

    def _plugin_path(self, core: str) -> bool:
        rel = re.sub(r"^\$\{?AFK_PLUGIN_ROOT\}?", "", core).replace("\\", "/")
        if rel.startswith("./"):
            rel = rel[2:]
        rel = rel.lstrip("/") if rel != core.replace("\\", "/") else rel
        if GENERIC_PATHS.match(rel):
            return True
        if rel.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
            return False
        here = self.plugin_root
        for segment in (s for s in rel.split("/") if s):
            if PLACEHOLDER_SEGMENT.match(segment):
                return here.is_dir()
            here = here / segment
        return here != self.plugin_root and here.exists()

    def redact(self, text: str) -> str:
        for _cls, rx, repl in self.rules:
            text = rx.sub(repl, text)
        return text

    def residual(self, text: str) -> list[tuple[int, str]]:
        hits: list[tuple[int, str]] = []
        for number, line in enumerate(text.splitlines(), 1):
            for cls, rx, repl in self.rules:
                for m in rx.finditer(line):
                    if self._substitute(repl, m) != m.group(0):
                        hits.append((number, cls))
                        break
            for piece in re.findall(r"[A-Za-z0-9+_=-]{20,}", line):
                if _high_entropy(piece):
                    hits.append((number, "high-entropy"))
            if re.search(r"(?i)\b(password|passwd|secret|api[_-]?key|private[_ -]key)\b\s*(?:[:=]|\bis\b)\s*(?!<)\S", line):
                hits.append((number, "secret-keyword"))
        return sorted(set(hits))

    @staticmethod
    def _substitute(repl, m: re.Match) -> str:
        return repl(m) if callable(repl) else m.expand(repl)


def _high_entropy(token: str) -> bool:
    """A key-shaped blob: letters and digits, not a hex id, not kebab words."""
    if re.fullmatch(r"[0-9a-fA-F]+", token) or re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)+", token):
        return False
    if not (re.search(r"[0-9]", token) and re.search(r"[A-Za-z]", token)):
        return False
    mixed = re.search(r"[a-z]", token) and re.search(r"[A-Z]", token)
    if not (mixed or not re.search(r"[a-z]", token)):
        return False
    counts = {c: token.count(c) for c in set(token)}
    entropy = -sum(n / len(token) * math.log2(n / len(token)) for n in counts.values())
    return entropy > 3.5


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="redact.py", add_help=True)
    parser.add_argument("input", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("--plugin-root", default=str(DEFAULT_PLUGIN_ROOT))
    parser.add_argument("--repo-root")
    parser.add_argument("--keep-repo")
    parser.add_argument("--check", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    try:
        text = (Path(args.input).read_text(encoding="utf-8") if args.input
                else sys.stdin.buffer.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError) as problem:
        sys.stderr.write(f"redact: cannot read input: {problem}\n")
        return 2
    try:
        redactor = Redactor(Path(args.plugin_root), Path(args.repo_root) if args.repo_root else None, args.keep_repo)
    except SystemExit as problem:
        sys.stderr.write(f"{problem}\n")
        return 2
    if not args.check:
        text = redactor.redact(text)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8", newline="\n")
        else:
            sys.stdout.buffer.write(text.encode("utf-8"))
    hits = redactor.residual(text)
    for number, cls in hits:
        sys.stderr.write(f"redact: line {number}: {cls}\n")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
