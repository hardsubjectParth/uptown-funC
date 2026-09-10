
import re
import yaml
from pathlib import Path


class ModelRouter:
    def __init__(self, path='config/models.yaml'):
        data = yaml.safe_load(Path(path).read_text()) if Path(path).exists() else {'models': []}
        self.models = data['models']

    def route(self, task):
        coding = bool(re.search(r'\b(code|coding|python|function|program|test)\b', task, re.I))
        vision = bool(re.search(r'\b(image|scan|drawing|photo|P&ID)\b', task, re.I))
        document = bool(re.search(r'\b(document|approval|report|inspection|docx|artifact)\b', task, re.I))

        if coding:
            task_type = 'coding'
        elif vision:
            task_type = 'multimodal'
        elif document:
            task_type = 'document_workflow'
        else:
            task_type = 'general'

        capability = 'coding' if coding else 'vision' if vision else 'document' if document else 'reasoning'
        preferred = {'coding': 'qwen-coder', 'vision': 'qwen-vision', 'document': 'qwen-quality', 'reasoning': 'qwen-fast'}[capability]
        enabled = [model for model in self.models if model.get('enabled') and 'embedding' not in model.get('capabilities', [])]
        model = next((item for item in enabled if item['id'] == preferred), None)
        if model is None:
            model = next((item for item in enabled if capability in item.get('capabilities', [])), None)
        if model is None:
            model = enabled[0] if enabled else {
                'id': 'fake-model',
                'provider': 'fake',
                'model': 'fake',
                'capabilities': [],
            }

        return {
            'task_type': task_type,
            'model_id': model['id'],
            'model_name': model.get('model'),
            'tier': model.get('tier', 'default'),
            'confidence': 0.82 if task_type == 'multimodal' else 0.96,
            'reason': f'Capability match for {task_type}.',
            'fallback_model_id': next((item['id'] for item in enabled if item['id'] != model['id']), None),
        }
