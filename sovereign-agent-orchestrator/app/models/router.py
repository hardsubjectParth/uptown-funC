import re
import yaml
from pathlib import Path


# Fine-grained task classes, matched against `task_types` in the model registry.
_PATTERNS = [
    ('coding', re.compile(r'\b(cod(?:e|ing)|program(?:ming)?|python|java(?:script)?|golang|rust|'
                          r'function|refactor|debug|bug|stack ?trace|unit ?test|test ?case|pytest|'
                          r'compile|script|regex|api endpoint)\b', re.I)),
    ('ocr', re.compile(r'\b(image|images|scan|scanned|drawing|drawings|photo|photograph|picture|'
                       r'figure|diagram|p&id|pid|ocr|handwritten|blueprint|screenshot)\b', re.I)),
    ('summarization', re.compile(r'\b(summari[sz]e|summari[sz]ation|summary|tl;dr|abstract|digest|recap)\b', re.I)),
    ('analysis', re.compile(r'\b(analy[sz]e|analy[sz]is|assess|evaluate|compare|comparison|breakdown|insight)\b', re.I)),
    ('approval_note', re.compile(r'\b(document|approval|approve|report|inspection|sop|docx|artifact|'
                                 r'memo|note|policy|certificate|compliance|audit|clause)\b', re.I)),
    ('planning', re.compile(r'\b(plan|planning|roadmap|steps|strategy|outline)\b', re.I)),
]

# Fine-grained class -> orchestrator workflow type (drives Orchestrator._plan).
_WORKFLOW = {
    'coding': 'coding',
    'ocr': 'multimodal',
    'summarization': 'document_workflow',
    'analysis': 'document_workflow',
    'approval_note': 'document_workflow',
    'planning': 'general',
    'general': 'general',
}

_CONFIDENCE = {'multimodal': 0.82, 'coding': 0.88}

_FAKE = {'id': 'fake-model', 'model_alias': None}


class ModelRouter:
    def __init__(self, path='config/model_registry.yaml'):
        data = yaml.safe_load(Path(path).read_text()) if Path(path).exists() else {'models': []}
        self.models = data.get('models') or []
        self.by_task = {}
        for entry in self.models:
            for task in entry.get('task_types', []):
                self.by_task.setdefault(task, entry)

    def classify(self, task):
        for name, pattern in _PATTERNS:
            if pattern.search(task or ''):
                return name
        return 'general'

    async def classify_with_model(self, task, adapter, alias='router'):
        """Classify with the small `router` model, falling back to regex.

        Regex misses paraphrases ("check this handwriting" is OCR without the
        word "scan"). Any failure — unreachable model, unknown label, timeout —
        returns the regex answer, so routing never depends on the model being up.
        """
        labels = sorted(self.by_task)
        if not labels or adapter is None:
            return self.classify(task), 'regex'
        messages = [
            {'role': 'system',
             'content': 'You classify tasks. Reply with exactly one label from the '
                        'provided list and nothing else.'},
            {'role': 'user',
             'content': f'Labels: {", ".join(labels)}\n\nTask: {task}\n\nLabel:'},
        ]
        try:
            response = await adapter.chat(messages, model=alias, max_tokens=16, temperature=0)
            answer = (response.get('content') or '').strip().lower()
            answer = re.sub(r'[^a-z_]', '', answer.split()[0]) if answer.split() else ''
            if answer in self.by_task:
                return answer, 'model'
        except Exception:
            pass
        return self.classify(task), 'regex'

    def _entry_for(self, registry_task):
        return (
            self.by_task.get(registry_task)
            or self.by_task.get('planning')
            or self.by_task.get('general')
            or (self.models[0] if self.models else _FAKE)
        )

    def route(self, task, registry_task=None, classifier='regex'):
        registry_task = registry_task or self.classify(task)
        workflow_type = _WORKFLOW.get(registry_task, 'general')

        model = self._entry_for(registry_task)
        fallback = next(
            (m for m in (self.by_task.get('planning'), self.by_task.get('general'), self.by_task.get('classification'))
             if m and m.get('id') != model.get('id')),
            None,
        )

        return {
            'task_type': workflow_type,
            'registry_task': registry_task,
            'model_id': model.get('id', 'fake-model'),
            'model_alias': model.get('model_alias'),
            'tier': model.get('id', 'default'),
            'confidence': _CONFIDENCE.get(workflow_type, 0.9),
            'classifier': classifier,
            'reason': f'Classified as {registry_task} by {classifier}; '
                      f'routed to {model.get("model_alias") or "fake"}.',
            'fallback_model_id': fallback.get('id') if fallback else None,
            'fallback_alias': fallback.get('model_alias') if fallback else None,
        }
