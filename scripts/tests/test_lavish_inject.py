"""The page-runtime injector `scripts/lavish/inject.py`: what lands in the page, and when bytes stay put."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lavish import inject  # noqa: E402

AUTHORED = "<!doctype html>\n<html lang=\"en\">\n<head>\n<title>Authored</title>\n</head>\n<body>\n<p>The PRD names a seam.</p>\n</body>\n</html>\n"
DAISY = ("<!doctype html>\n<html data-theme=\"light\">\n<head><meta charset=\"utf-8\"><title>D</title>"
         "<link href=\"daisyui.css\" rel=\"stylesheet\"></head>\n<body><p>x</p></body>\n</html>\n")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo with space"
    (root / ".git").mkdir(parents=True)
    return root


@pytest.fixture
def seed(tmp_path: Path) -> Path:
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"__meta": "ignored", "seam": "seed seam", "only-seed": "from the seed"}),
                    encoding="utf-8")
    return path


@pytest.fixture
def workflow(tmp_path: Path) -> Path:
    path = tmp_path / "WORKFLOW-GLOSSARY.md"
    path.write_text("**Seam**:\nworkflow seam\n\n**Gate**:\nworkflow gate\n", encoding="utf-8")
    return path


def page(folder: Path, text: str = AUTHORED, name: str = "page.html") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


def run(path: Path, seed: Path, workflow: Path, cwd: Path | None = None) -> bool:
    return inject.inject_file(path, cwd=cwd, seed=seed, workflow=workflow)


def dictionary(html: str) -> dict:
    start = html.index('<script id="afk-tips-dict" type="application/json">') + len(
        '<script id="afk-tips-dict" type="application/json">')
    return json.loads(html[start:html.index("</script>", start)].replace("<\\/", "</"))


def test_authored_page_gets_tips_dark_and_keeps_its_title(repo, seed, workflow):
    path = page(repo / "svc" / "docs")
    assert run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert html.count(inject.MARK_START) == 1 and html.count(inject.DARK_START) == 1
    assert "<title>Authored</title>" in html and html.count("<title>") == 1
    assert '<meta charset="utf-8">' in html
    assert "afk-lavish-invert" in html and "id=\"afk-nav\"" not in html  # nav is built by the runtime script
    assert "function navChrome()" in html and "function btw()" in html
    assert html.index(inject.DARK_END) < html.index("</body>")


def test_generated_kit_page_is_injected(repo, seed, workflow, tmp_path):
    sample = ROOT / "scripts" / "tests" / "samples" / "lavish-round.json"
    out = repo / "round.html"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "lavish_render.py"), str(sample), "-o", str(out)],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    rendered = out.read_bytes()
    assert run(out, seed, workflow)
    html = out.read_text(encoding="utf-8")
    assert inject.MARK_START in html and inject.DARK_START in html
    assert inject._strip(html).encode("utf-8") == rendered  # the renderer's bytes are untouched otherwise


def test_daisyui_page_is_forced_to_the_dark_theme(repo, seed, workflow):
    path = page(repo, DAISY)
    run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert '<html data-theme="dark">' in html
    assert "html{color-scheme:dark}" in html and "afk-lavish-invert" not in html


def test_a_daisyui_term_in_the_dictionary_does_not_switch_the_dark_path(repo, workflow, tmp_path):
    seed = tmp_path / "s.json"
    seed.write_text(json.dumps({"daisyui": "a component library"}), encoding="utf-8")
    path = page(repo)
    run(path, seed, workflow)
    run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert "afk-lavish-invert" in html and 'data-theme="dark"' not in html


def test_dictionary_precedence_later_sources_win(repo, seed, workflow):
    (repo / "GLOSSARY.md").write_text("**Gate**:\nroot gate\n\n**Seam**:\nroot seam\n", encoding="utf-8")
    (repo / "other").mkdir()
    (repo / "other" / "GLOSSARY.md").write_text("**Seam**:\nother seam\n", encoding="utf-8")
    (repo / "svc").mkdir()
    (repo / "svc" / "GLOSSARY.md").write_text("**Seam**:\nown seam\n\n**Lane**:\nown lane\n", encoding="utf-8")
    spec = repo / "svc" / "specs" / "feature"
    spec.mkdir(parents=True)
    (spec / "LAVISH-TIPS.md").write_text("**Lane**:\nfeature lane\n", encoding="utf-8")
    path = page(spec / "pages")
    run(path, seed, workflow)
    tips = dictionary(path.read_text(encoding="utf-8"))
    assert tips["only-seed"] == "from the seed"
    assert tips["gate"] == "root gate", "root glossary beats the workflow glossary"
    assert tips["seam"] == "own seam", "own service parses after every other service"
    assert tips["lane"] == "feature lane", "the feature terms file wins last"
    assert "__meta" not in tips


def test_spec_dir_meta_names_the_feature_terms_file(repo, seed, workflow):
    spec = repo / "specs" / "f1"
    spec.mkdir(parents=True)
    (spec / "LAVISH-TIPS.md").write_text("**Ledger**:\nfrom meta\n", encoding="utf-8")
    text = AUTHORED.replace("<head>", '<head><meta name="afk-spec-dir" content="specs/f1">')
    path = page(repo / "elsewhere", text)
    run(path, seed, workflow)
    assert dictionary(path.read_text(encoding="utf-8"))["ledger"] == "from meta"


def test_untitled_page_gets_a_title_and_charset(repo, seed, workflow):
    spec = repo / "specs" / "f2"
    spec.mkdir(parents=True)
    (spec / "LAVISH-TIPS.md").write_text("**X**:\ny\n", encoding="utf-8")
    path = page(spec, "<html><head></head><body><p>hi</p></body></html>", name="round-3.html")
    run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert "<title>round-3 — f2</title>" in html and '<meta charset="utf-8">' in html


def test_headless_fragment_gets_title_and_blocks_appended(repo, seed, workflow):
    path = page(repo, "<p>fragment</p>", name="frag.html")
    run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert html.startswith('<meta charset="utf-8">\n<title>frag</title>\n<p>fragment</p>')
    assert html.rstrip().endswith(inject.DARK_END)
    assert not run(path, seed, workflow)


def test_session_nav_runtime_ships_with_the_tips_block(repo, seed, workflow):
    text = AUTHORED.replace("<p>", '<section data-afk-item="r1" data-afk-state="current"><h2>Round 1</h2></section><p>')
    path = page(repo, text)
    run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    tips = html[html.index(inject.MARK_START):html.index(inject.MARK_END)]
    assert "#afk-nav" in tips and "data-afk-item" in tips and "afk-jump" in tips


def test_legacy_markers_migrate_to_one_current_block_each(repo, seed, workflow):
    legacy_dark = "<!-- afk-lavish-dark -->" + inject.DARK_INVERT
    old_tips = inject.MARK_START + "\n<script>old()</script>\n" + inject.MARK_END
    text = AUTHORED.replace("</body>", old_tips + "\n" + legacy_dark + "</body>")
    path = page(repo, text)
    assert run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert "<!-- afk-lavish-dark -->" not in html and "old()" not in html
    assert html.count(inject.MARK_START) == 1 and html.count(inject.DARK_START) == 1
    assert html.count("function lum(c)") == 1


def test_legacy_daisyui_marker_migrates(repo, seed, workflow):
    text = DAISY.replace("</body>", "<!-- afk-lavish-dark -->" + inject.DAISY_DARK + "</body>")
    path = page(repo, text)
    run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert "<!-- afk-lavish-dark -->" not in html and html.count("html{color-scheme:dark}") == 1


def test_a_changed_dictionary_replaces_the_block(repo, seed, workflow):
    path = page(repo)
    run(path, seed, workflow)
    workflow.write_text("**Seam**:\nnew meaning\n", encoding="utf-8")
    assert run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert dictionary(html)["seam"] == "new meaning" and html.count(inject.MARK_START) == 1


def test_unchanged_inputs_keep_bytes_and_mtime(repo, seed, workflow):
    path = page(repo)
    assert run(path, seed, workflow)
    before = path.read_bytes()
    past = path.stat().st_mtime_ns - 5_000_000_000
    os.utime(path, ns=(past, past))
    assert not run(path, seed, workflow)
    assert path.read_bytes() == before and path.stat().st_mtime_ns == past


def test_crlf_page_stays_crlf_and_idempotent(repo, seed, workflow):
    path = page(repo, AUTHORED.replace("\n", "\r\n"))
    run(path, seed, workflow)
    data = path.read_bytes()
    assert b"\n" not in data.replace(b"\r\n", b"")
    assert not run(path, seed, workflow) and path.read_bytes() == data


def test_utf8_text_and_dictionary_survive(repo, workflow, tmp_path):
    seed = tmp_path / "u.json"
    seed.write_text(json.dumps({"café": "naïve → ≥ </script> safe"}, ensure_ascii=False), encoding="utf-8")
    path = page(repo, AUTHORED.replace("seam", "café — ünïcode"))
    run(path, seed, workflow)
    html = path.read_text(encoding="utf-8")
    assert "café — ünïcode" in html and dictionary(html)["café"] == "naïve → ≥ </script> safe"
    assert "</script> safe" not in html


def test_a_rewrite_then_injection_restores_the_runtime(repo, seed, workflow):
    path = page(repo)
    run(path, seed, workflow)
    injected = path.read_bytes()
    path.write_bytes(AUTHORED.encode("utf-8"))  # a Write/Edit strips the runtime
    assert run(path, seed, workflow)
    assert path.read_bytes() == injected


def test_repository_falls_back_to_the_working_folder(tmp_path, seed, workflow):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "GLOSSARY.md").write_text("**Gate**:\ncwd gate\n", encoding="utf-8")
    path = page(tmp_path / "scratch")
    run(path, seed, workflow, cwd=repo)
    assert dictionary(path.read_text(encoding="utf-8"))["gate"] == "cwd gate"


def test_unreadable_page_raises(tmp_path, seed, workflow):
    path = tmp_path / "bad.html"
    path.write_bytes(b"\xff\xfe<html>")
    with pytest.raises(inject.InjectError):
        run(path, seed, workflow)
    with pytest.raises(inject.InjectError):
        run(tmp_path / "missing.html", seed, workflow)


def test_broken_seed_never_breaks_injection(repo, workflow, tmp_path):
    seed = tmp_path / "broken.json"
    seed.write_text("{not json", encoding="utf-8")
    path = page(repo)
    run(path, seed, workflow)
    assert dictionary(path.read_text(encoding="utf-8"))["seam"] == "workflow seam"


def test_the_shipped_seed_and_workflow_glossary_load():
    tips, _ = inject.load_dictionary(ROOT / "x.html", "", None)
    assert tips and all(isinstance(v, str) and v for v in tips.values())
    assert inject.SEED == ROOT / "scripts" / "lavish" / "tips.json" and inject.SEED.is_file()


def test_another_process_hash_seed_writes_the_same_bytes(tmp_path):
    code = "import sys; sys.path.insert(0, sys.argv[1]); from lavish import inject; inject.inject_file(sys.argv[2])"
    written = []
    for hash_seed in ("1", "2"):
        path = page(tmp_path / hash_seed)
        subprocess.run([sys.executable, "-c", code, str(ROOT / "scripts"), str(path)], cwd=ROOT, check=True,
                       env={**os.environ, "PYTHONHASHSEED": hash_seed}, timeout=60)
        written.append(path.read_bytes())
    assert written[0] == written[1]
