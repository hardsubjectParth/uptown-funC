import csv
import base64
import hashlib
import json
import math
import mimetypes
import re
import uuid
from pathlib import Path

import httpx
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import create_engine, text


SUPPORTED_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.csv', '.xlsx', '.xlsm', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}


class RagService:
    """Local document index with durable chunks and Ollama embeddings."""

    def __init__(self, database_url='sqlite:///./orchestrator.db', llm_base_url='http://localhost:8080/v1', embedding_model='embedder', vision_model='vision', api_key='', rerank_model=None, rerank_overfetch=4):
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)
        self.is_postgres = database_url.startswith('postgresql')
        base = llm_base_url.rstrip('/')
        self.embed_url = base + '/embeddings'
        self.vision_url = base + '/chat/completions'
        self.rerank_url = base + '/rerank'
        self.embedding_model = embedding_model
        self.vision_model = vision_model
        # When set, retrieval overfetches by `rerank_overfetch` and rescores the
        # candidates with a cross-encoder, which is far more accurate than
        # embedding cosine alone. Falls back silently to the embedding order.
        self.rerank_model = rerank_model
        self.rerank_overfetch = max(1, rerank_overfetch)
        self._headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
        with self.engine.begin() as db:
            db.execute(text('''
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, mime_type TEXT,
                    checksum TEXT UNIQUE NOT NULL, metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )'''))
            db.execute(text('''
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL, content TEXT NOT NULL,
                    embedding TEXT, metadata TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES rag_documents(id)
                )'''))
            db.execute(text('CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id)'))

    def extract(self, path):
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix in {'.txt', '.md'}:
            return path.read_text(errors='ignore')
        if suffix == '.pdf':
            pages = []
            for index, page in enumerate(PdfReader(str(path)).pages, 1):
                try:
                    content = page.extract_text(extraction_mode='layout') or ''
                except TypeError:
                    content = page.extract_text() or ''
                pages.append(f'[Page {index}]\n{content}')
            return '\n'.join(pages)
        if suffix == '.docx':
            return '\n'.join(p.text for p in Document(str(path)).paragraphs)
        if suffix in {'.xlsx', '.xlsm'}:
            workbook = load_workbook(path, read_only=True, data_only=True)
            rows = []
            for sheet in workbook.worksheets:
                rows.append(f'[Sheet: {sheet.title}]')
                rows.extend(' | '.join('' if value is None else str(value) for value in row) for row in sheet.iter_rows(values_only=True))
            return '\n'.join(rows)
        if suffix == '.csv':
            with path.open(newline='', encoding='utf-8-sig', errors='ignore') as stream:
                return '\n'.join(' | '.join(row) for row in csv.reader(stream))
        if suffix in {'.png', '.jpg', '.jpeg', '.tiff', '.bmp'}:
            return self._ocr(path)
        raise ValueError(f'UNSUPPORTED_DOCUMENT_TYPE: {suffix}')

    @staticmethod
    def _ocr(path):
        try:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(path))
        except Exception as exc:
            return f'[OCR unavailable: {exc}]'

    @staticmethod
    def _chunks(text, size=1200, overlap=150):
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return []
        result = []
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            result.append(text[start:end])
            if end == len(text):
                break
            start = end - overlap
        return result

    async def _embed(self, text):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(self.embed_url, json={'model': self.embedding_model, 'input': text}, headers=self._headers)
                response.raise_for_status()
                return response.json()['data'][0]['embedding']
        except Exception:
            return None

    async def ingest(self, path, metadata=None, name=None):
        """Index a document.

        `name` is the human-facing document name used in citations. The upload
        store prefixes files on disk with a UUID to avoid collisions, and that
        prefix must not leak into artifacts people read.
        """
        path = Path(path)
        display_name = name or path.name
        data = path.read_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        metadata = metadata or {}
        with self.engine.connect() as db:
            existing = db.execute(text('SELECT id FROM rag_documents WHERE checksum=:checksum'), {'checksum': checksum}).first()
            if existing:
                return {'document_id': existing[0], 'name': display_name, 'chunks': 0, 'existing': True}
        extracted_text = self.extract(path)
        if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tiff', '.bmp'} and extracted_text.startswith('[OCR unavailable:'):
            extracted_text = await self._vision_extract(path)
        chunks = self._chunks(extracted_text)
        document_id = str(uuid.uuid4())
        vectors = [await self._embed(chunk) for chunk in chunks]
        with self.engine.begin() as db:
            db.execute(text('INSERT INTO rag_documents(id,name,mime_type,checksum,metadata) VALUES(:id,:name,:mime,:checksum,' + ('CAST(:metadata AS JSONB)' if self.is_postgres else ':metadata') + ')'), {'id': document_id, 'name': display_name, 'mime': metadata.get('mime_type'), 'checksum': checksum, 'metadata': json.dumps(metadata)})
            for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                embedding = json.dumps(vector) if vector else None
                db.execute(text('INSERT INTO rag_chunks(id,document_id,chunk_index,content,embedding,metadata) VALUES(:id,:document,:index,:content,' + ('CAST(:embedding AS vector)' if self.is_postgres else ':embedding') + ',' + ('CAST(:metadata AS JSONB)' if self.is_postgres else ':metadata') + ')'), {'id': str(uuid.uuid4()), 'document': document_id, 'index': index, 'content': chunk, 'embedding': embedding, 'metadata': json.dumps(metadata)})
        return {'document_id': document_id, 'name': display_name, 'chunks': len(chunks), 'embedded': sum(vector is not None for vector in vectors)}

    def ingest_sync(self, path, metadata=None):
        """Index a document without network access for synchronous tools."""
        path = Path(path)
        data = path.read_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        metadata = metadata or {}
        with self.engine.connect() as db:
            existing = db.execute(text('SELECT id FROM rag_documents WHERE checksum=:checksum'), {'checksum': checksum}).first()
            if existing:
                return {'document_id': existing[0], 'name': path.name, 'chunks': 0, 'embedded': 0, 'existing': True}
        extracted_text = self.extract(path)
        chunks = self._chunks(extracted_text)
        document_id = str(uuid.uuid4())
        with self.engine.begin() as db:
            db.execute(text('INSERT INTO rag_documents(id,name,mime_type,checksum,metadata) VALUES(:id,:name,:mime,:checksum,' + ('CAST(:metadata AS JSONB)' if self.is_postgres else ':metadata') + ')'), {'id': document_id, 'name': path.name, 'mime': metadata.get('mime_type'), 'checksum': checksum, 'metadata': json.dumps(metadata)})
            for index, chunk in enumerate(chunks):
                db.execute(text('INSERT INTO rag_chunks(id,document_id,chunk_index,content,embedding,metadata) VALUES(:id,:document,:index,:content,NULL,' + ('CAST(:metadata AS JSONB)' if self.is_postgres else ':metadata') + ')'), {'id': str(uuid.uuid4()), 'document': document_id, 'index': index, 'content': chunk, 'metadata': json.dumps(metadata)})
        return {'document_id': document_id, 'name': path.name, 'chunks': len(chunks), 'embedded': 0}

    async def _vision_extract(self, path):
        try:
            encoded = base64.b64encode(path.read_bytes()).decode('ascii')
            mime = mimetypes.guess_type(str(path))[0] or 'image/png'
            payload = {'model': self.vision_model, 'stream': False, 'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': 'Transcribe all visible text exactly. Include handwritten text where legible. Return only the transcription.'},
                {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{encoded}'}},
            ]}]}
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(self.vision_url, json=payload, headers=self._headers)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content']
        except Exception as exc:
            return f'[OCR unavailable: install Tesseract or configure a local vision model: {exc}]'

    async def search(self, query, top_k=5, metadata=None):
        query_vector = await self._embed(query)
        if not self.rerank_model:
            return self._search_rows(query, query_vector, top_k, metadata)
        # Overfetch, then let the cross-encoder pick the real top_k.
        candidates = self._search_rows(query, query_vector, top_k * self.rerank_overfetch, metadata)
        return await self._rerank(query, candidates, top_k)

    async def _rerank(self, query, candidates, top_k):
        """Rescore candidates with the reranker model, preserving order on failure."""
        if len(candidates) <= 1:
            return candidates[:top_k]
        try:
            payload = {'model': self.rerank_model, 'query': query,
                       'documents': [c['content'] for c in candidates]}
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self.rerank_url, json=payload, headers=self._headers)
                response.raise_for_status()
                results = response.json()['results']
        except Exception:
            return candidates[:top_k]
        ranked = []
        for item in sorted(results, key=lambda r: -r['relevance_score']):
            hit = dict(candidates[item['index']])
            hit['retrieval_score'] = hit['score']       # keep the embedding score
            # Cross-encoders return raw logits (bge-reranker emits negatives).
            # Squash to 0-1 so the score reads consistently with cosine scores
            # in citations. Monotonic, so ordering is unchanged.
            hit['score'] = round(1.0 / (1.0 + math.exp(-item['relevance_score'])), 6)
            hit['rerank_logit'] = round(item['relevance_score'], 4)
            hit['reranked'] = True
            ranked.append(hit)
        return ranked[:top_k]

    def search_sync(self, query, top_k=5, metadata=None):
        """Search without network access for the synchronous tool dispatcher."""
        return self._search_rows(query, None, top_k, metadata)

    def _search_rows(self, query, query_vector, top_k, metadata):
        with self.engine.connect() as db:
            rows = db.execute(text('SELECT c.id,c.content,c.embedding,c.metadata,d.name FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id')).fetchall()
        scored = []
        query_words = set(re.findall(r'\w+', query.lower()))
        for chunk_id, content, embedding, chunk_metadata, name in rows:
            item_metadata = json.loads(chunk_metadata or '{}')
            if metadata and any(item_metadata.get(key) != value for key, value in metadata.items()):
                continue
            score = self._cosine(query_vector, json.loads(embedding)) if query_vector and embedding else self._lexical(query_words, content)
            scored.append({'chunk_id': chunk_id, 'source': name, 'content': content, 'score': round(score, 6), 'metadata': item_metadata})
        return sorted(scored, key=lambda item: item['score'], reverse=True)[:top_k]

    @staticmethod
    def _lexical(words, content):
        tokens = set(re.findall(r'\w+', content.lower()))
        return len(words & tokens) / max(len(words), 1)

    @staticmethod
    def _cosine(left, right):
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
        return dot / norm if norm else 0.0