import csv
import json
import os
import re
import sqlite3
import smtplib
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from docx import Document
from openpyxl import load_workbook
from sqlalchemy import text

from app.rag.report import write_knowledge_transfer_report

DEFAULT_TOOL_IDENTITY = {'role': 'lower', 'tenant_id': 'default', 'user_id': 'tool-user'}


class ToolRegistry:
    def __init__(self, workspace, rag=None):
        self.workspace = workspace
        self.rag = rag

    def names(self):
        return [
            'search_documents',
            'read_file',
            'write_file',
            'generate_docx',
            'ingest_document',
            'list_sources',
            'export_report',
            'spreadsheet_profile',
            'redact_pii',
            'extract_tables',
            'ocr_document',
            'search_db',
            'send_email',
            'create_calendar_event',
        ]

    def execute(self, jid, name, args):
        if name == 'search_documents':
            q = args.get('query', '').lower()
            if self.rag:
                identity = args.get('identity') or DEFAULT_TOOL_IDENTITY
                hits = self.rag.search_sync(q, identity, args.get('top_k', 5), args.get('metadata'), args.get('file_ids'))
                return {
                    'hits': hits,
                    'count': len(hits),
                    'sources': [{'name': hit['source'], 'source': hit['source']} for hit in hits],
                }
            hits = []

            input_root = self.workspace.root / jid / 'input'

            if input_root.exists():
                for p in input_root.rglob('*'):
                    if (
                        p.is_file()
                        and p.suffix.lower() in {'.txt', '.md'}
                    ):
                        t = p.read_text(errors='ignore')

                        if q in t.lower() or not q:
                            hits.append({
                                'name': p.name,
                                'snippet': t[:500],
                                'source': str(
                                    p.relative_to(
                                        self.workspace.root / jid
                                    )
                                ),
                            })

            return {
                'hits': hits,
                'count': len(hits),
                'sources': [
                    {
                        'name': h['name'],
                        'source': h['source'],
                    }
                    for h in hits
                ],
            }

        if name == 'ingest_document':
            if not self.rag:
                raise ValueError('RAG_NOT_CONFIGURED')
            identity = args.get('identity') or DEFAULT_TOOL_IDENTITY
            path = self.workspace.safe(jid, args['path'])
            return self.rag.ingest_sync(path, identity, args.get('scope'), {'job_id': jid, **(args.get('metadata') or {})})

        if name == 'list_sources':
            if not self.rag:
                raise ValueError('RAG_NOT_CONFIGURED')
            identity = args.get('identity') or DEFAULT_TOOL_IDENTITY
            return {'sources': self.rag.list_sources(identity)}

        if name == 'export_report':
            paths = [self.workspace.safe(jid, value) for value in args.get('paths', [])]
            if not paths:
                paths = [path for path in (self.workspace.root / jid / 'input').rglob('*') if path.is_file()]
            result = write_knowledge_transfer_report(paths, self.workspace.safe(jid, 'output', True), self.rag.extract if self.rag else lambda path: path.read_text(errors='ignore'))
            return {'path': str(Path(result['docx']).relative_to(self.workspace.root / jid)), 'json_path': str(Path(result['json']).relative_to(self.workspace.root / jid)), 'sources': len(paths)}

        if name == 'spreadsheet_profile':
            path = self.workspace.safe(jid, args['path'])
            workbook = load_workbook(path, read_only=True, data_only=True)
            sheets = []
            for sheet in workbook.worksheets:
                rows = list(sheet.iter_rows(min_row=1, max_row=2, values_only=True))
                sheets.append({'name': sheet.title, 'rows': max(sheet.max_row - 1, 0), 'columns': sheet.max_column, 'headers': [str(value) if value is not None else '' for value in rows[0]] if rows else []})
            return {'file': path.name, 'sheets': sheets}

        if name == 'redact_pii':
            path = self.workspace.safe(jid, args['path'])
            content = path.read_text(errors='ignore')
            email_matches = re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', content)
            redacted = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[REDACTED_EMAIL]', content)
            phone_matches = re.findall(r'(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)', redacted)
            redacted = re.sub(r'(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)', '[REDACTED_PHONE]', redacted)
            output = self.workspace.safe(jid, args.get('output', f'working/{path.stem}_redacted{path.suffix}'), True)
            output.write_text(redacted, encoding='utf-8')
            return {'path': str(output.relative_to(self.workspace.root / jid)), 'redactions': len(email_matches) + len(phone_matches)}

        if name == 'extract_tables':
            path = self.workspace.safe(jid, args['path'])
            tables = []
            if path.suffix.lower() in {'.xlsx', '.xlsm'}:
                workbook = load_workbook(path, read_only=True, data_only=True)
                for sheet in workbook.worksheets:
                    tables.append({'name': sheet.title, 'rows': [[value for value in row] for row in sheet.iter_rows(values_only=True)]})
            elif path.suffix.lower() == '.csv':
                with path.open(newline='', encoding='utf-8-sig', errors='ignore') as stream:
                    tables.append({'name': path.stem, 'rows': list(csv.reader(stream))})
            elif path.suffix.lower() == '.docx':
                document = Document(path)
                for index, table in enumerate(document.tables, 1):
                    tables.append({'name': f'table_{index}', 'rows': [[cell.text for cell in row.cells] for row in table.rows]})
            else:
                raise ValueError('UNSUPPORTED_TABLE_DOCUMENT')
            return {'file': path.name, 'tables': tables}

        if name == 'ocr_document':
            if not self.rag:
                raise ValueError('RAG_NOT_CONFIGURED')
            path = self.workspace.safe(jid, args['path'])
            return {'file': path.name, 'text': self.rag.extract(path)}

        if name == 'search_db':
            if not self.rag:
                raise ValueError('DATABASE_NOT_CONFIGURED')
            identity = args.get('identity') or DEFAULT_TOOL_IDENTITY
            # Raw SQL only ever runs against the caller's own tier database, never a merged
            # cross-tier read, so a crafted query cannot pull rows from a higher tier.
            own_tier = identity.get('role') if identity.get('role') in self.rag.services else 'lower'
            query = args.get('query', '').strip()
            if not re.match(r'^(SELECT|WITH)\b', query, re.IGNORECASE) or ';' in query:
                raise ValueError('READ_ONLY_SELECT_REQUIRED')
            tables = set(re.findall(r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)', query, re.IGNORECASE))
            if not tables.issubset({'rag_documents', 'rag_chunks'}):
                raise ValueError('DATABASE_TABLE_NOT_ALLOWED')
            with self.rag.service_for(own_tier).engine.connect() as db:
                result = db.execute(text(query), args.get('params') or {})
                return {'columns': list(result.keys()), 'rows': [list(row) for row in result.fetchmany(int(args.get('limit', 100)))]}

        if name in {'send_email', 'create_calendar_event'}:
            if name == 'send_email':
                smtp_host = os.getenv('SMTP_HOST', '').strip()
                if not smtp_host:
                    raise ValueError('SMTP_NOT_CONFIGURED')
                message = EmailMessage()
                message['From'] = os.getenv('SMTP_FROM', 'orchestrator@localhost')
                message['To'] = args['to']
                message['Subject'] = args.get('subject', '')
                message.set_content(args.get('body', ''))
                with smtplib.SMTP(smtp_host, int(os.getenv('SMTP_PORT', '25')), timeout=15) as client:
                    client.send_message(message)
                return {'status': 'sent', 'external_delivery': True, 'to': args['to']}
            outbox = self.workspace.safe(jid, 'output/outbox', True)
            outbox.mkdir(parents=True, exist_ok=True)
            payload = {'tool': name, 'status': 'local_event', 'created_at': datetime.now().isoformat(), 'request': args}
            target = outbox / f'{name}_{datetime.now().strftime("%Y%m%d%H%M%S%f")}.json'
            target.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
            return {'status': 'local_event', 'path': str(target.relative_to(self.workspace.root / jid)), 'external_delivery': False}

        if name == 'read_file':
            return {
                'text': self.workspace.safe(
                    jid,
                    args['path']
                ).read_text(errors='ignore')
            }

        if name == 'write_file':
            p = self.workspace.safe(
                jid,
                args['path'],
                True
            )

            p.write_text(
                args.get('content', '')
            )

            return {
                'path': str(
                    p.relative_to(
                        self.workspace.root / jid
                    )
                )
            }

        if name == 'generate_docx':
            p = self.workspace.safe(
                jid,
                'output/' + args.get(
                    'filename',
                    'approval_note.docx'
                ),
                True
            )

            d = Document()

            d.add_heading(
                args.get(
                    'title',
                    'Approval Note'
                ),
                0
            )

            for s in args.get('sections', []):
                d.add_heading(
                    s.get(
                        'heading',
                        'Section'
                    ),
                    1
                )

                d.add_paragraph(
                    s.get(
                        'body',
                        ''
                    )
                )

            citations = args.get('citations', [])

            if citations:
                d.add_heading(
                    'References',
                    1
                )

                for citation in citations:
                    d.add_paragraph(
                        str(citation)
                    )

            d.save(p)

            return {
                'path': str(
                    p.relative_to(
                        self.workspace.root / jid
                    )
                ),
                'name': p.name,
                'mime_type': (
                    'application/vnd.openxmlformats-officedocument'
                    '.wordprocessingml.document'
                ),
                'citations': citations,
            }

        raise ValueError('UNKNOWN_TOOL')
