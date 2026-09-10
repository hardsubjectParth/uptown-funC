from pathlib import Path


class Verifier:
    def __init__(self, workspace=None, require_evidence=False):
        # Without a workspace the artifact check falls back to ./workspace, which
        # is only correct when the process runs from the repo root with the
        # default WORKSPACE_ROOT. Pass the Workspace so it honours the setting.
        self.workspace = workspace
        # When true, a job with no retrieved evidence fails verification instead
        # of merely being flagged.
        self.require_evidence = require_evidence

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

        root = self.workspace.root if self.workspace else Path('workspace')
        out = root / job['job_id'] / 'output'

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

        # Whether the answer is backed by retrieved evidence. Always reported so
        # an ungrounded artifact is visible; only blocks delivery when
        # REQUIRE_EVIDENCE is set, because some task types legitimately have no
        # corpus to ground against.
        grounded = bool(job.get('retrieval')) or job.get('task_type') not in {'document_workflow', 'multimodal'}
        checks['evidence_grounded'] = grounded
        # Reported, never blocking: a legitimate SOP can quote an instruction,
        # so this flags for human review rather than failing the job.
        checks['no_injection_detected'] = not job.get('injection_findings')

        blocking = {k: v for k, v in checks.items()
                    if k not in {'evidence_grounded', 'no_injection_detected'}
                    or (k == 'evidence_grounded' and self.require_evidence)}
        passed = all(blocking.values())

        notes = []
        if not passed:
            notes.append('Verification gate blocked delivery.')
        if not grounded:
            notes.append(
                'No retrieved evidence backed this job. The artifact is not '
                'evidence-backed'
                + (' and delivery was blocked (REQUIRE_EVIDENCE).' if self.require_evidence
                   else '; set REQUIRE_EVIDENCE=true to make this blocking.')
            )

        if job.get('injection_findings'):
            sources = ', '.join(sorted({f.get('source') or '?' for f in job['injection_findings']}))
            notes.append(
                f'Prompt-injection patterns detected in retrieved content ({sources}). '
                'The model was instructed to treat retrieved text as data; review '
                'the artifact before acting on it.'
            )

        return {
            'passed': passed,
            'checks': checks,
            'notes': notes,
        }
