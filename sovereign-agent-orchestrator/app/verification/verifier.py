from pathlib import Path


class Verifier:
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

        out = (
            Path('workspace')
            / job['job_id']
            / 'output'
        )

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

        passed = all(checks.values())

        return {
            'passed': passed,
            'checks': checks,
            'notes': (
                []
                if passed
                else ['Verification gate blocked delivery.']
            ),
        }
