import asyncio
import re
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
        use_model_router=False,
        router_alias='router',
    ):
        self.store = store
        self.workspace = workspace
        self.router = router
        self.policy = policy
        self.tools = tools
        self.verifier = verifier
        self.model = model
        self.use_model_router = use_model_router
        self.router_alias = router_alias
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
            hits = await self.tools.rag.search(j['task'], 5, {'tenant_id': j.get('user_context', {}).get('tenant_id', 'default'), 'clearance': j.get('user_context', {}).get('clearance', 'internal')})
            j['retrieval'] = hits
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
                    'Do not claim to have accessed files unless they are provided '
                    'through the orchestrator tools.'
                ),
            },
            {
                'role': 'user',
                'content': j['task'] + context,
            },
        ]

        routing = j.get('routing', {})
        try:
            response = await self.model.chat(messages, model=routing.get('model_alias'))
        except Exception as exc:
            fallback = routing.get('fallback_alias')
            if not fallback:
                raise
            self._emit(j, 'model_fallback', {'from': routing.get('model_alias'), 'to': fallback, 'error': str(exc)})
            response = await self.model.chat(messages, model=fallback)
            j['routing']['model_alias_used'] = fallback

        j['model_response'] = response

        self._emit(
            j,
            'model_response',
            {
                'model_id': j['routing']['model_id'],
                'response': response,
            },
        )

        return response

    @staticmethod
    def _evidence(j):
        """Citations for the documents actually retrieved for this job.

        A compliance artifact must cite the evidence it relied on, not the model
        that wrote it. When retrieval returned nothing, say so explicitly rather
        than leaving a References section that implies grounding.
        """
        hits = j.get('retrieval') or []
        if not hits:
            return ['NO INDEXED EVIDENCE MATCHED THIS TASK. The content below is not '
                    'grounded in retrieved company documents and must not be treated '
                    'as evidence-backed.']
        citations = []
        for hit in hits:
            source = hit.get('source') or 'unknown source'
            chunk = str(hit.get('chunk_id') or '')[:8]
            score = hit.get('score')
            detail = f'chunk {chunk}' if chunk else 'chunk unknown'
            if isinstance(score, (int, float)):
                detail += f', retrieval score {score:.4f}'
            citations.append(f'{source} ({detail})')
        return citations

    # Fenced code block: ```lang\n...\n```
    _FENCE = re.compile(r'```([A-Za-z0-9_+-]*)\n(.*?)```', re.S)

    _EXTENSIONS = {
        'python': '.py', 'py': '.py', 'javascript': '.js', 'js': '.js',
        'typescript': '.ts', 'ts': '.ts', 'bash': '.sh', 'sh': '.sh',
        'sql': '.sql', 'yaml': '.yaml', 'yml': '.yaml', 'json': '.json',
        'java': '.java', 'go': '.go', 'rust': '.rs', 'rs': '.rs', 'c': '.c',
        'cpp': '.cpp', 'html': '.html', 'css': '.css',
    }

    @classmethod
    def _code_blocks(cls, text):
        """Extract fenced code blocks from a model response."""
        blocks = []
        for language, body in cls._FENCE.findall(text or ''):
            body = body.strip('\n')
            if body.strip():
                blocks.append((language.lower(), body))
        return blocks

    def _coding_plan(self, j, task, model_content):
        """Write the model's code to source files instead of a .docx.

        Falls back to a single .md transcript when the response contains no
        fenced code, so the work is never silently lost.
        """
        blocks = self._code_blocks(model_content)
        steps = []

        if not blocks:
            steps.append({
                'step_id': 's1',
                'description': 'Save the model response (no fenced code found)',
                'tool': 'write_file',
                'tool_args': {
                    'path': 'output/response.md',
                    'content': (model_content or '').strip()
                    or f'The local model returned no content. Task: {task}',
                },
                'status': 'pending',
            })
            return steps

        used = set()
        for index, (language, body) in enumerate(blocks, 1):
            suffix = self._EXTENSIONS.get(language, '.txt')
            name = f'snippet_{index}{suffix}'
            while name in used:
                index += 1
                name = f'snippet_{index}{suffix}'
            used.add(name)
            steps.append({
                'step_id': f's{len(steps) + 1}',
                'description': f'Write {language or "code"} block to {name}',
                'tool': 'write_file',
                'tool_args': {'path': f'output/{name}', 'content': body + '\n'},
                'status': 'pending',
            })

        # Keep the full response alongside the extracted files: the prose around
        # the code (assumptions, usage notes) is part of the deliverable.
        steps.append({
            'step_id': f's{len(steps) + 1}',
            'description': 'Save the full model response as a transcript',
            'tool': 'write_file',
            'tool_args': {'path': 'output/response.md', 'content': (model_content or '').strip()},
            'status': 'pending',
        })
        return steps

    def _plan(self, j):
        task = j['task']
        task_type = j.get('routing', {}).get('task_type')
        model_content = j.get('model_response', {}).get('content', '')

        # General conversational tasks do not need tools or document generation.
        if task_type == 'general':
            j['plan'] = []
            return

        # Coding tasks deliver source files, not an approval document.
        if task_type == 'coding':
            j['plan'] = self._coding_plan(j, task, model_content)
            return

        # Use the actual local model response as the document content.
        # The model is instructed not to invent file access or external facts.
        document_body = model_content.strip()

        if not document_body:
            document_body = (
                'The local model returned no document content. '
                'Task: ' + task
            )

        routing = j.get('routing', {})
        model_name = (
            routing.get('model_alias_used')
            or routing.get('model_alias')
            or j.get('model_response', {}).get('model')
            or getattr(self.model, 'model', 'unknown')
        )
        model_url = getattr(self.model, 'base_url', getattr(self.model, 'url', 'unknown'))

        # Reproduce the retrieved excerpts in the artifact so a reviewer can audit
        # the answer against its evidence without querying the index again.
        hits = j.get('retrieval') or []
        if hits:
            evidence_body = '\n\n'.join(
                f"[{index}] {hit.get('source', 'unknown source')} "
                f"(retrieval score {hit.get('score')}):\n{(hit.get('content') or '').strip()}"
                for index, hit in enumerate(hits, 1)
            )
        else:
            evidence_body = (
                'No indexed evidence matched this task. Nothing in this document is '
                'supported by retrieved company records, and it must not be relied on '
                'as an evidence-backed finding.'
            )

        steps = [
            {
                'step_id': 's1',
                'description': 'Inspect available input evidence',
                'tool': 'search_documents',
                'tool_args': {
                    'query': '',
                    'metadata': {'tenant_id': j.get('user_context', {}).get('tenant_id', 'default'), 'clearance': j.get('user_context', {}).get('clearance', 'internal')}
                },
                'status': 'pending',
            },
            {
                'step_id': 's2',
                'description': 'Generate the requested document artifact',
                'tool': 'generate_docx',
                'tool_args': {
                    'filename': 'sovereign_agent_local_llm.docx',
                    'title': 'Sovereign Agent Orchestrator and Local LLM',
                    'sections': [
                        {
                            'heading': 'Task',
                            'body': task,
                        },
                        {
                            'heading': 'Local Model Response',
                            'body': document_body,
                        },
                        {
                            'heading': 'Evidence Used',
                            'body': evidence_body,
                        },
                        {
                            'heading': 'Provenance',
                            'body': (
                                f'Model: {model_name} (routed for: '
                                f'{routing.get("registry_task", "general")})\n'
                                f'Inference endpoint: {model_url}\n'
                                'Invocation path: OpenAICompatibleAdapter -> '
                                '/v1/chat/completions -> llama-swap -> llama.cpp\n'
                                'All inference and retrieval ran locally.'
                            ),
                        },
                    ],
                    # References must cite the evidence the answer relied on, not
                    # the model that produced it. Provenance lives in its own
                    # section above.
                    'citations': self._evidence(j),
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
        if self.use_model_router:
            label, classifier = await self.router.classify_with_model(
                j['task'], self.model, self.router_alias)
            j['routing'] = self.router.route(j['task'], label, classifier)
        else:
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

        j['artifacts'] = self._artifacts(j)

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

