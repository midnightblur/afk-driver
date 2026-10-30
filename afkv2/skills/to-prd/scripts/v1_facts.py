"""The v1 string the first afkv2 publish must recognise: nothing else in this skill may name it."""

from __future__ import annotations

import re

PICTURE_NAME = re.compile(r"afk-fig\d+\.png")
