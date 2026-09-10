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
