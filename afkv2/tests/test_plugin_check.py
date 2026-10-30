import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plugin_check  # noqa: E402

# v1 names are assembled at run time so this file itself passes the no-v1-name rule.
V1 = "af" + "k"
V1_ENV = V1.upper() + "_"
MARKER = "afkv2-" + "core-behaviors"
PRD_START = "afkv2:" + "prd:start"


def run_check(*args):
    done = subprocess.run(
        [sys.executable, str(SCRIPTS / "plugin_check.py"), *args],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return done.returncode, json.loads(done.stdout)


def run_tree_check(root, *args):
    done = subprocess.run(
        [sys.executable, str(root / "scripts" / "plugin_check.py"), *args],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return done.returncode, json.loads(done.stdout)


@pytest.fixture
def tree(tmp_path):
    """A copy of the plugin tree the check can change freely."""
    root = tmp_path / "afkv2"
    shutil.copytree(PLUGIN, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return root


def write_source(root, text):
    (root / "core" / "CORE-BEHAVIORS.md").write_text(text, encoding="utf-8", newline="")


def test_marker_hash_is_first_12_hex_of_sha256_over_the_text():
    body = "rule one\nrule two"
    assert plugin_check.marker_hash(body) == hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def test_build_hook_outputs_makes_plain_and_json_variants_from_one_source():
    outputs = plugin_check.build_hook_outputs("rule one\r\nrule two\r\n\r\n")
    sha = plugin_check.marker_hash("rule one\nrule two")
    plain = f"{MARKER} begin {sha}\nrule one\nrule two\n{MARKER} end {sha}\n"
    assert outputs[plugin_check.PLAIN_VARIANT] == plain
    wrapped = json.loads(outputs[plugin_check.CLAUDE_SUBAGENT_VARIANT])
    assert wrapped == {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": plain}}
    assert set(outputs) == {plugin_check.PLAIN_VARIANT, plugin_check.CLAUDE_SUBAGENT_VARIANT}


def test_hash_in_markers_matches_text_between_the_marker_lines():
    plain = plugin_check.build_hook_outputs("a\nb\n")[plugin_check.PLAIN_VARIANT]
    lines = plain.split("\n")
    between = "\n".join(lines[1:-2])
    sha = plugin_check.marker_hash(between)
    assert lines[0] == f"{MARKER} begin {sha}"
    assert lines[-2] == f"{MARKER} end {sha}"


def test_core_size_8000_characters_passes():
    assert plugin_check.check_core_size("x" * 8000) == []


def test_core_size_8001_characters_fails():
    problems = plugin_check.check_core_size("x" * 8001)
    assert len(problems) == 1
    assert "8001" in problems[0]


def test_core_size_counts_characters_not_crlf_bytes():
    assert plugin_check.check_core_size("é\r\n" * 4000) == []


def test_tree_with_8001_character_source_fails_the_check(tree):
    write_source(tree, "x" * 8001)
    problems = plugin_check.run_checks(tree)
    assert any("8001" in p for p in problems)


def test_shipped_tree_passes_its_own_check():
    code, answer = run_check()
    assert code == 0, answer
    assert answer["ok"] is True


def test_stale_prebuilt_file_is_refused(tree):
    write_source(tree, "a changed rule\n")
    problems = plugin_check.run_checks(tree)
    assert any("stale" in p for p in problems)


def test_missing_prebuilt_file_is_refused(tree):
    (tree / "hooks" / "built" / plugin_check.PLAIN_VARIANT).unlink()
    assert any("stale" in p or "missing" in p for p in plugin_check.run_checks(tree))


def test_unexpected_prebuilt_file_is_refused(tree):
    (tree / "hooks" / "built" / "extra.txt").write_text("x", encoding="utf-8")
    assert any("extra.txt" in p for p in plugin_check.run_checks(tree))


def test_crlf_checkout_of_prebuilt_files_is_not_stale(tree):
    built = tree / "hooks" / "built" / plugin_check.PLAIN_VARIANT
    built.write_bytes(built.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert plugin_check.run_checks(tree) == []


def test_build_rewrites_stale_files(tree):
    write_source(tree, "a changed rule\n")
    assert plugin_check.build(tree) == []
    assert plugin_check.run_checks(tree) == []
    assert "a changed rule" in (tree / "hooks" / "built" / plugin_check.PLAIN_VARIANT).read_text(encoding="utf-8")


def test_build_refuses_an_oversized_source_and_writes_nothing(tree):
    before = (tree / "hooks" / "built" / plugin_check.PLAIN_VARIANT).read_bytes()
    write_source(tree, "x" * 8001)
    assert plugin_check.build(tree)
    assert (tree / "hooks" / "built" / plugin_check.PLAIN_VARIANT).read_bytes() == before


def test_missing_source_is_refused(tree):
    (tree / "core" / "CORE-BEHAVIORS.md").unlink()
    assert any("CORE-BEHAVIORS.md" in p for p in plugin_check.run_checks(tree))


@pytest.mark.parametrize(
    "relative",
    [f"scripts/{V1}_tool.py", f"{V1}-notes.md", f"skills/{V1}/x.md", f"{V1.upper()}.md"],
)
def test_v1_file_name_fails(tree, relative):
    path = tree / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")
    problems = plugin_check.check_no_v1_names(tree)
    assert any(relative in p.replace("\\", "/") for p in problems)


@pytest.mark.parametrize(
    "line",
    [
        f'root = os.environ["{V1_ENV}PLUGIN_ROOT"]',
        f"echo %{V1_ENV}X%",
        f'marker = "<!-- {V1}:subtasks:start -->"',
        f'key = "{V1}.draft.round"',
        f'<div class="{V1}-card">',
        f'path = "{V1}v1-thing"',
        f"cfg = Path('.{V1}') / 'config.yaml'",
        f"set D=%LOCALAPPDATA%\\{V1}\\state",
        f"D = 'C:\\{V1}'",
        f'Path("{V1}")',
        f"localStorage.getItem('{V1}')",
        f'<div class="{V1}">',
        f'<div class="{V1} card">',
        f'<div class="card {V1}">',
        f"set {V1.upper()}=1",
        f"echo %{V1.upper()}%",
        f"echo ${V1.upper()}",
        f"see skills/{V1}/x",
        f"echo ${{{V1.upper()}}}",
        f'<div className="{V1}">',
        f"{V1}\\state",
        f'<div class="my-{V1}">',
        f".card-{V1} {{ color: red }}",
        f"#{V1} {{ color: red }}",
        f'{{"key": "draft-{V1}"}}',
        f"env: MY_{V1.upper()}",
        f"set MY_{V1.upper()}=1",
        f'key = "{V1}_" + name',
        f'key = "{V1}-" + name',
        f'prefix = "{V1_ENV}"',
        f'name = f"{V1}_{{x}}"',
        f"localStorage.setItem('{V1}_' + key)",
        f'{{"prefix": "{V1}:"}}',
        f'{{"prefix": "{V1}."}}',
        f'{{"prefix": "{V1}/"}}',
        f"{V1_ENV}",
        f"_{V1} = 1",
        f"__{V1}__",
        f"self._{V1} = 1",
        f"set _{V1.upper()}=1",
        f"._{V1} {{ color: red }}",
    ],
)
@pytest.mark.parametrize("name", ["sample.py", "sample.txt"])
def test_v1_name_in_text_fails(tree, line, name):
    (tree / "scripts" / name).write_text(line + "\n", encoding="utf-8")
    assert any(f"{name}:1" in p for p in plugin_check.check_no_v1_names(tree))


def test_code_suffixes_are_the_recorded_set():
    assert plugin_check.CODE_SUFFIXES == {
        ".py", ".cmd", ".bat", ".ps1", ".sh", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".vue",
        ".html", ".css", ".yaml", ".yml", ".toml",
    }


@pytest.mark.parametrize("suffix", sorted(plugin_check.CODE_SUFFIXES))
@pytest.mark.parametrize("line", [f"{V1} = 1", f"def {V1}(x):", f"run({V1})"])
def test_bare_v1_word_in_code_fails(tree, line, suffix):
    (tree / "scripts" / f"sample{suffix}").write_text(line + "\n", encoding="utf-8")
    assert any(f"sample{suffix}:1" in p for p in plugin_check.check_no_v1_names(tree))


@pytest.mark.parametrize(
    "data",
    [
        "set X=1\r\nrem caf\xe9\r\n".encode("latin-1"),
        "set X=1\r\n".encode("utf-16"),
        f"set {V1_ENV}X=1\r\n".encode("utf-16-le"),
    ],
)
def test_code_file_that_is_not_utf8_is_a_problem(tree, data):
    (tree / "scripts" / "sample.cmd").write_bytes(data)
    assert any("sample.cmd" in p and "UTF-8" in p for p in plugin_check.check_no_v1_names(tree))


@pytest.mark.parametrize("name", ["sample.py", "sample.md"])
def test_file_that_cannot_be_opened_fails_the_tree_check(tree, name, monkeypatch):
    (tree / "scripts" / name).write_text("x = 1\n", encoding="utf-8")
    read_text = Path.read_text

    def locked(self, *args, **kwargs):
        if self.name == name:
            raise PermissionError(13, "locked by another process")
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", locked)
    assert any(name in p and "cannot read" in p for p in plugin_check.run_checks(tree))


def test_binary_file_outside_code_is_skipped(tree):
    (tree / "scripts" / "sample.png").write_bytes(b"\xff\xfe\x00")
    assert plugin_check.check_no_v1_names(tree) == []


@pytest.mark.parametrize(
    "line",
    [
        f'"description": "{V1.upper()} 2.0 beta: a workflow."',
        f"The {V1.upper()} 2.0 beta and the `{V1}` plugin are prose.",
        f"see https://github.com/owner/{V1}-driver for the source",
        f"Compare with {V1.upper()}. Then go on.",
        f"Run {V1.upper()}: then stop.",
        f"The tools ({V1.upper()}, Jira) stay.",
        f"{V1.upper()}",
    ],
)
def test_prose_passes_outside_code(tree, line):
    (tree / "scripts" / "sample.md").write_text(line + "\n", encoding="utf-8")
    assert plugin_check.check_no_v1_names(tree) == []


@pytest.mark.parametrize("line", ['x = "afkv2-core"', "set AFKV2_DATA=1", 'cls = "afkv2-card"', 'p = "afkv2"'])
def test_afkv2_names_in_code_pass(tree, line):
    (tree / "scripts" / "sample.py").write_text(line + "\n", encoding="utf-8")
    assert plugin_check.check_no_v1_names(tree) == []


@pytest.mark.parametrize(
    "line",
    [
        f'if line.startswith("{MARKER} begin"):',
        f'found = "{MARKER}" in text',
        f're.search(r"{MARKER} end ([0-9a-f]{{12}})", text)',
        f'at = text.find("{MARKER}")',
        f'const hit = body.includes("{PRD_START}");',
        f'findstr /c:"{MARKER}" out.txt',
        f'if line.startswith("<!-- {V1}:prd:start"):',
        f"/{MARKER}/.test(line)",
        f'Select-String -Pattern "{MARKER}" x.txt',
        f'sed -n "/{MARKER}/p" x',
        f'line[:20] == "{MARKER}"',
        f'line.slice(0, 5) === "{MARKER}"',
        f'"{MARKER}" == line[:20]',
        f'"{MARKER}" === line[0:20]',
        f'text.rsplit("{MARKER}")',
        f'text.rpartition("{MARKER}")',
        f'line.removeprefix("{MARKER}")',
        f'line.removesuffix("{MARKER}")',
        f'line.substring(0, 5) === "{MARKER}"',
        f'line.substr(0, 5) === "{MARKER}"',
        f'/{MARKER}/.exec(line)',
        f'[[ "$line" == {MARKER}* ]]',
        f'awk "/{MARKER}/" x',
        f'grep "{MARKER}" x',
    ],
)
def test_prefix_or_substring_marker_match_fails(tree, line):
    name = "sample.cmd" if line.startswith("findstr") else "sample.py"
    (tree / "scripts" / name).write_text(line + "\n", encoding="utf-8")
    assert any(f"{name}:1" in p for p in plugin_check.check_marker_matching(tree))


@pytest.mark.parametrize(
    "name, line",
    [
        ("sample.js", f'line.startsWith("{MARKER}")'),
        ("sample.js", f'line.endsWith("{MARKER}")'),
        ("sample.js", f'line.indexOf("{MARKER}")'),
        ("sample.ps1", f'$line.StartsWith("{MARKER}")'),
        ("sample.ps1", f'$line.Substring(0,5) -eq "{MARKER}"'),
        ("sample.ps1", f'$line -Match "{MARKER}"'),
        ("sample.ps1", f'$line -cmatch "{MARKER}"'),
        ("sample.ps1", f'$line -notmatch "{MARKER}"'),
        ("sample.ps1", f'$line -ilike "{MARKER}*"'),
        ("sample.ps1", f'select-string -Pattern "{MARKER}" x'),
        ("sample.ps1", f'sls "{MARKER}" x'),
        ("sample.cmd", f'FINDSTR /c:"{MARKER}" x'),
        ("sample.cmd", f'if "%line:~0,20%"=="{MARKER}" echo y'),
        ("sample.yaml", f'run: line.startswith("{MARKER}")'),
    ],
)
def test_marker_match_in_other_spellings_fails(tree, name, line):
    (tree / "scripts" / name).write_text(line + "\n", encoding="utf-8")
    assert any(f"{name}:1" in p for p in plugin_check.check_marker_matching(tree))


@pytest.mark.parametrize(
    "name, line",
    [
        ("sample.py", f'if line == "{MARKER} begin " + sha:'),
        ("sample.py", f're.fullmatch(r"{MARKER} end ([0-9a-f]{{12}})", line)'),
        ("sample.cmd", f'type "%~dp0built\\{MARKER}.txt"'),
        ("sample.py", f'd["{PRD_START}"] == x'),
        ("sample.py", f'd["a:b"] == "{MARKER}"'),
        ("sample.html", f"<p>the {MARKER} text in context</p>"),
        ("sample.yaml", f"marker: {MARKER} in file"),
    ],
)
def test_full_line_marker_match_passes(tree, name, line):
    (tree / "scripts" / name).write_text(line + "\n", encoding="utf-8")
    assert plugin_check.check_marker_matching(tree) == []


@pytest.mark.parametrize("relative", plugin_check.MANIFESTS)
def test_manifests_must_name_the_plugin_afkv2(tree, relative):
    manifest = tree / relative
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["name"] = "other"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert any("plugin.json" in p and "afkv2" in p for p in plugin_check.run_checks(tree))


def test_unparseable_hooks_file_fails(tree):
    (tree / "hooks" / "hooks.json").write_text("{", encoding="utf-8")
    assert any("hooks.json" in p for p in plugin_check.run_checks(tree))


@pytest.mark.parametrize("value", ["null", '"SessionStart SubagentStart"', "[]"])
def test_hooks_value_that_is_no_object_is_a_problem_not_a_crash(tree, value):
    (tree / "hooks" / "hooks.json").write_text('{"hooks": ' + value + "}", encoding="utf-8")
    assert any("hooks.json" in p for p in plugin_check.run_checks(tree))


@pytest.mark.parametrize("event", plugin_check.HOOK_EVENTS)
@pytest.mark.parametrize(
    "value",
    [None, [], "missing", [{}], [1], [{"matcher": "x", "hooks": []}], [{"hooks": [{"type": "command"}]}], [{"hooks": [1]}]],
)
def test_event_with_no_registration_is_a_problem(tree, event, value):
    path = tree / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if value == "missing":
        del data["hooks"][event]
    else:
        data["hooks"][event] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    assert any(f"no {event} registration" in p for p in plugin_check.run_checks(tree))


@pytest.mark.parametrize("verb", ["check", "build"])
def test_unreadable_source_answers_json(tree, verb):
    (tree / "core" / "CORE-BEHAVIORS.md").write_bytes(b"\xff\xfe bad\n")
    code, answer = run_tree_check(tree, verb)
    assert code == 1
    assert any("CORE-BEHAVIORS.md" in p for p in answer["problems"])


def test_prebuilt_file_that_does_not_decode_is_stale(tree):
    (tree / "hooks" / "built" / plugin_check.PLAIN_VARIANT).write_bytes(b"\xff bad")
    code, answer = run_tree_check(tree, "check")
    assert code == 1
    assert any("stale" in p for p in answer["problems"])


def test_prebuilt_path_that_cannot_be_written_answers_json(tree):
    built = tree / "hooks" / "built" / plugin_check.PLAIN_VARIANT
    built.unlink()
    built.mkdir()
    code, answer = run_tree_check(tree, "build")
    assert code == 1
    assert any("cannot write" in p for p in answer["problems"])


def test_built_folder_that_is_a_file_answers_json(tree):
    built = tree / "hooks" / "built"
    shutil.rmtree(built)
    built.write_text("not a folder\n", encoding="utf-8")
    code, answer = run_tree_check(tree, "build")
    assert code == 1
    assert any("cannot write" in p for p in answer["problems"])


@pytest.mark.xfail(strict=True, reason="known gap: the rule reads one line and traces no variable")
def test_marker_held_in_a_variable_and_matched_on_another_line_fails(tree):
    (tree / "scripts" / "sample.py").write_text(f'MARK = "{MARKER}"\nfound = MARK in text\n', encoding="utf-8")
    assert plugin_check.check_marker_matching(tree)


@pytest.mark.parametrize("args", [("nonsense",), ("--help",), ("check", "-h")])
def test_every_usage_error_answers_json_with_exit_2(args):
    code, answer = run_check(*args)
    assert code == 2
    assert answer["ok"] is False
    assert set(answer["error"]) == {"code", "reason"}
    assert answer["error"]["code"] == "usage"
    assert isinstance(answer["error"]["reason"], str) and answer["error"]["reason"]


def test_check_command_answers_json_and_exits_1_on_problems(tree):
    write_source(tree, "x" * 8001)
    done = subprocess.run(
        [sys.executable, str(tree / "scripts" / "plugin_check.py")],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    answer = json.loads(done.stdout)
    assert done.returncode == 1
    assert answer["ok"] is False
    assert answer["error"]["code"] == "check-failed"
    assert answer["problems"]


def test_build_command_regenerates_and_checks(tree):
    write_source(tree, "new rule\n")
    done = subprocess.run(
        [sys.executable, str(tree / "scripts" / "plugin_check.py"), "build"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert done.returncode == 0, done.stdout
    assert json.loads(done.stdout)["ok"] is True


def test_marketplace_lists_afkv2_beside_the_v1_plugin():
    marketplace = json.loads((PLUGIN.parent / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entries = {entry["name"]: entry for entry in marketplace["plugins"]}
    v1_manifest = json.loads((PLUGIN.parent / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert entries[V1] == {
        "name": V1,
        "source": "./",
        "version": v1_manifest["version"],
        "description": v1_manifest["description"],
    }
    assert entries["afkv2"]["source"] == "./afkv2"
    for manifest in plugin_check.MANIFESTS:
        data = json.loads((PLUGIN / manifest).read_text(encoding="utf-8"))
        assert data["version"] == entries["afkv2"]["version"]
