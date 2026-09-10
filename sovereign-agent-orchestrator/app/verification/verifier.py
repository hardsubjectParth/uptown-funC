import os
from pathlib import Path


class Verifier:
    def __init__(self, workspace_root=None):
        # Fall back to ./workspace only when no root is supplied. Passing the
        # configured WORKSPACE_ROOT keeps the artifact check correct when the
        # deployment stores job workspaces somewhere else.
        self._workspace_root = Path(workspace_root) if workspace_root else Path('workspace')
        self._require_evidence = os.getenv('REQUIRE_EVIDENCE', 'false').lower() in {'1', 'true', 'yes'}

    def verify(self, job):
        observations = job.get('observations', [])

        citations_present = any(
            (
                isinstance(x, dict)
                and (
                    bool(x.get('sources'))
                    or bool(x.get('citations'))
                    or any(
                        'source' in str(h).lower()
                        for h in x.get('hits', [])
                        if isinstance(h, dict)
                    )
                )
            )
            for x in observations
        )

        out = self._workspace_root / job['job_id'] / 'output'

        artifacts_exist = (
            bool(job.get('artifacts'))
            or (
                out.exists()
                and any(out.iterdir())
            )
        )

        retrieved_hits = [hit for observation in observations for hit in observation.get('hits', []) if isinstance(observation, dict) and isinstance(hit, dict)]
        checks = {
            'plan_completed': all(
                x.get('status') == 'done'
                for x in job.get('plan', [])
            ),

            'citations_present': (
                citations_present
                or job.get('task_type') != 'document_workflow'
            ),

            'citation_sources_valid': all(bool(hit.get('chunk_id')) and bool(hit.get('source')) for hit in retrieved_hits),

            'artifacts_exist': artifacts_exist,

            'no_unhandled_denials': not any(
                x.get('policy_decision') == 'deny'
                for x in job.get('tool_calls', [])
            ),
        }

        # Whether the answer is backed by retrieved evidence. Always reported so an
        # ungrounded artifact is visible; only blocks delivery when REQUIRE_EVIDENCE is
        # set, because some task types legitimately have no corpus to ground against.
        checks['evidence_grounded'] = (
            bool(job.get('retrieval'))
            or job.get('task_type') not in {'document_workflow', 'multimodal'}
        )

        # Advisory only, never blocking: a legitimate SOP can quote an instruction, so a
        # match flags the artifact for human review rather than failing the job. Stays
        # True until prompt-injection screening populates injection_findings.
        checks['no_injection_detected'] = not job.get('injection_findings')

        blocking = {
            name: value for name, value in checks.items()
            if name != 'no_injection_detected'
            and (name != 'evidence_grounded' or self._require_evidence)
        }
        passed = all(blocking.values())

        return {
            'passed': passed,
            'checks': checks,
            'notes': (
                []
                if passed
                else ['Verification gate blocked delivery.']
            ),
        }
