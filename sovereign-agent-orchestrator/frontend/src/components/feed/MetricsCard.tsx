import type { Job } from '../../types/api'
import MetricRow from '../shared/MetricRow'

// Every row here comes from a real field on the job object -- no fabricated numbers
// like the spec's illustrative copy ("4.2M tokens", "0.002 J/tok"), since this
// backend doesn't expose token/energy telemetry.
function MetricsCard({ job }: { job: Job }) {
  const rows: Array<[string, string]> = []
  if (job.routing) {
    rows.push(['Routed Model', job.routing.model_name || job.routing.model_id])
    rows.push(['Routing Confidence', `${Math.round(job.routing.confidence * 100)}%`])
  }
  if (job.verification) {
    const checks = Object.values(job.verification.checks)
    const passed = checks.filter(Boolean).length
    rows.push(['Verification', `${passed}/${checks.length} checks passed`])
  }
  if (job.artifacts.length) rows.push(['Artifacts Generated', String(job.artifacts.length)])
  if (job.retrieval?.length) rows.push(['Evidence Retrieved', `${job.retrieval.length} source${job.retrieval.length === 1 ? '' : 's'}`])

  if (!rows.length) return null

  return (
    <div className="border-hairline mt-3 bg-surface px-4 py-3">
      <p className="label-micro">Intelligence Synthesis</p>
      <div className="mt-2">
        {rows.map(([label, value], index) => <MetricRow key={label} label={label} value={value} index={index} />)}
      </div>
    </div>
  )
}

export default MetricsCard
