import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
import uuid

from app.config import settings
from app.network import network_monitor
from app.storage.store import Store
from app.workspace.manager import Workspace
from app.models.router import ModelRouter
from app.models.adapter import FakeModel, OllamaAdapter
from app.policy.engine import Policy
from app.tools.registry import ToolRegistry
from app.verification.verifier import Verifier
from app.orchestrator.service import Orchestrator
from app.rag.report import write_knowledge_transfer_report, write_workbook_report
from app.rag.tiered import TieredRagService

# A local CLI operator has full read/write access to every RAG tier. This must be a
# real tier role (admin/higher/lower): the orchestrator hands user_context straight
# to the tier-aware RAG service, which rejects any other role.
CLI_IDENTITY = {'user_id': 'cli-user', 'role': 'admin', 'tenant_id': 'default', 'clearance': 'internal'}


def _service(store, workspace, rag):
	if settings.model_mode.lower() == 'ollama':
		model = OllamaAdapter(settings.ollama_base_url, settings.ollama_model)
	else:
		model = FakeModel()
	return Orchestrator(
		store, workspace, ModelRouter('config/models.yaml'), Policy(),
		ToolRegistry(workspace, rag), Verifier(settings.workspace_root), model,
		ollama_base_url=settings.ollama_base_url, model_mode=settings.model_mode,
		max_iterations=settings.max_iterations, max_tool_calls=settings.max_tool_calls,
	)


async def _main():
	parser = argparse.ArgumentParser()
	parser.add_argument('task', nargs='?', default='Read the inspection report and generate an approval note citing the applicable SOP.')
	parser.add_argument('--approval', action='store_true')
	parser.add_argument('--report', type=Path, help='Ingest an XLSX workbook and generate a local DOCX and JSON report.')
	parser.add_argument('--knowledge-transfer', type=Path, nargs='+', help='Ingest documents and generate a consolidated knowledge-transfer DOCX and JSON report.')
	parser.add_argument('--output-dir', type=Path, default=Path('workspace/reports'))
	args = parser.parse_args()

	store = Store(settings.database_url)
	workspace = Workspace(settings.workspace_root)
	rag = TieredRagService(settings.tier_database_urls, settings.ollama_base_url, settings.ollama_embedding_model, settings.ollama_vision_model)

	if args.report:
		indexed = await rag.ingest(args.report, CLI_IDENTITY, None, {'source_type': 'workbook'})
		result = write_workbook_report(args.report, args.output_dir)
		result['index'] = indexed
		print(json.dumps(result, indent=2, default=str))
		return

	if args.knowledge_transfer:
		indexed = []
		for path in args.knowledge_transfer:
			indexed.append(await rag.ingest(path, CLI_IDENTITY, None, {'source_type': 'knowledge_transfer'}))
		result = write_knowledge_transfer_report(args.knowledge_transfer, args.output_dir, rag.extract)
		result['index'] = indexed
		print(json.dumps(result, indent=2, default=str))
		return

	service = _service(store, workspace, rag)
	job_id = uuid.uuid4().hex
	job = {
		'job_id': job_id, 'status': 'queued', 'task': args.task,
		'user_context': {**CLI_IDENTITY, 'department': 'inspection', 'project': 'demo', 'requested_role': 'approver_demo' if args.approval else 'user'},
		'routing': None, 'plan': [], 'tool_calls': [], 'observations': [], 'verification': None,
		'requires_human_approval': False, 'approval': None, 'artifacts': [], 'final_answer': None, 'error': None,
	}
	store.save(job)
	await service.run(job)
	completed = store.get(job_id)
	print(json.dumps(completed, indent=2, default=str))
	if completed['status'] == 'awaiting_approval':
		print(f'Approval required for job {job_id}.')


def _doctor(network_only=False, as_json=False):
	"""Local environment / connectivity / air-gap checks."""
	import httpx

	checks = []

	def add(name, ok, detail=''):
		checks.append({'check': name, 'ok': bool(ok), 'detail': detail})

	network = network_monitor.check()
	add('no_cloud_endpoint_configured', not network['cloud_endpoint_configured'],
	    'OLLAMA_CLOUD_ENDPOINT is set' if network['cloud_endpoint_configured'] else 'none')
	add('ollama_cloud_disabled', network['ollama_cloud_disabled'], f"OLLAMA_NO_CLOUD={network['ollama_cloud_disabled']}")
	add('egress_policy', True, network['egress_policy'])

	if not network_only:
		add('python_3_12+', sys.version_info[:2] >= (3, 12), sys.version.split()[0])
		for module in ('fastapi', 'httpx', 'docx', 'pptx', 'pymupdf', 'openpyxl', 'pytesseract', 'sqlalchemy', 'prometheus_client'):
			try:
				__import__(module)
				add(f'import:{module}', True)
			except Exception as exc:
				add(f'import:{module}', False, str(exc))
		add('tesseract_on_path', shutil.which('tesseract') is not None, shutil.which('tesseract') or 'not found')
		try:
			Store(settings.database_url); add('database_reachable', True, settings.database_url)
		except Exception as exc:
			add('database_reachable', False, str(exc))
		workspace_root = Path(settings.workspace_root)
		try:
			workspace_root.mkdir(parents=True, exist_ok=True)
			probe = workspace_root / '.doctor_probe'
			probe.write_text('ok'); probe.unlink()
			add('workspace_writable', True, str(workspace_root))
		except Exception as exc:
			add('workspace_writable', False, str(exc))
		if settings.model_mode.lower() == 'ollama':
			from urllib.parse import urlparse
			target = urlparse(settings.ollama_base_url)
			reachable = network_monitor.probe_local(target.hostname or '127.0.0.1', target.port or 11434)
			add('ollama_reachable', reachable, settings.ollama_base_url)
			if reachable:
				try:
					installed = {m['name'] for m in httpx.get(settings.ollama_base_url.rstrip('/') + '/api/tags', timeout=3).json().get('models', [])}
					installed |= {name.split(':', 1)[0] for name in installed}
					for want in (settings.ollama_model, settings.ollama_embedding_model, settings.ollama_vision_model):
						add(f'ollama_model:{want}', want in installed or want.split(':', 1)[0] in installed)
				except Exception as exc:
					add('ollama_models', False, str(exc))

	result = {'ok': all(c['ok'] for c in checks), 'checks': checks, 'network': network}
	if as_json:
		print(json.dumps(result, indent=2, default=str))
	else:
		for c in checks:
			print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['check']}" + (f"  ({c['detail']})" if c['detail'] else ''))
		print(f"\n{'OK' if result['ok'] else 'ISSUES FOUND'}")
	return 0 if result['ok'] else 1


def main():
	if len(sys.argv) > 1 and sys.argv[1] == 'doctor':
		flags = sys.argv[2:]
		sys.exit(_doctor(network_only='--network' in flags, as_json='--json' in flags))
	asyncio.run(_main())


if __name__ == '__main__':
	main()
