import csv
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from docx import Document
from openpyxl import load_workbook

from app.rag.report import write_knowledge_transfer_report

# Bounded local Python execution defaults. Callers may only *tighten* these
# per-call (shorter timeout / smaller output cap), never loosen them, so a
# single job cannot request unbounded execution.
RUN_PYTHON_MAX_TIMEOUT_SECONDS = int(os.getenv('RUN_PYTHON_TIMEOUT_SECONDS', '15'))
RUN_PYTHON_MAX_OUTPUT_CHARS = int(os.getenv('RUN_PYTHON_MAX_OUTPUT_CHARS', '20000'))
RUN_PYTHON_MEMORY_LIMIT_MB = int(os.getenv('RUN_PYTHON_MEMORY_LIMIT_MB', '512'))


def _limit_child_resources(cpu_seconds, memory_mb):
    """preexec_fn for the run_python subprocess: caps CPU time and address
    space on POSIX systems. Best-effort only -- this is a bounded local
    execution mode, not a hardened OS-level sandbox (no network namespace
    isolation). For defence/government production use this should be moved
    into a separate sandbox container or microVM."""
    def _apply():
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            mem_bytes = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except Exception:
            pass
    return _apply


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
            'run_python',
            'describe_image',
        ]

    def execute(self, jid, name, args):
        if name == 'search_documents':
            q = args.get('query', '').lower()
            if self.rag:
                hits = self.rag.search_sync(q, args.get('top_k', 5), args.get('metadata'))
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
            path = self.workspace.safe(jid, args['path'])
            return self.rag.ingest_sync(path, {'job_id': jid, **(args.get('metadata') or {})})

        if name == 'list_sources':
            if not self.rag:
                raise ValueError('RAG_NOT_CONFIGURED')
            with self.rag.engine.connect() as db:
                rows = db.execute(__import__('sqlalchemy').text('SELECT id,name,mime_type,checksum,metadata,created_at FROM rag_documents ORDER BY created_at DESC')).fetchall()
            return {'sources': [{'document_id': row[0], 'name': row[1], 'mime_type': row[2], 'checksum': row[3], 'metadata': json.loads(row[4] or '{}'), 'created_at': row[5]} for row in rows]}

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
            query = args.get('query', '').strip()
            if not re.match(r'^(SELECT|WITH)\b', query, re.IGNORECASE) or ';' in query:
                raise ValueError('READ_ONLY_SELECT_REQUIRED')
            with self.rag.engine.connect() as db:
                result = db.execute(__import__('sqlalchemy').text(query), args.get('params') or {})
                return {'columns': list(result.keys()), 'rows': [list(row) for row in result.fetchmany(int(args.get('limit', 100)))]}

        if name in {'send_email', 'create_calendar_event'}:
            outbox = self.workspace.safe(jid, 'output/outbox', True)
            outbox.mkdir(parents=True, exist_ok=True)
            payload = {'tool': name, 'status': 'draft', 'created_at': datetime.now().isoformat(), 'request': args}
            target = outbox / f'{name}_{datetime.now().strftime("%Y%m%d%H%M%S%f")}.json'
            target.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
            return {'status': 'draft', 'path': str(target.relative_to(self.workspace.root / jid)), 'external_delivery': False}

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

        if name == 'run_python':
            code = args.get('code')
            script_path = args.get('path')
            if not code and not script_path:
                raise ValueError('CODE_OR_PATH_REQUIRED')

            working_dir = self.workspace.safe(jid, 'working', True)
            working_dir.mkdir(parents=True, exist_ok=True)

            if script_path:
                target = self.workspace.safe(jid, script_path)
            else:
                target = working_dir / f'_run_{uuid.uuid4().hex}.py'
                target.write_text(code, encoding='utf-8')

            # Callers may only shrink these bounds, never grow them.
            timeout_seconds = min(
                int(args.get('timeout_seconds', RUN_PYTHON_MAX_TIMEOUT_SECONDS)),
                RUN_PYTHON_MAX_TIMEOUT_SECONDS,
            )
            max_output_chars = min(
                int(args.get('max_output_chars', RUN_PYTHON_MAX_OUTPUT_CHARS)),
                RUN_PYTHON_MAX_OUTPUT_CHARS,
            )

            env = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'}
            # -I: isolated mode (implies -E -P -s): ignores env vars, cwd is
            # not prepended to sys.path, and no user-site packages.
            command = [sys.executable, '-I', '-S', str(target)]
            preexec = (
                _limit_child_resources(timeout_seconds + 2, RUN_PYTHON_MEMORY_LIMIT_MB)
                if hasattr(os, 'fork') else None
            )

            started = datetime.now()
            timed_out = False
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(working_dir),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    preexec_fn=preexec,
                )
                stdout, stderr, return_code = completed.stdout, completed.stderr, completed.returncode
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or ''
                stderr = (exc.stderr or '') + f'\n[TIMEOUT] Execution exceeded {timeout_seconds}s'
                return_code, timed_out = -1, True

            duration_seconds = (datetime.now() - started).total_seconds()
            truncated = len(stdout) > max_output_chars or len(stderr) > max_output_chars

            return {
                'stdout': stdout[:max_output_chars],
                'stderr': stderr[:max_output_chars],
                'return_code': return_code,
                'timed_out': timed_out,
                'truncated': truncated,
                'duration_seconds': duration_seconds,
                'timeout_seconds': timeout_seconds,
                'workspace_only': True,
                'script': str(target.relative_to(self.workspace.root / jid)),
            }

        if name == 'describe_image':
            if not self.rag:
                raise ValueError('RAG_NOT_CONFIGURED')
            path = self.workspace.safe(jid, args['path'])
            return {'file': path.name, 'description': self.rag.extract(path)}

        raise ValueError('UNKNOWN_TOOL')
