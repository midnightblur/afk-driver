"""Build an offline Edge proof through the round writer and engine render entry points.

Run: python afkv2/tests/live/page_tip_browser.py --output <scratch-folder>
Open the printed HTML path in Edge and click Run proof. No server is needed.
"""

import argparse
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PLUGIN / "engine"), str(PLUGIN / "skills/grill/scripts")]
import engine
import round_document
from shell import inject

LITERAL = '<img id="tip-injected" src="https://example.invalid/tip" onerror="window.tipExecuted=1"><a href="https://example.invalid">link</a> **bold** &amp;'
TEXT = 'card card CASE-1 case-1 CASE-1s CASE-1-more xCASE-1 CASE-1.x Queue queues classes worker unsafe untouched xqueue pre-queue'
MONITOR = """<script>
window.tipRequests=0;
['fetch','WebSocket','EventSource'].forEach(key=>{window[key]=function(){window.tipRequests++;throw Error('Unexpected request');};});
XMLHttpRequest.prototype.open=function(){window.tipRequests++;throw Error('Unexpected XHR');};
navigator.sendBeacon=function(){window.tipRequests++;return false;};
document.addEventListener('DOMContentLoaded',()=>{window.tipScanStart=performance.now();});
</script>"""
END = "<script>document.addEventListener('DOMContentLoaded',()=>{window.tipScanMs=performance.now()-window.tipScanStart;});</script>"


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    root = output / "repo"
    (root / ".afkv2").mkdir(parents=True, exist_ok=True)
    (root / ".afkv2/config.json").write_text('{"spec_folder":"specs"}', "utf-8")
    os.environ["LOCALAPPDATA"] = str(output / "local")

    def render(name, text, tips=None, shared=None, legacy=False):
        path = root / "specs/pages" / ("grill-" + name + ".json")
        # A new path each time avoids resume behavior when the proof is rebuilt.
        if path.exists():
            path.unlink()
        body = {"type": "text", "id": "sample", "props": {"text": text}}
        value = {"banner": {"settled": [], "unlocks": [], "parked": []},
                 "items": [{"id": "card", "kind": "info", "body": body},
                           {"id": "CASE-1", "kind": "info", "body": {"type": "text", "props": {"text": "Other item"}}}]}
        if tips is not None:
            value["tips"] = tips
        round_document.build_round_document(path, {"id": name, "skill": "grill", "feature": "sample", "ticket": "sample"}, value)
        if legacy:
            doc = json.loads(path.read_text("utf-8")); doc["schema"] = "afkv2.page/0"
            path.write_text(json.dumps(doc), "utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as log:
            assert engine.main(["render", str(path)]) == 0, log.getvalue()
        html = inject.inject(path.with_suffix(".html").read_text("utf-8"), shared or {})
        # Instrument only timing and request observation; use the shipped runtime unchanged.
        html = html.replace(inject.MARK_START, MONITOR + inject.MARK_START)
        html = html.replace(inject.MARK_END, inject.MARK_END + END)
        return html

    normal = render("normal", TEXT, {"ids": [{"id": "card", "title": "Current title"}, {"id": "CASE-1", "title": "Exact title"}],
                    "terms": [{"term": k, "definition": v} for k, v in {"card": "Page card", "queue": "Page queue", "class": "Page class", "unsafe": LITERAL}.items()]},
                    {"card": "Shared card", "queue": "Shared queue", "worker": "Shared worker"})
    payload_block = r'(<script id="afkv2-tips-payload"[^>]*>).*?(</script>)'
    broken = re.sub(payload_block, r'\1{\2', normal, flags=re.S)
    # The failure fixture retains only the shared fallback under test.
    shared_block = r'(<script id="afkv2-tips-dict"[^>]*>).*?(</script>)'
    broken = re.sub(shared_block, r'\1{"worker":"Shared worker"}\2', broken, flags=re.S)
    legacy = render("legacy", "MRs Queue", shared={"MR": "Merge request", "queue": "Shared queue"}, legacy=True)
    words = [f"term{i:04d}" for i in range(2000)]
    performance_text = (" ".join(words) + " ") * 12
    performance_text = performance_text[:199998] + "  "  # Full tokens; exactly 200000 characters.
    performance_html = render("performance", performance_text, {"terms": [{"term": w, "definition": "Meaning " + w} for w in words]})
    cases = {"normal": normal, "broken": broken, "legacy": legacy, "performance": performance_html,
             "text": TEXT, "literal": LITERAL, "performanceText": performance_text, "matches": len(performance_text.split())}
    template = Path(__file__).with_suffix(".html").read_text("utf-8")
    target = output / "page-tip-proof.html"
    target.write_text(template.replace("__CASES__", json.dumps(cases).replace("<", "\\u003c")), "utf-8")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    print(build(parser.parse_args().output).as_uri())
