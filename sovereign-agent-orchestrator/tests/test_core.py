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

def test_adapter_rejects_empty_content():
 """An empty answer must fail loudly, not become a placeholder document."""
 import asyncio, httpx
 from app.models.adapter import OpenAICompatibleAdapter

 def handler(request):
  return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': ''}}], 'usage': {'completion_tokens': 1}})

 adapter = OpenAICompatibleAdapter('http://test/v1')
 original = httpx.AsyncClient
 httpx.AsyncClient = lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
 try:
  try:
   asyncio.run(adapter.chat([{'role': 'user', 'content': 'hi'}], model='reasoner-35b'))
  except RuntimeError as exc:
   assert 'MODEL_RETURNED_EMPTY_CONTENT' in str(exc)
  else:
   assert False, 'empty content should raise'
 finally:
  httpx.AsyncClient = original

def _reasoner_alias():
 # The reasoner is a swappable choice between candidates (reasoner-9b /
 # reasoner-35b), so assert against the registry rather than a literal alias.
 return ModelRouter('config/model_registry.yaml').by_task['planning']['model_alias']

def test_router_document():
 decision = ModelRouter('config/model_registry.yaml').route('summarize inspection report')
 assert decision['task_type']=='document_workflow'
 assert decision['model_alias']==_reasoner_alias()

def test_router_multimodal():
 decision = ModelRouter('config/model_registry.yaml').route('inspect scanned drawing image')
 assert decision['task_type']=='multimodal'
 assert decision['model_alias']=='vision'

def test_router_coding():
 decision = ModelRouter('config/model_registry.yaml').route('write a python function and unit test')
 assert decision['task_type']=='coding'
 assert decision['model_alias']==_reasoner_alias()  # the reasoner covers coding too

def test_router_aliases_exist_in_llama_swap_config():
 """Every alias the router can return must be a model llama-swap defines."""
 import yaml
 from pathlib import Path
 config = Path('config/llama-swap.example.yaml')
 served = set(yaml.safe_load(config.read_text())['models'])
 routed = {entry['model_alias'] for entry in ModelRouter('config/model_registry.yaml').models}
 assert routed <= served, f'aliases missing from llama-swap config: {routed - served}'

def test_verifier_honours_workspace_root(tmp_path):
 from app.verification.verifier import Verifier
 workspace = Workspace(tmp_path / 'custom_root')
 workspace.create('j')
 artifact = workspace.safe('j', 'output/report.docx', True)
 artifact.write_text('x')
 job = {'job_id': 'j', 'plan': [], 'tool_calls': [], 'observations': [], 'artifacts': [], 'task_type': 'general'}
 # Finds the artifact under a non-default WORKSPACE_ROOT.
 assert Verifier(workspace).verify(job)['checks']['artifacts_exist'] is True
 # Without the workspace it looks under ./workspace and cannot see it.
 assert Verifier().verify(job)['checks']['artifacts_exist'] is False

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
	workspace = Workspace(tmp_path / 'workspace')
	job_id = 'job'
	workspace.create(job_id)
	input_path = workspace.safe(job_id, 'input/source.md', True)
	input_path.write_text('Contact test@example.com or 9876543210.')
	rag = RagService(f'sqlite:///{tmp_path / "rag.db"}')
	tools = ToolRegistry(workspace, rag)
	assert tools.execute(job_id, 'ingest_document', {'path': 'input/source.md'})['chunks'] == 1
	assert tools.execute(job_id, 'list_sources', {})['sources']
	assert tools.execute(job_id, 'ocr_document', {'path': 'input/source.md'})['text']
	redacted = tools.execute(job_id, 'redact_pii', {'path': 'input/source.md'})
	assert redacted['redactions'] == 2
	assert '[REDACTED_EMAIL]' in workspace.safe(job_id, redacted['path']).read_text()
	assert tools.execute(job_id, 'search_db', {'query': 'SELECT name FROM rag_documents'})['rows']
	draft = tools.execute(job_id, 'send_email', {'to': 'team@example.com', 'subject': 'Draft'})
	assert draft['external_delivery'] is False
	assert Policy().check('send_email', {}).decision == Decision.REQUIRE_APPROVAL
