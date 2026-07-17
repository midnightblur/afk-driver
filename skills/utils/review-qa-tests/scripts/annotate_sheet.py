# -*- coding: utf-8 -*-
"""Annotate an .xlsx with THREADED comments (not legacy notes) + highlighted new rows.

Usage:
    python annotate_sheet.py config.json          # write
    python annotate_sheet.py --verify out.xlsx     # validate a written file

config.json:
    backup        clean source .xlsx to read from (never == out)
    out           destination .xlsx (deleted and rewritten)
    sheet         worksheet name to annotate
    author        comment author display name
    template_row  int; row whose style new rows copy
    comments      { "G3": "text", ... }  cells on existing rows
    new_rows      [ { "C": "...", "D": "...", "G": "..." }, ... ]  appended after last row
    dt            optional ISO datetime string for the comments (default fixed)

Why the two-step: openpyxl writes only legacy notes. This converts them to threaded
comments by editing the package. Two faults trigger Excel's "repair?" prompt even
though the XML is valid — see EXCEL.md; both are handled here.
"""
import sys, os, re, json, uuid, zipfile
from xml.sax.saxutils import escape
from copy import copy

PERSON_ID = '{0C5AF367-69BB-4C84-BB7C-B41C21C97D64}'


def build(cfg):
    import openpyxl
    from openpyxl.comments import Comment
    from openpyxl.styles import PatternFill

    backup, out, sheet = cfg['backup'], cfg['out'], cfg['sheet']
    author = cfg.get('author', 'reviewer')
    dt = cfg.get('dt', '2026-01-01T00:00:00.00')
    trow = int(cfg.get('template_row', 2))
    if os.path.abspath(backup) == os.path.abspath(out):
        sys.exit('ERROR: backup and out must differ — read clean, write fresh.')
    stage = out + '.stage'

    wb = openpyxl.load_workbook(backup)
    ws = wb[sheet]

    fill = PatternFill(start_color='FFFFF2CC', end_color='FFFFF2CC', fill_type='solid')
    start = ws.max_row + 1
    for i, row in enumerate(cfg.get('new_rows', [])):
        r = start + i
        for col, val in row.items():
            src, tgt = ws[f'{col}{trow}'], ws[f'{col}{r}']
            tgt.value = val
            tgt.font = copy(src.font); tgt.alignment = copy(src.alignment)
            tgt.border = copy(src.border); tgt.number_format = src.number_format
            tgt.fill = fill

    comments = cfg.get('comments', {})
    for coord, text in comments.items():
        c = Comment(text, author); c.width, c.height = 480, 300
        ws[coord].comment = c
    wb.save(stage)

    # ---- convert legacy notes -> threaded comments ----
    zin = zipfile.ZipFile(stage)
    names = zin.namelist()
    parts = {n: zin.read(n) for n in names}
    zin.close()

    cpart = next((n for n in names if re.match(r'xl/comments/comment\d+\.xml$', n)
                  or re.match(r'xl/comments\d+\.xml$', n)), None)
    if cpart is None:
        os.replace(stage, out)  # no comments — nothing to convert
        return start, len(comments), len(cfg.get('new_rows', []))

    cx = parts[cpart].decode('utf8')
    refs = re.findall(r'<comment ref="([A-Z]+\d+)"', cx)
    guid = {ref: '{' + str(uuid.uuid4()).upper() + '}' for ref in refs}

    authors = ''.join(f'<author>tc={guid[r]}</author>' for r in refs)
    cx = re.sub(r'<authors>.*?</authors>', f'<authors>{authors}</authors>', cx, count=1, flags=re.S)
    cx = re.sub(r'<comment ref="([A-Z]+\d+)" authorId="\d+"',
                lambda m: f'<comment ref="{m.group(1)}" authorId="{refs.index(m.group(1))}"', cx)
    parts[cpart] = cx.encode('utf8')

    items = ''.join(
        f'<threadedComment ref="{r}" dT="{dt}" personId="{PERSON_ID}" id="{guid[r]}">'
        f'<text>{escape(comments[r])}</text></threadedComment>' for r in refs)
    parts['xl/threadedComments/threadedComment1.xml'] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
        '<ThreadedComments xmlns="http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments" '
        'xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{items}</ThreadedComments>').encode('utf8')
    parts['xl/persons/person.xml'] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
        '<personList xmlns="http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments" '
        'xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<person displayName="{escape(author)}" id="{PERSON_ID}" userId="{escape(author)}" providerId="None"/>'
        '</personList>').encode('utf8')

    # sheet rels -> threadedComment
    srel = next(n for n in names if re.match(r'xl/worksheets/_rels/.*\.rels$', n))
    rx = parts[srel].decode('utf8').replace('</Relationships>',
        '<Relationship Id="threadedComment1" '
        'Type="http://schemas.microsoft.com/office/2017/10/relationships/threadedComment" '
        'Target="/xl/threadedComments/threadedComment1.xml"/></Relationships>')
    parts[srel] = rx.encode('utf8')

    # GOTCHA 1: workbook rels -> person (else orphan -> Excel repair)
    wrel = 'xl/_rels/workbook.xml.rels'
    wx = parts[wrel].decode('utf8')
    wids = [int(x) for x in re.findall(r'Id="rId(\d+)"', wx)] or [0]
    wx = wx.replace('</Relationships>',
        f'<Relationship Id="rId{max(wids)+1}" '
        'Type="http://schemas.microsoft.com/office/2017/10/relationships/person" '
        'Target="/xl/persons/person.xml"/></Relationships>')
    parts[wrel] = wx.encode('utf8')

    ct = parts['[Content_Types].xml'].decode('utf8').replace('</Types>',
        '<Override PartName="/xl/threadedComments/threadedComment1.xml" '
        'ContentType="application/vnd.ms-excel.threadedcomments+xml"/>'
        '<Override PartName="/xl/persons/person.xml" '
        'ContentType="application/vnd.ms-excel.person+xml"/></Types>')
    parts['[Content_Types].xml'] = ct.encode('utf8')

    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in parts:
            z.writestr(n, parts[n])
    os.remove(stage)
    return start, len(comments), len(cfg.get('new_rows', []))


def verify(path):
    import openpyxl, posixpath
    from xml.etree import ElementTree as ET
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    for n in names:
        if n.endswith(('.xml', '.rels')):
            ET.fromstring(z.read(n))
    def norm(base, tgt):
        return tgt[1:] if tgt.startswith('/') else posixpath.normpath(
            posixpath.join(posixpath.dirname(base), tgt))
    referenced, dangling = set(), []
    for rp in [n for n in names if n.endswith('.rels')]:
        base = rp.replace('_rels/', '').replace('.rels', '')
        for rel in ET.fromstring(z.read(rp)):
            if rel.get('TargetMode') == 'External':
                continue
            t = norm(base, rel.get('Target')); referenced.add(t)
            if t not in names:
                dangling.append((rp, rel.get('Target')))
    orphans = [n for n in names if n not in referenced
               and not n.endswith('.rels') and n != '[Content_Types].xml']
    ct = z.read('[Content_Types].xml').decode('utf8')
    openpyxl.load_workbook(path)
    ok = not dangling and not orphans and 'threadedcomments+xml' in ct and 'person+xml' in ct
    print('dangling:', dangling or 'none')
    print('orphans :', orphans or 'none')
    print('content-types threaded+person:', 'threadedcomments+xml' in ct and 'person+xml' in ct)
    print('VERIFY:', 'OK' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--verify':
        sys.exit(0 if verify(sys.argv[2]) else 1)
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding='utf8') as f:
        cfg = json.load(f)
    start, nc, nr = build(cfg)
    print(f'OK -> {cfg["out"]}  | comments: {nc} | new rows from {start} ({nr})')
    verify(cfg['out'])
