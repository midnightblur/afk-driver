import os

import setup
from conftest import SHA, end_marker, fire, v1_block


def _install(places):
    setup.write_install_record(places, {"path": "/py", "version": "3.12"}, "/rg")


def test_the_fired_record_has_the_frozen_name(places):
    assert places.fired_record("codex") == places.data / "fired-codex.txt"


def test_no_install_record_refuses(places, plugin_root):
    answer = setup.prove_hook(places, "claude", end_marker(), plugin_root, ["claude"])
    assert not answer["proved"] and answer["error"]["code"] == "no-install-record"


def test_proof_passes_with_newer_record_and_matching_sha(places, plugin_root):
    _install(places)
    fire(places, "claude")
    answer = setup.prove_hook(places, "claude", end_marker(), plugin_root, ["claude"])
    assert answer["proved"], answer


def test_record_older_than_install_fails(places, plugin_root):
    _install(places)
    fire(places, "claude", later=-60)
    answer = setup.prove_hook(places, "claude", end_marker(), plugin_root, ["claude"])
    assert not answer["proved"] and "before setup's install record" in answer["reasons"][0]


def test_wrong_or_missing_marker_fails(places, plugin_root):
    _install(places)
    fire(places, "claude")
    wrong = setup.prove_hook(places, "claude", end_marker("ffffffffffff"), plugin_root, ["claude"])
    assert not wrong["proved"]
    partial = setup.prove_hook(places, "claude", "x " + end_marker(), plugin_root, ["claude"])
    assert not partial["proved"]
    empty = setup.prove_hook(places, "claude", "", plugin_root, ["claude"])
    assert "no end-marker line" in empty["reasons"][0]


def test_missing_codex_record_names_the_trust_review(places, plugin_root):
    _install(places)
    fire(places, "claude")
    answer = setup.prove_hook(places, "claude", end_marker(), plugin_root, ["claude", "codex"])
    assert not answer["proved"]
    assert any("trust the afkv2 hooks" in r for r in answer["reasons"])


def test_codex_is_required_when_it_still_uses_v1(places):
    assert setup.required_providers(places, "claude", {}) == ["claude"]
    assert setup.required_providers(places, "claude", {"afk@afk-toolkit": True}) == ["claude", "codex"]
    path = places.instruction_file("codex")
    path.parent.mkdir(parents=True)
    path.write_text(v1_block(), encoding="utf-8")
    assert setup.required_providers(places, "claude", {}) == ["claude", "codex"]


def test_expected_sha_ignores_tests_and_partial_lines(tmp_path):
    root = tmp_path / "p"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "x.txt").write_text(
        "afkv2-core-behaviors begin aaaaaaaaaaaa\nafkv2-core-behaviors end aaaaaaaaaaaa\n")
    (root / "y.txt").write_text(
        f"say afkv2-core-behaviors begin {SHA}\nafkv2-core-behaviors end {SHA}\n")
    assert setup.expected_sha12s(root) == set()


def test_install_record_keeps_the_first_time(places):
    first = setup.write_install_record(places, {"path": "/py", "version": "3.12"}, "/rg")
    os.utime(places.install_record, (1, 1))
    second = setup.write_install_record(places, {"path": "/py2", "version": "3.13"}, None)
    assert second["installed"] == first["installed"] and second["python"] == "/py2 3.13"


def test_no_install_record_gives_a_reason_to_relay(places, plugin_root):
    answer = setup.prove_hook(places, "claude", end_marker(), plugin_root, ["claude"])
    assert not answer["proved"] and answer["error"]["code"] == "no-install-record"
    assert answer["reasons"] == [answer["error"]["reason"]]
