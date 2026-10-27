"""Repository port checks against disposable Git repositories."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from glossary_lifecycle.repository import PinnedRepositoryAdapter


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout.decode().strip()


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')


@pytest.fixture
def history(tmp_path):
    remote = tmp_path / 'remote'
    remote.mkdir()
    git(remote, 'init', '-q', '-b', 'main')
    git(remote, 'config', 'user.name', 'Test')
    git(remote, 'config', 'user.email', 'test@example.invalid')
    write(remote, '.afk/config.yaml', 'schema: 1\nglossary:\n  manifest: team/manifest.json\n')
    manifest = {'version': 1, 'roots': ['src'], 'exclusions': ['src/private/**'], 'routes': [
        {'id': 'billing', 'path_patterns': ['src/**'], 'domain_areas': ['billing'],
         'glossary_path': 'billing/GLOSSARY.md', 'owner_chain': ['owner']}]}
    write(remote, 'team/manifest.json', json.dumps(manifest))
    write(remote, 'GLOSSARY-MAP.md', '# Glossaries\n- [Billing](./billing/GLOSSARY.md) — owns billing\n')
    write(remote, 'billing/GLOSSARY.md', '**Invoice**:\nA request for payment.\n_ID_: invoice\n_Owner_: billing/GLOSSARY.md\n')
    write(remote, 'src/billing.txt', 'billing invoice payment\n')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'base')
    clone = tmp_path / 'clone'
    subprocess.run(['git', 'clone', '-q', str(remote), str(clone)], check=True)
    git(clone, 'config', 'user.name', 'Test')
    git(clone, 'config', 'user.email', 'test@example.invalid')
    linked = tmp_path / 'linked'
    git(clone, 'worktree', 'add', '-qb', 'feature', str(linked))
    return remote, clone, linked


def test_linked_worktree_pins_ref_and_ignores_feature_controls(history):
    remote, clone, root = history
    base = git(root, 'rev-parse', 'HEAD')
    write(remote, 'target-change.txt', 'new target commit')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'target advances')
    write(root, '.afk/config.yaml', 'schema: 1\nglossary:\n  manifest: attacker.json\n')
    write(root, 'src/space and ü.txt', 'billing invoice')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'feature changes')
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    assert snapshot.target_commit == git(remote, 'rev-parse', 'HEAD')
    assert snapshot.merge_base == base
    controls = adapter.read_controls(snapshot)
    assert controls.manifest_path == 'team/manifest.json'
    assert controls.config['glossary']['manifest'] == 'team/manifest.json'
    assert controls.manifest.routes[0].owner_chain == ('owner',)
    assert adapter.changed_paths(snapshot) == ('.afk/config.yaml', 'src/space and ü.txt')
    assert adapter.common_dir() == (clone / '.git').resolve()
    assert adapter.read_definitions(snapshot)['billing/GLOSSARY.md'].definitions[0].id == 'invoice'


def test_manifest_cannot_route_outside_pinned_ownership_map(history):
    from glossary_lifecycle.repository import ControlError
    remote, _, root = history
    manifest = json.loads((remote / 'team/manifest.json').read_text())
    manifest['routes'][0]['glossary_path'] = 'other/GLOSSARY.md'
    write(remote, 'team/manifest.json', json.dumps(manifest))
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'invalid route')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    adapter = PinnedRepositoryAdapter(root)
    with pytest.raises(ControlError, match='unmapped'):
        adapter.read_controls(adapter.refresh('origin/main'))


def test_tracked_text_ranking_bounds(history):
    from glossary_lifecycle.repository import SearchScope
    remote, _, root = history
    definitions = '\n\n'.join(
        f'**Invoice {number}**:\nBilling payment item {number}.\n_ID_: invoice-{number:02}\n_Owner_: billing/GLOSSARY.md'
        for number in range(25))
    write(remote, 'billing/GLOSSARY.md', definitions)
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'definitions')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    write(root, 'src/ranked ü.txt', '\n'.join(f'billing invoice payment item {number}' for number in (24, 24, 24, 24, *range(5))))
    for path in ('src/fixtures/secret.txt', 'src/seeds/secret.txt', 'src/node_modules/secret.txt',
                 'src/generated/secret.txt', 'src/private/secret.txt', 'src/export.csv', 'src/run.log',
                 'outside/source.txt'):
        write(root, path, 'billing invoice payment secret')
    (root / 'src/binary.bin').write_bytes(b'\x00billing invoice')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'tracked sources')
    write(root, 'src/untracked.txt', 'billing invoice secret')
    write(root, 'src/ranked ü.txt', 'uncommitted secret')
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    scope = SearchScope(('billing',), ('src',), ('invoice',))
    result = adapter.semantic_candidates(snapshot, scope)
    assert len(result.candidates) == 20
    assert len({candidate.term_id for candidate in result.candidates}) == 20
    assert result.candidates[0].term_id == 'invoice-24'
    assert result.candidates[0].score > result.candidates[1].score
    assert {candidate.term_id for candidate in result.candidates[:6]} == {'invoice-24', *(f'invoice-{number:02}' for number in range(5))}
    assert result.candidates[5].score > result.candidates[6].score
    assert all(candidate.area == 'billing' and len(candidate.snippets) == 3 for candidate in result.candidates)
    assert all(snippet.path in ('src/billing.txt', 'src/ranked ü.txt') for candidate in result.candidates for snippet in candidate.snippets)
    assert result.evidence.truncated is True
    assert result.evidence.roots == ('src',)
    assert 'src/private/**' in result.evidence.exclusions
    assert result.evidence.method == 'token-overlap-v1'
    assert result.evidence.model == 'none'
    assert result == adapter.semantic_candidates(snapshot, scope)


def test_definition_write_round_trip(history):
    from dataclasses import replace
    from glossary_lifecycle.markdown import GlossaryDocument
    _, _, root = history
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    original = adapter.read_definitions(snapshot)['billing/GLOSSARY.md'].definitions[0]
    definitions = (replace(original, definition='A revised request for payment.'), *(
        replace(original, id=f'id-{number}', canonical_term=f'Term {number}', aliases=(f'Alias {number}',))
        for number in range(30)))
    adapter.write_definitions(snapshot, 'billing/GLOSSARY.md', (root / 'billing/GLOSSARY.md').read_bytes(), GlossaryDocument(definitions))
    assert adapter.codec.parse((root / 'billing/GLOSSARY.md').read_text()).definitions == definitions
    assert adapter.read_definitions(snapshot)['billing/GLOSSARY.md'].definitions == (original,)
    from glossary_lifecycle.repository import ControlError
    with pytest.raises(ControlError):
        adapter.write_definitions(snapshot, '../outside.md', b'', GlossaryDocument(definitions))


def test_exact_matches_are_unlimited_and_match_aliases(history):
    remote, _, root = history
    write(remote, 'billing/GLOSSARY.md', '\n\n'.join(
        f'**Term {number}**:\nA payment.\n_ID_: id-{number:02}\n_Owner_: billing/GLOSSARY.md\n_Also_: Alias {number}'
        for number in range(30)))
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'many exact terms')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    adapter = PinnedRepositoryAdapter(root)
    matches = adapter.exact_matches(adapter.refresh('origin/main'), tuple(f'ALIAS {number}' for number in range(30)))
    assert tuple(definition.id for definition in matches) == tuple(f'id-{number:02}' for number in range(30))


def test_tracked_text_ranking_bounds_provider_failure_is_typed(history):
    from glossary_lifecycle.repository import SearchScope, SemanticProviderError

    class Unavailable:
        method = 'unavailable'
        model = 'none'

        def rank(self, *args):
            raise OSError('offline')

    _, _, root = history
    adapter = PinnedRepositoryAdapter(root, Unavailable())
    with pytest.raises(SemanticProviderError, match='offline'):
        adapter.semantic_candidates(adapter.refresh('origin/main'), SearchScope(('billing',), ('src',)))


def test_unverifiable_target_is_typed(history):
    from glossary_lifecycle.repository import RepositoryError
    _, _, root = history
    with pytest.raises(RepositoryError):
        PinnedRepositoryAdapter(root).refresh('origin/missing')


def test_refresh_isolated_from_another_fetch(history, monkeypatch):
    remote, _, root = history
    expected = git(remote, 'rev-parse', 'HEAD')
    git(remote, 'checkout', '-qb', 'other')
    write(remote, 'other.txt', 'another target')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'other branch')
    original_run = subprocess.run

    def with_competing_fetch(args, **kwargs):
        result = original_run(args, **kwargs)
        if 'fetch' in args and 'refs/heads/main' in ' '.join(args):
            original_run(['git', '-C', str(root), 'fetch', 'origin', 'other'], check=True, capture_output=True)
        return result

    monkeypatch.setattr(subprocess, 'run', with_competing_fetch)
    assert PinnedRepositoryAdapter(root).refresh('origin/main').target_commit == expected


@pytest.mark.parametrize('change', ['unknown-field', 'version', 'empty-owner', 'unreachable-route', 'absolute-root'])
def test_strict_manifest_rejects_invalid_controls(history, change):
    from glossary_lifecycle.repository import ControlError
    remote, _, root = history
    manifest = json.loads((remote / 'team/manifest.json').read_text())
    if change == 'unknown-field':
        manifest['unknown'] = True
    elif change == 'version':
        manifest['version'] = True
    elif change == 'empty-owner':
        manifest['routes'][0]['owner_chain'] = []
    elif change == 'unreachable-route':
        manifest['routes'][0]['path_patterns'] = []
        manifest['routes'][0]['domain_areas'] = []
    elif change == 'absolute-root':
        manifest['roots'] = ['/secret']
    write(remote, 'team/manifest.json', json.dumps(manifest))
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'invalid controls')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    adapter = PinnedRepositoryAdapter(root)
    with pytest.raises(ControlError):
        adapter.read_controls(adapter.refresh('origin/main'))


def test_write_preserves_replacement_links_in_other_glossaries(history):
    from glossary_lifecycle.markdown import GlossaryDocument, UnresolvedReplacementError
    remote, _, root = history
    write(remote, 'GLOSSARY-MAP.md', '- [Billing](billing/GLOSSARY.md)\n- [Shared](shared/GLOSSARY.md)\n')
    write(remote, 'shared/GLOSSARY.md', '**Payment**:\nA transfer.\n_ID_: payment\n_Owner_: shared/GLOSSARY.md\n_Replaces_: invoice\n')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'replacement in another glossary')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    adapter = PinnedRepositoryAdapter(root)
    before = (root / 'billing/GLOSSARY.md').read_bytes()
    with pytest.raises(UnresolvedReplacementError):
        adapter.write_definitions(adapter.refresh('origin/main'), 'billing/GLOSSARY.md', before, GlossaryDocument(()))
    assert (root / 'billing/GLOSSARY.md').read_bytes() == before


@pytest.mark.parametrize('link', ['GLOSSARY.md', './GLOSSARY.md'])
def test_root_glossary_ownership_links(history, link):
    remote, _, root = history
    manifest = json.loads((remote / 'team/manifest.json').read_text())
    manifest['routes'][0]['glossary_path'] = 'GLOSSARY.md'
    write(remote, 'team/manifest.json', json.dumps(manifest))
    write(remote, 'GLOSSARY-MAP.md', f'- [Shared]({link})\n')
    write(remote, 'GLOSSARY.md', '**Invoice**:\nA request.\n_ID_: invoice\n_Owner_: GLOSSARY.md\n')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'root glossary')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    assert adapter.read_controls(snapshot).ownership_paths == ('GLOSSARY.md',)
    assert adapter.read_definitions(snapshot)['GLOSSARY.md'].definitions[0].owner == 'GLOSSARY.md'


@pytest.mark.parametrize('owner', ['attacker', 'other/GLOSSARY.md'])
def test_read_rejects_owner_outside_owning_glossary(history, owner):
    from glossary_lifecycle.repository import ControlError
    remote, _, root = history
    write(remote, 'billing/GLOSSARY.md', f'**Invoice**:\nA request.\n_ID_: invoice\n_Owner_: {owner}\n')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'invalid owner')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    adapter = PinnedRepositoryAdapter(root)
    with pytest.raises(ControlError, match='Owner'):
        adapter.read_definitions(adapter.refresh('origin/main'))


def test_write_rejects_owner_outside_pinned_ownership(history):
    from dataclasses import replace
    from glossary_lifecycle.markdown import GlossaryDocument
    from glossary_lifecycle.repository import ControlError
    _, _, root = history
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    document = adapter.read_definitions(snapshot)['billing/GLOSSARY.md']
    changed = GlossaryDocument((replace(document.definitions[0], owner='attacker'),))
    before = (root / 'billing/GLOSSARY.md').read_bytes()
    write(root, 'GLOSSARY-MAP.md', '- [Attacker](billing/GLOSSARY.md)\n')
    with pytest.raises(ControlError, match='Owner'):
        adapter.write_definitions(snapshot, 'billing/GLOSSARY.md', before, changed)
    assert (root / 'billing/GLOSSARY.md').read_bytes() == before


@pytest.mark.parametrize('retain_original', [False, True])
def test_write_rejects_silent_adopted_id_change(history, retain_original):
    from dataclasses import replace
    from glossary_lifecycle.markdown import GlossaryDocument
    from glossary_lifecycle.repository import ControlError
    _, _, root = history
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    original = adapter.read_definitions(snapshot)['billing/GLOSSARY.md'].definitions[0]
    before = (root / 'billing/GLOSSARY.md').read_bytes()
    revised = replace(original, id='new-invoice')
    definitions = (replace(original, canonical_term='Legacy invoice'), revised) if retain_original else (revised,)
    with pytest.raises(ControlError, match='ID|Replaces'):
        adapter.write_definitions(snapshot, 'billing/GLOSSARY.md', before, GlossaryDocument(definitions))
    assert (root / 'billing/GLOSSARY.md').read_bytes() == before


def test_write_accepts_explicit_replacement_with_retained_prior_id(history):
    from dataclasses import replace
    from glossary_lifecycle.markdown import GlossaryDocument
    _, _, root = history
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    original = adapter.read_definitions(snapshot)['billing/GLOSSARY.md'].definitions[0]
    definitions = GlossaryDocument((replace(original, canonical_term='Legacy invoice'),
                                   replace(original, id='new-invoice', replaces=(original.id,))))
    adapter.write_definitions(snapshot, 'billing/GLOSSARY.md', (root / 'billing/GLOSSARY.md').read_bytes(), definitions)
    assert adapter.codec.parse((root / 'billing/GLOSSARY.md').read_text()).definitions == definitions.definitions


def test_public_definition_source_supports_sequential_writes_and_rejects_stale_bytes(history):
    from dataclasses import replace
    from glossary_lifecycle.markdown import GlossaryDocument
    from glossary_lifecycle.repository import RepositoryError
    _, _, root = history
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    source = adapter.read_definition_source(snapshot, 'billing/GLOSSARY.md')
    first = GlossaryDocument((replace(source.document.definitions[0], definition='First revised meaning.'),))
    first_bytes = adapter.write_definitions(snapshot, source.path, source.raw_bytes, first)
    assert first_bytes == (root / source.path).read_bytes()
    second = GlossaryDocument((replace(first.definitions[0], definition='Second revised meaning.'),))
    second_bytes = adapter.write_definitions(snapshot, source.path, first_bytes, second)
    assert second_bytes == (root / source.path).read_bytes()
    with pytest.raises(RepositoryError, match='content changed'):
        adapter.write_definitions(snapshot, source.path, first_bytes, first)
    assert (root / source.path).read_bytes() == second_bytes


def test_write_preserves_concurrent_edits_before_replace(history, monkeypatch):
    import os
    from dataclasses import replace
    from glossary_lifecycle.markdown import GlossaryDocument
    from glossary_lifecycle.repository import RepositoryError
    _, _, root = history
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    source = adapter.read_definition_source(snapshot, 'billing/GLOSSARY.md')
    updated = GlossaryDocument((replace(source.document.definitions[0], definition='Updated meaning.'),))
    concurrent = source.raw_bytes + b'\nConcurrent author note.\n'
    original_fsync = os.fsync

    def concurrent_edit(fd):
        original_fsync(fd)
        (root / source.path).write_bytes(concurrent)

    monkeypatch.setattr(os, 'fsync', concurrent_edit)
    with pytest.raises(RepositoryError, match='content changed'):
        adapter.write_definitions(snapshot, source.path, source.raw_bytes, updated)
    assert (root / source.path).read_bytes() == concurrent
    assert list((root / 'billing').glob('.GLOSSARY.md.*')) == []


def test_committed_null_glossary_disables_manifest(history):
    remote, _, root = history
    write(remote, '.afk/config.yaml', 'schema: 1\nglossary: null\n')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'disable glossary')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    assert adapter.read_controls(snapshot).manifest is None
    assert dict(adapter.read_definitions(snapshot)) == {}


@pytest.mark.parametrize(('second_path', 'linked_worktree'), [
    ('billing/GLOSSARY.md', False), ('shared/GLOSSARY.md', False), ('billing/GLOSSARY.md', True),
])
def test_repository_lock_serializes_writers_and_cross_glossary_identity(history, monkeypatch, second_path, linked_worktree):
    import os
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import replace
    from glossary_lifecycle.markdown import DuplicateTermIdError, GlossaryDocument
    from glossary_lifecycle.repository import RepositoryError

    remote, clone, root = history
    write(remote, 'GLOSSARY-MAP.md', '- [Billing](billing/GLOSSARY.md)\n- [Shared](shared/GLOSSARY.md)\n')
    write(remote, 'shared/GLOSSARY.md', '**Credit**:\nA credit amount.\n_ID_: credit\n_Owner_: shared/GLOSSARY.md\n')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'shared glossary')
    git(root, 'fetch', 'origin')
    git(root, 'reset', '--hard', 'origin/main')
    git(clone, 'reset', '--hard', 'origin/main')
    first = PinnedRepositoryAdapter(root)
    second_root = clone if linked_worktree else root
    second = PinnedRepositoryAdapter(second_root, lock_timeout=0.2)
    snapshot = first.refresh('origin/main')
    source_a = first.read_definition_source(snapshot, 'billing/GLOSSARY.md')
    source_b = second.read_definition_source(snapshot, second_path)
    update_a = GlossaryDocument((*source_a.document.definitions,
                                 replace(source_a.document.definitions[0], id='adjustment', canonical_term='Billing adjustment')))
    update_b = GlossaryDocument((*source_b.document.definitions,
                                 replace(source_b.document.definitions[0], id='adjustment', canonical_term='Shared adjustment')))
    replacing = threading.Event()
    release = threading.Event()
    original_replace = os.replace

    def pause_first_replace(source, target):
        if threading.current_thread().name.startswith('first-writer'):
            replacing.set()
            assert release.wait(15), 'test did not release first writer'
        return original_replace(source, target)

    monkeypatch.setattr(os, 'replace', pause_first_replace)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='first-writer') as executor:
        future = executor.submit(first.write_definitions, snapshot, source_a.path, source_a.raw_bytes, update_a)
        try:
            assert replacing.wait(15), 'first writer did not reach replacement'
            with pytest.raises(RepositoryError, match='lock.*timed out'):
                second.write_definitions(snapshot, source_b.path, source_b.raw_bytes, update_b)
        finally:
            release.set()
        written = future.result(timeout=15)
    assert (root / source_a.path).read_bytes() == written
    assert first.common_dir() == second.common_dir() == (clone / '.git').resolve()
    assert (first.common_dir() / 'afk/glossary-lifecycle/write.lock').is_file()
    if linked_worktree:
        assert (second_root / source_b.path).read_bytes() == source_b.raw_bytes
        second.write_definitions(snapshot, source_b.path, source_b.raw_bytes, update_b)
        assert (root / source_a.path).read_bytes() == written
    elif source_a.path == source_b.path:
        with pytest.raises(RepositoryError, match='content changed'):
            second.write_definitions(snapshot, source_b.path, source_b.raw_bytes, update_b)
    else:
        assert (root / source_b.path).read_bytes() == source_b.raw_bytes
        with pytest.raises(DuplicateTermIdError):
            second.write_definitions(snapshot, source_b.path, source_b.raw_bytes, update_b)
        assert (root / source_b.path).read_bytes() == source_b.raw_bytes


@pytest.mark.parametrize('operation', ['files', 'changed_paths'])
def test_git_filename_decode_errors_are_typed(tmp_path, monkeypatch, operation):
    from glossary_lifecycle.repository import PinnedSnapshot, RepositoryError
    adapter = PinnedRepositoryAdapter(tmp_path)
    snapshot = PinnedSnapshot('origin/main', 'a' * 40, 'a' * 40, 'b' * 40)
    raw_path = b'src/invalid-\xff.txt\0'
    raw = b'100644 blob ' + b'c' * 40 + b'\t' + raw_path if operation == 'files' else raw_path
    monkeypatch.setattr(adapter, '_git', lambda *args: raw)
    with pytest.raises(RepositoryError, match='filename.*UTF-8'):
        if operation == 'files':
            adapter._files(snapshot.head)
        else:
            adapter.changed_paths(snapshot)


@pytest.mark.parametrize('payload', [
    pytest.param(b'not a tree record\0', id='missing-separator'),
    pytest.param(b'100644 blob\tsource.txt\0', id='missing-object-id'),
    pytest.param(b'100644 bl\xffb ' + b'a' * 40 + b'\tsource.txt\0', id='non-ascii-metadata'),
    pytest.param(b'100644 blob invalid\tsource.txt\0', id='invalid-object-id'),
    pytest.param(b'100644 blob ' + b'a' * 40 + b'\tsource.txt', id='missing-terminator'),
    pytest.param(b'100644 blob ' + b'a' * 40 + b'\t\0', id='empty-filename'),
])
def test_malformed_tree_output_is_typed(tmp_path, monkeypatch, payload):
    from glossary_lifecycle.repository import RepositoryError
    adapter = PinnedRepositoryAdapter(tmp_path)
    monkeypatch.setattr(adapter, '_git', lambda *args: payload)
    with pytest.raises(RepositoryError, match='malformed Git tree output'):
        adapter._files('a' * 40)


def test_tracked_text_reads_many_objects_in_one_batch(history, monkeypatch):
    from glossary_lifecycle.repository import SearchScope
    _, _, root = history
    expected = {'src/billing.txt': 'billing invoice payment\n'}
    for number in range(24):
        path = f'src/file-{number:02}.txt'
        expected[path] = f'billing record {number}\nwith a second line\n'
        write(root, path, expected[path])
    write(root, 'src/empty.txt', '')
    expected['src/empty.txt'] = ''
    write(root, 'src/repeated.txt', expected['src/file-00.txt'])
    expected['src/repeated.txt'] = expected['src/file-00.txt']
    write(root, 'src/private/excluded.txt', 'excluded content')
    (root / 'src/binary.bin').write_bytes(b'\x00binary\ncontent')
    (root / 'src/non-utf8.bin').write_bytes(b'\xff\xfe')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'many tracked sources')
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    calls = []
    original_run = subprocess.run

    def record_calls(args, **kwargs):
        if 'cat-file' in args:
            calls.append((tuple(args), kwargs.get('input')))
        return original_run(args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', record_calls)
    documents = adapter.tracked_text(snapshot, SearchScope(('billing',), ('src',)))
    assert {document.path: document.text for document in documents} == expected
    assert tuple(document.path for document in documents) == tuple(sorted(expected))
    batches = [call for call in calls if '--batch' in call[0]]
    assert len(batches) == 1
    assert len(batches[0][1].splitlines()) == len(expected) + 2
    assert len(calls) == 3, 'only map, manifest, and the batch should read blobs'


@pytest.mark.parametrize('payload', [
    pytest.param(b'', id='missing-header'),
    pytest.param(b'b' * 40 + b' blob 1\nx\n', id='wrong-object'),
    pytest.param(b'a' * 40 + b' missing\n', id='missing-object'),
    pytest.param(b'a' * 40 + b' tree 1\nx\n', id='wrong-type'),
    pytest.param(b'a' * 40 + b' blob -1\nx\n', id='invalid-size'),
    pytest.param(b'a' * 40 + b' blob 8\nx\n', id='truncated-content'),
    pytest.param(b'a' * 40 + b' blob 1\nx!', id='invalid-delimiter'),
    pytest.param(b'a' * 40 + b' blob 1\nx\nextra', id='trailing-content'),
])
def test_malformed_batch_output_is_typed(tmp_path, monkeypatch, payload):
    from glossary_lifecycle.repository import RepositoryError
    adapter = PinnedRepositoryAdapter(tmp_path)
    monkeypatch.setattr(adapter, '_git', lambda *args, **kwargs: payload)
    with pytest.raises(RepositoryError, match='malformed Git batch output'):
        adapter._batch_blobs(('a' * 40,))


def test_tracked_text_propagates_malformed_batch_error(history, monkeypatch):
    from glossary_lifecycle.repository import RepositoryError, SearchScope
    _, _, root = history
    adapter = PinnedRepositoryAdapter(root)
    snapshot = adapter.refresh('origin/main')
    original_run = subprocess.run

    def malformed_reply(args, **kwargs):
        if 'cat-file' in args and '--batch' in args:
            return subprocess.CompletedProcess(args, 0, stdout=b'not a batch header\n', stderr=b'')
        return original_run(args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', malformed_reply)
    with pytest.raises(RepositoryError, match='malformed Git batch output'):
        adapter.tracked_text(snapshot, SearchScope(('billing',), ('src',)))
