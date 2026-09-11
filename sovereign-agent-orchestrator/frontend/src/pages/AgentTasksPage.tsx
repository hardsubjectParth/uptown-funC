import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as Tabs from '@radix-ui/react-tabs'
import { useJobs } from '../hooks/useJob'
import StatCard from '../components/shared/StatCard'
import StatusDot, { STATUS_LABEL } from '../components/shared/StatusDot'
import type { JobStatus } from '../types/api'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'review', label: 'Review' },
] as const

const IN_PROGRESS: JobStatus[] = ['queued', 'planning', 'acting', 'observing', 'verifying', 'delivering']

function relativeTime(iso?: string) {
  if (!iso) return '—'
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

function AgentTasksPage() {
  const navigate = useNavigate()
  const { jobs } = useJobs(100)
  const [filter, setFilter] = useState<string>('all')

  const active = jobs.filter((job) => IN_PROGRESS.includes(job.status)).length
  const completed = jobs.filter((job) => job.status === 'done').length
  const pending = jobs.filter((job) => job.status === 'queued').length
  const finished = jobs.filter((job) => job.status === 'done' || job.status === 'failed')
  const successRate = finished.length ? Math.round((completed / finished.length) * 100) : 100

  const filtered = jobs.filter((job) => {
    if (filter === 'in_progress') return IN_PROGRESS.includes(job.status)
    if (filter === 'review') return job.status === 'awaiting_approval'
    return true
  })

  return (
    <main className="flex-1 overflow-y-auto px-8 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Agent Task Oversight</h1>
        <button type="button" onClick={() => navigate('/app/feed')} className="bg-accent px-4 py-2 text-xs font-semibold text-accent-foreground">
          Delegate New Task
        </button>
      </div>

      <div className="mt-6 grid grid-cols-4 gap-3">
        <StatCard label="Active Protocols" value={active} accent />
        <StatCard label="Completed" value={completed} />
        <StatCard label="Pending Ingest" value={pending} />
        <StatCard label="Success Rate" value={successRate} suffix="%" accent />
      </div>

      <div className="mt-8">
        <p className="label-micro mb-3">Current Assignments</p>
        <Tabs.Root value={filter} onValueChange={setFilter}>
          <Tabs.List className="flex gap-1 border-b border-white/8">
            {FILTERS.map((item) => (
              <Tabs.Trigger
                key={item.value}
                value={item.value}
                className="px-3 py-2 text-xs text-muted-foreground transition data-[state=active]:border-b data-[state=active]:border-accent data-[state=active]:text-accent"
              >
                {item.label}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
        </Tabs.Root>

        <div className="mt-3 flex flex-col gap-2">
          {filtered.length === 0 ? <p className="text-sm text-muted-foreground">No tasks match this filter.</p> : null}
          {filtered.map((job) => (
            <div key={job.job_id} className="border-hairline flex items-center justify-between gap-4 bg-surface px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">{job.task}</p>
                <div className="mt-1 flex items-center gap-2">
                  <StatusDot status={job.status} />
                  <span className="label-micro">{STATUS_LABEL[job.status]}</span>
                  {job.model_name ? <span className="text-xs text-muted-foreground">· Routed to {job.model_name}</span> : null}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <p className="label-micro">{relativeTime(job.created_at)}</p>
                {job.verification_passed ? <p className="mt-0.5 text-xs text-accent">Verified ✓</p> : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}

export default AgentTasksPage
