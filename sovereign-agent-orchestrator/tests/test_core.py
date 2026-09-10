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

def test_rerank_failure_preserves_embedding_order(tmp_path):
 """A broken/unreachable reranker must never lose or reorder results badly."""
 import asyncio
 rag = RagService(f'sqlite:///{tmp_path / "r.db"}', 'http://127.0.0.1:9/v1', rerank_model='reranker')
 candidates = [{'chunk_id': 'a', 'source': 'a.md', 'content': 'alpha', 'score': 0.9},
               {'chunk_id': 'b', 'source': 'b.md', 'content': 'beta', 'score': 0.5}]
 out = asyncio.run(rag._rerank('q', list(candidates), 2))
 assert [h['source'] for h in out] == ['a.md', 'b.md']

def test_rerank_disabled_by_default(tmp_path):
 rag = RagService(f'sqlite:///{tmp_path / "r.db"}')
 assert rag.rerank_model is None

def test_coding_plan_writes_source_files_not_docx():
 """Coding tasks must deliver code, not an approval document."""
 from app.orchestrator.service import Orchestrator
 response = 'Here you go:\n\n```python\ndef add(a, b):\n    return a + b\n```\n\nAnd a test:\n\n```python\ndef test_add():\n    assert add(1, 2) == 3\n```\n'
 plan = Orchestrator._coding_plan(Orchestrator, {}, 'write an add function', response)
 tools = [s['tool'] for s in plan]
 assert 'generate_docx' not in tools
 assert tools == ['write_file', 'write_file', 'write_file']
 paths = [s['tool_args']['path'] for s in plan]
 assert paths[:2] == ['output/snippet_1.py', 'output/snippet_2.py']
 assert paths[2] == 'output/response.md'
 assert 'def add(a, b):' in plan[0]['tool_args']['content']

def test_coding_plan_without_code_still_saves_response():
 from app.orchestrator.service import Orchestrator
 plan = Orchestrator._coding_plan(Orchestrator, {}, 'explain recursion', 'Recursion is when...')
 assert len(plan) == 1
 assert plan[0]['tool_args']['path'] == 'output/response.md'
 assert 'Recursion' in plan[0]['tool_args']['content']

def test_verifier_reports_grounding_and_blocks_only_when_required(tmp_path):
 from app.verification.verifier import Verifier
 workspace = Workspace(tmp_path / 'ws'); workspace.create('j')
 workspace.safe('j', 'output/a.docx', True).write_text('x')
 # Carries citations (so citations_present passes) but no retrieval — the
 # ungrounded-but-otherwise-valid case the grounding check exists to catch.
 ungrounded = {'job_id': 'j', 'plan': [], 'tool_calls': [],
               'observations': [{'citations': ['no evidence matched']}],
               'artifacts': [], 'task_type': 'document_workflow', 'retrieval': []}
 # Reported but not blocking by default.
 result = Verifier(workspace).verify(ungrounded)
 assert result['checks']['evidence_grounded'] is False
 assert result['passed'] is True
 assert any('not' in n and 'evidence-backed' in n for n in result['notes'])
 # Blocking when required.
 strict = Verifier(workspace, require_evidence=True).verify(ungrounded)
 assert strict['passed'] is False

def test_model_router_falls_back_to_regex_when_model_fails():
 """Routing must never depend on the classifier model being reachable."""
 import asyncio
 class Broken:
  async def chat(self, *a, **kw): raise RuntimeError('unreachable')
 router = ModelRouter('config/model_registry.yaml')
 label, how = asyncio.run(router.classify_with_model('summarize the report', Broken()))
 assert how == 'regex'
 assert label == 'summarization'

def test_model_router_accepts_valid_label():
 import asyncio
 class Fake:
  async def chat(self, *a, **kw): return {'content': 'ocr'}
 router = ModelRouter('config/model_registry.yaml')
 label, how = asyncio.run(router.classify_with_model('look at this handwriting', Fake()))
 assert (label, how) == ('ocr', 'model')

def test_model_router_rejects_invented_label():
 import asyncio
 class Liar:
  async def chat(self, *a, **kw): return {'content': 'sandwich'}
 router = ModelRouter('config/model_registry.yaml')
 label, how = asyncio.run(router.classify_with_model('write a python function', Liar()))
 assert how == 'regex' and label == 'coding'

def test_citations_reference_retrieved_evidence():
 """References must cite the evidence, not the model that wrote the document."""
 from app.orchestrator.service import Orchestrator
 job = {'retrieval': [{'source': 'inspection-2026-03.md', 'chunk_id': 'abcd1234efgh', 'score': 0.6330, 'content': 'FE-114 overdue'}]}
 citations = Orchestrator._evidence(job)
 assert citations == ['inspection-2026-03.md (chunk abcd1234, retrieval score 0.6330)']
 # No model alias or endpoint should leak into the References section.
 assert not any('reasoner' in c or 'localhost' in c for c in citations)

def test_citations_flag_absence_of_evidence():
 """An ungrounded document must say so rather than show an empty reference list."""
 from app.orchestrator.service import Orchestrator
 citations = Orchestrator._evidence({'retrieval': []})
 assert len(citations) == 1
 assert 'NO INDEXED EVIDENCE' in citations[0]

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
