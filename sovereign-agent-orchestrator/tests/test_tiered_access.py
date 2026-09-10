import asyncio
import tempfile
from pathlib import Path

import pytest

from app.access import allowed_scopes, readable_tiers, resolve_upload_tier
from app.rag.tiered import TieredRagService


def test_readable_tiers_cascade_downward():
    assert readable_tiers('lower') == ('lower',)
    assert readable_tiers('higher') == ('higher', 'lower')
    assert readable_tiers('admin') == ('admin', 'higher', 'lower')


def test_upload_scope_resolution():
    assert resolve_upload_tier('admin', 'private') == 'admin'
    assert resolve_upload_tier('admin', 'everyone') == 'lower'
    assert resolve_upload_tier('higher', 'restricted') == 'higher'
    assert resolve_upload_tier('higher', 'everyone') == 'lower'
    assert resolve_upload_tier('lower', None) == 'lower'
    assert allowed_scopes('lower') == ['private']


@pytest.fixture
def tiered_rag(tmp_path):
    urls = {tier: f"sqlite:///{tmp_path}/{tier}.db" for tier in ('admin', 'higher', 'lower')}
    return TieredRagService(urls, 'http://localhost:11434', 'nomic-embed-text', 'qwen2.5vl:3b')


def test_admin_private_upload_is_invisible_to_other_tiers(tmp_path, tiered_rag):
    admin_identity = {'role': 'admin', 'user_id': 'a1', 'tenant_id': 'default'}
    higher_identity = {'role': 'higher', 'user_id': 'h1', 'tenant_id': 'default'}
    lower_identity = {'role': 'lower', 'user_id': 'l1', 'tenant_id': 'default'}

    secret = tmp_path / 'secret.txt'
    secret.write_text('The secret launch code is ORION-7.')

    async def scenario():
        ingested = await tiered_rag.ingest(secret, admin_identity, 'private', {'file_id': 'f1'})
        assert ingested['tier'] == 'admin'

        admin_hits = await tiered_rag.search('secret launch code', admin_identity, 5)
        higher_hits = await tiered_rag.search('secret launch code', higher_identity, 5)
        lower_hits = await tiered_rag.search('secret launch code', lower_identity, 5)
        return admin_hits, higher_hits, lower_hits

    admin_hits, higher_hits, lower_hits = asyncio.run(scenario())
    assert any('ORION-7' in hit['content'] for hit in admin_hits)
    assert not any('ORION-7' in hit['content'] for hit in higher_hits)
    assert not any('ORION-7' in hit['content'] for hit in lower_hits)


def test_everyone_scope_upload_reaches_all_tiers(tmp_path, tiered_rag):
    admin_identity = {'role': 'admin', 'user_id': 'a1', 'tenant_id': 'default'}
    higher_identity = {'role': 'higher', 'user_id': 'h1', 'tenant_id': 'default'}
    lower_identity = {'role': 'lower', 'user_id': 'l1', 'tenant_id': 'default'}

    note = tmp_path / 'holiday.txt'
    note.write_text('Company holiday schedule is posted on the intranet.')

    async def scenario():
        ingested = await tiered_rag.ingest(note, admin_identity, 'everyone', {'file_id': 'f2'})
        assert ingested['tier'] == 'lower'
        return (
            await tiered_rag.search('holiday schedule', admin_identity, 5),
            await tiered_rag.search('holiday schedule', higher_identity, 5),
            await tiered_rag.search('holiday schedule', lower_identity, 5),
        )

    admin_hits, higher_hits, lower_hits = asyncio.run(scenario())
    assert any('holiday' in hit['content'] for hit in admin_hits)
    assert any('holiday' in hit['content'] for hit in higher_hits)
    assert any('holiday' in hit['content'] for hit in lower_hits)


def test_higher_restricted_upload_hidden_from_lower(tmp_path, tiered_rag):
    higher_identity = {'role': 'higher', 'user_id': 'h1', 'tenant_id': 'default'}
    lower_identity = {'role': 'lower', 'user_id': 'l1', 'tenant_id': 'default'}

    memo = tmp_path / 'memo.txt'
    memo.write_text('Budget figures for the regional rollout are confidential.')

    async def scenario():
        ingested = await tiered_rag.ingest(memo, higher_identity, 'restricted', {'file_id': 'f3'})
        assert ingested['tier'] == 'higher'
        return (
            await tiered_rag.search('budget figures', higher_identity, 5),
            await tiered_rag.search('budget figures', lower_identity, 5),
        )

    higher_hits, lower_hits = asyncio.run(scenario())
    assert any('confidential' in hit['content'] for hit in higher_hits)
    assert not any('confidential' in hit['content'] for hit in lower_hits)


def test_shared_upload_is_retrievable_by_a_non_owner(tmp_path, tiered_rag):
    """Tier membership alone must grant retrieval.

    Regression: the API used to pass an owner-scoped file_ids allowlist into tier
    search, so a lower user who owned no files got zero hits and every 'everyone'
    upload looked broken. Retrieval must not depend on file ownership.
    """
    admin_identity = {'role': 'admin', 'user_id': 'a1', 'tenant_id': 'default'}
    lower_identity = {'role': 'lower', 'user_id': 'l1', 'tenant_id': 'default'}

    handbook = tmp_path / 'handbook.txt'
    handbook.write_text('Expense reports must be filed within thirty days.')

    async def scenario():
        await tiered_rag.ingest(handbook, admin_identity, 'everyone', {'file_id': 'f4'})
        return await tiered_rag.search('expense reports', lower_identity, 5)

    hits = asyncio.run(scenario())
    assert any('thirty days' in hit['content'] for hit in hits)
    assert all(hit['metadata']['owner_id'] == 'a1' for hit in hits)


def test_empty_file_id_filter_matches_nothing(tmp_path, tiered_rag):
    """An empty allowlist means 'nothing', never 'everything'.

    Callers must pass None to search a whole tier. This pins the distinction so the
    owner-scoped-allowlist regression cannot silently return.
    """
    lower_identity = {'role': 'lower', 'user_id': 'l1', 'tenant_id': 'default'}

    notice = tmp_path / 'notice.txt'
    notice.write_text('Parking garage closes at midnight.')

    async def scenario():
        await tiered_rag.ingest(notice, lower_identity, None, {'file_id': 'f5'})
        return (
            await tiered_rag.search('parking garage', lower_identity, 5, None, []),
            await tiered_rag.search('parking garage', lower_identity, 5, None, None),
        )

    filtered, unfiltered = asyncio.run(scenario())
    assert filtered == []
    assert any('midnight' in hit['content'] for hit in unfiltered)


def test_unknown_or_multiple_roles_resolve_to_least_privilege():
    from app.auth import _resolve_role

    assert _resolve_role('admin') == 'admin'
    assert _resolve_role(['user', 'admin']) == 'admin'
    assert _resolve_role(['lower', 'higher']) == 'higher'
    assert _resolve_role('ADMIN') == 'admin'
    assert _resolve_role('superuser') == 'lower'
    assert _resolve_role(None) == 'lower'
    assert _resolve_role([]) == 'lower'


def test_every_resolved_role_is_a_valid_readable_role():
    """_resolve_role must never produce a value readable_tiers rejects."""
    from app.auth import _resolve_role

    for claim in ('admin', 'higher', 'lower', 'user', None, ['nonsense']):
        assert readable_tiers(_resolve_role(claim))
