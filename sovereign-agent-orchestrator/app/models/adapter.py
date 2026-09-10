from typing import Protocol
import httpx
import json
import re


class ModelAdapter(Protocol):
    async def chat(self, messages, tools=None, **kwargs):
        ...


_CODE_HINT = re.compile(r'\b(cod(?:e|ing)|python|function|script|program|implement|algorithm|unit test)\b', re.I)
_CALC_HINT = re.compile(r'\b(calculat|comput|estimat|sizing|how many|what is the|convert)\b', re.I)


class FakeModel:
    """Deterministic stand-in used by the tests and by ``MODEL_MODE=fake``.

    It never calls a model server. The reply is shaped to the task so the whole
    pipeline -- including the coding/sandbox path -- can be exercised offline:
    a coding task gets a runnable fenced Python block, a calculation task gets a
    worked answer, everything else gets a short document body.
    """

    model = 'fake'
    url = 'fake://local'

    async def chat(self, messages, tools=None, **kwargs):
        task = ''
        for message in messages:
            if message.get('role') == 'user':
                task = str(message.get('content', ''))
        if _CODE_HINT.search(task):
            return {'content': (
                'Here is a small, self-contained solution.\n\n'
                '```python\n'
                'def add(a, b):\n'
                '    """Return the sum of two numbers."""\n'
                '    return a + b\n\n\n'
                'if __name__ == "__main__":\n'
                '    assert add(2, 3) == 5\n'
                '    print("add(2, 3) =", add(2, 3))\n'
                '```\n\n'
                'The block above defines `add` and checks it with an assertion.'
            )}
        if _CALC_HINT.search(task):
            return {'content': (
                'Worked solution:\n'
                '1. Identify the quantities given in the task.\n'
                '2. Apply the relevant formula step by step.\n'
                '3. State the result with units.\n\n'
                'Result: (deterministic stub -- run with a real local model for a real figure).'
            )}
        return {'content': 'Use the registered document tools and produce a verified artifact.'}


class OllamaAdapter:
    def __init__(self, base_url, model):
        self.base_url = base_url.rstrip('/')
        self.url = self.base_url + '/api/chat'
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
