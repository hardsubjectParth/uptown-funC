from typing import Protocol
import httpx
import json


class ModelAdapter(Protocol):
    async def chat(self, messages, tools=None, **kwargs):
        ...


class FakeModel:
    async def chat(self, messages, tools=None, **kwargs):
        return {
            'content': 'Use the registered document tools and produce a verified artifact.'
        }


class OllamaAdapter:
    def __init__(self, base_url, model):
        self.url = base_url.rstrip('/') + '/api/chat'
        self.model = model

    async def chat(self, messages, tools=None, **kwargs):
        payload = {
            'model': self.model,
            'messages': messages,
            'stream': False
        }

        if tools:
            payload['tools'] = tools

        # Convert UUID and other non-JSON-native objects to strings
        payload = json.loads(json.dumps(payload, default=str))

        async with httpx.AsyncClient(
            timeout=kwargs.get('timeout', 120)
        ) as c:
            r = await c.post(
                self.url,
                json=payload
            )
            r.raise_for_status()
            return r.json()['message']