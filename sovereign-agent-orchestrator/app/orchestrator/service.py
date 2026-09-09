import asyncio
import uuid
from datetime import datetime, timezone
from typing import TypedDict, Any

try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    START = '__start__'
    END = '__end__'

    class StateGraph:
        def __init__(self, state_type):
            self.node = None

        def add_node(self, name, fn):
            self.node = fn

        def add_edge(self, *args):
            pass

        def compile(self):
            node = self.node

            class Graph:
                async def ainvoke(self, state):
                    return await node(state)

            return Graph()

from app.schemas.contracts import JobStatus


class State(TypedDict, total=False):
    job: dict


class Orchestrator:
    def __init__(
        self,
        store,
        workspace,
        router,
        policy,
        tools,
        verifier,
        model,
    ):
        self.store = store
        self.workspace = workspace
        self.router = router
        self.policy = policy
        self.tools = tools
        self.verifier = verifier
        self.model = model
        self.tasks = {}
        self.graph = self._build_graph()

    def _emit(self, j, t, data=None):
        self.store.event(j['job_id'], t, data or {})
        self.store.save(j)

    def _status(self, j, s):
        j['status'] = s.value
        self._emit(j, 'status_changed', {'status': s.value})

    async def _call_model(self, j):
        context = ''
        if getattr(self.tools, 'rag', None):
            user_context = j.get('user_context', {})
            attached_ids = [item['file_id'] for item in j.get('attachments', []) if item.get('file_id')]
            allowed_ids = attached_ids or self.store.accessible_file_ids(user_context)
            hits = await self.tools.rag.search(j['task'], 8, {'tenant_id': user_context.get('tenant_id', 'default'), 'clearance': user_context.get('clearance', 'internal')}, allowed_ids)
            j['retrieval'] = hits
            j['citations'] = hits
            if hits:
                j['observations'].append({'hits': hits, 'sources': [{'name': hit['source'], 'source': hit['source']} for hit in hits]})
            context = '\n\nRetrieved company evidence:\n' + '\n'.join(
                f"[{hit['source']}] {hit['content']}" for hit in hits
            ) if hits else '\n\nNo indexed company evidence matched this task.'
        messages = [
            {
                'role': 'system',
                'content': (
                    'You are the local planning model for the Sovereign Agent '
                    'Orchestrator. Analyze the task and provide a concise plan. '
                    'Use conversation history and retrieved evidence when provided. '
                    'For factual claims, cite evidence using [source] markers. '
                    'If the evidence is insufficient, say so explicitly. '
                    'Do not claim to have accessed files unless they are provided '
                    'through the orchestrator tools.'
                ),
            },
        ]
        if j.get('conversation_id'):
            history = self.store.messages(j['conversation_id'], 20)
            if history and history[-1]['role'] == 'user' and history[-1]['content'] == j['task']:
                history = history[:-1]
            messages.extend({'role': item['role'], 'content': item['content']} for item in history)
        messages.append({'role': 'user', 'content': j['task'] + context})

        response = await self.model.chat(messages)

        j['model_response'] = response
        if j.get('conversation_id'):
            self.store.add_message(str(uuid.uuid4()), j['conversation_id'], 'assistant', response.get('content', str(response)), j.get('retrieval', []))

        self._emit(
            j,
            'model_response',
            {
                'model_id': j['routing']['model_id'],
                'response': response,
            },
        )

        return response

    def _plan(self, j):
        task = j['task']
        task_type = j.get('routing', {}).get('task_type')
        model_content = j.get('model_response', {}).get('content', '')

        # General conversational tasks do not need tools or document generation.
        if task_type == 'general':
            j['plan'] = []
            return

        # Use the actual local model response as the document content.
        # The model is instructed not to invent file access or external facts.
        document_body = model_content.strip()

        if not document_body:
            document_body = (
                'The local model returned no document content. '
                'Task: ' + task
            )

        model_name = getattr(self.model, 'model', 'unknown')
        model_url = getattr(self.model, 'url', 'unknown')
        allowed_file_ids = [item['file_id'] for item in j.get('attachments', []) if item.get('file_id')]
        if not allowed_file_ids:
            allowed_file_ids = self.store.accessible_file_ids(j.get('user_context', {}))

        steps = [
            {
                'step_id': 's1',
                'description': 'Inspect available input evidence',
                'tool': 'search_documents',
                'tool_args': {
                    'query': '',
                    'metadata': {'tenant_id': j.get('user_context', {}).get('tenant_id', 'default'), 'clearance': j.get('user_context', {}).get('clearance', 'internal')},
                    'file_ids': allowed_file_ids
                },
                'status': 'pending',
            },
            {
                'step_id': 's2',
                'description': 'Generate the requested document artifact',
                'tool': 'generate_docx',
                'tool_args': {
                    'filename': 'sovereign_agent_local_llm.docx',
                    'title': 'Sovereign Agent Orchestrator and Local Ollama LLM',
                    'sections': [
                        {
                            'heading': 'Task',
                            'body': task,
                        },
                        {
                            'heading': 'Model',
                            'body': model_name,
                        },
                        {
                            'heading': 'Ollama Endpoint',
                            'body': model_url,
                        },
                        {
                            'heading': 'Local Model Response',
                            'body': document_body,
                        },
                        {
                            'heading': 'How the Local Model Is Invoked',
                            'body': (
                                'The Sovereign Agent Orchestrator invokes the '
                                'configured Ollama model through its local HTTP API. '
                                'The model adapter sends the task as chat messages '
                                'to the Ollama /api/chat endpoint and receives the '
                                'model response locally.'
                            ),
                        },
                    ],
                    'citations': [
                        f'Configured local model: {model_name}',
                        f'Configured Ollama endpoint: {model_url}',
                        'Local invocation path: OllamaAdapter -> /api/chat',
                    ],
                },
                'status': 'pending',
            },
        ]

        j['plan'] = steps

    def _build_graph(self):
        g = StateGraph(State)

        async def workflow(state):
            await self._run_impl(state['job'])
            return state

        g.add_node('ORCHESTRATOR', workflow)
        g.add_edge(START, 'ORCHESTRATOR')
        g.add_edge('ORCHESTRATOR', END)

        return g.compile()

    async def run(self, j):
        await self.graph.ainvoke({'job': j})

    async def _run_impl(self, j):
        self.workspace.create(j['job_id'])

        self._status(j, JobStatus.planning)

        # Select the logical model.
        j['routing'] = self.router.route(j['task'])

        # Keep the top-level task_type synchronized with routing.
        j['task_type'] = j['routing']['task_type']

        self._emit(
            j,
            'model_selected',
            j['routing'],
        )

        # Actually invoke the configured model adapter.
        try:
            await self._call_model(j)
        except Exception as exc:
            j['error'] = f'Model invocation failed: {exc}'
            self._emit(
                j,
                'model_error',
                {
                    'error': str(exc),
                    'model_id': j['routing']['model_id'],
                },
            )
            self._status(j, JobStatus.failed)
            return

        self._plan(j)

        self._emit(
            j,
            'plan_created',
            {
                'steps': j['plan']
            },
        )

        # General tasks are complete after the local model responds.
        if j.get('routing', {}).get('task_type') == 'general':
            j['final_answer'] = j['model_response'].get(
                'content',
                str(j['model_response']),
            )

            self._status(j, JobStatus.done)

            self._emit(
                j,
                'job_completed',
                {
                    'final_answer': j['final_answer']
                },
            )

            return

        for step in j['plan']:
            self._status(j, JobStatus.acting)

            self._emit(
                j,
                'step_started',
                {
                    'step_id': step['step_id']
                },
            )

            decision = self.policy.check(
                step['tool'],
                j['user_context'],
            )

            tc = {
                'call_id': str(uuid.uuid4()),
                'tool': step['tool'],
                'risk_tier': self.policy.risks.get(
                    step['tool'],
                    99,
                ),
                'policy_decision': decision.decision.value,
                'success': None,
                'result_summary': decision.reason,
            }

            j['tool_calls'].append(tc)

            self._emit(
                j,
                'tool_started',
                tc,
            )

            if decision.decision.value == 'deny':
                tc['success'] = False
                j['error'] = decision.reason
                self._status(j, JobStatus.failed)
                return

            if decision.decision.value == 'require_approval':
                j['requires_human_approval'] = True

                j['approval'] = {
                    'risk_tier': tc['risk_tier'],
                    'reason': decision.reason,
                    'pending_tool': step['tool'],
                    'pending_args': step['tool_args'],
                }

                self._status(
                    j,
                    JobStatus.awaiting_approval,
                )

                self._emit(
                    j,
                    'approval_required',
                    j['approval'],
                )

                return

            result = self.tools.execute(
                j['job_id'],
                step['tool'],
                step['tool_args'],
            )

            tc['success'] = True
            tc['result_summary'] = str(result)[:300]

            step['status'] = 'done'

            j['observations'].append(result)

            self._emit(
                j,
                'tool_completed',
                {
                    'call_id': tc['call_id'],
                    'result': result,
                },
            )

            self._emit(
                j,
                'step_completed',
                {
                    'step_id': step['step_id']
                },
            )

        self._status(j, JobStatus.observing)

        self._emit(
            j,
            'observation',
            {
                'summary': 'Tool outputs collected.'
            },
        )

        self._status(j, JobStatus.verifying)

        j['artifacts'] = self._artifacts(j)

        v = self.verifier.verify(j)

        j['verification'] = v

        self._emit(
            j,
            'verification_passed' if v['passed'] else 'verification_failed',
            v,
        )

        if not v['passed']:
            j['error'] = 'Verification failed'
            self._status(j, JobStatus.failed)
            return

        self._status(j, JobStatus.delivering)

        j['final_answer'] = (
            'Completed the requested workflow. '
            'The verified artifact is available through the artifact API.'
        )

        self._emit(
            j,
            'artifact_created',
            {
                'artifacts': j['artifacts']
            },
        )

        self._status(j, JobStatus.done)

        self._emit(
            j,
            'job_completed',
            {
                'final_answer': j['final_answer']
            },
        )

    def _artifacts(self, j):
        out = self.workspace.root / j['job_id'] / 'output'
        result = []

        for p in out.glob('*'):
            if p.is_file():
                result.append(
                    {
                        'artifact_id': str(uuid.uuid4()),
                        'name': p.name,
                        'mime_type': (
                            'application/vnd.openxmlformats-officedocument'
                            '.wordprocessingml.document'
                            if p.suffix == '.docx'
                            else 'application/octet-stream'
                        ),
                        'size_bytes': p.stat().st_size,
                        'url': (
                            f"/api/v1/agent/{j['job_id']}"
                            f"/artifacts/{p.name}"
                        ),
                    }
                )

        return result

    async def resume(self, j, approved, reviewer):
        self.store.approval(
            j['job_id'],
            approved,
            reviewer,
        )

        j['approval']['reviewer_user_id'] = reviewer
        j['approval']['approved'] = approved

        if not approved:
            j['requires_human_approval'] = False
            j['error'] = 'APPROVAL_REJECTED'

            self._status(
                j,
                JobStatus.failed,
            )

            self._emit(
                j,
                'approval_rejected',
                j['approval'],
            )

            return

        j['requires_human_approval'] = False

        self._emit(
            j,
            'approval_approved',
            j['approval'],
        )

        pending = j['approval']['pending_tool']
        args = j['approval']['pending_args']

        self._status(
            j,
            JobStatus.acting,
        )

        result = self.tools.execute(
            j['job_id'],
            pending,
            args,
        )

        j['observations'].append(result)

        j['plan'][-1]['status'] = 'done'

        self._emit(
            j,
            'tool_completed',
            {
                'tool': pending,
                'result': result,
            },
        )

        self._status(
            j,
            JobStatus.verifying,
        )

        v = self.verifier.verify(j)

        j['verification'] = v

        self._emit(
            j,
            'verification_passed' if v['passed'] else 'verification_failed',
            v,
        )

        if not v['passed']:
            j['error'] = 'Verification failed'
            self._status(j, JobStatus.failed)
            return

        self._status(
            j,
            JobStatus.delivering,
        )

        j['artifacts'] = self._artifacts(j)

        j['final_answer'] = (
            'Completed after explicit human approval.'
        )

        self._emit(
            j,
            'artifact_created',
            {
                'artifacts': j['artifacts']
            },
        )

        self._status(
            j,
            JobStatus.done,
        )

        self._emit(
            j,
            'job_completed',
            {}
        )

