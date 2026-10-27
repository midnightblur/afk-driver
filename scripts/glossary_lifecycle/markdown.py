"""Canonical Markdown codec for glossary definitions."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import ClassVar


class GlossaryMarkdownError(ValueError):
    """Base class for invalid glossary Markdown."""


class DuplicateTermIdError(GlossaryMarkdownError):
    """Two definitions use one stable ID."""


class UnresolvedReplacementError(GlossaryMarkdownError):
    """A replacement link has no definition."""


class ReplacementCycleError(GlossaryMarkdownError):
    """Replacement links form a cycle."""


class AliasCollisionError(GlossaryMarkdownError):
    """One spelling identifies more than one definition."""


class MissingIdentityError(GlossaryMarkdownError):
    """An adopted definition has no stable ID or owner."""


@dataclass(frozen=True, slots=True)
class GlossaryDefinition:
    id: str
    canonical_term: str
    definition: str
    owner: str
    aliases: tuple[str, ...] = ()
    replaces: tuple[str, ...] = ()
    code: str | None = None
    related: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GlossaryDocument:
    definitions: tuple[GlossaryDefinition, ...]

    @property
    def by_id(self) -> dict[str, GlossaryDefinition]:
        return {definition.id: definition for definition in self.definitions}


class GlossaryMarkdownCodec:
    """Parse and serialize the adopted glossary grammar."""

    ENTRY: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:[-*+]\s+)?\*\*(.+?)\*\*\s*(?:\(([^)]*)\))?\s*:\s*(.*)$"
    )
    META: ClassVar[re.Pattern[str]] = re.compile(
        r"^[`_]*(ID|Owner|Replaces|Also|Avoid|Code|Related)[`_]*\s*:\s*(.*)$",
        re.IGNORECASE,
    )

    def parse(self, text: str, *, known_ids: tuple[str, ...] = ()) -> GlossaryDocument:
        raw_entries = self._entries(text)
        definitions: list[GlossaryDefinition] = []
        ids: set[str] = set()
        spellings: dict[str, str] = {}

        for term, heading_aliases, body in raw_entries:
            metadata: dict[str, str] = {}
            definition_lines: list[str] = []
            for line in body:
                stripped = line.strip()
                match = self.META.match(stripped)
                if match:
                    metadata[match.group(1).casefold()] = match.group(2).strip()
                elif stripped and not stripped.startswith("#"):
                    definition_lines.append(stripped)

            term_id = self._scalar(metadata.get("id", ""))
            owner = self._scalar(metadata.get("owner", ""))
            if not term_id or not owner:
                raise MissingIdentityError(f"definition {term!r} requires ID and Owner")
            if term_id in ids:
                raise DuplicateTermIdError(f"duplicate glossary ID: {term_id}")
            ids.add(term_id)

            aliases = self._unique(
                self._split(heading_aliases, "/") + self._csv_values(metadata.get("also", ""))
            )
            for spelling in (term, *aliases):
                key = self._normal_spelling(spelling)
                previous = spellings.get(key)
                if previous is not None and previous != term_id:
                    raise AliasCollisionError(
                        f"spelling {spelling!r} identifies both {previous} and {term_id}"
                    )
                spellings[key] = term_id

            definition = " ".join(definition_lines).strip()
            if not definition:
                raise GlossaryMarkdownError(f"definition {term!r} has no text")
            definitions.append(
                GlossaryDefinition(
                    term_id,
                    self._scalar(term),
                    definition,
                    owner,
                    aliases,
                    self._unique(self._csv_values(metadata.get("replaces", ""))),
                    self._scalar(metadata["code"]) if metadata.get("code") else None,
                    self._unique(self._csv_values(metadata.get("related", ""))),
                    self._unique(self._csv_values(metadata.get("avoid", ""))),
                )
            )

        all_ids = ids.union(known_ids)
        for definition in definitions:
            for replaced in definition.replaces:
                if replaced not in all_ids:
                    raise UnresolvedReplacementError(
                        f"definition {definition.id} replaces unknown ID {replaced}"
                    )
        self._reject_replacement_cycles(definitions)
        return GlossaryDocument(tuple(definitions))

    def serialize(self, document: GlossaryDocument) -> str:
        blocks: list[str] = []
        for definition in document.definitions:
            lines = [
                f"**{definition.canonical_term}**:",
                definition.definition,
                f"_ID_: {definition.id}",
                f"_Owner_: {definition.owner}",
            ]
            if definition.aliases:
                lines.append(f"_Also_: {self._csv_line(definition.aliases)}")
            if definition.replaces:
                lines.append(f"_Replaces_: {self._csv_line(definition.replaces)}")
            if definition.code:
                lines.append(f"_Code_: {definition.code}")
            if definition.related:
                lines.append(f"_Related_: {self._csv_line(definition.related)}")
            if definition.avoid:
                lines.append(f"_Avoid_: {self._csv_line(definition.avoid)}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks) + ("\n" if blocks else "")

    def tooltip_dictionary(self, text: str) -> dict[str, str]:
        entries: dict[str, str] = {}
        for term, heading_aliases, body in self._entries(text):
            metadata: dict[str, str] = {}
            definition_lines = [
                line.strip()
                for line in body
                if line.strip() and not self.META.match(line.strip()) and not line.strip().startswith("#")
            ]
            for line in body:
                match = self.META.match(line.strip())
                if match:
                    metadata[match.group(1).casefold()] = match.group(2).strip()
            definition = self._tooltip_clean(" ".join(definition_lines))
            if not definition:
                continue
            for key in self._tooltip_keys(term):
                entries[key] = definition
            for alias in self._split(heading_aliases, "/"):
                entries[self._normal_spelling(alias)] = definition
            for alias in self._csv_values(metadata.get("also", "")):
                entries[self._normal_spelling(alias)] = definition
        return entries

    def _entries(self, text: str) -> list[tuple[str, str, list[str]]]:
        entries: list[tuple[str, str, list[str]]] = []
        current: tuple[str, str, list[str]] | None = None
        for line in text.splitlines():
            match = self.ENTRY.match(line.strip())
            if match:
                if current is not None:
                    entries.append(current)
                current = (match.group(1).strip(), (match.group(2) or "").strip(), [])
                if match.group(3).strip():
                    current[2].append(match.group(3).strip())
            elif current is not None:
                current[2].append(line)
        if current is not None:
            entries.append(current)
        return entries

    def _reject_replacement_cycles(self, definitions: list[GlossaryDefinition]) -> None:
        graph = {definition.id: definition.replaces for definition in definitions}

        def visit(term_id: str, path: tuple[str, ...]) -> None:
            if term_id in path:
                raise ReplacementCycleError("replacement cycle: " + " -> ".join((*path, term_id)))
            for replaced in graph.get(term_id, ()):
                if replaced in graph:
                    visit(replaced, (*path, term_id))

        for term_id in graph:
            visit(term_id, ())

    @staticmethod
    def _split(value: str, separator: str) -> tuple[str, ...]:
        return tuple(part.strip() for part in value.split(separator) if part.strip())

    @staticmethod
    def _csv_values(value: str) -> tuple[str, ...]:
        if not value.strip():
            return ()
        try:
            row = next(csv.reader([value], skipinitialspace=True, strict=True))
        except csv.Error as problem:
            raise GlossaryMarkdownError("invalid comma-separated metadata") from problem
        return tuple(part.strip() for part in row if part.strip())

    @staticmethod
    def _csv_line(values: tuple[str, ...]) -> str:
        output = io.StringIO()
        csv.writer(output, lineterminator="").writerow(values)
        return output.getvalue()

    @staticmethod
    def _scalar(value: str) -> str:
        return value.strip().strip("`").strip()

    @staticmethod
    def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))

    @staticmethod
    def _normal_spelling(value: str) -> str:
        return " ".join(value.strip().strip("`").casefold().split())

    def _tooltip_keys(self, term: str) -> tuple[str, ...]:
        out: dict[str, None] = {}

        def add(value: str) -> None:
            key = " ".join(
                word.lower() if len(word) > 1 and word[1:].islower() else word
                for word in value.strip().split()
            )
            if key:
                out.setdefault(key, None)

        raw = term.replace("`", "").strip()
        base = re.sub(r"\s*\([^)]*\)", "", raw).strip()
        for part in re.split(r"\s*/\s*", base):
            add(part)
            add(re.split(r"\s+—\s+", part)[0])
        for match in re.finditer(r"\(([^)]*)\)", raw):
            inner = match.group(1).strip()
            if re.fullmatch(r"[\w.\-]+", inner):
                add(inner)
        return tuple(out)

    @staticmethod
    def _tooltip_clean(value: str) -> str:
        value = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", value)
        value = value.replace("`", "")
        value = re.sub(r"(\*\*|\*|__)", "", value)
        value = re.sub(r"(?<![\w])_|_(?![\w])", "", value)
        return re.sub(r"\s+", " ", value).strip()
