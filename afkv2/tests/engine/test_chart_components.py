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
    "line": {"caption": CAPTION, "unit": "ms", "target": 1000,
             "points": [{"at": "2026-10-01", "value": 2400}, {"at": "2026-10-08", "value": 2100},
                        {"at": "2026-10-15", "value": 1300}, {"at": "2026-10-22", "value": 1240}]},
    "bullet": {"caption": CAPTION, "label": "test coverage", "value": 72, "target": 80, "unit": "%",
               "bands": [{"upto": 50, "label": "poor"}, {"upto": 75, "label": "fair"}, {"upto": 100, "label": "good"}]},
    "range": {"caption": CAPTION, "unit": "days", "means": "9 in 10 such tasks end between low and high",
              "items": [{"label": "export rework", "low": 3, "likely": 5, "high": 9},
                        {"label": "cache", "low": 1, "likely": 2, "high": 3}]},
    "signed-bars": {"caption": CAPTION, "unit": "ms", "below": "faster", "above": "slower",
                    "items": [{"label": "export", "value": -420}, {"label": "import", "value": 130},
                              {"label": "search", "value": 0}]},
    "box-plot": {"caption": CAPTION, "unit": "ms",
                 "items": [{"label": "before", "min": 20, "q1": 80, "median": 120, "q3": 300, "max": 900},
                           {"label": "after", "min": 15, "q1": 40, "median": 60, "q3": 110, "max": 400}]},
    "flame": {"caption": CAPTION, "unit": "ms",
              "root": {"name": "export job", "value": 1000, "children": [
                  {"name": "read orders", "value": 600, "children": [{"name": "sql query", "value": 550}]},
                  {"name": "write file", "value": 300}]}},
    "sparkline": {"caption": CAPTION, "rows": [{"label": "export time", "values": [2400, 2100, 1300, 1240], "unit": "ms"},
                                               {"label": "error rate", "values": [2, 3, 1, 0.5], "unit": "%"}]},
    "waterfall": {"caption": CAPTION, "unit": "ms", "spans": [
        {"id": "s-api", "label": "export endpoint", "start": 0, "duration": 900},
        {"id": "s-auth", "label": "check access", "start": 10, "duration": 60, "parent": "s-api"},
        {"id": "s-read", "label": "read orders", "start": 80, "duration": 700, "parent": "s-api"},
        {"id": "s-sql", "label": "sql query", "start": 90, "duration": 650, "parent": "s-read"},
        {"id": "s-mail", "label": "send mail", "start": 100, "duration": 200, "parent": "s-api"}]},
}


def _deep(levels):
    frame = {"name": "leaf", "value": 1}
    for _ in range(levels - 1):
        frame = {"name": "caller", "value": 1, "children": [frame]}
    return frame


# Each chart: props that break a rule, with the field the refusal names.
BAD = {
    "tile": [({"grade": "guessed"}, "grade"), ({"low": 1300}, "low"), ({"high": None}, "high"),
             ({"value": float("nan")}, "value")],
    "bars": [({"items": []}, "items"), ({"items": [{"label": "a", "value": -1}]}, "items"),
             ({"items": [{"label": f"r{k}", "value": k} for k in range(41)]}, "items"),
             ({"split": True, "items": [{"label": "a", "value": 0}]}, "items"),
             ({"items": [{"label": "a", "value": 1, "colour": "red"}]}, "items")],
    "line": [({"points": [{"at": "d1", "value": 1}]}, "points"), ({"points": [{"at": "", "value": 1}] * 2}, "points"),
             ({"points": [{"at": "d", "value": "1"}] * 2}, "points"), ({"target": float("inf")}, "target"),
             ({"points": [{"at": "d", "value": 1}] * 401}, "points")],
    "bullet": [({"bands": [{"upto": 75, "label": "fair"}, {"upto": 50, "label": "poor"}]}, "bands"),
               ({"value": 101}, "value"), ({"target": -1}, "target"), ({"bands": []}, "bands"),
               ({"bands": [{"upto": k, "label": "b"} for k in range(1, 7)], "value": 1, "target": 1}, "bands"),
               ({"start": 75, "bands": [{"upto": 100, "label": "good"}]}, "value")],
    "range": [({"items": [{"label": "a", "low": 1, "likely": 5, "high": 3}]}, "items"),
              ({"items": [{"label": "a", "low": 4, "likely": 2, "high": 6}]}, "items"), ({"means": None}, "means"),
              ({"items": []}, "items"), ({"items": [{"label": "a", "low": 1, "likely": 1, "high": 1}] * 41}, "items")],
    "signed-bars": [({"items": []}, "items"), ({"items": [{"label": "a", "value": "1"}]}, "items"),
                    ({"items": [{"label": "a", "value": 1}] * 41}, "items"), ({"below": ""}, "below"),
                    ({"items": [{"label": "a", "value": float("-inf")}]}, "items")],
    "box-plot": [({"items": [{"label": "a", "min": 1, "q1": 5, "median": 4, "q3": 6, "max": 7}]}, "items"),
                 ({"items": [{"label": "a", "min": 1, "q1": 2, "median": 3, "q3": 4}]}, "items"), ({"items": []}, "items"),
                 ({"items": [{"label": "a", "min": 1, "q1": 1, "median": 1, "q3": 1, "max": 1}] * 21}, "items")],
    "flame": [({"root": {"name": "a", "value": 10, "children": [{"name": "b", "value": 8}, {"name": "c", "value": 5}]}},
               "root"),
              ({"root": {"name": "a", "value": 0}}, "root"), ({"root": {"name": "", "value": 1}}, "root"),
              ({"root": {"name": "a", "value": 1, "self": 1}}, "root"), ({"root": _deep(17)}, "root"),
              ({"root": {"name": "a", "value": 501, "children": [{"name": "b", "value": 1}] * 500}}, "root")],
    "sparkline": [({"rows": [{"label": "a", "values": [1]}]}, "rows"), ({"rows": []}, "rows"),
                  ({"rows": [{"label": "a", "values": [1, 2]}] * 41}, "rows"),
                  ({"rows": [{"label": "a", "values": [1] * 401}]}, "rows"), ({"rows": [{"label": "", "values": [1, 2]}]}, "rows")],
    "waterfall": [({"spans": [{"id": "a", "label": "a", "start": 0, "duration": 1, "parent": "b"}]}, "spans"),
                  ({"spans": [{"id": "a", "label": "a", "start": 0, "duration": 1, "parent": "b"},
                              {"id": "b", "label": "b", "start": 0, "duration": 1}]}, "spans"),
                  ({"spans": [{"id": "a", "label": "a", "start": 0, "duration": 1}] * 2}, "spans"),
                  ({"spans": []}, "spans"), ({"spans": [{"id": "a", "label": "a", "start": 0, "duration": -1}]}, "spans"),
                  ({"spans": [{"id": f"s{k}", "label": "a", "start": 0, "duration": 1} for k in range(201)]}, "spans")],
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


# --- line (K-03) ---

POLYLINE = re.compile(r'<polyline points="([^"]*)"')


def _line_points(html):
    return [tuple(float(n) for n in pair.split(",")) for pair in POLYLINE.search(html).group(1).split()]


def test_a_line_joins_dated_points_and_labels_the_latest_value():
    html = drawn("line")
    written = words(html)
    assert "latest 1,240 ms" in written and "2026-10-01" in written and "2026-10-22" in written
    points = _line_points(html)
    assert len(points) == 4 and [x for x, _ in points] == sorted(x for x, _ in points)
    assert points[0][1] < points[-1][1], "the higher value sits higher"


def test_a_line_draws_its_target_as_a_labelled_dashed_line_only_when_one_exists():
    assert "target 1,000 ms" in words(drawn("line")) and "stroke-dasharray" in drawn("line")
    props = {k: v for k, v in CHARTS["line"].items() if k != "target"}
    html = registry.render_component({"type": "line", "props": props})
    assert "stroke-dasharray" not in html and not any(w.startswith("target") for w in words(html))


# --- bullet (K-35) ---

MIX = re.compile(r"color-mix\(in srgb, var\(--neutral\) (\d+)%")
TICK = re.compile(r'<line x1="([\d.]+)" y1="[\d.]+" x2="\1" y2="[\d.]+" style="stroke:var\(--fg\);stroke-width:3"')
VALUE_BAR = re.compile(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="10\.0" style="fill:var\(--fg\)')


def test_a_bullet_draws_the_value_bar_the_target_tick_and_named_bands():
    html = drawn("bullet")
    written = words(html)
    assert {"test coverage", "poor", "fair", "good"} <= set(written)
    assert "72% · target 80% · fair" in written
    strengths = MIX.findall(html)
    assert len(strengths) == 3 and len(set(strengths)) == 3, "each band its own strength of one hue"
    start, width = (float(n) for n in VALUE_BAR.search(html).groups())
    tick = float(TICK.search(html).group(1))
    assert (tick - start) / width == pytest.approx(80 / 72, rel=0.01)


# --- range (K-37) ---

RANGE_BAR = re.compile(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="8\.0"')
LIKELY = re.compile(r'<circle cx="([\d.]+)"')


def test_range_bars_share_one_scale_with_a_dot_at_the_likely_value_and_numbers_at_the_end():
    html = drawn("range")
    written = words(html)
    assert written[:4] == ["export rework", "3 to 9 days, likely 5", "cache", "1 to 3 days, likely 2"]
    assert len(written) == 4 and "The range: 9 in 10 such tasks end between low and high</p>" in html
    (x1, w1), (x2, w2) = [(float(a), float(b)) for a, b in RANGE_BAR.findall(html)]
    assert w1 / w2 == pytest.approx((9 - 3) / (3 - 1), rel=0.01), "one scale for every bar"
    dots = [float(x) for x in LIKELY.findall(html)]
    assert x1 < dots[0] < x1 + w1 and x2 < dots[1] < x2 + w2


# --- signed bars (K-38) ---

ZERO = re.compile(r'<line x1="([\d.]+)" y1="0\.0" x2="\1" y2="[\d.]+" style="stroke:var\(--fg\)')
SIGNED_BAR = re.compile(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="14\.0"')


def test_signed_bars_grow_left_and_right_of_a_zero_line_with_the_sign_in_the_label():
    html = drawn("signed-bars")
    written = words(html)
    assert written[:2] == ["\u2190 faster", "slower \u2192"]
    assert written[2:] == ["export", "\u2212420 ms", "import", "+130 ms", "search", "0 ms"]
    zero = float(ZERO.search(html).group(1))
    (x1, w1), (x2, w2), (x3, w3) = [(float(a), float(b)) for a, b in SIGNED_BAR.findall(html)]
    assert x1 + w1 == pytest.approx(zero, abs=0.2) and x2 == pytest.approx(zero, abs=0.2) and w3 == 0
    assert w1 / w2 == pytest.approx(420 / 130, rel=0.01)


def test_signed_bars_with_no_side_words_write_none():
    props = {k: v for k, v in CHARTS["signed-bars"].items() if k not in ("below", "above")}
    written = words(registry.render_component({"type": "signed-bars", "props": props}))
    assert written[0] == "export"


# --- box plot (K-36) ---

BOX = re.compile(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="16\.0"')
MEDIAN = re.compile(r'<line x1="([\d.]+)" y1="[\d.]+" x2="\1" y2="[\d.]+" style="stroke:var\(--fg\);stroke-width:2"')


def test_box_plots_share_one_scale_and_write_the_median_and_the_spread():
    html = drawn("box-plot")
    written = words(html)
    assert written[:4] == ["before", "median 120 ms (20 to 900)", "after", "median 60 ms (15 to 400)"]
    assert written[-2:] == ["15", "900"], "the shared scale runs from the lowest min to the highest max"
    (x1, w1), (x2, w2) = [(float(a), float(b)) for a, b in BOX.findall(html)]
    assert w1 / w2 == pytest.approx((300 - 80) / (110 - 40), rel=0.01)
    medians = [float(x) for x in MEDIAN.findall(html)]
    assert x1 < medians[0] < x1 + w1 and x2 < medians[1] < x2 + w2


# --- flame graph (K-47) ---

FRAME = re.compile(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="18\.0" [^>]*><title>([^<]*)</title>')


def test_a_flame_graph_sizes_each_box_by_its_share_with_callers_below_callees():
    frames = {title.split(":")[0]: (float(x), float(y), float(w), title)
              for x, y, w, title in FRAME.findall(drawn("flame"))}
    root, read, query, write = (frames[n] for n in ("export job", "read orders", "sql query", "write file"))
    assert root[1] > read[1] > query[1] and read[1] == write[1], "the caller sits below its callees"
    assert read[2] / root[2] == pytest.approx(0.6, rel=0.01) and query[0] == read[0]
    assert write[0] == pytest.approx(read[0] + read[2], abs=0.2)
    assert read[3] == "read orders: 600 ms, 60% of the total"
    assert {"export job", "read orders", "sql query", "write file"} <= set(words(drawn("flame")))


# --- sparklines (K-48) ---

def test_sparklines_draw_a_tiny_line_per_row_with_the_latest_value_beside_it():
    html = drawn("sparkline")
    assert words(html) == ["export time", "1,240 ms", "error rate", "0.5%"]
    lines = [[tuple(float(n) for n in pair.split(",")) for pair in found.split()] for found in POLYLINE.findall(html)]
    assert [len(points) for points in lines] == [4, 4]
    first, second = lines
    assert max(y for _, y in first) < min(y for _, y in second), "each row keeps its own band"
    assert first[0][1] < first[-1][1] and second[1][1] < second[0][1], "a higher value sits higher in its row"


# --- span waterfall (K-49) ---

SPAN = re.compile(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="12\.0" style="fill:([^;"]+)')


def test_a_waterfall_draws_each_step_on_one_time_axis_with_the_slowest_path_strong():
    html = drawn("waterfall")
    written = words(html)
    assert written[0] == "\u25c6 the slowest path"
    assert written[1:11] == ["\u25c6 export endpoint", "900 ms", "check access", "60 ms", "\u25c6 read orders", "700 ms",
                             "\u25c6 sql query", "650 ms", "send mail", "200 ms"]
    assert written[-2:] == ["0", "900 ms"]
    spans = [(float(x), float(w), fill) for x, w, fill in SPAN.findall(html)]
    api, auth, read, sql, mail = spans
    per_ms = api[1] / 900
    assert read[0] - api[0] == pytest.approx(80 * per_ms, abs=0.2) and sql[1] == pytest.approx(650 * per_ms, abs=0.2)
    strong = {fill for _, _, fill in (api, read, sql)}
    assert strong == {"var(--accent)"} and auth[2] != "var(--accent)" and mail[2] != "var(--accent)"


def test_a_waterfall_indents_a_step_under_its_parent():
    html = drawn("waterfall")
    xs = {w: float(x) for x, w in re.findall(r'<text x="([\d.]+)" [^>]*>([^<]*)</text>', html)}
    assert xs["\u25c6 export endpoint"] < xs["check access"] < xs["\u25c6 sql query"]
