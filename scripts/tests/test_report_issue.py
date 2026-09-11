"""redact.py and fingerprint.py, the two pure scripts of /afk:report-issue.

Sensitive literals (tokens, account ids) are built at runtime, so this file
itself never ships one.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2]
SCRIPTS = WORKFLOW / "skills" / "utils" / "report-issue" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fingerprint  # noqa: E402
import redact  # noqa: E402

TOKEN = "ghp" + "_" + "A1b2C3d4" * 5
ACCOUNT = "a1" * 12


def run(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], input=stdin.encode("utf-8"), capture_output=True,
    )


@pytest.fixture
def product(tmp_path: Path) -> Path:
    repo = tmp_path / "widget-service"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "OrderLedger.java").write_text("class OrderLedger {}\n")
    for cmd in (["init", "-q"], ["remote", "add", "origin", "git@github.com:acme/widget-service.git"],
                ["add", "."]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True, capture_output=True)
    return repo


def redactor(repo: Path | None = None) -> redact.Redactor:
    return redact.Redactor(WORKFLOW, repo, "midnightblur/afk-driver")


@pytest.mark.parametrize("raw, gone", [
    (f"token {TOKEN} leaked", TOKEN),
    ("Authorization: Bearer abc.def.123456789", "abc.def"),
    ("API_KEY=s3cr3t-value", "s3cr3t-value"),
    ('DB_PASSWORD: "hunter2hunter2"', "hunter2"),
    ("clone https://bot:pa55word@git.example.com/x.git", "pa55word"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----", "MIIabc"),
    ("mail someone@example.com now", "someone@example.com"),
    (f"account {ACCOUNT}", ACCOUNT),
    ("ping @some-handle please", "@some-handle"),
    ("see PAY-4821 for context", "PAY-4821"),
    ("host build01.corp and 10.2.3.4", "build01.corp"),
    ("docs at https://intranet.example.com/page", "intranet.example.com"),
])
def test_known_shapes_are_replaced(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


AWS_TEMP = "AS" + "IA" + "QWERTY7XK2M9PL3R"


@pytest.mark.parametrize("raw, gone", [
    (f"temporary key {AWS_TEMP} expired", AWS_TEMP),
    ("broke in src/payroll-widget.ts line 4", "payroll-widget"),
    ("see lib/billing.v2/report.cfg for it", "billing.v2"),
    ("the PayrollWidget class threw", "PayrollWidget"),
    ("connect db01.payments.acme.com failed", "acme"),
    ("curl -s -H Authorization: Bearer x9y8z7w6v5u4t3 http://h", "x9y8z7"),
])
def test_review_misses_are_redacted(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


def test_an_unredacted_temporary_key_is_residual():
    assert (1, "token") in redactor().residual(f"key {AWS_TEMP}")


def test_the_remote_owner_is_redacted_on_its_own(product: Path):
    out = redactor(product).redact("the acme org owns it")
    assert "acme" not in out


def test_plugin_paths_and_known_words_survive():
    text = ("`hooks/genericity-gate.sh:78` exit 2; see skills/utils/report-issue/scripts/publish.sh, "
            "${AFK_PLUGIN_ROOT}/skills/afk/lessons/CAPTURE.md, plan/PLAN.md, and github.com")
    assert redactor().redact(text) == text


def test_notation_ids_and_target_repo_urls_survive():
    text = "ADR-0002 and UTF-8, see https://github.com/midnightblur/afk-driver/issues/3"
    assert redactor().redact(text) == text


def test_plugin_root_becomes_the_variable():
    text = f"failed: {WORKFLOW / 'hooks' / 'wiring-gate.sh'}"
    assert redactor().redact(text).startswith("failed: ${AFK_PLUGIN_ROOT}")


def test_a_path_outside_the_plugin_is_redacted(monkeypatch):
    monkeypatch.setenv("HOME", "/home/alice")
    monkeypatch.delenv("USERPROFILE", raising=False)
    out = redact.Redactor(WORKFLOW, None, None).redact("log at /home/alice/.cache/x")
    assert out == "log at <path>"


def test_consuming_repository_identity_and_product_code_are_removed(product: Path):
    text = (f"in {product}\\src\\OrderLedger.java via acme/widget-service, "
            "class `OrderLedger` in widget-service")
    out = redactor(product).redact(text)
    for gone in ("widget-service", "acme", "OrderLedger", str(product)):
        assert gone not in out
    assert "<product-file>" in out and "`<product-symbol>`" in out


def test_high_entropy_blob_is_residual_not_redacted():
    blob = "Zx9" + "Qw7Er5Ty3Ui1Op0As8Df6Gh4Jk2Lm" + "Nb"
    hits = redactor().residual(f"value {blob}")
    assert (1, "high-entropy") in hits


def test_cli_exit_codes(tmp_path: Path):
    clean = run(str(SCRIPTS / "redact.py"), stdin="plain plugin text\n")
    assert clean.returncode == 0 and clean.stdout.decode() == "plain plugin text\n"
    body = tmp_path / "b.md"
    body.write_text(f"leak {TOKEN}\n", encoding="utf-8")
    checked = run(str(SCRIPTS / "redact.py"), "--check", str(body))
    assert checked.returncode == 1 and b"line 1: token" in checked.stderr
    out = tmp_path / "o.md"
    fixed = run(str(SCRIPTS / "redact.py"), "-o", str(out), str(body))
    assert fixed.returncode == 0 and TOKEN not in out.read_text(encoding="utf-8")
    assert run(str(SCRIPTS / "redact.py"), "--nope").returncode == 2


def test_fingerprint_ignores_volatile_detail():
    a = fingerprint.fingerprint("bug", "./hooks/wiring-gate.sh",
                                "Error at /tmp/x1/a.sh line 42: 'foo' failed (abc1234def)")
    b = fingerprint.fingerprint("bug", "hooks\\wiring-gate.sh",
                                "error at C:\\t\\b.sh line 7: 'bar' failed (9f8e7d6c5b)")
    assert a == b and len(a) == 12


def test_fingerprint_moves_with_kind_file_and_message():
    base = fingerprint.fingerprint("bug", "hooks/a.sh", "x failed")
    assert fingerprint.fingerprint("feedback", "hooks/a.sh", "x failed") != base
    assert fingerprint.fingerprint("bug", "hooks/b.sh", "x failed") != base
    assert fingerprint.fingerprint("bug", "hooks/a.sh", "y crashed") != base


def test_fingerprint_cli():
    ok = run(str(SCRIPTS / "fingerprint.py"), "--kind", "bug", "--file", "a", "--signature", "s")
    assert ok.returncode == 0 and len(ok.stdout.decode().strip()) == 12
    bad = run(str(SCRIPTS / "fingerprint.py"), "--kind", "other", "--file", "a", "--signature", "s")
    assert bad.returncode == 2


def test_the_shared_pattern_file_is_the_one_the_gate_reads():
    gate = (WORKFLOW / "hooks" / "genericity-gate.sh").read_text(encoding="utf-8")
    assert "hooks/lib/sensitive-patterns.tsv" in gate
    assert set(redact.load_patterns(WORKFLOW)) >= {
        "ticket-id", "notation-prefixes", "account-id", "email", "source-file"}
