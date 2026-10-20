"""Pattern resolver and the built-in pattern records BP-1 to BP-5 with their charters."""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from team import resolver  # noqa: E402
from team.resolver import PatternRefused  # noqa: E402

PATTERNS = SCRIPTS / "team" / "patterns"
FEATURE = "feat-x"
ALL = list(resolver.ABILITIES)
PROGRESS = "progress: MILESTONE — SENTENCE"
PROPERTIES = ("Segregation of duty", "Independent cross-check", "Several angles", "Maximum autonomy")
RECORD_FIELDS = {"name", "description", "charter", "schema-version", "record-version", "roles", "edges", "steps",
                 "includes"}
ROLE_FIELDS = {"model", "lifespan", "count", "report-target", "hub", "charter"}
BUILTIN = {"BP-1-solo.json": "solo", "BP-2-debate.json": "debate", "BP-3-build-verify.json": "build-verify",
           "BP-4-review-panel.json": "review-panel", "BP-5-afk-lite.json": "afk-lite"}


def role(model="m1", target="", hub=False, charter="role part", lifespan="Step", **extra):
    return {"model": model, "lifespan": lifespan, "count": 1, "report-target": target, "hub": hub,
            "charter": charter, **extra}


def pattern(name, roles=None, steps=None, includes=(), charter="pattern part", edges=(), **extra):
    roles = {"worker": role()} if roles is None else roles
    record = {"name": name, "description": f"{name} description", "schema-version": 1, "record-version": 1,
              "roles": roles, "edges": list(edges),
              "steps": steps if steps is not None else [{"name": "work", "roles": list(roles)}],
              "includes": list(includes)}
    if charter is not None:
        record["charter"] = charter
    record.update(extra)
    return record


def resolve(tmp_path, pick, saved=None, fill=lambda model: True, abilities=ALL, moderator="mod-model", **kw):
    return resolver.resolve_pattern(tmp_path, FEATURE, pick, session="contact-1", can_fill=fill,
                                    abilities=abilities, moderator_model=moderator, saved=saved, **kw)


def refused(tmp_path, pick, **kw) -> str:
    with pytest.raises(PatternRefused) as caught:
        resolve(tmp_path, pick, **kw)
    assert not resolver.resolved_path(tmp_path, FEATURE).exists(), "a refused pattern starts nothing"
    return str(caught.value)


def run_cli(tmp_path, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / "team" / "resolver.py"), "--root", str(tmp_path),
                           "--feature", FEATURE, "--session", "contact-1", "--moderator-model", "frontier@claude",
                           *args], capture_output=True, text=True, encoding="utf-8")


def every_model(*extra):
    models = [f"{tier}@{provider}" for tier in ("frontier", "implementation", "digest", "deterministic")
              for provider in ("claude", "codex")]
    return [arg for model in [*models, *extra] for arg in ("--model", model)]


def every_ability():
    return [arg for ability in ALL for arg in ("--ability", ability)]


# --- built-in records, loaded by their real file names --------------------------------------------------------


def test_the_resolver_names_every_record_file_and_ships_nothing_else():
    assert set(resolver.BUILTIN_FILES) == set(BUILTIN)
    assert sorted(p.name for p in PATTERNS.glob("*.json")) == sorted(BUILTIN)
    assert sorted(p.name for p in PATTERNS.glob("*.md")) == ["STANDARD.md", resolver.MODERATOR_PART]


@pytest.mark.parametrize("file,name", sorted(BUILTIN.items()))
def test_each_builtin_record_resolves_by_its_real_file_name(tmp_path, file, name):
    record = json.loads((PATTERNS / file).read_text(encoding="utf-8"))
    assert record["name"] == name and record["record-version"] == 1 and record["schema-version"] == 1
    assert set(record) <= RECORD_FIELDS, "no pattern record carries an agent, message or spend limit"
    for fields in record["roles"].values():
        assert set(fields) <= ROLE_FIELDS
    done = run_cli(tmp_path, "--pattern", name, *every_model(), *every_ability())
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    written = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert written["pattern-name"] == name and written["source"] == "built-in" and written["record-version"] == 1
    assert set(out["charters"]) == set(written["team"]["roles"])


@pytest.mark.parametrize("file,name", sorted(BUILTIN.items())[1:])
def test_each_builtin_record_with_roles_is_refused_with_exit_2_when_a_role_cannot_be_filled(tmp_path, file, name):
    done = run_cli(tmp_path, "--pattern", name, *every_ability())
    assert done.returncode == 2
    assert re.search(r"refused: (role \S+ cannot be filled|debate \S+: its moderator \S+ cannot be filled)",
                     done.stderr), done.stderr
    assert not resolver.resolved_path(tmp_path, FEATURE).exists()


def test_bp1_solo_has_no_roles_no_charter_and_needs_none(tmp_path):
    record = json.loads((PATTERNS / "BP-1-solo.json").read_text(encoding="utf-8"))
    assert record["roles"] == {} and "charter" not in record
    result = resolve(tmp_path, "solo", fill=lambda model: False, abilities=[])
    assert result.charters == {} and result.pattern["team"]["roles"] == {}
    assert result.pattern["team"]["edges"] == []


@pytest.mark.parametrize("file", ["BP-2-debate.json", "BP-3-build-verify.json", "BP-4-review-panel.json",
                                  "BP-5-afk-lite.json"])
def test_every_role_part_and_the_moderator_part_carry_the_reporting_duties(file):
    record = json.loads((PATTERNS / file).read_text(encoding="utf-8"))
    parts = {role: fields["charter"] for role, fields in record["roles"].items()}
    parts["the moderator part"] = (PATTERNS / resolver.MODERATOR_PART).read_text(encoding="utf-8")
    for where, part in parts.items():
        assert PROGRESS in part, f"{file} {where}"
        assert "Milestones:" in part, f"{file} {where}"
        assert "at each milestone" in part and "at once on a blocker or a question" in part
        assert "finished at the end" in part
        assert "only answers to their questions and data their current duty uses" in part


@pytest.mark.parametrize("file", ["BP-2-debate.json", "BP-3-build-verify.json", "BP-4-review-panel.json",
                                  "BP-5-afk-lite.json"])
def test_each_record_that_starts_agents_says_how_it_meets_the_standard_twice(file):
    record = json.loads((PATTERNS / file).read_text(encoding="utf-8"))
    for text in (record["description"], record["charter"]):
        for prop in PROPERTIES:
            assert prop.lower() in text.lower(), (file, prop)


def test_debate_runs_two_debaters_on_different_models_plus_a_moderator(tmp_path):
    record = json.loads((PATTERNS / "BP-2-debate.json").read_text(encoding="utf-8"))
    step = record["steps"][0]
    assert step["debate"] is True and len(step["roles"]) >= 2
    assert len({record["roles"][r]["model"] for r in step["roles"]}) == len(step["roles"])
    result = resolve(tmp_path, "debate")
    assert resolver.MODERATOR in result.pattern["team"]["steps"][0]["roles"]


def test_no_description_names_a_workflow_stage():
    for file in BUILTIN:
        description = json.loads((PATTERNS / file).read_text(encoding="utf-8"))["description"]
        assert "/afk:" not in description


def test_the_markdown_parts_name_no_harness_or_tool():
    for path in PATTERNS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\b(Claude Code|Codex|SendMessage|subagent_type|mcp__)", text), path.name


def test_the_standard_states_ps1_to_ps4_once():
    text = (PATTERNS / "STANDARD.md").read_text(encoding="utf-8")
    assert text.startswith("# Pattern standard")
    for ident in ("PS-1", "PS-2", "PS-3", "PS-4"):
        assert len(re.findall(rf"^\| {ident} \|", text, re.M)) == 1


def test_the_config_reader_holds_the_builtin_names_the_records_carry():
    spec = importlib.util.spec_from_file_location("afk_config", SCRIPTS / "afk-config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.BUILTIN_PATTERNS) == set(resolver.builtin_records())


def test_records_live_outside_the_folders_the_gates_read():
    parts = PATTERNS.relative_to(REPO).parts
    assert not {"agents", "adapters", ".agents", ".codex", "lib", "build", "dist", "var", "env"} & set(parts)


# --- refusals ---------------------------------------------------------------------------------------------------


def test_an_unfillable_role_is_refused_naming_it(tmp_path):
    saved = {"p": pattern("p", roles={"ok": role(model="good"), "gap": role(model="bad")})}
    message = refused(tmp_path, "p", saved=saved, fill=lambda model: model == "good")
    assert "role gap cannot be filled" in message and "bad" in message


def test_a_fillable_pattern_starts(tmp_path):
    saved = {"p": pattern("p", roles={"ok": role(model="good")})}
    assert resolve(tmp_path, "p", saved=saved, fill=lambda model: model == "good").path.is_file()


def test_a_missing_messaging_ability_is_refused_naming_it(tmp_path):
    saved = {"p": pattern("p", roles={"a": role(), "b": role(target="a")})}
    message = refused(tmp_path, "p", saved=saved, abilities=["worker-to-contact", "exit-signal", "limit-signal"])
    assert "worker-to-worker" in message
    for missing in ("worker-to-contact", "exit-signal", "limit-signal"):
        rest = [a for a in ALL if a != missing]
        assert missing in refused(tmp_path, "p", saved=saved, abilities=rest)


def test_a_team_with_no_role_to_role_edge_needs_no_worker_to_worker(tmp_path):
    saved = {"p": pattern("p", roles={"a": role()})}
    assert resolve(tmp_path, "p", saved=saved, abilities=["worker-to-contact", "exit-signal", "limit-signal"])


@pytest.mark.parametrize("chain", [["p"], ["p", "q"], ["p", "q", "r"]])
def test_a_pattern_that_includes_itself_is_refused(tmp_path, chain):
    saved = {name: pattern(name, roles={f"r-{name}": role()}, includes=[chain[(i + 1) % len(chain)]])
             for i, name in enumerate(chain)}
    assert "includes itself" in refused(tmp_path, "p", saved=saved)


def test_an_unknown_record_version_is_refused_naming_pattern_and_version(tmp_path):
    message = refused(tmp_path, "p", saved={"p": pattern("p", **{"record-version": 2})})
    assert "pattern p" in message and "record version 2" in message
    assert "schema version 3" in refused(tmp_path, "p", saved={"p": pattern("p", **{"schema-version": 3})})


def test_a_builtin_record_of_an_unknown_version_is_refused(tmp_path, monkeypatch):
    real = resolver.builtin_records()
    bumped = copy.deepcopy(real)
    bumped["debate"]["record-version"] = 9
    monkeypatch.setattr(resolver, "builtin_records", lambda: bumped)
    message = refused(tmp_path, "debate")
    assert "pattern debate" in message and "record version 9" in message


def test_a_saved_record_without_a_version_reads_as_version_1(tmp_path):
    record = pattern("p")
    del record["record-version"]
    del record["schema-version"]
    assert resolve(tmp_path, "p", saved={"p": record}).pattern["record-version"] == 1


def test_a_debate_with_no_fillable_moderator_is_refused_naming_the_debate(tmp_path):
    saved = {"p": pattern("p", roles={"a": role(model="m1"), "b": role(model="m2")},
                          steps=[{"name": "argue", "roles": ["a", "b"], "debate": True}])}
    message = refused(tmp_path, "p", saved=saved, fill=lambda model: model != "mod-model")
    assert "debate argue" in message and "cannot be filled" in message
    hubbed = {"p": pattern("p", roles={"h": role(model="hub-model", hub=True), "a": role(), "b": role()},
                           steps=[{"name": "argue", "roles": ["h", "a", "b"], "debate": True}])}
    message = refused(tmp_path, "p", saved=hubbed, fill=lambda model: model != "hub-model")
    assert "debate argue" in message and "its moderator h" in message


def test_a_debate_gets_the_hub_else_an_added_moderator_with_the_shipped_part(tmp_path):
    saved = {"p": pattern("p", roles={"a": role(model="m1"), "b": role(model="m2")},
                          steps=[{"name": "argue", "roles": ["a", "b"], "debate": True}])}
    result = resolve(tmp_path, "p", saved=saved)
    step = result.pattern["team"]["steps"][0]
    assert step["moderator"] == resolver.MODERATOR and resolver.MODERATOR in step["roles"]
    assert result.pattern["team"]["roles"][resolver.MODERATOR]["model"] == "mod-model"
    shipped = (PATTERNS / resolver.MODERATOR_PART).read_text(encoding="utf-8")
    assert result.charters[resolver.MODERATOR] == "pattern part\n\n" + shipped
    edges = result.pattern["team"]["edges"]
    for debater in ("a", "b"):
        assert {"from": resolver.MODERATOR, "to": debater, "kinds": ["message"]} in edges
        assert {"from": debater, "to": resolver.MODERATOR, "kinds": ["message"]} in edges
    hubbed = {"p": pattern("p", roles={"h": role(hub=True), "a": role(), "b": role()},
                           steps=[{"name": "argue", "roles": ["h", "a", "b"], "debate": True}])}
    result = resolve(tmp_path, "p", saved=hubbed)
    assert result.pattern["team"]["steps"][0]["moderator"] == "h"
    assert resolver.MODERATOR not in result.pattern["team"]["roles"]


@pytest.mark.parametrize("value", ["absent", None, "", "   "])
def test_a_missing_or_empty_role_part_is_refused_naming_pattern_and_role(tmp_path, value):
    fields = role()
    if value == "absent":
        del fields["charter"]
    else:
        fields["charter"] = value
    message = refused(tmp_path, "p", saved={"p": pattern("p", roles={"ok": role(), "gap": fields})})
    assert "pattern p" in message and "role gap" in message and "charter part" in message


@pytest.mark.parametrize("value", ["absent", None, ""])
def test_a_missing_or_empty_pattern_part_is_refused_naming_the_pattern(tmp_path, value):
    record = pattern("p", charter=None if value == "absent" else value)
    message = refused(tmp_path, "p", saved={"p": record})
    assert "pattern p" in message and "charter pattern part" in message


def test_the_charter_check_tests_presence_not_content(tmp_path):
    saved = {"p": pattern("p", roles={"a": role(charter="x")}, charter="y")}
    assert resolve(tmp_path, "p", saved=saved).charters == {"a": "y\n\nx"}


def test_a_one_off_with_roles_and_a_missing_role_part_is_refused_with_exit_2(tmp_path):
    one_off = pattern("quick", roles={"gap": role(charter="")})
    del one_off["record-version"]
    path = tmp_path / "one-off.json"
    path.write_text(json.dumps(one_off), encoding="utf-8")
    done = run_cli(tmp_path, "--one-off", str(path), *every_model("m1"), *every_ability())
    assert done.returncode == 2
    assert "pattern quick" in done.stderr and "role gap" in done.stderr


def test_a_one_off_with_no_roles_needs_no_charter(tmp_path):
    one_off = pattern("quick", roles={}, charter=None, steps=[{"name": "alone", "roles": []}])
    result = resolve(tmp_path, one_off, fill=lambda model: False, abilities=[])
    assert result.charters == {}
    assert result.pattern["source"] == "one-off" and result.pattern["record-version"] is None
    assert result.pattern["sources"] == [{"name": "quick", "record-version": None, "source": "one-off"}]


def test_a_one_off_with_roles_resolves_with_its_own_charter(tmp_path):
    one_off = pattern("quick", roles={"a": role(charter="mine")}, charter="ours")
    result = resolve(tmp_path, one_off)
    assert result.charters == {"a": "ours\n\nmine"}
    assert "charter" not in json.dumps(result.pattern["team"])


def test_a_one_off_cannot_take_a_builtin_or_saved_name(tmp_path):
    assert "built-in or saved" in refused(tmp_path, pattern("debate"))
    assert "built-in or saved" in refused(tmp_path, pattern("p"), saved={"p": pattern("p")})


def test_a_one_off_is_never_written_to_repository_configuration(tmp_path):
    saved: dict = {}
    resolve(tmp_path, pattern("quick"), saved=saved)
    assert saved == {}
    assert sorted(p.name for p in (tmp_path / FEATURE).iterdir()) == ["pattern.json"]


def test_a_role_defined_two_ways_is_refused(tmp_path):
    saved = {"p": pattern("p", roles={"shared": role(model="m1")}, includes=["q"]),
             "q": pattern("q", roles={"shared": role(model="m2")})}
    message = refused(tmp_path, "p", saved=saved)
    assert "role shared has 2 different definitions" in message and "p" in message and "q" in message


def test_a_role_defined_the_same_way_merges_into_one(tmp_path):
    saved = {"p": pattern("p", roles={"shared": role()}, includes=["q"]),
             "q": pattern("q", roles={"shared": role(), "other": role()})}
    roles = resolve(tmp_path, "p", saved=saved).pattern["team"]["roles"]
    assert sorted(roles) == ["other", "shared"]


@pytest.mark.parametrize("record,needle", [
    (pattern("p", edges=[{"from": "worker", "to": "ghost", "kinds": ["message"]}]), "'ghost' names a role"),
    (pattern("p", edges=[{"from": "ghost", "to": "worker", "kinds": ["message"]}]), "'ghost' names a role"),
    (pattern("p", steps=[{"name": "s", "roles": ["ghost"]}]), "starts 'ghost'"),
    (pattern("p", roles={"worker": role(target="ghost")}), "reports to 'ghost'"),
])
def test_an_undefined_role_in_an_edge_a_step_or_a_report_target_is_refused(tmp_path, record, needle):
    assert needle in refused(tmp_path, "p", saved={"p": record})


@pytest.mark.parametrize("change,needle", [
    ({"lifespan": "Week"}, "lifespan"), ({"count": 0}, "count"), ({"hub": "yes"}, "hub"),
    ({"model": ""}, "model"), ({"limit": 3}, "unknown field limit"),
])
def test_a_malformed_role_field_is_refused_naming_it(tmp_path, change, needle):
    saved = {"p": pattern("p", roles={"worker": {**role(), **change}})}
    assert needle in refused(tmp_path, "p", saved=saved)


def test_two_hubs_and_two_steps_of_one_name_are_refused(tmp_path):
    saved = {"p": pattern("p", roles={"a": role(hub=True), "b": role(hub=True)})}
    assert "2 hubs" in refused(tmp_path, "p", saved=saved)
    saved = {"p": pattern("p", steps=[{"name": "s", "roles": []}, {"name": "s", "roles": []}])}
    assert "2 steps named s" in refused(tmp_path, "p", saved=saved)


def test_an_edge_kind_outside_the_kind_set_is_refused(tmp_path):
    saved = {"p": pattern("p", roles={"a": role(), "b": role()},
                          edges=[{"from": "a", "to": "b", "kinds": ["gossip"]}])}
    assert "kinds" in refused(tmp_path, "p", saved=saved)


def test_a_pick_that_names_no_pattern_is_refused(tmp_path):
    assert "'nope' names no pattern" in refused(tmp_path, "nope")
    assert "'nope' names no pattern" in refused(tmp_path, "p", saved={"p": pattern("p", includes=["nope"])})


@pytest.mark.parametrize("where", ["record", "role"])
def test_a_saved_record_carrying_a_limit_field_is_refused(tmp_path, where):
    record = pattern("p", **({"max-agents": 3} if where == "record" else {}))
    if where == "role":
        record["roles"]["worker"]["max-agents"] = 3
    assert "unknown field max-agents" in refused(tmp_path, "p", saved={"p": record})


@pytest.mark.parametrize("feature", ["", ".", "..", "a/b", "a\\b", "a:b"])
def test_an_unsafe_feature_identifier_is_refused(tmp_path, feature):
    with pytest.raises(PatternRefused, match="unsafe feature identifier"):
        resolver.resolve_pattern(tmp_path, feature, "solo", session="contact-1", can_fill=lambda model: True,
                                 abilities=ALL, moderator_model="mod-model")


@pytest.mark.parametrize("name", ["..", "a/b", "a\\b", "a:b", " "])
def test_a_role_or_report_target_that_is_no_safe_name_is_refused(tmp_path, name):
    saved = {"p": pattern("p", roles={name: role()}, steps=[{"name": "s", "roles": []}])}
    assert "is not a role name" in refused(tmp_path, "p", saved=saved)
    saved = {"p": pattern("p", roles={"worker": role(target=name)})}
    assert "is not a role name" in refused(tmp_path, "p", saved=saved)


@pytest.mark.parametrize("record", [
    pattern("p", roles={"a": role(), "b": role()}, edges=[{"from": ["a"], "to": "b", "kinds": ["message"]}]),
    pattern("p", roles={"a": role(), "b": role()}, edges=[{"from": "a", "to": {"b": 1}, "kinds": ["message"]}]),
    pattern("p", steps=[{"name": "s", "roles": [["worker"]]}]),
])
def test_an_edge_end_or_step_role_that_is_no_name_is_refused(tmp_path, record):
    assert "a role it does not define" in refused(tmp_path, "p", saved={"p": record})


def test_an_edge_end_that_is_no_name_exits_2_on_the_command_line(tmp_path):
    one_off = pattern("quick", roles={"a": role(), "b": role()},
                      edges=[{"from": ["a"], "to": "b", "kinds": ["message"]}])
    path = tmp_path / "one-off.json"
    path.write_text(json.dumps(one_off), encoding="utf-8")
    done = run_cli(tmp_path, "--one-off", str(path), *every_model("m1"), *every_ability())
    assert done.returncode == 2 and "pattern quick" in done.stderr, done.stderr


@pytest.mark.parametrize("roles,needle", [
    ({"a": role(target="a")}, "role a reports to itself"),
    ({"a": role(target="b"), "b": role(target="a")}, "report targets loop"),
    ({"a": role(target="b"), "b": role(target="c"), "c": role(target="b")}, "report targets loop"),
    ({"a": role(target="b"), "b": role(target="c"), "c": role(target="a")}, "report targets loop"),
    ({"a": role(target="b"), "b": role(target="ghost")}, "reports to 'ghost', a role it does not define"),
])
def test_a_role_reporting_to_itself_or_a_report_loop_is_refused(tmp_path, roles, needle):
    assert needle in refused(tmp_path, "p", saved={"p": pattern("p", roles=roles)})


DEBATERS = {"a": role(model="m1"), "b": role(model="m2")}
ARGUE = [{"name": "argue", "roles": ["a", "b"], "debate": True}]


def _same_as_added():
    return role(model="mod-model", charter=(PATTERNS / resolver.MODERATOR_PART).read_text(encoding="utf-8"))


@pytest.mark.parametrize("saved,owner,step", [
    ({"p": pattern("p", roles=DEBATERS, includes=["q"], steps=ARGUE),
      "q": pattern("q", roles={resolver.MODERATOR: role()})}, "q", "argue of pattern p"),
    ({"p": pattern("p", roles={**DEBATERS, resolver.MODERATOR: role()}, steps=ARGUE)}, "p", "argue of pattern p"),
    ({"p": pattern("p", roles=DEBATERS, includes=["q"], steps=ARGUE),
      "q": pattern("q", roles={resolver.MODERATOR: _same_as_added()})}, "q", "argue of pattern p"),
    ({"p": pattern("p", roles=DEBATERS, includes=["q", "r"],
                   steps=[{"name": "one", "roles": ["a", "b"], "debate": True}]),
      "q": pattern("q", roles=DEBATERS, steps=[{"name": "two", "roles": ["a", "b"], "debate": True}]),
      "r": pattern("r", roles={resolver.MODERATOR: role()})}, "r", "one of pattern p"),
    *[({"p": pattern("p", roles={}, charter=None, includes=["q", "r"], steps=[{"name": "go", "roles": []}]),
        "q": pattern("q", roles={resolver.MODERATOR: fields()}),
        "r": pattern("r", roles=DEBATERS, steps=ARGUE)}, "q", "argue of pattern r")
      for fields in (role, _same_as_added)],
], ids=["included-role", "own-role", "same-values-as-added", "first-debate-step-named", "role-walked-first",
        "same-values-walked-first"])
def test_a_role_named_like_the_added_moderator_is_refused_naming_both(tmp_path, saved, owner, step):
    message = refused(tmp_path, "p", saved=saved)
    assert f"role moderator of pattern {owner} takes the name" in message
    assert f"debate step {step}" in message


@pytest.mark.parametrize("text", [None, "", "  \n"])
def test_an_empty_moderator_part_is_refused_only_when_a_moderator_is_added(tmp_path, monkeypatch, text):
    part = tmp_path / "moderator.md"
    if text is not None:
        part.write_text(text, encoding="utf-8")
    monkeypatch.setattr(resolver, "MODERATOR_PART", str(part))
    saved = {"p": pattern("p", roles={"a": role(model="m1"), "b": role(model="m2")},
                          steps=[{"name": "argue", "roles": ["a", "b"], "debate": True}])}
    message = refused(tmp_path, "p", saved=saved)
    assert "role moderator" in message and "charter part is missing or empty" in message
    assert resolve(tmp_path, "build-verify").charters


@pytest.mark.parametrize("kw,needle", [
    ({"session": ""}, "owning contact session"), ({"session": 7}, "owning contact session"),
    ({"moderator_model": ""}, "moderator's model"), ({"saved": [("p", {})]}, "saved patterns must be a map"),
    ({"pick": []}, "the pick must be"), ({"pick": ["solo", ""]}, "the pick must be"),
    ({"saved": {"p": {**pattern("p"), "includes": "q"}}, "pick": "p"}, "includes must be a list"),
    ({"saved": {"p": {**pattern("p"), "name": "other"}}, "pick": "p"}, "its name field says 'other'"),
    ({"saved": {"p": pattern("p", steps=[{"name": "s", "roles": [], "debate": "yes"}])}, "pick": "p"},
     "is not true or false"),
])
def test_every_input_guard_refuses_naming_the_input(tmp_path, kw, needle):
    args = {"session": "contact-1", "can_fill": lambda model: True, "abilities": ALL, "moderator_model": "mod-model",
            "saved": None, "pick": "solo", **kw}
    pick = args.pop("pick")
    with pytest.raises(PatternRefused) as caught:
        resolver.resolve_pattern(tmp_path, FEATURE, pick, **args)
    assert needle in str(caught.value)
    assert not resolver.resolved_path(tmp_path, FEATURE).exists()


def test_two_debate_steps_over_one_pair_write_each_moderator_edge_once(tmp_path):
    saved = {"p": pattern("p", roles={"a": role(model="m1"), "b": role(model="m2")},
                          steps=[{"name": "one", "roles": ["a", "b"], "debate": True},
                                 {"name": "two", "roles": ["a", "b"], "debate": True}])}
    edges = resolve(tmp_path, "p", saved=saved).pattern["team"]["edges"]
    plain = [json.dumps(edge, sort_keys=True) for edge in edges]
    assert len(plain) == len(set(plain)) and len(edges) == 4 + 6


# --- flattening -------------------------------------------------------------------------------------------------


def test_included_steps_follow_the_includers_own_in_order_depth_first(tmp_path):
    saved = {"a": pattern("a", roles={"ra": role()}, includes=["b", "d"]),
             "b": pattern("b", roles={"rb": role()}, includes=["c"]),
             "c": pattern("c", roles={"rc": role()}),
             "d": pattern("d", roles={"rd": role()})}
    result = resolve(tmp_path, "a", saved=saved)
    assert [s["name"] for s in result.pattern["team"]["steps"]] == ["work", "b/work", "c/work", "d/work"]
    assert [s["name"] for s in result.pattern["sources"]] == ["a", "b", "c", "d"]


def test_a_combined_pattern_lists_every_agent_once(tmp_path):
    saved = {"a": pattern("a", roles={"x": role(), "y": role()}, includes=["b"]),
             "b": pattern("b", roles={"x": role(), "z": role()})}
    roles = resolve(tmp_path, "a", saved=saved).pattern["team"]["roles"]
    assert sorted(roles) == ["x", "y", "z"]


def test_a_list_of_patterns_combines_in_list_order(tmp_path):
    saved = {"a": pattern("a", roles={"ra": role()}), "b": pattern("b", roles={"rb": role()})}
    result = resolve(tmp_path, ["b", "a"], saved=saved)
    assert [s["name"] for s in result.pattern["team"]["steps"]] == ["b/work", "a/work"]
    assert result.pattern["pattern-name"] == "b+a" and result.pattern["source"] == "combined"
    assert result.pattern["record-version"] is None
    assert [(s["name"], s["record-version"], s["source"]) for s in result.pattern["sources"]] == [
        ("b", 1, "saved"), ("a", 1, "saved")]


def test_a_single_name_keeps_its_own_step_names(tmp_path):
    assert [s["name"] for s in resolve(tmp_path, ["afk-lite"]).pattern["team"]["steps"]] == [
        "design", "build", "verify", "review"]


def test_a_pattern_reached_twice_is_refused(tmp_path):
    saved = {"a": pattern("a", roles={"ra": role()}, includes=["b", "c"]),
             "b": pattern("b", roles={"rb": role()}, includes=["d"]),
             "c": pattern("c", roles={"rc": role()}, includes=["d"]),
             "d": pattern("d", roles={"rd": role()})}
    assert "pattern d is reached twice" in refused(tmp_path, "a", saved=saved)
    assert "reached twice" in refused(tmp_path, ["a", "d"], saved=saved)


def test_each_charter_carries_every_pattern_part_includer_first_then_the_role_part(tmp_path):
    saved = {"a": pattern("a", roles={"ra": role(charter="A-role")}, charter="A", includes=["s", "b"]),
             "s": pattern("s", roles={}, charter=None, steps=[{"name": "alone", "roles": []}]),
             "b": pattern("b", roles={"rb": role(charter="B-role")}, charter="B")}
    charters = resolve(tmp_path, "a", saved=saved).charters
    assert charters == {"ra": "A\n\nB\n\nA-role", "rb": "A\n\nB\n\nB-role"}


def test_every_role_gets_two_implied_message_edges_with_its_report_target(tmp_path):
    saved = {"p": pattern("p", roles={"lead": role(), "member": role(target="lead")})}
    edges = resolve(tmp_path, "p", saved=saved).pattern["team"]["edges"]
    implied = [(e["from"], e["to"], e["kinds"]) for e in edges if e.get("implied")]
    assert implied == [("lead", "", ["message"]), ("", "lead", ["message"]),
                       ("member", "lead", ["message"]), ("lead", "member", ["message"])]


def test_the_resolved_file_carries_its_fields_and_no_charter(tmp_path):
    now = datetime(2026, 10, 19, 22, 40, 5, 999, tzinfo=timezone.utc)
    result = resolve(tmp_path, "afk-lite", now=now)
    written = json.loads(result.path.read_text(encoding="utf-8"))
    assert written == result.pattern
    assert result.path == resolver.resolved_path(tmp_path, FEATURE)
    assert written["created-at"] == "2026-10-19T22:40:05Z" and written["owning-session"] == "contact-1"
    assert written["pattern-name"] == "afk-lite" and written["schema-version"] == 1
    assert written["sources"] == [{"name": "afk-lite", "record-version": 1, "source": "built-in"}]
    assert "charter" not in json.dumps(written["team"])
    assert sorted(written["team"]) == ["edges", "roles", "steps"]


def test_the_command_line_refusal_exits_2_with_its_text(tmp_path):
    done = run_cli(tmp_path, "--pattern", "nope")
    assert done.returncode == 2 and "refused: 'nope' names no pattern" in done.stderr
