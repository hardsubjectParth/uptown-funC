import { useState } from 'react'
import type { Job } from '../../types/api'
import { useAuth } from '../../context/AuthContext'
import { useApproveJob } from '../../hooks/useJob'

function ApprovalGate({ job, onResolved }: { job: Job; onResolved: () => void }) {
  const { user } = useAuth()
  const approve = useApproveJob(job.job_id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function decide(approved: boolean) {
    if (!user) return
    setBusy(true)
    setError(null)
    try {
      await approve(approved, user.id)
      onResolved()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to submit decision')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="border-hairline mt-4 rounded-2xl border-warning/35 bg-surface px-5 py-4">
      <p className="text-sm font-semibold text-foreground">Human approval required</p>
      <p className="label-micro mt-2">Action</p>
      <p className="text-sm text-foreground">{job.plan?.[job.plan.length - 1]?.description ?? 'Generate artifact'}</p>
      <p className="label-micro mt-2">Reason</p>
      <p className="text-sm text-foreground">{job.approval?.reason ?? 'This action is configured to require reviewer confirmation.'}</p>

      {error ? <p className="mt-2 text-xs text-danger">{error}</p> : null}

      <div className="mt-3 flex justify-end gap-2">
        <button type="button" disabled={busy} onClick={() => decide(false)} className="rounded-lg border border-white/12 px-4 py-2 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50">
          Reject
        </button>
        <button type="button" disabled={busy} onClick={() => decide(true)} className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary-hover disabled:opacity-50">
          Approve
        </button>
      </div>
    </div>
  )
}

export default ApprovalGate
