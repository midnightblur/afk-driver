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
CRED_URL = "https://alice:s3cr3t" + "@" + "db01.payments.acme.museum/path"
MAIL = "a" + "@" + "b.io"


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


@pytest.mark.parametrize("raw, gone", [
    ("Authorization=Bearer abcdefghijklmnopqrstuvwxyz", "abcdefghij"),
    ('{"authorization": "Bearer abcdefghijklmnop"}', "abcdefghij"),
    ('"password": "hunter2hunter2"', "hunter2"),
    ("token ab12cd34ef56gh", "ab12cd34"),
    ("api-key: zz99yy88xx77", "zz99yy88"),
    ("connect db01.payments.acme.museum failed", "acme"),
    ("at com.acme.billing.Zorblax.run(x)", "Zorblax"),
])
def test_second_review_leaks_are_redacted(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


def test_a_word_from_the_consuming_repository_is_residual(product: Path):
    (product / "src" / "Zorblax.java").write_text("class Zorblax {}\n")
    subprocess.run(["git", "-C", str(product), "add", "."], check=True, capture_output=True)
    assert (1, "repo-vocabulary") in redactor(product).residual("class Zorblax threw at build01")
    assert redactor(product).residual("the gate threw at step 3") == []


@pytest.mark.parametrize("raw, gone", [
    ('password "abc12345" was wrong', "abc12345"),
    ("cookie 'xy9zzzzz' sent", "xy9zzzzz"),
    ("peer 2001:db8:85a3::8a2e:370:7334 refused", "8a2e"),
    ("peer 2001:0db8:85a3:0000:0000:8a2e:0370:7334 refused", "0370"),
    ("peer fe80::1ff:fe23:4567:890a refused", "fe80"),
    (f"clone {CRED_URL} failed", "s3cr3t"),
    ("calls svc.lookup first", "svc.lookup"),
    ("then shard.fetch", "shard.fetch"),
])
def test_third_review_leaks_are_redacted(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


def test_times_file_lines_and_loopback_survive_the_ipv6_rule():
    text = "at 10:30:00 in redact.py:262 via ::1"
    assert redactor().redact(text) == text


def test_a_credential_url_goes_whole():
    assert redactor().redact(f"x {CRED_URL} y") == "x <url> y"


def test_no_placeholder_is_rewritten_by_a_later_rule():
    raw = (f"{CRED_URL} {MAIL} {TOKEN} @someone PAY-12 "
           "db02.acme.museum 10.1.2.3 2001:db8::1 Authorization: Bearer abcdefghijklmnop")
    out = redactor().redact(raw)
    stripped = redact.PLACEHOLDER.sub("", out)
    assert "<" not in stripped and ">" not in stripped and "@" not in stripped


def test_plural_and_compound_repo_names_are_residual(product: Path):
    for rel in ("src/Zorblax.java", "src/products/list.ts", "src/frobnicator-core/a.ts"):
        (product / rel).parent.mkdir(parents=True, exist_ok=True)
        (product / rel).write_text("x\n")
    subprocess.run(["git", "-C", str(product), "add", "."], check=True, capture_output=True)
    r = redactor(product)
    for line in ("the Zorblaxes failed", "all Products broke", "two Frobnicators died"):
        assert (1, "repo-vocabulary") in r.residual(line), line
    assert r.residual("the product gate failed") == []


SCHEMELESS = "alice:s3cr3t" + "@" + "db01.payments.acme.museum/path"


@pytest.mark.parametrize("raw, gone", [
    ('password "abcdefgh" was wrong', "abcdefgh"),
    ("cookie 'abcdefgh' sent", "abcdefgh"),
    ('password "abc12345 and no closing quote', "abc12345"),
    ("see database.prod.log for it", "database.prod"),
    ("db.x refused", "db.x"),
    ("db.123 refused", "db.123"),
    (f"connect {SCHEMELESS} failed", "s3cr3t"),
    ("peer [2001:db8::1%25eth0]:8080 refused", "eth0"),
    ("peer fe80::1%eth0 refused", "eth0"),
    ("GITLAB" + "_TOKEN abc12345defgh expired", "abc12345"),
    ("MY_SECRET hunter2hunter set", "hunter2"),
])
def test_fourth_review_leaks_are_redacted(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


@pytest.mark.parametrize("raw, gone", [
    ('password "abc def" was wrong', "abc def"),
    ('password "abc def with no closing quote', "abc def"),
    ('password "a" was wrong', '"a"'),
    ("cookie 'x' sent", "'x'"),
    ("GITLAB" + "_TOKEN abc expired", "abc"),
    ("MY_SECRET a set", "MY_SECRET a"),
    ("connect user:pass" + "@" + "build01 failed", "build01"),
    ("connect user:pass" + "@" + "[2001:db8::1]:5432/db failed", "2001:db8"),
    ("host redact.py accepted a connection", "redact.py"),
    ("curl -u bob:s3cr3t https://api.internal/", "s3cr3t"),
    ("psql -h db01.corp -U appuser -W hunter2", "appuser"),
])
def test_fifth_review_leaks_are_redacted(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


@pytest.mark.parametrize("raw", [
    "password <something> hunter2hunter",
    "password <redacted> hunter2hunter",
    "Authorization: <redacted> REALTOKEN123456",
])
def test_a_placeholder_in_the_input_is_residual(raw: str):
    """It splits a line the way pass 1's own do, hiding what follows it."""
    r = redactor()
    assert (1, "placeholder-in-input") in r.residual(r.redact(raw))


@pytest.mark.parametrize("raw", [
    "Trace: password <REDACTED> correcthorse",
    "note: token <XXX> swordfish99",
    "password <Redacted> correcthorse",
    "password <!-- correcthorse",
    "password (hidden) correcthorse",
    "token [REDACTED] swordfish99",
    "secret: ***** correcthorse",
    "DB_PASSWORD=[masked] correcthorse",
])
def test_a_mask_the_input_brought_is_residual(raw: str):
    """Only our own lowercase spelling counts as a redaction; every other
    bracketed token is a mask over an undecidable value."""
    r = redactor()
    assert [cls for _n, cls in r.residual(r.redact(raw))]


@pytest.mark.parametrize("raw", [
    "password <redacted>",
    "the run wrote <url> and <path> here",
    "Authorization: <redacted>",
    "connect to <host> then retry",
    'password = "<redacted>"',
    "mysql -u <redacted> -p<redacted> -h <host>",
    "the password (required) for the run",
    "sort -u hooks/README.md",
    "git log -p --stat",
])
def test_a_placeholder_hiding_nothing_is_not_residual(raw: str):
    """A queued draft carries our own placeholders; the probe clears it."""
    r = redactor()
    assert r.residual(r.redact(raw)) == []


def test_a_queued_draft_republishes_without_a_waiver(tmp_path):
    """Pass 1's own output must probe clean, or no queued run can ever drain."""
    r = redactor()
    once = r.redact("connect " + "admin:s3cr3t" + "@" + "db.internal.example.org now")
    twice = redactor()
    assert twice.residual(twice.redact(once)) == []


@pytest.mark.parametrize("raw, kept", [
    ("see e.g. the gate", "e.g."),
    ("call line.strip() first", "line.strip()"),
    ("re.compile(pattern) is enough", "re.compile("),
])
def test_prose_abbreviations_and_calls_survive_the_host_rule(raw: str, kept: str):
    assert kept in redactor().redact(raw)


@pytest.mark.parametrize("raw, gone", [
    ('password "line1\nline2"', "line2"),
    ('password "ab\\"cd"', "cd"),
    ("connect user:p:ss" + "@" + "host.internal.example.org now", "p:ss"),
    ("connect user:pass" + "@" + "[fe80::1%25eth0]:5432/db now", "eth0"),
    ("connect user:p%40ss" + "@" + "build01 now", "p%40ss"),
    ("telnet provider.sh", "provider.sh"),
    ("curl provider.sh", "provider.sh"),
    ("ping -c 1 provider.sh", "provider.sh"),
    ("TLS handshake with provider.sh", "provider.sh"),
    ("provider.sh is the host", "provider.sh"),
])
def test_sixth_review_leaks_are_redacted(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


def test_a_connection_string_spanning_lines_loses_every_pair():
    out = redactor().redact("Server=db01\nUser ID=alice\nDatabase=payroll")
    for gone in ("db01", "alice", "payroll"):
        assert gone not in out
    assert redactor().residual(out) == []


def test_spaces_around_the_separators_are_not_residual():
    out = redactor().redact("Host = db01 ; Username = alice ; Pwd = p")
    for gone in ("db01", "alice"):
        assert gone not in out
    assert redactor().residual(out) == []


def test_a_connection_string_loses_every_identity_pair():
    out = redactor().redact("Server=db01;User ID=alice;Password=hunter2;Database=payroll")
    for gone in ("db01", "alice", "hunter2", "payroll"):
        assert gone not in out
    assert redactor().residual(out) == []


def test_a_lone_assignment_is_not_a_connection_string():
    """One `user=` in a script line is the plugin's own evidence."""
    for text in ("user=$(gh api user --jq .login)", "The docs say user = the person, no more."):
        assert redactor().redact(text) == text


def test_the_plugins_own_file_names_survive_in_prose():
    """An issue body is ABOUT plugin files; blanking them removes the payload."""
    text = ("The gate lives in provider.sh; CAPTURE.md owns the route table, "
            "`SKILL.md` and plugin.json ship with it, redact.py failed")
    assert redactor().redact(text) == text


def test_a_redacted_line_is_not_residual():
    """Pass 2 must not flag pass 1's own output, or nothing can ever publish."""
    for raw in ("password: hunter2 then it crashed", "secret = value123456",
                "Server=db01;Password=hunter2"):
        assert redactor().residual(redactor().redact(raw)) == [], raw


def test_a_path_both_trees_hold_is_identity(product: Path):
    """`hooks/provider.sh` exists in the plugin too, so the spellings are one."""
    (product / "hooks").mkdir(parents=True, exist_ok=True)
    (product / "hooks" / "provider.sh").write_text("x\n")
    subprocess.run(["git", "-C", str(product), "add", "."], check=True, capture_output=True)
    r = redactor(product)
    assert r.redact("crash in hooks/provider.sh line 4") == "crash in <path> line 4"
    assert r.redact("crash in hooks/lesson-append.sh line 4") == "crash in hooks/lesson-append.sh line 4"


def test_a_bare_source_file_name_reaches_the_product_file_rule():
    """The host rule runs after it, so a product file is never just a host."""
    assert redactor().redact("OrderLedger.java broke") == "<product-file> broke"
    assert redactor().redact("order.py broke") == "<product-file> broke"
    assert redactor().redact("redact.py:262 broke") == "redact.py:262 broke"


def test_a_scheme_less_credential_authority_goes_whole():
    assert redactor().redact(f"x {SCHEMELESS} y") == "x <url> y"


def test_a_missing_plugin_script_survives():
    text = "missing skills/utils/report-issue/scripts/missing-helper.py and hooks/nope.sh"
    assert redactor().redact(text) == text


def test_versions_and_notation_survive_the_host_rule():
    text = "version 1.0.15, ADR-0002, UTF-8, plan/PLAN.md, github.com"
    assert redactor().redact(text) == text


def test_the_remote_owner_beats_the_plugin_vocabulary(product: Path):
    """A remote segment is identity first, whatever ordinary word it spells."""
    subprocess.run(["git", "-C", str(product), "remote", "set-url", "origin",
                    "git@github.com:owner/widget-service.git"], check=True, capture_output=True)
    assert (1, "repo-vocabulary") in redactor(product).residual("the Owners approved it")


def test_plugin_side_detail_survives():
    missing = WORKFLOW / "skills" / "afk" / "nope" / "MISSING.md"
    out = redactor().redact(f"missing {missing}; skills/afk/lessons/NOPE.md; PermissionError, NullPointerException")
    assert "<path>" not in out and "MISSING.md" in out and "NOPE.md" in out
    assert "PermissionError" in out and "NullPointerException" in out
    assert redactor().redact("OrderLedgerException thrown") == "<symbol> thrown"


def test_an_unredacted_temporary_key_is_residual():
    assert (1, "token") in redactor().residual(f"key {AWS_TEMP}")


def test_the_remote_owner_is_redacted_on_its_own(product: Path):
    """In a repo-shaped place the owner goes. In prose an ordinary word stays
    readable and pass 2 QUEUES the draft, so a human decides — blanking the word
    everywhere destroyed the plugin's own evidence (round 7, item O)."""
    r = redactor(product)
    assert "acme" not in r.redact("cd acme/widget-service && ls")
    assert (1, "repo-vocabulary") in r.residual(r.redact("the acme org owns it"))


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
    # The whole path goes as one `<path>`; a bare source-file name is the
    # `<product-file>` rule's case (test_a_bare_source_file_name_...).
    assert "<path>" in out and "`<product-symbol>`" in out


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


def test_fingerprint_holds_across_path_and_timestamp():
    """One defect seen on two machines at two times is one issue; another
    message is another issue."""
    a = fingerprint.fingerprint("bug", "hooks/wiring-gate.sh",
                                "2026-09-15T10:22:31Z /home/a/work/hooks/wiring-gate.sh: orphan found")
    b = fingerprint.fingerprint("bug", "hooks/wiring-gate.sh",
                                "2025-01-02T23:04:05Z C:\\Users\\b\\src\\hooks\\wiring-gate.sh: orphan found")
    c = fingerprint.fingerprint("bug", "hooks/wiring-gate.sh",
                                "2026-09-15T10:22:31Z /home/a/work/hooks/wiring-gate.sh: gate timed out")
    assert a == b and a != c


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


@pytest.mark.parametrize("raw, gone, kept", [
    ("mysql -u root -phunter2swordfish", "hunter2swordfish", "mysql"),
    ("psql -U adminuser -W topsecretpw", "adminuser", "psql"),
    ("user=jsmith2;timeout=30", "jsmith2", "timeout=30"),
])
def test_sixth_review_leaks_are_redacted(raw: str, gone: str, kept: str):
    out = redactor().redact(raw)
    assert gone not in out and kept in out
    assert redactor().residual(out) == []


@pytest.mark.parametrize("raw", ["sort -u hooks/README.md", "grep -U -n pattern x"])
def test_a_short_flag_needs_a_network_command(raw: str):
    """`-u` is a user to `mysql`, a flag to `sort`."""
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw", [
    "password <<redacted>> correcthorse",
    "password xxxxx correcthorse",
    "password ----- correcthorse",
    "api key ...... correcthorse",
    "password ***hidden*** correcthorse",
])
def test_a_mask_in_any_fence_is_residual(raw: str):
    """One repeated character, or a fenced token in any fence and any depth."""
    r = redactor()
    assert (1, "secret-masked") in r.residual(r.redact(raw))


@pytest.mark.parametrize("raw", [
    "we ran curl earlier in the report\nsort -u README",
    "The server\nredact.py refused it.",
])
def test_context_does_not_cross_a_line_break(raw: str):
    """A command or a host word binds only what shares its line."""
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw", ["password <<correcthorse", "password <REDACTED>correcthorse"])
def test_a_fence_glued_to_a_word_is_a_value(raw: str):
    """A bracket worn by a token is not a mask, so the token goes whole."""
    assert "correcthorse" not in redactor().redact(raw)


@pytest.mark.parametrize("raw, gone", [
    ("| password | swordfish99 |", "swordfish99"),
    ("| GITLAB" + "_TOKEN | glpat-shortone99 |", "shortone99"),
    ('password "swordfish99 and more text', "swordfish99"),
])
def test_a_table_cell_and_an_unclosed_quote_lose_their_value(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out and "None" not in out
    assert redactor().residual(out) == []


@pytest.mark.parametrize("raw", [
    "with token <token>.",
    "The token `--check` skips",
])
def test_punctuation_after_a_placeholder_is_not_a_value(raw: str):
    r = redactor()
    assert r.redact(raw) == raw and r.residual(raw) == []


@pytest.mark.parametrize("raw, gone", [
    ("DB_PASSWORD:\n  swordfish99", "swordfish99"),
    ("API" + "_KEY =\nswordfish99", "swordfish99"),
    ("MY_SECRET:\nswordfish99", "swordfish99"),
])
def test_a_value_under_its_key_is_still_the_value(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


def test_a_key_does_not_reach_the_next_paragraph():
    raw = "the quoted secret:\n\nit broke"
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw", ["see SDD.md and INDEX.md", "the PLAN.md tracker"])
def test_a_run_artifact_name_survives_the_host_rule(raw: str):
    """An issue body cites these more often than it cites a machine."""
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw", [
    "verification.tiers and afk.branchNameGate",
    "pom.xml broke",
    "see SDD.md and INDEX.md",
    "v1.0.15 tag",
    # Tracked plugin source spells both, so both are public: mcp-servers/
    # tracker/server.py holds one, skills/afk/tdd/tests.md the other.
    "calls api.call first",
    "then db.query",
])
def test_a_dotted_token_the_plugin_publishes_survives(raw: str):
    """An issue must be able to cite the config key it is about."""
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw, gone", [
    ("NO_PROXY=.corp.acme.local,localhost", "acme"),
    ("x509: certificate is valid for *.corp.acme.local, not gateway", "acme"),
    ("nameserver .corp.acme.local", "acme"),
    ("domain=.corp.acme.local; path=/", "acme"),
    ("mail me at jane [at] corp.acme.local or @corp.acme.local", "acme"),
])
def test_a_leading_dot_or_wildcard_does_not_shield_a_domain(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


@pytest.mark.parametrize("raw, gone", [
    ("credentials:\n  password: swordfish99\n  api_key: correcthorse", "swordfish99"),
    ('{"credentials": {"password": "swordfish99"}}', "swordfish99"),
    ("db:\n  creds:\n    password: swordfish99", "swordfish99"),
    ("db:\n  password: >\n    swordfish99\n    correcthorse\nnext: 1", "swordfish99"),
    ("password: |\n  swordfish99", "swordfish99"),
    ("docker login -u jsmith -p correcthorse", "correcthorse"),
])
def test_seventh_review_leaks_are_redacted(raw: str, gone: str):
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


def test_a_keyword_followed_by_prose_is_not_residual():
    raw = "the password is required for the adapter."
    r = redactor()
    assert r.redact(raw) == raw and r.residual(raw) == []


def test_a_credential_literal_is_reported_never_guessed():
    raw = "INSERT INTO users (name, pw) VALUES ('jsmith', 'Hunter2!dragon');"
    r = redactor()
    assert (1, "credential-literal") in r.residual(r.redact(raw))


def test_the_probe_reads_the_line_under_the_mask():
    r = redactor()
    assert r.residual(r.redact("password <REDACTED>\ncorrecthorse2")) != []


def test_a_port_mapping_is_not_a_password():
    assert redactor().redact("docker run -p 8080:80 image") == "docker run -p 8080:80 image"


@pytest.mark.parametrize("raw,gone", [
    ("GITLAB" + "_TOKEN=zk4qv= more", "zk4qv="),
    ("DB_PASSWORD: \"zk4qv\": tail", "zk4qv"),
    ("credentials: zk4qv= x", "zk4qv="),
])
def test_a_value_carrying_a_separator_is_still_a_value(raw: str, gone: str):
    """Only the NEXT-LINE branch refuses a key; on its own line a value may
    carry any `:` or `=` it likes."""
    out = redactor().redact(raw)
    assert gone not in out
    assert redactor().residual(out) == []


def test_our_own_placeholder_does_not_bind_the_next_line():
    """A queued draft republishes: the probe reads one line for our spelling."""
    r = redactor()
    assert r.residual("password: <redacted>\nContact the owner") == []


def test_a_rule_name_in_prose_keeps_the_next_word():
    raw = "The secret-assignment rule fires twice."
    assert redactor().redact(raw) == raw


def test_a_shouted_key_reaches_across_a_blank_line():
    out = redactor().redact("PASSWORD:\n\nhunt3rdragon")
    assert "hunt3rdragon" not in out


def test_a_prose_word_still_stops_at_the_paragraph():
    raw = "the quoted secret:\n\nit broke"
    assert redactor().redact(raw) == raw


def test_one_stray_quote_keeps_the_rest_of_the_body():
    raw = '## Actual\nthe log printed password "unterminated\n\n## Steps\n1. run it'
    out = redactor().redact(raw)
    assert "unterminated" not in out
    assert "## Steps" in out and "1. run it" in out


@pytest.mark.parametrize("raw", ["find . -print", "mvn -pl module test"])
def test_a_long_flag_is_not_a_glued_password(raw: str):
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw", ["mysql -h db1 -pcorrecthorse", "docker login -pcorrecthorse"])
def test_a_glued_password_after_a_command_goes(raw: str):
    assert "correcthorse" not in redactor().redact(raw)


@pytest.mark.parametrize("raw", [
    "skills/afk/<name>/SKILL.md is the spine",
    "adapters/<family>/<kind>/adapter.json",
])
def test_a_placeholder_segment_keeps_its_path(raw: str):
    """A placeholder inside a path is a segment, not a wall."""
    r = redactor()
    assert r.redact(raw) == raw
    assert r.residual(r.redact(raw)) == []


def test_a_user_flag_does_not_wall_off_its_command():
    """The `-u` placeholder must not hide `mysql` from the flags after it."""
    assert "correcthorse" not in redactor().redact("mysql -u root -pcorrecthorse")


def test_docker_login_loses_its_password():
    out = redactor().redact("docker login -u jsmith -p correcthorse")
    assert "correcthorse" not in out


@pytest.mark.parametrize("raw", [
    "scripts/tests/test_report_issue.py::test_host_context FAILED",
    "scripts/tests/test_report_issue.py:118: AssertionError",
])
def test_a_plugin_test_identity_survives_its_failure(raw: str):
    """Which test failed is the report; a node id and a line number are half of it."""
    assert redactor().redact(raw) == raw


def test_a_foreign_test_path_keeps_only_its_line_number():
    """A coordinate is not an identity; a test NAME is product vocabulary."""
    out = redactor().redact("tests/test_widget.py:118: AssertionError")
    assert out == "<path>:118: AssertionError"


@pytest.mark.parametrize("raw,kept", [
    ('File "/c/Users/someone/.claude/plugins/cache/afk-toolkit/afk/1.0.18/hooks/lib/adapter.sh"',
     "afk/1.0.18/hooks/lib/adapter.sh"),
    ("~/.codex/plugins/cache/afk-toolkit/afk/1.0.18/hooks/lib/provider.sh",
     "afk/1.0.18/hooks/lib/provider.sh"),
])
def test_an_installed_plugin_frame_keeps_its_file_and_version(raw: str, kept: str):
    out = redactor().redact(raw)
    # The rewrite stays TRUE: the run used an installed cache copy, so the body
    # says so; only the home directory goes (round 7, item P).
    assert kept in out and "someone" not in out
    assert ".claude/plugins/cache/afk-toolkit" in out or ".codex/plugins/cache/afk-toolkit" in out


@pytest.mark.parametrize("raw", [
    "git config --get tracker.kind",
    "set verification.tiers and git.branch-pattern",
])
def test_a_config_key_the_reader_accepts_survives(raw: str):
    """The config reader, not prose frequency, says what a key is."""
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw", ["telnet tracker.kind", "git.corp.acme.local is unreachable"])
def test_a_machine_named_like_a_config_key_still_goes(raw: str):
    assert "<host>" in redactor().redact(raw)


def test_a_default_expansion_keeps_its_shape():
    out = redactor().redact("+ AFK_PLUGIN_ROOT=${AFK_PLUGIN_ROOT:-/c/plugins/afk}")
    assert out == "+ AFK_PLUGIN_ROOT=${AFK_PLUGIN_ROOT:-<path>}"


@pytest.mark.parametrize("raw", [
    "AFK_SKIP_BRANCH_CHECK=1 git commit",
    "GATE_CACHE_DISABLE=1 bash hooks/wiring-gate.sh",
])
def test_a_documented_toggle_does_not_queue_the_draft(raw: str):
    r = redactor()
    assert r.residual(r.redact(raw)) == []


def test_an_undocumented_blob_still_queues():
    r = redactor()
    assert (1, "high-entropy") in r.residual(r.redact("SOME_PRIVATE_BLOB=aZ9qW3eR7tY1uI5oP2xK"))


@pytest.mark.parametrize("raw", [
    "release v1.0.15", "bump to v1.0.18", "see verification.tiers", "edit pom.xml",
    "git config afk.branchNameGate false",
])
def test_a_version_or_dotted_name_an_issue_cites_survives(raw: str):
    """Pinned: v1.0.15 was redacted to <host> earlier in this round."""
    assert redactor().redact(raw) == raw


@pytest.mark.parametrize("raw", ["/afk:execute exits contract_mismatch", "run /afk:report-issue"])
def test_a_skill_invocation_is_not_a_path(raw: str):
    """Every issue about this plugin names the skill it is about."""
    assert redactor().redact(raw) == raw


# ---------------------------------------------------------------------------
# The round-7 register. Every attacker finding of this round, both directions,
# in one table: a LEAK fixture names text that must not survive, a SURVIVAL
# fixture names text an issue needs kept. Two of these were broken and refixed
# inside the round, so the table — not the prose — is what holds them fixed.
# ---------------------------------------------------------------------------

ROUND_SEVEN_LEAKS = [
    # (item, raw, what must be gone)
    ("B yaml parent", "credentials:\n  password: swordfish99", "swordfish99"),
    ("B json nested", '{"credentials": {"password": "swordfish99"}}', "swordfish99"),
    ("C block scalar", "db:\n  password: >\n    swordfish99\n    correcthorse", "swordfish99"),
    ("C literal block", "password: |\n  swordfish99", "swordfish99"),
    ("D real secret", "password = swordfish99", "swordfish99"),
    ("F leading dot", "NO_PROXY=.corp.acme.local", "acme.local"),
    ("F wildcard", "allow *.corp.acme.local", "acme.local"),
    ("F cookie", "Set-Cookie: a=b; domain=.corp.acme.local", "acme.local"),
    ("F x509", "CN=*.corp.acme.local", "acme.local"),
    ("H handle head", "ping @corp.acme.local", "acme.local"),
    ("opt docker", "docker login -u jsmith -p correcthorse", "correcthorse"),
    ("D1 blank line", "PASSWORD:\n\ncorrecthorse9", "correcthorse9"),
    ("D2 stray quote", 'password "correcthorse9', "correcthorse9"),
    ("D3 glued", "mysql -h db1 -pcorrecthorse", "correcthorse"),
]

ROUND_SEVEN_SURVIVALS = [
    # (item, raw, what must still be readable)
    ("A config key", "set verification.tiers in the config", "verification.tiers"),
    ("A git key", "git config afk.branchNameGate false", "afk.branchNameGate"),
    ("A build file", "edit pom.xml", "pom.xml"),
    ("D prose", "the password is required for the adapter.", "password is required"),
    ("I node id", "tests/test_widget.py::test_host_context FAILED", "::test_host_context"),
    ("I line number", "tests/test_widget.py:118: AssertionError", ":118:"),
    ("I plugin path", "scripts/tests/test_report_issue.py:118: E", "scripts/tests/test_report_issue.py:118"),
    ("J installed file", 'File "/c/Users/someone/.claude/plugins/cache/afk-toolkit/'
                         'afk/1.0.18/hooks/lib/adapter.sh"', "afk/1.0.18/hooks/lib/adapter.sh"),
    ("J install shape", 'File "/c/Users/someone/.claude/plugins/cache/afk-toolkit/'
                        'afk/1.0.18/hooks/lib/adapter.sh"', ".claude/plugins/cache/afk-toolkit"),
    ("K reader key", "git config --get tracker.kind", "tracker.kind"),
    ("K contract key", "set git.branch-pattern", "git.branch-pattern"),
    ("L expansion", "+ AFK_PLUGIN_ROOT=${AFK_PLUGIN_ROOT:-/c/plugins/afk}",
     "${AFK_PLUGIN_ROOT:-"),
    ("M toggle", "AFK_SKIP_BRANCH_CHECK=1 git commit", "AFK_SKIP_BRANCH_CHECK=1"),
    ("N version", "release v1.0.15", "v1.0.15"),
    ("slash command", "/afk:execute exits contract_mismatch", "/afk:execute"),
    ("path placeholder", "skills/afk/<name>/SKILL.md", "skills/afk/<name>/SKILL.md"),
    ("D3 long flag", "find . -print", "-print"),
    ("D4 port", "docker run -p 8080:80 image", "-p 8080:80"),
]


@pytest.mark.parametrize("item,raw,gone",
                         ROUND_SEVEN_LEAKS, ids=[c[0] for c in ROUND_SEVEN_LEAKS])
def test_round_seven_leak_register(item: str, raw: str, gone: str):
    assert gone not in redactor().redact(raw)


@pytest.mark.parametrize("item,raw,kept",
                         ROUND_SEVEN_SURVIVALS, ids=[c[0] for c in ROUND_SEVEN_SURVIVALS])
def test_round_seven_survival_register(item: str, raw: str, kept: str):
    assert kept in redactor().redact(raw)


def test_a_repo_name_that_is_an_ordinary_word_stays_in_prose(tmp_path: Path):
    """The directory name is identity where it addresses the repository, and a
    word of the plugin's own evidence everywhere else."""
    product = tmp_path / "consumer"
    product.mkdir()
    subprocess.run(["git", "init", "-q", str(product)], check=True)
    r = redactor(product)
    assert r.redact("orphan: scripts/x.py has no consumer") == "orphan: scripts/x.py has no consumer"
    assert "consumer" not in r.redact("cd consumer/src && ls")


def test_a_stray_quote_ends_at_its_paragraph():
    """A quote closing three headings later is a different quote: an unbalanced
    one must not swallow the sections under it (verify-seams final, defect 1)."""
    raw = ('## Evidence\nagent logged: password "\n\n'
           '## Environment\nran on v1.0.15 with the "afk" plugin\n')
    out = redactor().redact(raw)
    assert "## Environment" in out and "v1.0.15" in out


def test_a_quoted_secret_still_crosses_its_own_lines():
    out = redactor().redact('password "correcthorse\nstill the value"')
    assert "correcthorse" not in out


@pytest.mark.parametrize("raw", [
    "adapters/build-gate/<repo>/app-start-gate.sh",
    "skills/afk/<name>/SKILL.md",
])
def test_a_placeholder_segment_never_costs_the_tail(raw: str):
    """Whatever the placeholder spells, the path is judged whole."""
    assert redactor().redact(raw) == raw


def test_a_path_rooted_in_a_placeholder_is_not_plugin_side():
    assert redactor().redact("<repo>/src/App.java") == "<path>"


def test_a_walled_placeholder_does_not_blind_a_flag_rule():
    """A wall next to a slash used to be both unprobed and blinding."""
    assert "correcthorse" not in redactor().redact("mysql skills/<path> -pcorrecthorse")


@pytest.mark.parametrize("raw", [
    "ping the box, then find . -print | wc -l",
    "the host list came from find . -print",
])
def test_a_command_word_in_prose_does_not_own_a_flag(raw: str):
    """`host`, `ping` and `mount` are ordinary English too."""
    assert redactor().redact(raw) == raw


def test_a_long_flag_does_not_wall_off_its_command():
    out = redactor().redact("mysql --host db1 --port 3306 --user root -pcorrecthorse")
    assert "correcthorse" not in out and "root" not in out


# ---------------------------------------------------------------------------
# The round-8 register, both directions, one row per finding.
# ---------------------------------------------------------------------------

FENCE = "`" * 3

ROUND_EIGHT_LEAKS = [
    # (item, raw, what must be gone)
    ("2 prose handle", "ask @jane about it", "@jane"),
    ("2 handle opens a line", "@jane can you look", "@jane"),
    ("2 prose decorator word", "the @dataclass decorator", "@dataclass"),
    ("2 bare domain alone", "@corp.acme.local", "acme.local"),
    ("2 domain after a word", "ping @corp.acme.local", "acme.local"),
    ("3 multi-label dot host", "NO_PROXY=.corp.acme.local", "acme.local"),
    ("4 escape stays private", "../../etc/shadow", "etc/shadow"),
    ("6 foreign test file", "tests/test_redact.py::test_x FAILED", "test_redact.py"),
]

ROUND_EIGHT_SURVIVALS = [
    # (item, raw, what must still be readable)
    ("2 decorator call", '@pytest.mark.parametrize("case", CASES)', "@pytest.mark.parametrize("),
    ("2 indented decorator", "    @pytest.fixture", "@pytest.fixture"),
    ("2 bare decorator", "@dataclass", "@dataclass"),
    ("2 annotation", "@Override", "@Override"),
    ("2 fenced annotation", f"{FENCE}java\n@Override\npublic void run() {{}}\n{FENCE}", "@Override"),
    ("3 dotfile", "see .pre-commit-config.yaml", ".pre-commit-config.yaml"),
    ("4 parent-relative", "../plan/PLAN.md", "../plan/PLAN.md"),
    ("4 dot-relative", "./scripts/run.sh", "./scripts/run.sh"),
    ("4 glob", "**/*.py", "**/*.py"),
    ("4 glob under a dir", "skills/**/SKILL.md", "skills/**/SKILL.md"),
    ("5 npm scope", "npm i @anthropic-ai/claude-code", "@anthropic-ai/claude-code"),
    ("6 foreign node id", "tests/test_redact.py::test_x FAILED", "::test_x FAILED"),
]


@pytest.mark.parametrize("item,raw,gone",
                         ROUND_EIGHT_LEAKS, ids=[c[0] for c in ROUND_EIGHT_LEAKS])
def test_round_eight_leak_register(item: str, raw: str, gone: str):
    assert gone not in redactor().redact(raw)


@pytest.mark.parametrize("item,raw,kept",
                         ROUND_EIGHT_SURVIVALS, ids=[c[0] for c in ROUND_EIGHT_SURVIVALS])
def test_round_eight_survival_register(item: str, raw: str, kept: str):
    assert kept in redactor().redact(raw)


def _consumer_repo(tmp_path: Path) -> Path:
    """A consuming repo whose DIRECTORY is a plugin word and whose remote owner
    and name are ordinary words too."""
    product = tmp_path / "consumer"
    product.mkdir()
    subprocess.run(["git", "init", "-q", str(product)], check=True)
    subprocess.run(["git", "-C", str(product), "remote", "add", "origin",
                    "git@gitlab.example.com:orders/widget.git"], check=True)
    return product


def test_the_directory_basename_in_prose_raises_no_residual(tmp_path: Path):
    """Round 8 item 1: a plugin gate sentence must publish."""
    r = redactor(_consumer_repo(tmp_path))
    raw = "wiring-gate.sh: orphan: scripts/fingerprint.py has no consumer"
    assert r.redact(raw) == raw and r.residual(r.redact(raw)) == []


@pytest.mark.parametrize("raw", ["the orders team owns it", "widget broke again"])
def test_the_remote_owner_and_name_keep_their_residual(tmp_path: Path, raw: str):
    """Identity first, whatever word they spell (the round-8 correction)."""
    r = redactor(_consumer_repo(tmp_path))
    assert (1, "repo-vocabulary") in r.residual(r.redact(raw))


def test_the_directory_basename_still_goes_where_it_addresses_the_repo(tmp_path: Path):
    assert "consumer" not in redactor(_consumer_repo(tmp_path)).redact("cd consumer/src")


# ---------------------------------------------------------------------------
# The round-9 register, both directions.
# ---------------------------------------------------------------------------

ROUND_NINE_LEAKS = [
    # (item, raw, what must be gone)
    ("1 private npm scope", "npm i @acme-internal/billing-sdk", "acme-internal"),
    ("2 indented bare domain", "    @corp.acme.local", "acme.local"),
    ("2 yaml list of domains", "  - @corp.acme.local", "acme.local"),
    ("2 country-code domain", "    @mail.acme.de", "acme.de"),
]

ROUND_NINE_SURVIVALS = [
    # (item, raw, what must still be readable)
    ("1 public npm scope", "npm i @anthropic-ai/claude-code", "@anthropic-ai/claude-code"),
    ("2 indented fixture", "    @pytest.fixture", "@pytest.fixture"),
    ("2 indented parametrize", '    @pytest.mark.parametrize("case", CASES)',
     '@pytest.mark.parametrize("case"'),
    ("2 indented cache", "    @functools.lru_cache", "@functools.lru_cache"),
]


@pytest.mark.parametrize("item,raw,gone",
                         ROUND_NINE_LEAKS, ids=[c[0] for c in ROUND_NINE_LEAKS])
def test_round_nine_leak_register(item: str, raw: str, gone: str):
    assert gone not in redactor().redact(raw)


@pytest.mark.parametrize("item,raw,kept",
                         ROUND_NINE_SURVIVALS, ids=[c[0] for c in ROUND_NINE_SURVIVALS])
def test_round_nine_survival_register(item: str, raw: str, kept: str):
    assert kept in redactor().redact(raw)


# ---------------------------------------------------------------------------
# The round-11 register: V3, a URL placeholder that hid a later `-u` from its
# command. Both directions.
#
# Declared, not fixed:
# - `docker run -u 1000:1000` loses its uid:gid: a colon after `-u` is
#   `name:secret` whatever the command.
# - Gap (a) at its true width: most column-0 unfenced dotted decorators become
#   <host> (25 of 28 in the reviewer's set), and so do indented ones whose last
#   label is a listed suffix or 2 letters (`@attr.ib`). Evidence lost, never a
#   secret shipped.
# ---------------------------------------------------------------------------

ROUND_ELEVEN_LEAKS = [
    # (item, raw, what must be gone)
    ("V3 -u after a url", "curl https://api.corp.acme.local/v1 -u admin:SECRETvalue9", "SECRETvalue9"),
    ("V3 -u after && and a url",
     "git clone https://gitlab.example.com/g/r.git && curl https://x.corp.acme.local -u admin:SECRETvalue9",
     "SECRETvalue9"),
    ("V3 second pair", "curl https://x.corp.acme.local -u jsmith:hunter2dragon", "hunter2dragon"),
    ("V3 user name after a url", "curl https://x.corp.acme.local -u jsmith", "jsmith"),
    ("V3 -U after a url", "curl https://x.corp.acme.local -U proxy:SECRETvalue9", "SECRETvalue9"),
    ("colon pair, any command", "tool -u admin:SECRETvalue9", "SECRETvalue9"),
    ("V3 glued -p after a url", "mysql -h https://db.corp.acme.local -pSECRETvalue9", "SECRETvalue9"),
    ("V3 login -p after a url", "docker login https://reg.corp.acme.local -p SECRETvalue9", "SECRETvalue9"),
    ("control -u before the url", "curl -u admin:SECRETvalue9 https://x.corp.acme.local", "SECRETvalue9"),
    ("control --user", "curl --user admin:SECRETvalue9 https://x.corp.acme.local", "SECRETvalue9"),
    ("control --password", "mysql --password SECRETvalue9", "SECRETvalue9"),
    ("control auth header single", "curl -H 'Authorization: Bearer abcdefghijklmnop123' https://x.io",
     "abcdefghijklmnop123"),
    ("control auth header double", 'curl -H "Authorization: Bearer abcdefghijklmnop123" https://x.io',
     "abcdefghijklmnop123"),
    ("declared: docker uid:gid goes", "docker run -u 1000:1000 image", "1000:1000"),
]

ROUND_ELEVEN_SURVIVALS = [
    # (item, raw, what must still be readable)
    # File names the plugin ships, so the whole line can survive: a name it
    # does not ship goes to <host> or <product-file> by the file-name rule.
    ("sort -u", "sort -u CHANGELOG.md", "sort -u CHANGELOG.md"),
    ("diff -u", "diff -u a b", "diff -u a b"),
    ("git add -u", "git add -u", "git add -u"),
    ("python -u", "python -u redact.py", "python -u redact.py"),
]


@pytest.mark.parametrize("item,raw,gone",
                         ROUND_ELEVEN_LEAKS, ids=[c[0] for c in ROUND_ELEVEN_LEAKS])
def test_round_eleven_leak_register(item: str, raw: str, gone: str):
    r = redactor()
    out = r.redact(raw)
    assert gone not in out and not [h for h in r.residual(out) if h[1] == "credential-flag"]


@pytest.mark.parametrize("item,raw,kept",
                         ROUND_ELEVEN_SURVIVALS, ids=[c[0] for c in ROUND_ELEVEN_SURVIVALS])
def test_round_eleven_survival_register(item: str, raw: str, kept: str):
    r = redactor()
    out = r.redact(raw)
    assert kept in out and r.residual(out) == []


@pytest.mark.parametrize("left", ["curl <url> -u admin:SECRETvalue9",
                                  "x -U proxy:SECRETvalue9", "x --user=admin:SECRETvalue9"])
def test_a_user_pair_left_in_the_output_queues(left: str):
    """The residual net: whatever rule missed it, a `name:secret` after a user
    flag keeps the draft off the forge."""
    assert (1, "credential-flag") in redactor().residual(left)


# ---------------------------------------------------------------------------
# The round-12 register: machine context in front of a wall reaches the host
# after it. Both directions.
# ---------------------------------------------------------------------------

ROUND_TWELVE_LEAKS = [
    # (item, raw, what must be gone)
    ("host after -u wall", "curl -u admin:hunter2dragon pom.xml", "pom.xml"),
    ("dotted key after -u wall", "curl -u admin:hunter2dragon verification.tiers", "verification.tiers"),
    ("basename after -u wall", "curl -u admin:hunter2dragon redact.py", "redact.py"),
    ("basename after a path wall", "ssh -i ~/.ssh/id_rsa redact.py", "redact.py"),
    ("config key after --user wall", "wget --user admin:hunter2dragon tracker.kind", "tracker.kind"),
    ("capital host after -U wall", "psql -U appuser SDD.md", "SDD.md"),
]

ROUND_TWELVE_SURVIVALS = [
    # (item, raw, what must still be readable)
    ("version after -u wall", "curl -u admin:hunter2dragon v1.0.15", "v1.0.15"),
    ("version after a path wall", "ssh -i ~/.ssh/id_rsa v1.0.15", "v1.0.15"),
    ("basename after a url, prose", "see https://x.io then redact.py", "then redact.py"),
    ("dotted key after a path, prose", "read /c/work/consumer/x.py and verification.tiers",
     "and verification.tiers"),
    ("dotted key after a url, prose", "ran https://x.io and verification.tiers passed",
     "and verification.tiers passed"),
    ("file after a ticket, prose", "the gate <ticket> wrote SDD.md", "wrote SDD.md"),
    # verify-seams round 12: the -u owner is the shell SEGMENT, not the line.
    ("sort -u after &&", "curl https://x.io && sort -u CHANGELOG.md", "sort -u CHANGELOG.md"),
    ("sort -u after a pipe", "curl https://x.io | sort -u CHANGELOG.md", "sort -u CHANGELOG.md"),
    # verify-seams round 12: pass 2 sees the fence pass 1 saw.
    ("fenced decorator, residual", "\n".join([FENCE, "@pytest.fixture", "def f(): pass", FENCE]),
     "@pytest.fixture"),
]


@pytest.mark.parametrize("item,raw,gone",
                         ROUND_TWELVE_LEAKS, ids=[c[0] for c in ROUND_TWELVE_LEAKS])
def test_round_twelve_leak_register(item: str, raw: str, gone: str):
    assert gone not in redactor().redact(raw)


@pytest.mark.parametrize("item,raw,kept",
                         ROUND_TWELVE_SURVIVALS, ids=[c[0] for c in ROUND_TWELVE_SURVIVALS])
def test_round_twelve_survival_register(item: str, raw: str, kept: str):
    r = redactor()
    out = r.redact(raw)
    assert kept in out and r.residual(out) == []
