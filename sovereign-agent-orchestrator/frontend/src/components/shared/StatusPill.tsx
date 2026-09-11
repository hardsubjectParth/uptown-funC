import type { JobStatus } from '../../types/api'
import { STATUS_LABEL } from './StatusDot'
import type { Tone } from './IconTile'

// Tone per real backend status. Anything in flight reads as informational, a
// stopped-and-waiting job as a warning, and only `done` earns the success green --
// the pill is a status readout, not decoration, so it never flatters a job.
const STATUS_TONE: Record<JobStatus, Tone> = {
  queued: 'warning',
  planning: 'info',
  acting: 'info',
  observing: 'info',
  verifying: 'info',
  delivering: 'info',
  awaiting_approval: 'warning',
  done: 'success',
  failed: 'danger',
  cancelled: 'neutral',
}

const TONE_CLASS: Record<Tone, string> = {
  info: 'text-info border-info/35 bg-info/10',
  success: 'text-success border-success/35 bg-success/10',
  warning: 'text-warning border-warning/35 bg-warning/10',
  danger: 'text-danger border-danger/35 bg-danger/10',
  accent: 'text-accent border-accent/35 bg-accent/10',
  neutral: 'text-muted-foreground border-white/10 bg-white/5',
}

export function Pill({ tone = 'neutral', children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-flex shrink-0 items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-[0.1em] uppercase ${TONE_CLASS[tone]}`}>
      {children}
    </span>
  )
}

function StatusPill({ status }: { status: JobStatus }) {
  return <Pill tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Pill>
}

export default StatusPill
export { STATUS_TONE }
