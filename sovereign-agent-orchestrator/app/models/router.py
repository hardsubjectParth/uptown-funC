
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

        preferred = 'general-local' if coding else 'hermes-agent'

        model = next(
            (
                m for m in self.models
                if m['id'] == preferred and m.get('enabled')
            ),
            self.models[0] if self.models else {
                'id': 'fake-model',
                'provider': 'fake',
                'model': 'fake'
            }
        )

        return {
            'task_type': task_type,
            'model_id': model['id'],
            'confidence': 0.82 if task_type == 'multimodal' else 0.96,
            'reason': f'Capability match for {task_type}.',
            'fallback_model_id': 'hermes-agent' if model['id'] != 'hermes-agent' else None
        }
