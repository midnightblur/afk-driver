"""The chart components (ADR-0005 design, PRD table K): each draws inline SVG from its props and the theme tokens,
carries a 1-line caption, writes its numbers as text, and refuses props outside its schema."""

import json
import re
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import engine  # noqa: E402
import registry  # noqa: E402

KIT = (ENGINE_DIR / "shell" / "kit.css").read_text(encoding="utf-8")
DARK, LIGHT = KIT.split(':root[data-theme="light"] {', 1)
TOKEN_USE = re.compile(r"var\((--[\w-]+)\)")
HEX_COLOUR = re.compile(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b")
SVG_TEXT = re.compile(r"<text [^>]*>([^<]*)</text>")
FIGURE = re.compile(r'^<figure class="afkv2-chart afkv2-chart--([\w-]+)"[^>]*><svg [^>]*role="img"[^>]*>.*</svg>'
                    r'.*<figcaption[^>]*>([^<]*)</figcaption></figure>$', re.S)

CAPTION = "Export time halved after the cache"
CHARTS = {
    "tile": {"caption": CAPTION, "value": 1240, "unit": "ms", "low": 900, "high": 1500, "label": "export time",
             "grade": "estimated", "source": "3 runs on the staging host"},
    "bars": {"caption": CAPTION, "unit": "rows", "items": [{"label": "orders", "value": 120},
                                                          {"label": "returns", "value": 340},
                                                          {"label": "refunds", "value": 15}]},
}
# Each chart: props that break a rule, with the field the refusal names.
BAD = {
    "tile": [({"grade": "guessed"}, "grade"), ({"low": 1300}, "low"), ({"high": None}, "high"),
             ({"value": float("nan")}, "value")],
    "bars": [({"items": []}, "items"), ({"items": [{"label": "a", "value": -1}]}, "items"),
             ({"items": [{"label": f"r{k}", "value": k} for k in range(41)]}, "items"),
             ({"split": True, "items": [{"label": "a", "value": 0}]}, "items"),
             ({"items": [{"label": "a", "value": 1, "colour": "red"}]}, "items")],
}
NAMES = sorted(CHARTS)


def chart(name, **change):
    return {"type": name, "props": {**CHARTS[name], **change}}


def drawn(name, **change):
    component = chart(name, **change)
    assert registry.validate(component) == []
    return registry.render_component(component)


def words(html):
    """The text the SVG writes, one string per text element."""
    return [re.sub(r"&#x27;", "'", w).replace("&amp;", "&") for w in SVG_TEXT.findall(html)]


def defined(block, token):
    return re.search(rf"^\s*{re.escape(token)}:", block, re.M) is not None


# --- every chart ---

@pytest.mark.parametrize("name", NAMES)
def test_a_chart_draws_inline_svg_with_its_caption(name):
    html = drawn(name)
    found = FIGURE.match(html)
    assert found, html[:300]
    assert found.group(1) == name and found.group(2) == CAPTION
    assert f'aria-label="{CAPTION}"' in html
    assert "<script" not in html.lower() and not re.search(r"<[^>]*\son\w+=", html)


@pytest.mark.parametrize("name", NAMES)
def test_a_chart_paints_only_tokens_both_themes_define(name):
    html = drawn(name)
    used = set(TOKEN_USE.findall(html))
    assert used
    for token in used:
        assert defined(DARK, token) and defined(LIGHT, token), token
    assert not HEX_COLOUR.findall(html)


@pytest.mark.parametrize("name", NAMES)
def test_a_chart_lives_in_its_own_module(name):
    assert registry.lookup(name) is not None
    assert (ENGINE_DIR / "components" / f"chart_{name.replace('-', '_')}.py").is_file()


@pytest.mark.parametrize("name", NAMES)
def test_a_chart_without_a_caption_is_refused(name):
    props = {k: v for k, v in CHARTS[name].items() if k != "caption"}
    assert registry.validate({"type": name, "props": props}) != []
    assert registry.validate(chart(name, caption="")) != []
    assert registry.validate(chart(name, caption="c" * 161)) != []


@pytest.mark.parametrize("name, change, field",
                         [(name, change, field) for name in NAMES for change, field in BAD[name]],
                         ids=lambda v: v if isinstance(v, str) else "")
def test_a_chart_refuses_props_outside_its_rules(name, change, field):
    props = {**CHARTS[name], **change}
    props = {k: v for k, v in props.items() if v is not None}
    found = registry.validate({"type": name, "props": props})
    assert found, change
    assert any(field in path for path, _ in found), found


@pytest.mark.parametrize("name", NAMES)
def test_the_check_refuses_a_page_with_a_bad_chart_before_the_human_sees_it(name, tmp_path, capsys):
    change, _ = BAD[name][0]
    doc = {"schema": "afkv2.page/1",
           "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                       "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
           "maps": [], "notes": [],
           "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                       "items": [{"id": "i-a", "kind": "info", "body": {**chart(name), "id": "c-chart"}}]}]}
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(doc), "utf-8")
    assert engine.main(["check", str(path)]) == 0
    capsys.readouterr()
    doc["rounds"][0]["items"][0]["body"]["props"].update(change)
    path.write_text(json.dumps(doc), "utf-8")
    assert engine.main(["check", str(path)]) != 0
    assert json.loads(capsys.readouterr().out)["ok"] is False


# --- tile (K-01) ---

def test_a_tile_shows_the_number_large_its_label_its_range_and_how_it_is_known():
    html = drawn("tile")
    written = words(html)
    assert written[0] == "1,240 ms"
    assert "export time" in written and "range 900 to 1,500 ms" in written
    assert int(re.search(r'font-size:(\d+)px;font-weight:700">1,240 ms', html).group(1)) >= 28
    assert 'class="afkv2-chip afkv2-tone--estimated"' in html and "estimated" in html
    assert "3 runs on the staging host" in html


def test_a_tile_with_no_range_writes_no_range_line():
    props = {k: v for k, v in CHARTS["tile"].items() if k not in ("low", "high")}
    html = registry.render_component({"type": "tile", "props": props})
    assert not any(w.startswith("range") for w in words(html))


# --- bars (K-02) ---

BAR = re.compile(r'<rect x="[\d.]+" y="[\d.]+" width="([\d.]+)" height="14\.0" style="fill:var\(--accent\)')


def test_bars_sort_largest_first_and_write_each_value_at_the_end():
    written = words(drawn("bars"))
    assert written == ["returns", "340 rows", "orders", "120 rows", "refunds", "15 rows"]
    widths = [float(w) for w in BAR.findall(drawn("bars"))]
    assert widths == sorted(widths, reverse=True) and widths[0] / widths[1] == pytest.approx(340 / 120, rel=0.01)


def test_bars_of_a_share_draw_one_split_bar_with_a_numbered_key_not_a_pie():
    html = drawn("bars", split=True)
    assert "<circle" not in html and "<path" not in html
    written = words(html)
    assert "1. returns: 340 rows, 72%" in written and "3. refunds: 15 rows, 3%" in written
    assert all(f"var(--afkv2-set-{k})" in html for k in (1, 2, 3))
