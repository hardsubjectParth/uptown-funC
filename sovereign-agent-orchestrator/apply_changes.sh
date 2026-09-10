#!/usr/bin/env bash
# apply_changes.sh
#
# Applies a focused set of fixes and improvements to the
# sovereign-agent-orchestrator codebase (SIH #26117 submission):
#
#   1. Fixes a real, verified bug: app/Workspace/ (capital W) is imported
#      everywhere as app.workspace.manager (lowercase). This works by
#      accident on case-insensitive filesystems (Windows/macOS default) but
#      breaks EVERY import of that module -- including the whole app and
#      the entire test suite -- on Linux/Podman, which is the actual
#      deployment target. Renamed to app/workspace/.
#   2. Fixes app/verification/verifier.py, which hardcoded Path('workspace')
#      instead of reading the configured WORKSPACE_ROOT, so verification
#      could silently check the wrong directory whenever WORKSPACE_ROOT was
#      overridden (as the Podman deployment does).
#   3. Implements the 'run_python' and 'describe_image' tools. Both already
#      had risk tiers configured in app/policy/engine.py (i.e. the policy
#      engine believed they existed and would authorize them), but neither
#      was implemented in app/tools/registry.py, so any plan step naming
#      them would fail with UNKNOWN_TOOL. run_python is bounded: workspace-
#      scoped script, isolated interpreter (-I -S, no user-site packages),
#      per-call timeout and output-size caps that a caller may only shrink
#      (never extend) past the server-configured maximum, and best-effort
#      CPU/memory rlimits on POSIX. This is a bounded local execution mode,
#      NOT a hardened OS-level sandbox -- see the note in the tool's
#      docstring for the recommended microVM/container-per-execution path
#      for defence/government production use.
#   4. Adds two new, additive, non-breaking API endpoints:
#        GET /api/v1/tools   -- lists registered tool names
#        GET /api/v1/models  -- lists configured models and their status
#      No existing route, request/response shape, or status code changes.
#   5. Rewrites cli.py into a proper subcommand CLI:
#        cli.py run "<task>" [--approval] [--report PATH]
#                             [--knowledge-transfer PATH...] [--output-dir DIR]
#        cli.py report PATH [--output-dir DIR]
#        cli.py knowledge-transfer PATH... [--output-dir DIR]
#        cli.py tools [list] [--json]
#        cli.py models [list] [--json]
#        cli.py doctor [--json] [--network]
#        cli.py serve [--host H] [--port P] [--reload]
#      Backward compatible: `python cli.py "task" [old flags]` with NO
#      subcommand keeps working exactly as before -- it is silently routed
#      to the `run` subcommand.
#   6. Adds regression + coverage tests for all of the above to
#      tests/test_core.py.
#
# Usage:
#   ./apply_changes.sh [path-to-sovereign-agent-orchestrator]
#
# If no path is given, the script assumes it is being run from the
# repository root that contains sovereign-agent-orchestrator/, or from
# inside sovereign-agent-orchestrator/ itself.
#
# The script is idempotent: running it twice does not double-apply changes.

set -euo pipefail

TARGET_ARG="${1:-}"

resolve_target() {
  if [[ -n "$TARGET_ARG" ]]; then
    echo "$TARGET_ARG"
    return
  fi
  if [[ -d "sovereign-agent-orchestrator" ]]; then
    echo "sovereign-agent-orchestrator"
    return
  fi
  if [[ -f "cli.py" && -d "app" ]]; then
    echo "."
    return
  fi
  echo ""
}

ROOT="$(resolve_target)"
if [[ -z "$ROOT" ]]; then
  echo "ERROR: could not find sovereign-agent-orchestrator/ (or app/ + cli.py)." >&2
  echo "Run this script from the repo root, from inside sovereign-agent-orchestrator/," >&2
  echo "or pass the path explicitly: ./apply_changes.sh /path/to/sovereign-agent-orchestrator" >&2
  exit 1
fi
ROOT="$(cd "$ROOT" && pwd)"
echo "Target project: $ROOT"
cd "$ROOT"

backup() {
  local f="$1"
  if [[ -f "$f" && ! -f "$f.pre-apply-changes.bak" ]]; then
    cp "$f" "$f.pre-apply-changes.bak"
  fi
}

echo "==> [1/6] Fixing app/Workspace -> app/workspace case-sensitivity bug"
if [[ -d "app/Workspace" && ! -d "app/workspace" ]]; then
  # Two-step move avoids failures on case-insensitive filesystems where
  # `mv Workspace workspace` is otherwise a no-op rename-to-self.
  mv "app/Workspace" "app/__workspace_tmp__"
  mv "app/__workspace_tmp__" "app/workspace"
  echo "    Renamed app/Workspace -> app/workspace"
elif [[ -d "app/workspace" ]]; then
  echo "    app/workspace already exists (already applied) -- skipping"
else
  echo "    WARNING: neither app/Workspace nor app/workspace found; skipping" >&2
fi

echo "==> [2/6] Writing app/tools/registry.py (adds run_python, describe_image)"
backup "app/tools/registry.py"
mkdir -p app/tools
cat > app/tools/registry.py << 'REGISTRY_EOF'
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
REGISTRY_EOF

echo "==> [3/6] Writing app/verification/verifier.py (uses configured WORKSPACE_ROOT)"
backup "app/verification/verifier.py"
mkdir -p app/verification
cat > app/verification/verifier.py << 'VERIFIER_EOF'
from pathlib import Path

from app.config import settings


class Verifier:
    def verify(self, job):
        observations = job.get('observations', [])

        citations_present = any(
            (
                isinstance(x, dict)
                and (
                    bool(x.get('sources'))
                    or bool(x.get('citations'))
                    or any(
                        'source' in str(h).lower()
                        for h in x.get('hits', [])
                        if isinstance(h, dict)
                    )
                )
            )
            for x in observations
        )

        # Use the configured workspace root (WORKSPACE_ROOT) instead of a
        # hardcoded relative path, so verification checks the same directory
        # the orchestrator actually writes artifacts into.
        out = (
            Path(settings.workspace_root)
            / job['job_id']
            / 'output'
        )

        artifacts_exist = (
            bool(job.get('artifacts'))
            or (
                out.exists()
                and any(out.iterdir())
            )
        )

        retrieved_hits = [hit for observation in observations for hit in observation.get('hits', []) if isinstance(observation, dict) and isinstance(hit, dict)]
        checks = {
            'plan_completed': all(
                x.get('status') == 'done'
                for x in job.get('plan', [])
            ),

            'citations_present': (
                citations_present
                or job.get('task_type') != 'document_workflow'
            ),

            'citation_sources_valid': all(bool(hit.get('chunk_id')) and bool(hit.get('source')) for hit in retrieved_hits),

            'artifacts_exist': artifacts_exist,

            'no_unhandled_denials': not any(
                x.get('policy_decision') == 'deny'
                for x in job.get('tool_calls', [])
            ),
        }

        passed = all(checks.values())

        return {
            'passed': passed,
            'checks': checks,
            'notes': (
                []
                if passed
                else ['Verification gate blocked delivery.']
            ),
        }
VERIFIER_EOF

echo "==> [4/6] Writing app/api/routes.py (adds GET /tools, GET /models -- additive only)"
backup "app/api/routes.py"
mkdir -p app/api
cat > app/api/routes.py << 'ROUTES_EOF'
import asyncio, uuid, mimetypes, shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from app.schemas.contracts import *
from app.auth import current_identity
router=APIRouter(prefix='/api/v1')
SERVICE=None

def init_service(s):
 global SERVICE; SERVICE=s
@router.get('/health')
def health(): return {'status':'ok'}
@router.get('/ready')
def ready(): return {'status':'ready'}
@router.get('/tools')
def list_tools(identity: dict=Depends(current_identity)): return {'tools': SERVICE.tools.names()}
@router.get('/models')
def list_models(identity: dict=Depends(current_identity)): return {'models': [{'id': m['id'], 'model': m.get('model'), 'capabilities': m.get('capabilities', []), 'enabled': m.get('enabled', False), 'tier': m.get('tier')} for m in SERVICE.router.models]}
@router.post('/files')
async def upload(file: UploadFile=File(...), identity: dict=Depends(current_identity)):
 fid=str(uuid.uuid4()); p=SERVICE.workspace.root/'uploads'; p.mkdir(exist_ok=True); dest=p/(fid+'_'+Path(file.filename or 'upload').name)
 data=await file.read(); dest.write_bytes(data)
 try:
  indexed=await SERVICE.tools.rag.ingest(dest, {'mime_type':file.content_type,'file_id':fid,'tenant_id':identity['tenant_id'],'clearance':identity['clearance']})
 except ValueError as exc:
  raise HTTPException(400,str(exc)) from exc
 SERVICE.store.register_file(fid, identity['user_id'], identity['tenant_id'], file.filename or 'upload', str(dest), {'mime_type':file.content_type, 'index':indexed})
 SERVICE.store.audit(identity['user_id'], identity['tenant_id'], 'file_indexed', fid, indexed)
 return {'file_id':fid,'name':file.filename,'mime_type':file.content_type,'size_bytes':len(data),'index':indexed}
@router.post('/knowledge/search')
async def knowledge_search(request: dict, identity: dict=Depends(current_identity)):
 query=str(request.get('query','')).strip()
 if not query: raise HTTPException(422,'QUERY_REQUIRED')
 metadata=dict(request.get('metadata') or {}); metadata.update({'tenant_id': identity['tenant_id']})
 return {'hits':await SERVICE.tools.rag.search(query, int(request.get('top_k',5)), metadata)}
@router.post('/agent/run')
async def run(req:AgentRunRequest, identity: dict=Depends(current_identity)):
 jid=str(uuid.uuid4()); context=req.user_context.model_dump(); context.update(identity); context['requested_role']=req.user_context.role
 SERVICE.workspace.create(jid)
 attachments=[]
 for attachment in req.attachments:
  if not attachment.file_id: raise HTTPException(422,'ATTACHMENT_FILE_ID_REQUIRED')
  record=SERVICE.store.file_for(attachment.file_id, identity)
  if not record: raise HTTPException(403,'ATTACHMENT_NOT_AUTHORIZED')
  destination=SERVICE.workspace.safe(jid, 'input/'+Path(record['name']).name, True)
  shutil.copyfile(record['path'], destination)
  attachments.append({'file_id': record['id'], 'name': record['name'], 'path': str(destination.relative_to(SERVICE.workspace.root/jid)), 'mime_type': record['metadata']})
 j={'job_id':jid,'status':'queued','task':req.task,'user_context':context,'attachments':attachments,'routing':None,'plan':[],'tool_calls':[],'observations':[],'verification':None,'requires_human_approval':False,'approval':None,'artifacts':[],'final_answer':None,'error':None,'task_type':'document_workflow'}; SERVICE.store.save(j); SERVICE.store.enqueue(jid); SERVICE.store.audit(identity['user_id'], identity['tenant_id'], 'job_created', jid, {'task': req.task, 'attachments': [a['file_id'] for a in attachments]}); SERVICE._emit(j,'job_created',{'status':'queued'}); return {'job_id':jid,'status':'queued'}
@router.get('/agent/{job_id}')
def get_job(job_id, identity: dict=Depends(current_identity)):
 j=SERVICE.store.get(job_id)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 if j.get('user_context',{}).get('tenant_id') != identity['tenant_id']: raise HTTPException(404,'JOB_NOT_FOUND')
 return j
@router.post('/agent/{job_id}/approve')
async def approve(job_id,req:ApprovalRequest, identity: dict=Depends(current_identity)):
 j=get_job(job_id, identity)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 if j['status']!='awaiting_approval': raise HTTPException(409,'JOB_NOT_AWAITING_APPROVAL')
 await SERVICE.resume(j,req.approved,identity['user_id']); SERVICE.store.audit(identity['user_id'], identity['tenant_id'], 'approval_decision', job_id, {'approved': req.approved}); return {'job_id':job_id,'status':j['status']}
@router.post('/agent/{job_id}/cancel')
def cancel(job_id, identity: dict=Depends(current_identity)):
 j=get_job(job_id, identity)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 j['status']='cancelled'; SERVICE.store.save(j); SERVICE._emit(j,'job_cancelled',{}); return {'job_id':job_id,'status':'cancelled'}
@router.get('/agent/{job_id}/events')
def events(job_id, identity: dict=Depends(current_identity)):
 get_job(job_id, identity)
 async def gen():
  sent=0
  while True:
   rows=SERVICE.store.events(job_id)
   for e in rows[sent:]: yield f"event: {e['type']}\ndata: {__import__('json').dumps(e)}\n\n"
   sent=len(rows); j=SERVICE.store.get(job_id)
   if j and j['status'] in {'done','failed','cancelled'} and sent>=len(rows): break
   await asyncio.sleep(.25)
 return StreamingResponse(gen(),media_type='text/event-stream')
@router.get('/agent/{job_id}/artifacts')
def artifacts(job_id, identity: dict=Depends(current_identity)):
 j=get_job(job_id, identity)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 return j['artifacts']
@router.get('/agent/{job_id}/artifacts/{artifact_name}')
def artifact(job_id,artifact_name, identity: dict=Depends(current_identity)):
 get_job(job_id, identity)
 p=SERVICE.workspace.safe(job_id,'output/'+artifact_name)
 if not p.is_file(): raise HTTPException(404,'ARTIFACT_NOT_FOUND')
 return FileResponse(p,filename=p.name,media_type=mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
ROUTES_EOF

echo "==> [5/6] Writing cli.py (subcommand CLI, backward compatible)"
backup "cli.py"
cat > cli.py << 'CLI_EOF'
import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from app.config import settings
from app.storage.store import Store
from app.workspace.manager import Workspace
from app.models.router import ModelRouter
from app.models.adapter import FakeModel, OllamaAdapter
from app.policy.engine import Policy
from app.tools.registry import ToolRegistry
from app.verification.verifier import Verifier
from app.orchestrator.service import Orchestrator
from app.rag.report import write_knowledge_transfer_report, write_workbook_report
from app.rag.service import RagService

KNOWN_COMMANDS = {'run', 'report', 'knowledge-transfer', 'tools', 'models', 'doctor', 'serve'}


def _service(store, workspace, rag):
	if settings.model_mode.lower() == 'ollama':
		model = OllamaAdapter(settings.ollama_base_url, settings.ollama_model)
	else:
		model = FakeModel()
	return Orchestrator(store, workspace, ModelRouter('config/models.yaml'), Policy(), ToolRegistry(workspace, rag), Verifier(), model)


def _rag():
	return RagService(settings.database_url, settings.ollama_base_url, settings.ollama_embedding_model, settings.ollama_vision_model)


def _build_parser():
	parser = argparse.ArgumentParser(prog='cli.py', description='Sovereign Agent Orchestrator CLI')
	sub = parser.add_subparsers(dest='command')

	# `run` reproduces the ORIGINAL cli.py behaviour and flags exactly, so
	# every existing invocation (`python cli.py "task"`, `--report`,
	# `--knowledge-transfer`, `--approval`, `--output-dir`) keeps working
	# unchanged. It is also now selectable explicitly as `run`.
	run_p = sub.add_parser('run', help='Submit a task to the orchestrator (default command).')
	run_p.add_argument('task', nargs='?', default='Read the inspection report and generate an approval note citing the applicable SOP.')
	run_p.add_argument('--approval', action='store_true')
	run_p.add_argument('--report', type=Path, help='Ingest an XLSX workbook and generate a local DOCX and JSON report.')
	run_p.add_argument('--knowledge-transfer', type=Path, nargs='+', help='Ingest documents and generate a consolidated knowledge-transfer DOCX and JSON report.')
	run_p.add_argument('--output-dir', type=Path, default=Path('workspace/reports'))

	report_p = sub.add_parser('report', help='Ingest an XLSX workbook and generate a DOCX/JSON report.')
	report_p.add_argument('path', type=Path)
	report_p.add_argument('--output-dir', type=Path, default=Path('workspace/reports'))

	kt_p = sub.add_parser('knowledge-transfer', help='Ingest documents and generate a consolidated knowledge-transfer report.')
	kt_p.add_argument('paths', type=Path, nargs='+')
	kt_p.add_argument('--output-dir', type=Path, default=Path('workspace/reports'))

	tools_p = sub.add_parser('tools', help='Inspect registered tools.')
	tools_p.add_argument('action', nargs='?', default='list', choices=['list'])
	tools_p.add_argument('--json', action='store_true')

	models_p = sub.add_parser('models', help='Inspect configured models.')
	models_p.add_argument('action', nargs='?', default='list', choices=['list'])
	models_p.add_argument('--json', action='store_true')

	doctor_p = sub.add_parser('doctor', help='Run local environment/connectivity/air-gap checks.')
	doctor_p.add_argument('--json', action='store_true')
	doctor_p.add_argument('--network', action='store_true', help='Only run the air-gap / no-outbound-cloud check.')

	serve_p = sub.add_parser('serve', help='Start the API server (uvicorn).')
	serve_p.add_argument('--host', default=settings.api_host)
	serve_p.add_argument('--port', type=int, default=settings.api_port)
	serve_p.add_argument('--reload', action='store_true')

	return parser


def _normalize_argv(argv):
	"""Backward compatibility shim: `python cli.py "task" [--flags]` with no
	subcommand name keeps working exactly as it did before subcommands were
	added, by defaulting to `run`."""
	if not argv:
		return ['run']
	if argv[0] in KNOWN_COMMANDS:
		return argv
	return ['run', *argv]


async def _cmd_run(args):
	store = Store(settings.database_url)
	workspace = Workspace(settings.workspace_root)
	rag = _rag()

	if args.report:
		indexed = await rag.ingest(args.report, {'source_type': 'workbook', 'tenant_id': 'default', 'clearance': 'internal'})
		result = write_workbook_report(args.report, args.output_dir)
		result['index'] = indexed
		print(json.dumps(result, indent=2, default=str))
		return

	if args.knowledge_transfer:
		indexed = []
		for path in args.knowledge_transfer:
			indexed.append(await rag.ingest(path, {'source_type': 'knowledge_transfer', 'tenant_id': 'default', 'clearance': 'internal'}))
		result = write_knowledge_transfer_report(args.knowledge_transfer, args.output_dir, rag.extract)
		result['index'] = indexed
		print(json.dumps(result, indent=2, default=str))
		return

	service = _service(store, workspace, rag)
	job_id = uuid.uuid4().hex
	job = {
		'job_id': job_id, 'status': 'queued', 'task': args.task,
		'user_context': {'user_id': 'cli-user', 'role': 'approver_demo' if args.approval else 'user', 'department': 'inspection', 'clearance': 'internal', 'project': 'demo'},
		'routing': None, 'plan': [], 'tool_calls': [], 'observations': [], 'verification': None,
		'requires_human_approval': False, 'approval': None, 'artifacts': [], 'final_answer': None, 'error': None,
	}
	store.save(job)
	await service.run(job)
	completed = store.get(job_id)
	print(json.dumps(completed, indent=2, default=str))
	if completed['status'] == 'awaiting_approval':
		print(f'Approval required for job {job_id}.')


async def _cmd_report(args):
	rag = _rag()
	indexed = await rag.ingest(args.path, {'source_type': 'workbook', 'tenant_id': 'default', 'clearance': 'internal'})
	result = write_workbook_report(args.path, args.output_dir)
	result['index'] = indexed
	print(json.dumps(result, indent=2, default=str))


async def _cmd_knowledge_transfer(args):
	rag = _rag()
	indexed = []
	for path in args.paths:
		indexed.append(await rag.ingest(path, {'source_type': 'knowledge_transfer', 'tenant_id': 'default', 'clearance': 'internal'}))
	result = write_knowledge_transfer_report(args.paths, args.output_dir, rag.extract)
	result['index'] = indexed
	print(json.dumps(result, indent=2, default=str))


def _cmd_tools(args):
	registry = ToolRegistry(Workspace(settings.workspace_root), None)
	names = registry.names()
	if args.json:
		print(json.dumps({'tools': names}, indent=2))
	else:
		for n in names:
			print(n)


def _cmd_models(args):
	router = ModelRouter('config/models.yaml')
	rows = [{'id': m['id'], 'model': m.get('model'), 'capabilities': m.get('capabilities', []), 'enabled': m.get('enabled', False), 'tier': m.get('tier')} for m in router.models]
	if args.json:
		print(json.dumps({'models': rows}, indent=2))
	else:
		for m in rows:
			status = 'enabled' if m['enabled'] else 'disabled'
			print(f"{m['id']:<16} {status:<9} {str(m.get('tier','')):<10} {','.join(m['capabilities'])}")


def _cmd_doctor(args):
	checks = {}

	if not args.network:
		try:
			store = Store(settings.database_url)
			store.engine.connect().close()
			checks['database'] = {'ok': True, 'detail': settings.database_url}
		except Exception as exc:
			checks['database'] = {'ok': False, 'detail': str(exc)}

		try:
			workspace = Workspace(settings.workspace_root)
			probe = workspace.root / '.doctor_write_test'
			probe.write_text('ok')
			probe.unlink()
			checks['workspace_writable'] = {'ok': True, 'detail': str(workspace.root)}
		except Exception as exc:
			checks['workspace_writable'] = {'ok': False, 'detail': str(exc)}

		checks['model_mode'] = {'ok': True, 'detail': settings.model_mode}

		if settings.model_mode.lower() == 'ollama':
			try:
				import httpx
				r = httpx.get(settings.ollama_base_url.rstrip('/') + '/api/tags', timeout=3)
				r.raise_for_status()
				names = [m.get('model') or m.get('name') for m in r.json().get('models', [])]
				required = {settings.ollama_model, settings.ollama_embedding_model, settings.ollama_vision_model}
				missing = [m for m in required if m not in names]
				checks['ollama_reachable'] = {'ok': True, 'detail': f'{len(names)} models available'}
				checks['ollama_models_present'] = {'ok': not missing, 'detail': ('missing: ' + ', '.join(missing)) if missing else 'all configured models present'}
			except Exception as exc:
				checks['ollama_reachable'] = {'ok': False, 'detail': str(exc)}

	# Air-gap / sovereignty proof. This is the check the demo should show live:
	# it asserts the deployment is configured to refuse outbound Ollama-cloud
	# access, which is the closest static signal this process can give without
	# an external network monitor / firewall log.
	no_cloud_env = os.getenv('OLLAMA_NO_CLOUD', '').strip().lower() in {'1', 'true', 'yes'}
	checks['air_gap_no_cloud_configured'] = {
		'ok': no_cloud_env or settings.model_mode.lower() != 'ollama',
		'detail': (
			'OLLAMA_NO_CLOUD is set; outbound Ollama-cloud access should be disabled.'
			if no_cloud_env else
			'OLLAMA_NO_CLOUD is not set. For an air-gapped deployment, set OLLAMA_NO_CLOUD=true '
			'and block outbound network access for the container/host after models are pulled.'
		),
	}

	passed = all(c['ok'] for c in checks.values())
	if args.json:
		print(json.dumps({'passed': passed, 'checks': checks}, indent=2))
	else:
		for name, c in checks.items():
			print(f"[{'OK' if c['ok'] else 'FAIL'}] {name}: {c['detail']}")
		print('PASSED' if passed else 'FAILED')
	if not passed:
		sys.exit(1)


def _cmd_serve(args):
	import uvicorn
	uvicorn.run('app.main:app', host=args.host, port=args.port, reload=args.reload)


async def _async_main(args):
	if args.command in (None, 'run'):
		await _cmd_run(args)
	elif args.command == 'report':
		await _cmd_report(args)
	elif args.command == 'knowledge-transfer':
		await _cmd_knowledge_transfer(args)


def main():
	parser = _build_parser()
	argv = _normalize_argv(sys.argv[1:])
	args = parser.parse_args(argv)

	if args.command in (None, 'run', 'report', 'knowledge-transfer'):
		asyncio.run(_async_main(args))
	elif args.command == 'tools':
		_cmd_tools(args)
	elif args.command == 'models':
		_cmd_models(args)
	elif args.command == 'doctor':
		_cmd_doctor(args)
	elif args.command == 'serve':
		_cmd_serve(args)
	else:
		parser.print_help()


if __name__ == '__main__':
	main()
CLI_EOF

echo "==> [6/6] Appending new tests to tests/test_core.py"
if [[ -f "tests/test_core.py" ]] && grep -q "test_run_python_executes_and_captures_stdout" tests/test_core.py; then
  echo "    New tests already present -- skipping append"
else
  mkdir -p tests
  cat >> tests/test_core.py << 'TESTS_EOF'

def test_run_python_executes_and_captures_stdout(tmp_path):
	from app.tools.registry import ToolRegistry
	workspace = Workspace(tmp_path / 'workspace')
	job_id = 'job-py'
	workspace.create(job_id)
	tools = ToolRegistry(workspace)
	result = tools.execute(job_id, 'run_python', {'code': 'print(2 + 2)'})
	assert result['return_code'] == 0
	assert result['stdout'].strip() == '4'
	assert result['timed_out'] is False
	assert result['workspace_only'] is True

def test_run_python_enforces_timeout(tmp_path):
	from app.tools.registry import ToolRegistry
	workspace = Workspace(tmp_path / 'workspace')
	job_id = 'job-timeout'
	workspace.create(job_id)
	tools = ToolRegistry(workspace)
	result = tools.execute(job_id, 'run_python', {'code': 'import time\ntime.sleep(5)', 'timeout_seconds': 1})
	assert result['timed_out'] is True
	assert result['return_code'] != 0

def test_run_python_blocks_user_site_packages(tmp_path):
	from app.tools.registry import ToolRegistry
	workspace = Workspace(tmp_path / 'workspace')
	job_id = 'job-isolated'
	workspace.create(job_id)
	tools = ToolRegistry(workspace)
	result = tools.execute(job_id, 'run_python', {'code': 'import sys\nprint(sys.flags.no_user_site)'})
	assert result['stdout'].strip() == '1'

def test_run_python_truncates_large_output(tmp_path):
	from app.tools.registry import ToolRegistry
	workspace = Workspace(tmp_path / 'workspace')
	job_id = 'job-truncate'
	workspace.create(job_id)
	tools = ToolRegistry(workspace)
	result = tools.execute(job_id, 'run_python', {'code': "print('x' * 5000)", 'max_output_chars': 100})
	assert result['truncated'] is True
	assert len(result['stdout']) <= 100

def test_describe_image_tool_returns_description(tmp_path):
	from app.tools.registry import ToolRegistry
	from app.rag.service import RagService
	from PIL import Image
	workspace = Workspace(tmp_path / 'workspace')
	job_id = 'job-image'
	workspace.create(job_id)
	image_path = workspace.safe(job_id, 'input/photo.png', True)
	Image.new('RGB', (10, 10), color='white').save(image_path)
	rag = RagService(f'sqlite:///{tmp_path / "rag.db"}')
	tools = ToolRegistry(workspace, rag)
	result = tools.execute(job_id, 'describe_image', {'path': 'input/photo.png'})
	assert result['file'] == 'photo.png'
	assert 'description' in result

def test_tool_registry_lists_run_python_and_describe_image():
	from app.tools.registry import ToolRegistry
	names = ToolRegistry(Workspace(Path('/tmp/sao-tool-list-test'))).names()
	assert 'run_python' in names
	assert 'describe_image' in names

def test_policy_allows_previously_unregistered_tools():
	# run_python and describe_image already had risk tiers configured in
	# Policy before they were implemented in ToolRegistry; this locks in
	# that they are now actually usable end to end.
	assert Policy().check('run_python', {}).decision != Decision.DENY
	assert Policy().check('describe_image', {}).decision != Decision.DENY

def test_verifier_uses_configured_workspace_root(tmp_path, monkeypatch):
	from app.config import settings
	from app.verification.verifier import Verifier
	monkeypatch.setattr(settings, 'workspace_root', str(tmp_path))
	job_id = 'job-verify'
	output_dir = tmp_path / job_id / 'output'
	output_dir.mkdir(parents=True)
	(output_dir / 'artifact.docx').write_text('x')
	job = {'job_id': job_id, 'observations': [], 'plan': [], 'tool_calls': [], 'artifacts': [], 'task_type': 'general'}
	result = Verifier().verify(job)
	assert result['checks']['artifacts_exist'] is True

def test_workspace_module_is_lowercase_and_importable():
	# Regression test: the package directory must be named `workspace`
	# (lowercase) to match every import site (`app.workspace.manager`).
	# On case-insensitive filesystems the mismatch is invisible; on Linux
	# (the actual container/deployment target) it previously broke every
	# import of this module, including the whole app and test suite.
	import importlib
	module = importlib.import_module('app.workspace.manager')
	assert hasattr(module, 'Workspace')
TESTS_EOF
  echo "    Appended new tests"
fi

echo ""
echo "==> Running test suite"
if command -v python3 >/dev/null 2>&1; then
  if python3 -m pytest tests/ -q; then
    echo ""
    echo "All tests passed."
  else
    echo ""
    echo "One or more tests FAILED. Review output above before deploying." >&2
    exit 1
  fi
else
  echo "python3 not found on PATH -- skipping automatic test run." >&2
  echo "Run manually: python3 -m pytest tests/ -q" >&2
fi

echo ""
echo "Done. Summary of what changed:"
echo "  - app/Workspace/  -> app/workspace/   (case-sensitivity fix; required for Linux/Podman)"
echo "  - app/verification/verifier.py         (now honors WORKSPACE_ROOT)"
echo "  - app/tools/registry.py                (+ run_python, + describe_image)"
echo "  - app/api/routes.py                    (+ GET /api/v1/tools, + GET /api/v1/models)"
echo "  - cli.py                               (subcommands: run/report/knowledge-transfer/tools/models/doctor/serve)"
echo "  - tests/test_core.py                   (+ 9 tests covering all of the above)"
echo ""
echo "Try it:"
echo "  python3 cli.py tools"
echo "  python3 cli.py models"
echo "  python3 cli.py doctor"
echo "  python3 cli.py run \"summarize inspection report\""
echo "  python3 cli.py serve"
