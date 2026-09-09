from typing import Protocol

import httpx


class ModelAdapter(Protocol):
    async def chat(self, messages, tools=None, **kwargs): ...


class FakeModel:
    model = 'fake'
    url = 'fake://local'

    async def chat(self, messages, tools=None, **kwargs):
        return {'content': 'Use the registered document tools and produce a verified artifact.'}


class OllamaAdapter:
    """Legacy adapter for Ollama's proprietary /api/chat endpoint. Kept for
    reference; the supported path is OpenAICompatibleAdapter + llama-swap."""

    def __init__(self, base_url, model):
        self.url = base_url.rstrip('/') + '/api/chat'
        self.model = model

    async def chat(self, messages, tools=None, **kwargs):
        payload = {'model': kwargs.get('model') or self.model, 'messages': messages, 'stream': False}
        if tools:
            payload['tools'] = tools
        async with httpx.AsyncClient(timeout=kwargs.get('timeout', 30)) as c:
            r = await c.post(self.url, json=payload)
            r.raise_for_status()
            return r.json()['message']


class OpenAICompatibleAdapter:
    """Talks to any OpenAI-compatible /v1 endpoint.

    The concrete model is chosen per call via ``model=<alias>`` (the Router
    picks a different alias per job); llama-swap loads/evicts the backing
    llama.cpp model for that alias on demand.
    """

    def __init__(self, base_url, api_key='', default_model='reasoner',
                 enable_thinking=False, max_tokens=2048):
        self.base_url = base_url.rstrip('/')
        self.url = self.base_url + '/chat/completions'
        self.api_key = api_key
        self.default_model = default_model
        # Qwen3.5/3.6 are thinking models: with thinking on they emit the chain of
        # thought into `reasoning_content` and only then fill `content`. If the
        # token budget runs out mid-thought, `content` comes back EMPTY. The
        # pipeline wants the answer, not the reasoning, so thinking is off by
        # default; turn it on per call with think=True and a large max_tokens.
        self.enable_thinking = enable_thinking
        self.max_tokens = max_tokens
        # Surfaced for logging / document provenance.
        self.model = default_model

    async def chat(self, messages, tools=None, model=None, think=None, **kwargs):
        payload = {
            'model': model or self.default_model,
            'messages': messages,
            'stream': False,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }
        if tools:
            payload['tools'] = tools
        for key in ('temperature', 'top_p'):
            if key in kwargs:
                payload[key] = kwargs[key]

        thinking = self.enable_thinking if think is None else think
        if not thinking:
            # Honoured by llama.cpp when llama-server runs with --jinja.
            payload['chat_template_kwargs'] = {'enable_thinking': False}

        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        async with httpx.AsyncClient(timeout=kwargs.get('timeout', 300)) as c:
            r = await c.post(self.url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        choice = (data.get('choices') or [{}])[0]
        message = choice.get('message', {})
        content = message.get('content') or ''
        reasoning = message.get('reasoning_content') or ''
        finish = choice.get('finish_reason')

        if not content and finish == 'length' and reasoning:
            raise RuntimeError(
                'MODEL_TRUNCATED_WHILE_THINKING: the model used the whole token '
                f'budget ({payload["max_tokens"]}) on reasoning and returned no '
                'answer. Raise max_tokens or disable thinking.'
            )

        return {
            'role': message.get('role', 'assistant'),
            'content': content,
            'reasoning_content': reasoning,
            'finish_reason': finish,
            'tool_calls': message.get('tool_calls'),
            'model': data.get('model', payload['model']),
            'usage': data.get('usage'),
        }
