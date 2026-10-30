import setup
from conftest import v1_block


def _write(places, provider, text, newline=""):
    path = places.instruction_file(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def test_block_is_found_only_by_full_lines():
    inline = b"see <!-- afk:behaviors:start --> here\n<!-- afk:behaviors:end --> tail\n"
    assert setup.find_blocks(inline) == ([], None)
    blocks, problem = setup.find_blocks(b"a\n" + v1_block().encode() + b"b\n")
    assert problem is None and len(blocks) == 1 and blocks[0][2] == "behaviors"


def test_crlf_block_and_legacy_names_are_found():
    data = (v1_block("\r\n") + "<!-- afk:investigation:start -->\r\nx\r\n"
            "<!-- afk:investigation:end -->\r\n").encode()
    blocks, problem = setup.find_blocks(data)
    assert problem is None and [b[2] for b in blocks] == ["behaviors", "investigation"]


def test_broken_blocks_are_refused():
    assert setup.find_blocks(b"<!-- afk:behaviors:start -->\nx\n")[1]
    assert setup.find_blocks(b"<!-- afk:behaviors:end -->\n")[1]
    nested = b"<!-- afk:behaviors:start -->\n<!-- afk:investigation:start -->\n"
    assert setup.find_blocks(nested)[1]


def test_removal_from_both_files_keeps_outside_bytes(places):
    before_c = "head\r\n" + v1_block("\r\n") + "tail\r\n"
    before_x = v1_block() + "codex rules\n"
    claude = _write(places, "claude", before_c)
    codex = _write(places, "codex", before_x)
    answer = setup.remove_v1_block(places)
    assert answer["ok"] and [f["action"] for f in answer["files"]] == ["removed", "removed"]
    assert claude.read_bytes() == b"head\r\ntail\r\n"
    assert codex.read_bytes() == b"codex rules\n"
    again = setup.remove_v1_block(places)
    assert [f["action"] for f in again["files"]] == ["absent", "absent"]


def test_bad_block_in_one_file_changes_neither(places):
    good = _write(places, "claude", "a\n" + v1_block())
    _write(places, "codex", "<!-- afk:behaviors:start -->\nno end\n")
    before = good.read_bytes()
    answer = setup.remove_v1_block(places)
    assert not answer["ok"] and answer["error"]["code"] == "bad-block"
    assert good.read_bytes() == before


def test_restore_is_byte_identical(places):
    original = "x\n" + v1_block() + "y"
    path = _write(places, "claude", original)
    setup.remove_v1_block(places)
    assert setup.restore_v1_block(places) == [{"path": str(path), "action": "restored"}]
    assert path.read_bytes() == original.encode()
    assert not (places.backup / "instructions" / "claude").exists()


def test_restore_after_an_edit_appends_the_block(places):
    path = _write(places, "claude", "x\n" + v1_block())
    setup.remove_v1_block(places)
    path.write_bytes(b"x\nnew line")
    assert setup.restore_v1_block(places)[0]["action"] == "appended"
    assert path.read_bytes() == b"x\nnew line\n" + v1_block().encode()
