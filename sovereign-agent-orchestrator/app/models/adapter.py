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

    def __init__(self, base_url, api_key='', default_model='reasoner'):
        self.base_url = base_url.rstrip('/')
        self.url = self.base_url + '/chat/completions'
        self.api_key = api_key
        self.default_model = default_model
        # Surfaced for logging / document provenance.
        self.model = default_model

    async def chat(self, messages, tools=None, model=None, **kwargs):
        payload = {
            'model': model or self.default_model,
            'messages': messages,
            'stream': False,
        }
        if tools:
            payload['tools'] = tools
        for key in ('temperature', 'top_p', 'max_tokens'):
            if key in kwargs:
                payload[key] = kwargs[key]

        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        async with httpx.AsyncClient(timeout=kwargs.get('timeout', 120)) as c:
            r = await c.post(self.url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        message = (data.get('choices') or [{}])[0].get('message', {})
        return {
            'role': message.get('role', 'assistant'),
            'content': message.get('content') or '',
            'tool_calls': message.get('tool_calls'),
            'model': data.get('model', payload['model']),
            'usage': data.get('usage'),
        }
