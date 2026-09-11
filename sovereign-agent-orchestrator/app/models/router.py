
import re
import yaml
from pathlib import Path

# Task classification is deterministic and ordered: the first pattern that matches
# wins. Order matters -- coding and multimodal are checked before the broader
# document/general buckets so "summarise the scanned drawing" routes to vision,
# not to the document workflow.
_PATTERNS = [
    ('coding', re.compile(r'\b(code|coding|python|javascript|typescript|golang|rust|function|program|programme|script|algorithm|refactor|debug|compile)\b|\bunit tests?\b', re.I)),
    ('multimodal', re.compile(r'\b(images?|scans?|scanned|drawings?|photos?|photograph|pictures?|figure|diagram|p&id|pid|ocr|handwritten|blueprint|screenshot)\b', re.I)),
    ('presentation', re.compile(r'\b(presentation|slides?|slide deck|deck|powerpoint|pptx)\b|\.ppt', re.I)),
    ('spreadsheet', re.compile(r'\b(spreadsheet|excel|xlsx|xlsm|workbook)\b|\bpivot table\b|\btabular\b', re.I)),
    ('calculation', re.compile(r'\bcalculat(?:e|es|ed|ing|ion|ions|or)\b|\bcomput(?:e|es|ed|ing|ation|ational)\b|\bestimat(?:e|es|ed|ing|ion)\b|\bsizing\b|\bload factor\b|\bflow rate\b|\bpressure drop\b|\bhow many\b|\bconvert\b.+\bto\b', re.I)),
    ('document_workflow', re.compile(r'\b(document|approval|reports?|inspection|docx|pdf|word file|artifact|summar\w*|memo|notes?|letter|minutes|briefing)\b', re.I)),
]

# task_type -> the model capability that should serve it.
_CAPABILITY = {
    'coding': 'coding',
    'multimodal': 'vision',
    'presentation': 'document',
    'spreadsheet': 'document',
    'calculation': 'reasoning',
    'document_workflow': 'document',
    'general': 'reasoning',
}

# Preferred registry id per capability; falls back to any enabled model that
# advertises the capability, then to the first enabled model.
_PREFERRED = {
    'coding': 'qwen-coder',
    'vision': 'qwen-vision',
    'document': 'qwen-quality',
    'reasoning': 'qwen-reasoning',
}


class ModelRouter:
    def __init__(self, path='config/models.yaml'):
        data = yaml.safe_load(Path(path).read_text()) if Path(path).exists() else {'models': []}
        self.models = data.get('models', [])

    def classify(self, task):
        for task_type, pattern in _PATTERNS:
            if pattern.search(task or ''):
                return task_type
        return 'general'

    def _enabled(self):
        return [m for m in self.models if m.get('enabled') and 'embedding' not in m.get('capabilities', [])]

    def route(self, task):
        task_type = self.classify(task)
        capability = _CAPABILITY[task_type]
        preferred = _PREFERRED.get(capability)

        enabled = self._enabled()
        model = next((m for m in enabled if m['id'] == preferred), None)
        if model is None:
            model = next((m for m in enabled if capability in m.get('capabilities', [])), None)
        if model is None:
            model = enabled[0] if enabled else {'id': 'fake-model', 'provider': 'fake', 'model': 'fake', 'capabilities': []}

        exact = model['id'] == preferred or capability in model.get('capabilities', [])
        return {
            'task_type': task_type,
            'model_id': model['id'],
            'model_name': model.get('model'),
            'provider': model.get('provider', 'fake'),
            'tier': model.get('tier', 'default'),
            'capability': capability,
            'confidence': (0.96 if exact else 0.7) - (0.1 if task_type == 'multimodal' else 0.0),
            'reason': (
                f'Classified as {task_type}; matched capability "{capability}" to model "{model["id"]}".'
                if exact else
                f'Classified as {task_type}; no model advertises "{capability}", fell back to "{model["id"]}".'
            ),
            'fallback_model_id': next((m['id'] for m in enabled if m['id'] != model['id']), None),
        }
