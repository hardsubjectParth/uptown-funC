import argparse
import asyncio
import json
from pathlib import Path
import uuid

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
	return Orchestrator(store, workspace, ModelRouter('config/models.yaml'), Policy(), ToolRegistry(workspace, rag), Verifier(settings.workspace_root), model)


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


def main():
	asyncio.run(_main())


if __name__ == '__main__':
	main()
