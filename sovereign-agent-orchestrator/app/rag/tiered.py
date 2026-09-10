"""Routes RAG ingestion and retrieval across three isolated tier databases."""
import json

from sqlalchemy import text

from app.access import readable_tiers, resolve_upload_tier
from app.rag.service import RagService


class TieredRagService:
    def __init__(self, tier_urls, ollama_base_url, embedding_model, vision_model, embedding_dimensions=768):
        self.services = {
            tier: RagService(url, ollama_base_url, embedding_model, vision_model, embedding_dimensions)
            for tier, url in tier_urls.items()
        }

    def service_for(self, tier):
        return self.services[tier]

    def extract(self, path):
        return next(iter(self.services.values())).extract(path)

    async def ingest(self, path, identity, scope=None, metadata=None):
        tier = resolve_upload_tier(identity.get('role', 'lower'), scope)
        payload = {**(metadata or {}), 'owner_id': identity.get('user_id'), 'tenant_id': identity.get('tenant_id'), 'visibility_tier': tier}
        result = await self.services[tier].ingest(path, payload)
        result['tier'] = tier
        return result

    def ingest_sync(self, path, identity, scope=None, metadata=None):
        tier = resolve_upload_tier(identity.get('role', 'lower'), scope)
        payload = {**(metadata or {}), 'owner_id': identity.get('user_id'), 'tenant_id': identity.get('tenant_id'), 'visibility_tier': tier}
        result = self.services[tier].ingest_sync(path, payload)
        result['tier'] = tier
        return result

    async def search(self, query, identity, top_k=5, metadata=None, file_ids=None):
        results = []
        for tier in readable_tiers(identity.get('role', 'lower')):
            hits = await self.services[tier].search(query, top_k, metadata, file_ids)
            for hit in hits:
                hit['tier'] = tier
            results.extend(hits)
        return sorted(results, key=lambda item: item['score'], reverse=True)[:top_k]

    def search_sync(self, query, identity, top_k=5, metadata=None, file_ids=None):
        results = []
        for tier in readable_tiers(identity.get('role', 'lower')):
            hits = self.services[tier].search_sync(query, top_k, metadata, file_ids)
            for hit in hits:
                hit['tier'] = tier
            results.extend(hits)
        return sorted(results, key=lambda item: item['score'], reverse=True)[:top_k]

    async def evaluate(self, cases, identity, metadata=None, file_ids=None):
        results = []
        reciprocal_ranks = []
        hits = 0
        for case in cases:
            expected = set(case.get('expected_file_ids') or [])
            found = await self.search(case['query'], identity, case.get('top_k', 5), metadata, file_ids)
            found_ids = [item['metadata'].get('file_id') for item in found]
            rank = next((index + 1 for index, file_id in enumerate(found_ids) if file_id in expected), None)
            if rank:
                hits += 1
                reciprocal_ranks.append(1 / rank)
            else:
                reciprocal_ranks.append(0)
            results.append({'query': case['query'], 'expected_file_ids': list(expected), 'found_file_ids': found_ids, 'hit': bool(rank), 'rank': rank})
        total = len(cases)
        return {'cases': results, 'metrics': {'count': total, 'hit_rate': hits / total if total else 0, 'mrr': sum(reciprocal_ranks) / total if total else 0}}

    def list_sources(self, identity):
        sources = []
        for tier in readable_tiers(identity.get('role', 'lower')):
            with self.services[tier].engine.connect() as db:
                rows = db.execute(text('SELECT id,name,mime_type,checksum,metadata,created_at FROM rag_documents ORDER BY created_at DESC')).fetchall()
            for row in rows:
                metadata = row[4] if isinstance(row[4], dict) else json.loads(row[4] or '{}')
                sources.append({'document_id': row[0], 'name': row[1], 'mime_type': row[2], 'checksum': row[3], 'metadata': metadata, 'created_at': row[5], 'tier': tier})
        return sources

    def delete_document(self, file_id, tier=None):
        tiers = [tier] if tier else list(self.services.keys())
        return sum(self.services[t].delete_document(file_id) for t in tiers)
