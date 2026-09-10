from pathlib import Path
from app.policy.engine import Policy,Decision
from app.workspace.manager import Workspace
from app.models.router import ModelRouter
from app.rag.service import RagService

def test_policy_unknown_denied(): assert Policy().check('nope',{}).decision==Decision.DENY
def test_workspace_traversal(tmp_path):
 w=Workspace(tmp_path); w.create('j')
 try:w.safe('j','../../secret')
 except ValueError as e: assert str(e)=='PATH_OUTSIDE_JOB_WORKSPACE'
 else: assert False

def test_router_document(): assert ModelRouter('config/models.yaml').route('summarize inspection report')['task_type']=='document_workflow'
def test_router_multimodal(): assert ModelRouter('config/models.yaml').route('inspect scanned drawing image')['task_type']=='multimodal'

def test_router_marks_coding_tasks():
	assert ModelRouter('config/models.yaml').route('write Python code and run a test')['task_type'] == 'coding'

def test_run_python_tool_is_bounded(tmp_path):
	from app.tools.registry import ToolRegistry
	workspace = Workspace(tmp_path / 'workspace')
	workspace.create('job')
	result = ToolRegistry(workspace).execute('job', 'run_python', {'code': 'print(2 + 2)'})
	assert result['status'] == 'passed'
	assert result['stdout'].strip() == '4'

def test_rag_extracts_csv_and_searches_without_ollama(tmp_path):
	source = tmp_path / 'findings.csv'
	source.write_text('finding,status\nfire extinguisher,recertify\n')
	rag = RagService(f'sqlite:///{tmp_path / "rag.db"}')
	assert 'fire extinguisher' in rag.extract(source)
	import asyncio
	indexed = asyncio.run(rag.ingest(source))
	assert indexed['chunks'] == 1
	hits = asyncio.run(rag.search('fire extinguisher'))
	assert hits[0]['source'] == 'findings.csv'

def test_rag_extracts_docx(tmp_path):
	from docx import Document
	source = tmp_path / 'report.docx'
	document = Document()
	document.add_paragraph('Pump P-101 requires inspection.')
	document.save(source)
	rag = RagService(f'sqlite:///{tmp_path / "rag.db"}')
	assert 'Pump P-101' in rag.extract(source)

def test_workbook_report_summarizes_recruitment_data(tmp_path):
	from openpyxl import Workbook
	from app.rag.report import analyze_workbook, write_workbook_report
	source = tmp_path / 'responses.xlsx'
	workbook = Workbook()
	sheet = workbook.active
	sheet.title = 'Form Responses 1'
	sheet.append(['Name', 'Branch', 'Year', 'Domain', 'Rate collaboratively'])
	sheet.append(['A', 'B.Tech CE', '2nd', 'Marketing, Technical', 5])
	sheet.append(['B', 'B.Tech CE', '1st', 'Marketing', 3])
	workbook.save(source)
	analysis = analyze_workbook(source)
	assert analysis['sheets'][0]['rows'] == 2
	assert analysis['sheets'][0]['summary']['domains']['Marketing'] == 2
	result = write_workbook_report(source, tmp_path / 'reports', analysis)
	assert Path(result['docx']).is_file()
	assert Path(result['json']).is_file()

def test_knowledge_transfer_report_combines_sources(tmp_path):
	from app.rag.report import write_knowledge_transfer_report
	sources = [tmp_path / 'problem.md', tmp_path / 'README.md']
	sources[0].write_text('# Problem\nBuild a safe knowledge system.')
	sources[1].write_text('# Setup\nRun the local server.')
	result = write_knowledge_transfer_report(sources, tmp_path / 'reports', lambda path: path.read_text())
	assert Path(result['docx']).is_file()
	assert result['analysis']['sources'][0]['source'] == 'problem.md'

def test_requested_tools_are_scoped_and_auditable(tmp_path):
	from app.tools.registry import ToolRegistry
	from app.rag.tiered import TieredRagService
	workspace = Workspace(tmp_path / 'workspace')
	job_id = 'job'
	workspace.create(job_id)
	input_path = workspace.safe(job_id, 'input/source.md', True)
	input_path.write_text('Contact test@example.com or 9876543210.')
	# Production always routes tool calls through the tier-aware wrapper so a tool
	# invocation cannot silently read across the admin/higher/lower boundary.
	urls = {tier: f'sqlite:///{tmp_path / (tier + "_rag.db")}' for tier in ('admin', 'higher', 'lower')}
	rag = TieredRagService(urls, 'http://localhost:11434', 'nomic-embed-text', 'qwen2.5vl:3b')
	tools = ToolRegistry(workspace, rag)
	identity = {'user_id': 'u1', 'tenant_id': 't1', 'role': 'lower'}
	assert tools.execute(job_id, 'ingest_document', {'path': 'input/source.md', 'identity': identity})['chunks'] == 1
	assert tools.execute(job_id, 'list_sources', {'identity': identity})['sources']
	assert tools.execute(job_id, 'ocr_document', {'path': 'input/source.md'})['text']
	redacted = tools.execute(job_id, 'redact_pii', {'path': 'input/source.md'})
	assert redacted['redactions'] == 2
	assert '[REDACTED_EMAIL]' in workspace.safe(job_id, redacted['path']).read_text()
	assert tools.execute(job_id, 'search_db', {'query': 'SELECT name FROM rag_documents', 'identity': identity})['rows']
	import pytest
	with pytest.raises(ValueError, match='SMTP_NOT_CONFIGURED'):
		tools.execute(job_id, 'send_email', {'to': 'team@example.com', 'subject': 'Draft'})
	assert Policy().check('send_email', {}).decision == Decision.REQUIRE_APPROVAL

def test_conversation_history_is_durable_and_tenant_scoped(tmp_path):
 from app.storage.store import Store
 store = Store(f'sqlite:///{tmp_path / "store.db"}')
 identity = {'user_id': 'u1', 'tenant_id': 't1', 'role': 'user'}
 conversation = store.create_conversation('c1', 't1', 'u1', 'Research')
 assert conversation['title'] == 'Research'
 store.add_message('m1', 'c1', 'user', 'What is in the report?')
 store.add_message('m2', 'c1', 'assistant', 'The report contains findings.', [{'chunk_id': 'x'}])
 assert [message['role'] for message in store.messages('c1')] == ['user', 'assistant']
 assert store.messages('c1')[1]['citations'][0]['chunk_id'] == 'x'
 assert store.conversation('c1', {'user_id': 'u2', 'tenant_id': 't1', 'role': 'user'}) is None

def test_delete_document_removes_indexed_chunks(tmp_path):
 source = tmp_path / 'source.md'
 source.write_text('Retention policy requires annual review.')
 rag = RagService(f'sqlite:///{tmp_path / "rag.db"}')
 import asyncio
 asyncio.run(rag.ingest(source, {'file_id': 'file-1', 'tenant_id': 't1'}))
 assert asyncio.run(rag.search('retention policy'))
 assert rag.delete_document('file-1') == 1
 assert asyncio.run(rag.search('retention policy')) == []

def test_file_sharing_and_attachment_scope_are_enforced(tmp_path):
 from app.storage.store import Store
 store = Store(f'sqlite:///{tmp_path / "store.db"}')
 owner = {'user_id': 'alice', 'tenant_id': 't1', 'role': 'user'}
 reader = {'user_id': 'bob', 'tenant_id': 't1', 'role': 'user'}
 store.register_file('f1', 'alice', 't1', 'a.md', str(tmp_path / 'a.md'), {})
 store.register_file('f2', 'alice', 't1', 'b.md', str(tmp_path / 'b.md'), {})
 assert store.accessible_file_ids(reader) == []
 share = store.share_file('f1', owner, 'bob')
 assert share['shared_with_user_id'] == 'bob'
 assert store.accessible_file_ids(reader) == ['f1']
 rag = RagService(f'sqlite:///{tmp_path / "rag.db"}')
 first = tmp_path / 'a.md'; second = tmp_path / 'b.md'
 first.write_text('private alpha policy'); second.write_text('private beta policy')
 rag.ingest_sync(first, {'file_id': 'f1', 'tenant_id': 't1', 'owner_id': 'alice'})
 rag.ingest_sync(second, {'file_id': 'f2', 'tenant_id': 't1', 'owner_id': 'alice'})
 hits = rag.search_sync('private policy', file_ids=['f1'])
 assert {hit['metadata']['file_id'] for hit in hits} == {'f1'}
 assert store.revoke_share(share['id'], owner)
 assert store.accessible_file_ids(reader) == []

def test_jwt_identity_uses_signed_claims(monkeypatch):
 import jwt
 from app.auth import current_identity
 monkeypatch.setenv('AUTH_MODE', 'jwt')
 monkeypatch.setenv('JWT_SECRET', 'test-secret-with-at-least-32-bytes')
 token = jwt.encode({'sub': 'alice', 'tenant_id': 't1', 'role': 'user', 'clearance': 'internal', 'exp': 4102444800}, 'test-secret-with-at-least-32-bytes', algorithm='HS256')
 identity = current_identity(authorization=f'Bearer {token}')
 assert identity['user_id'] == 'alice'
 assert identity['tenant_id'] == 't1'

def test_local_reranker_marks_and_orders_results(tmp_path):
 rag = RagService(f'sqlite:///{tmp_path / "rag.db"}')
 first = tmp_path / 'first.md'; second = tmp_path / 'second.md'
 first.write_text('inspection interval annual review')
 second.write_text('inspection unrelated note')
 rag.ingest_sync(first, {'file_id': 'f1', 'tenant_id': 't1'})
 rag.ingest_sync(second, {'file_id': 'f2', 'tenant_id': 't1'})
 hits = rag.search_sync('inspection annual review', file_ids=['f1', 'f2'])
 assert hits[0]['metadata']['file_id'] == 'f1'
 assert 'local_rerank' in hits[0]['retrieval_method']

def test_request_limiter_blocks_after_limit():
 from app.operations import RequestLimiter
 limiter = RequestLimiter(1)
 assert limiter.allow('user')
 assert not limiter.allow('user')

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
