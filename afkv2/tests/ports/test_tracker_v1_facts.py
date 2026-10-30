"""Pins the v1 strings by digest. The digests come from the text that v1's publish script writes."""

from __future__ import annotations

import hashlib

from tracker import v1_facts


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_v1_block_lines_are_the_lines_v1_writes():
    assert digest(v1_facts.BLOCK_BEGIN_LINES[0]) == "6cddbb1e7d10a28331284ad32f81f072b59caa84f4cbd88a22f17403a54e124a"
    assert digest(v1_facts.BLOCK_BEGIN_LINES[1]) == "c0a7e9808c9bc3256bb75d787263c21fbf63f00833d3e4aa3a8b8dadc42dd34f"
    assert digest(v1_facts.BLOCK_END_LINE) == "93dd4c1dddb5be1a5c434069d9d565461097eb587cf39d8044276c4216316e02"


def test_the_v1_picture_name_is_the_name_v1_writes():
    assert digest(v1_facts.PICTURE_NAME.pattern) == "5b4adf3d945233a43109234dcd4953a221f54775e0c9dcfcfdf916c1c2f36871"
