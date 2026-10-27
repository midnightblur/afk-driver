"""Pinned Git access for glossary controls, definitions, and tracked text."""

from __future__ import annotations

import importlib.util
import errno
import json
import math
import os
import re
import subprocess
import tempfile
import time
import uuid
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from types import MappingProxyType

from .domain import GlossaryDomainError, GlossaryDomainRules, GlossaryRoute
from .markdown import GlossaryDefinition, GlossaryDocument, GlossaryMarkdownCodec


class RepositoryError(RuntimeError):
    """A repository input cannot be verified."""

    code = 'repository_unverified'


class ControlError(RepositoryError):
    code = 'repository_controls_invalid'


class SemanticProviderError(RepositoryError):
    code = 'semantic_provider_failed'


class RepositoryLockTimeout(RepositoryError):
    code = 'repository_lock_timeout'


@dataclass(frozen=True, slots=True)
class PinnedSnapshot:
    target_ref: str
    target_commit: str
    merge_base: str
    head: str


@dataclass(frozen=True, slots=True)
class GlossaryManifest:
    version: int
    roots: tuple[str, ...]
    exclusions: tuple[str, ...]
    routes: tuple[GlossaryRoute, ...]


@dataclass(frozen=True, slots=True)
class RepositoryControls:
    commit: str
    config: Mapping
    manifest_path: str | None
    manifest: GlossaryManifest | None
    ownership_paths: tuple[str, ...]
    ownership_map: str


@dataclass(frozen=True, slots=True)
class DefinitionSource:
    path: str
    raw_bytes: bytes
    document: GlossaryDocument


@dataclass(frozen=True, slots=True)
class SearchScope:
    domain_areas: tuple[str, ...]
    paths: tuple[str, ...]
    terms: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrackedText:
    path: str
    text: str


@dataclass(frozen=True, slots=True)
class EvidenceSnippet:
    path: str
    line: int
    text: str


@dataclass(frozen=True, slots=True)
class SemanticCandidate:
    area: str
    term_id: str
    score: float
    snippets: tuple[EvidenceSnippet, ...]


@dataclass(frozen=True, slots=True)
class SearchEvidence:
    roots: tuple[str, ...]
    exclusions: tuple[str, ...]
    method: str
    model: str
    truncated: bool
    excluded_paths: tuple[str, ...]
    counts: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True, slots=True)
class SearchResult:
    candidates: tuple[SemanticCandidate, ...]
    evidence: SearchEvidence


BUILTIN_EXCLUSIONS = tuple(f'**/{directory}/**' for directory in (
    'node_modules', 'vendor', 'target', 'dist', 'build', 'generated', 'generated-sources',
    'logs', 'fixtures', '__fixtures__', 'seeds', 'exports', 'data-exports', '.git',
)) + ('**/*.log', '**/*.csv', '**/*.tsv', '**/*.jsonl', '**/*.parquet', '**/*.sqlite', '**/*.db')


def _matches(path: str, pattern: str) -> bool:
    return fnmatchcase(path, pattern) or (pattern.startswith('**/') and fnmatchcase(path, pattern[3:]))


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root + '/')


def _tokens(text: str) -> set[str]:
    return set(re.findall(r'\w+', text.casefold()))


class TrackedTextRanker:
    """Deterministic token overlap; all evidence comes from supplied Git text."""

    method = 'token-overlap-v1'
    model = 'none'

    def rank(self, area: str, terms: tuple[str, ...], documents: tuple[TrackedText, ...],
             definitions: tuple[GlossaryDefinition, ...]) -> tuple[SemanticCandidate, ...]:
        query = _tokens(' '.join((area, *terms)))
        candidates = []
        for definition in definitions:
            words = _tokens(' '.join((definition.canonical_term, definition.definition, *definition.aliases)))
            snippets = []
            score = 0.0
            for document in documents:
                for number, line in enumerate(document.text.splitlines(), 1):
                    tokens = _tokens(line)
                    overlap = words.intersection(tokens)
                    if overlap and query.intersection(tokens):
                        score += len(overlap) / len(words.union(tokens))
                        snippets.append(EvidenceSnippet(document.path, number, line[:240]))
            if snippets:
                candidates.append(SemanticCandidate(area, definition.id, score, tuple(snippets)))
        return tuple(sorted(candidates, key=lambda candidate: (-candidate.score, candidate.term_id)))


def _config_reader():
    spec = importlib.util.spec_from_file_location('afk_config', Path(__file__).resolve().parents[1] / 'afk-config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _path(value: str) -> str:
    normalized = _config_reader().normalize_path(value)
    if normalized is None or '\x00' in normalized or ':' in normalized:
        raise ControlError(f'invalid repository path: {value!r}')
    return normalized


def _strings(value, field: str, *, empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ControlError(f'{field} must be a list of non-empty strings')
    if not empty and not value:
        raise ControlError(f'{field} must not be empty')
    if len(set(value)) != len(value):
        raise ControlError(f'{field} must not contain duplicates')
    return tuple(value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ControlError(f'duplicate manifest key: {key}')
        result[key] = value
    return result


class PinnedRepositoryAdapter:
    """Repository port. Each command obtains a new snapshot through refresh."""

    def __init__(self, root: str | Path, semantic_provider=None, *, lock_timeout: float = 10.0):
        self.root = Path(root).resolve()
        self.semantic_provider = semantic_provider if semantic_provider is not None else TrackedTextRanker()
        self.codec = GlossaryMarkdownCodec()
        self.lock_timeout = lock_timeout

    def _git(self, *args: str, input: bytes | None = None) -> bytes:
        try:
            result = subprocess.run(['git', '-C', str(self.root), *args], input=input, capture_output=True, check=True)
            return result.stdout
        except (OSError, subprocess.CalledProcessError) as error:
            raise RepositoryError(f'Git {args[0]} failed; repository state cannot be verified') from error

    def refresh(self, target_ref: str, remote: str = 'origin') -> PinnedSnapshot:
        if not isinstance(remote, str) or not remote or remote.startswith('-'):
            raise RepositoryError('invalid target remote')
        if not isinstance(target_ref, str) or not target_ref:
            raise RepositoryError('invalid target reference')
        branch = target_ref.removeprefix(f'refs/remotes/{remote}/').removeprefix(f'{remote}/').removeprefix('refs/heads/')
        self._git('check-ref-format', f'refs/heads/{branch}')
        temporary_ref = f'refs/afk/glossary-refresh/{uuid.uuid4().hex}'
        try:
            self._git('fetch', '--no-tags', '--no-write-fetch-head', '--refmap=', '--', remote,
                      f'refs/heads/{branch}:{temporary_ref}')
            target = self._git('rev-parse', '--verify', f'{temporary_ref}^{{commit}}').decode('ascii').strip()
        finally:
            self._git('update-ref', '-d', temporary_ref)
        head = self._git('rev-parse', '--verify', 'HEAD^{commit}').decode('ascii').strip()
        base = self._git('merge-base', target, head).decode('ascii').strip()
        if not re.fullmatch(r'[0-9a-f]{40,64}', base):
            raise RepositoryError('merge base cannot be verified')
        return PinnedSnapshot(target_ref, target, base, head)

    def common_dir(self) -> Path:
        return Path(self._git('rev-parse', '--path-format=absolute', '--git-common-dir').decode('utf-8').strip()).resolve()

    def _files(self, commit: str) -> dict[str, tuple[str, str]]:
        result = {}
        output = self._git('ls-tree', '-rz', '--full-tree', commit)
        if not output:
            return result
        if not output.endswith(b'\0'):
            raise RepositoryError('malformed Git tree output: missing record terminator')
        for record in output[:-1].split(b'\0'):
            metadata, separator, path = record.partition(b'\t')
            match = re.fullmatch(rb'([0-7]{6}) (blob|tree|commit) ([0-9a-f]{40}|[0-9a-f]{64})', metadata)
            if not separator or not path or match is None:
                raise RepositoryError('malformed Git tree output: invalid record')
            mode, kind, object_id = (field.decode('ascii') for field in match.groups())
            if (mode, kind) not in {('100644', 'blob'), ('100755', 'blob'), ('120000', 'blob'),
                                    ('040000', 'tree'), ('160000', 'commit')}:
                raise RepositoryError('malformed Git tree output: invalid object mode')
            try:
                decoded_path = path.decode('utf-8')
            except UnicodeDecodeError as error:
                raise RepositoryError('Git filename is not UTF-8') from error
            if kind == 'blob' and mode in ('100644', '100755'):
                result[decoded_path] = (mode, object_id)
        return result

    def _read(self, commit: str, path: str) -> str:
        path = _path(path)
        files = self._files(commit)
        if path not in files:
            raise ControlError(f'{path} is not a committed regular file at {commit}')
        try:
            return self._git('cat-file', 'blob', files[path][1]).decode('utf-8')
        except UnicodeDecodeError as error:
            raise ControlError(f'{path} is not UTF-8 text') from error

    def read_controls(self, snapshot: PinnedSnapshot) -> RepositoryControls:
        reader = _config_reader()
        try:
            config = reader.load_committed(self.root, snapshot.merge_base)
        except reader.ConfigError as error:
            raise ControlError(str(error)) from error
        manifest_path = (config.get('glossary') or {}).get('manifest')
        if manifest_path is None:
            return RepositoryControls(snapshot.merge_base, _freeze(config), None, None, (), '')
        text = self._read(snapshot.merge_base, 'GLOSSARY-MAP.md')
        paths = tuple(sorted({_path(path) for path in re.findall(r'\[[^\]]+\]\((?:<)?([^)>]*GLOSSARY\.md)(?:>)?\)', text)}))
        manifest = self._manifest(self._read(snapshot.merge_base, manifest_path))
        try:
            for route in manifest.routes:
                if route.glossary_path not in paths:
                    raise ControlError(f'route {route.id} targets unmapped glossary {route.glossary_path}')
            GlossaryDomainRules.resolve_routes((), tuple(area for route in manifest.routes for area in route.domain_areas),
                                                manifest.routes, {path: path for path in paths})
        except GlossaryDomainError as error:
            raise ControlError(str(error)) from error
        return RepositoryControls(snapshot.merge_base, _freeze(config), manifest_path, manifest, paths, text)

    @staticmethod
    def _manifest(text: str) -> GlossaryManifest:
        try:
            raw = json.loads(text, object_pairs_hook=_unique_object)
        except (ValueError, TypeError) as error:
            raise ControlError('manifest must contain valid JSON') from error
        if not isinstance(raw, dict) or set(raw) != {'version', 'roots', 'exclusions', 'routes'}:
            raise ControlError('manifest requires version, roots, exclusions, and routes only')
        if type(raw['version']) is not int or raw['version'] != 1:
            raise ControlError('manifest version must be 1')
        roots = tuple(_path(path) for path in _strings(raw['roots'], 'roots', empty=False))
        exclusions = tuple(_path(path) for path in _strings(raw['exclusions'], 'exclusions'))
        if not isinstance(raw['routes'], list) or not raw['routes']:
            raise ControlError('routes must be a non-empty list')
        routes = []
        for row in raw['routes']:
            keys = {'id', 'path_patterns', 'domain_areas', 'glossary_path', 'owner_chain'}
            if not isinstance(row, dict) or set(row) != keys:
                raise ControlError('route fields do not match manifest version 1')
            if not isinstance(row['id'], str) or not row['id'].strip():
                raise ControlError('route id must be non-empty text')
            routes.append(GlossaryRoute(row['id'], tuple(_path(path) for path in _strings(row['path_patterns'], 'path_patterns')),
                                        _strings(row['domain_areas'], 'domain_areas'), _path(row['glossary_path']),
                                        _strings(row['owner_chain'], 'owner_chain', empty=False)))
            if not routes[-1].path_patterns and not routes[-1].domain_areas:
                raise ControlError('a route requires path patterns or domain areas')
        if len({route.id for route in routes}) != len(routes):
            raise ControlError('route IDs must be unique')
        return GlossaryManifest(1, roots, exclusions, tuple(routes))

    def changed_paths(self, snapshot: PinnedSnapshot) -> tuple[str, ...]:
        raw = self._git('diff', '--name-only', '-z', '--no-renames', snapshot.merge_base, snapshot.head, '--')
        try:
            return tuple(sorted(path.decode('utf-8') for path in raw.split(b'\0') if path))
        except UnicodeDecodeError as error:
            raise RepositoryError('Git filename is not UTF-8') from error

    def read_definitions(self, snapshot: PinnedSnapshot, paths: Sequence[str] | None = None) -> Mapping[str, GlossaryDocument]:
        controls = self.read_controls(snapshot)
        selected = controls.ownership_paths if paths is None else tuple(_path(path) for path in paths)
        if any(path not in controls.ownership_paths for path in selected):
            raise ControlError('definition path is not in the ownership map')
        documents = self._parse_definitions({path: self._read(snapshot.merge_base, path) for path in controls.ownership_paths})
        return MappingProxyType({path: documents[path] for path in selected})

    def _parse_definitions(self, sources: Mapping[str, str]) -> dict[str, GlossaryDocument]:
        known_ids = tuple(self.codec.parse('\n\n'.join(sources.values())).by_id)
        documents = {}
        for path, text in sources.items():
            document = self.codec.parse(text, known_ids=known_ids)
            for definition in document.definitions:
                if definition.owner != path:
                    raise ControlError(f'definition {definition.id} Owner must equal owning glossary path {path}')
            documents[path] = document
        return documents

    def exact_matches(self, snapshot: PinnedSnapshot, terms: Sequence[str],
                      paths: Sequence[str] | None = None) -> tuple[GlossaryDefinition, ...]:
        wanted = {' '.join(term.casefold().split()) for term in terms}
        found = {}
        for document in self.read_definitions(snapshot, paths).values():
            for definition in document.definitions:
                spellings = (definition.id, definition.canonical_term, *definition.aliases)
                if any(' '.join(spelling.casefold().split()) in wanted for spelling in spellings):
                    found[definition.id] = definition
        return tuple(found[key] for key in sorted(found))

    def read_definition_source(self, snapshot: PinnedSnapshot, path: str) -> DefinitionSource:
        path = _path(path)
        controls = self.read_controls(snapshot)
        if path not in controls.ownership_paths:
            raise ControlError('definition path is not in the pinned ownership map')
        sources = {item: self._read(snapshot.head, item) for item in controls.ownership_paths}
        documents = self._parse_definitions(sources)
        self._validate_identity(self.read_definitions(snapshot), documents)
        target = self._definition_target(path)
        self._assert_head(snapshot)
        try:
            current = target.read_bytes()
        except OSError as error:
            raise RepositoryError(f'cannot read glossary {path}') from error
        if current.replace(b'\r\n', b'\n') != sources[path].encode('utf-8').replace(b'\r\n', b'\n'):
            raise RepositoryError('working glossary content changed from the pinned feature head')
        return DefinitionSource(path, current, documents[path])

    def _definition_target(self, path: str) -> Path:
        target = self.root / path
        if target.is_symlink() or target.resolve() != target.absolute():
            raise ControlError('definition path resolves outside the repository or through a symlink')
        return target

    def _assert_head(self, snapshot: PinnedSnapshot) -> None:
        if self._git('rev-parse', 'HEAD').decode('ascii').strip() != snapshot.head:
            raise RepositoryError('head changed after the snapshot; refresh before writing')

    def _assert_expected(self, path: str, expected: bytes) -> None:
        try:
            current = self._definition_target(path).read_bytes()
        except OSError as error:
            raise RepositoryError(f'cannot read glossary {path}') from error
        if current != expected:
            raise RepositoryError('glossary content changed; read the current definition source before writing')

    @staticmethod
    def _validate_identity(before: Mapping[str, GlossaryDocument], after: Mapping[str, GlossaryDocument]) -> None:
        adopted = {definition.id: definition for document in before.values() for definition in document.definitions}
        updated = {definition.id: definition for document in after.values() for definition in document.definitions}
        missing = sorted(set(adopted) - set(updated))
        if missing:
            raise ControlError(f'adopted IDs must remain present; retain prior definitions when using Replaces: {missing}')
        names = {}
        for definition in adopted.values():
            for spelling in (definition.canonical_term, *definition.aliases):
                names[' '.join(spelling.casefold().split())] = definition.id
        for definition in updated.values():
            if definition.id in adopted:
                continue
            for spelling in (definition.canonical_term, *definition.aliases):
                prior_id = names.get(' '.join(spelling.casefold().split()))
                if prior_id is not None and prior_id not in definition.replaces:
                    raise ControlError(f'new ID {definition.id} reuses an adopted term; Replaces must include {prior_id}')

    @contextmanager
    def _repository_write_lock(self):
        if (not isinstance(self.lock_timeout, (int, float)) or not math.isfinite(self.lock_timeout)
                or self.lock_timeout < 0):
            raise RepositoryError('glossary write lock timeout must be a finite non-negative number')
        common = self.common_dir()
        path = common / 'afk' / 'glossary-lifecycle' / 'write.lock'
        if path.is_symlink() or not path.resolve().is_relative_to(common):
            raise RepositoryError('glossary write lock must stay inside the Git common directory')
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = path.open('a+b')
        except OSError as error:
            raise RepositoryError('cannot open glossary write lock') from error
        locked = False
        try:
            try:
                stream.seek(0, os.SEEK_END)
                if stream.tell() == 0:
                    stream.write(b'\0')
                    stream.flush()
            except OSError as error:
                raise RepositoryError('cannot initialize glossary write lock') from error
            deadline = time.monotonic() + self.lock_timeout
            while True:
                try:
                    stream.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise RepositoryError('cannot acquire glossary write lock') from error
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RepositoryLockTimeout('glossary write lock acquisition timed out') from error
                    time.sleep(min(0.05, remaining))
            yield
        finally:
            try:
                if locked:
                    stream.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError as error:
                raise RepositoryError('cannot release glossary write lock') from error
            finally:
                stream.close()

    def write_definitions(self, snapshot: PinnedSnapshot, path: str, expected: bytes,
                          updated: GlossaryDocument) -> bytes:
        with self._repository_write_lock():
            return self._write_definitions(snapshot, path, expected, updated)

    def _write_definitions(self, snapshot: PinnedSnapshot, path: str, expected: bytes,
                           updated: GlossaryDocument) -> bytes:
        path = _path(path)
        controls = self.read_controls(snapshot)
        if path not in controls.ownership_paths:
            raise ControlError('definition path is not in the pinned ownership map')
        if not isinstance(expected, bytes):
            raise ControlError('expected glossary content must be bytes')
        target = self._definition_target(path)
        self._assert_head(snapshot)
        self._assert_expected(path, expected)
        serialized = self.codec.serialize(updated)
        prospective = {path: serialized}
        for other_path in controls.ownership_paths:
            if other_path == path:
                continue
            other = self.root / other_path
            if other.is_symlink() or other.resolve() != other.absolute():
                raise ControlError('definition path resolves through a symlink')
            try:
                prospective[other_path] = other.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError) as error:
                raise ControlError(f'cannot verify glossary {other_path} before writing') from error
        documents = self._parse_definitions(prospective)
        self._validate_identity(self.read_definitions(snapshot), documents)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=target.parent,
                                             prefix=f'.{target.name}.', delete=False) as stream:
                temporary = stream.name
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            self._assert_head(snapshot)
            self._assert_expected(path, expected)
            os.replace(temporary, target)
            temporary = None
            return serialized.encode('utf-8')
        except OSError as error:
            raise RepositoryError(f'cannot write glossary {path}') from error
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def _tracked_text(self, snapshot: PinnedSnapshot, scope: SearchScope, manifest: GlossaryManifest):
        scope_paths = tuple(_path(path) for path in scope.paths)
        exclusions = tuple(dict.fromkeys((*BUILTIN_EXCLUSIONS, *manifest.exclusions,
                                         *(_path(path) for path in scope.exclusions))))
        documents, excluded, eligible = [], [], []
        for path, (_, object_id) in sorted(self._files(snapshot.head).items()):
            if not any(_inside(path, root) for root in manifest.roots) or not any(_inside(path, root) for root in scope_paths):
                continue
            if any(_matches(path, pattern) for pattern in exclusions):
                excluded.append(path)
                continue
            eligible.append((path, object_id))
        blobs = self._batch_blobs(tuple(object_id for _, object_id in eligible))
        for (path, _), data in zip(eligible, blobs, strict=True):
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                excluded.append(path)
                continue
            if any(ord(character) < 32 and character not in '\n\r\t' for character in text):
                excluded.append(path)
                continue
            documents.append(TrackedText(path, text))
        return tuple(documents), exclusions, tuple(sorted(excluded))

    def _batch_blobs(self, object_ids: tuple[str, ...]) -> tuple[bytes, ...]:
        if not object_ids:
            return ()
        output = self._git('cat-file', '--batch', input=('\n'.join(object_ids) + '\n').encode('ascii'))
        offset = 0
        blobs = []
        for object_id in object_ids:
            end = output.find(b'\n', offset)
            if end < 0:
                raise RepositoryError('malformed Git batch output: missing object header')
            fields = output[offset:end].split(b' ')
            if (len(fields) != 3 or fields[0] != object_id.encode('ascii')
                    or fields[1] != b'blob' or not fields[2].isdigit()):
                raise RepositoryError('malformed Git batch output: unexpected object header')
            try:
                size = int(fields[2])
            except ValueError as error:
                raise RepositoryError('malformed Git batch output: invalid object size') from error
            start = end + 1
            offset = start + size
            if offset >= len(output) or output[offset:offset + 1] != b'\n':
                raise RepositoryError('malformed Git batch output: incomplete object content')
            blobs.append(output[start:offset])
            offset += 1
        if offset != len(output):
            raise RepositoryError('malformed Git batch output: trailing content')
        return tuple(blobs)

    def tracked_text(self, snapshot: PinnedSnapshot, scope: SearchScope) -> tuple[TrackedText, ...]:
        manifest = self.read_controls(snapshot).manifest
        if manifest is None:
            raise ControlError('glossary manifest is not enabled at the merge base')
        return self._tracked_text(snapshot, scope, manifest)[0]

    def semantic_candidates(self, snapshot: PinnedSnapshot, scope: SearchScope) -> SearchResult:
        controls = self.read_controls(snapshot)
        manifest = controls.manifest
        if manifest is None:
            raise ControlError('glossary manifest is not enabled at the merge base')
        documents, exclusions, excluded = self._tracked_text(snapshot, scope, manifest)
        source = {document.path: document.text.splitlines() for document in documents}
        definitions = self.read_definitions(snapshot)
        kept, counts = [], []
        truncated = False
        for area in sorted(set(scope.domain_areas)):
            selection = GlossaryDomainRules.resolve_routes((), (area,), manifest.routes,
                                                            {path: path for path in controls.ownership_paths})
            terms = tuple(definition for path in selection.glossary_paths for definition in definitions[path].definitions)
            allowed = {definition.id for definition in terms}
            try:
                raw = tuple(self.semantic_provider.rank(area, scope.terms, documents, terms))
                unique = {}
                for candidate in raw:
                    if not isinstance(candidate, SemanticCandidate) or candidate.area != area or candidate.term_id not in allowed:
                        raise ValueError('provider returned an unknown term or area')
                    if not isinstance(candidate.score, (int, float)) or not math.isfinite(candidate.score):
                        raise ValueError('provider returned an invalid score')
                    if not candidate.snippets:
                        raise ValueError('provider returned a candidate without evidence')
                    for snippet in candidate.snippets:
                        lines = source.get(snippet.path, ())
                        if (type(snippet.line) is not int or not 1 <= snippet.line <= len(lines)
                                or not snippet.text or snippet.text not in lines[snippet.line - 1]):
                            raise ValueError('provider evidence is outside tracked text')
                    previous = unique.get(candidate.term_id)
                    snippets = tuple(dict.fromkeys((*(previous.snippets if previous else ()), *candidate.snippets)))
                    unique[candidate.term_id] = SemanticCandidate(area, candidate.term_id,
                                                                 max(previous.score, candidate.score) if previous else candidate.score,
                                                                 snippets)
                ranked = sorted(unique.values(), key=lambda candidate: (-candidate.score, candidate.term_id))
                truncated |= len(ranked) > 20 or any(len(candidate.snippets) > 3 for candidate in ranked)
                counts.append((area, len(ranked), min(len(ranked), 20)))
                kept.extend(SemanticCandidate(area, candidate.term_id, candidate.score, candidate.snippets[:3]) for candidate in ranked[:20])
                method, model = self.semantic_provider.method, self.semantic_provider.model
                if not isinstance(method, str) or not method or not isinstance(model, str) or not model:
                    raise ValueError('provider must name its method and model')
            except Exception as error:
                raise SemanticProviderError(f'semantic provider failed for {area}: {error}') from error
        return SearchResult(tuple(kept), SearchEvidence(manifest.roots, exclusions, self.semantic_provider.method,
                                                        self.semantic_provider.model, truncated, excluded, tuple(counts)))
