import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import type { Job, JobEvent, PlanStep, Verification } from '../../types/api'
import { CheckIcon, XIcon } from '../shell/icons'

/* The live "prompt → model selection → plan → execution → verification → delivery"
   readout. Every stage is driven by a real SSE event emitted by the orchestrator
   (app/orchestrator/service.py), not by a timer -- if the backend never emits
   `plan_created`, the planning stage never lights up. */

type StageState = 'pending' | 'active' | 'done' | 'failed'

const STAGES = [
  { key: 'received', label: 'Task Received' },
  { key: 'routing', label: 'Model Selection' },
  { key: 'planning', label: 'Execution Plan' },
  { key: 'execution', label: 'Tool Execution' },
  { key: 'verification', label: 'Verification' },
  { key: 'delivery', label: 'Delivery' },
] as const

// Which stage each emitted event belongs to. Anything not listed (status_changed,
// model_response) is deliberately ignored -- it carries no stage transition.
const EVENT_STAGE: Record<string, number> = {
  job_created: 0,
  model_selected: 1,
  model_fallback: 1,
  model_error: 1,
  plan_created: 2,
  replanning: 2,
  step_started: 3,
  tool_started: 3,
  tool_completed: 3,
  step_completed: 3,
  observation: 3,
  approval_required: 3,
  approval_approved: 3,
  approval_rejected: 3,
  verification_passed: 4,
  verification_failed: 4,
  artifact_created: 5,
  job_completed: 5,
}

const TERMINAL_OK = new Set(['done'])
const TERMINAL_BAD = new Set(['failed', 'cancelled'])

function clockOf(iso?: string) {
  if (!iso) return null
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date.toLocaleTimeString([], { hour12: false })
}

function Node({ state }: { state: StageState }) {
  if (state === 'done') {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full border border-accent/50 bg-accent/15 text-accent">
        <CheckIcon size={13} />
      </span>
    )
  }
  if (state === 'failed') {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full border border-danger/50 bg-danger/15 text-danger">
        <XIcon size={13} />
      </span>
    )
  }
  if (state === 'active') {
    return (
      <span className="relative flex h-6 w-6 items-center justify-center rounded-full border border-info/60 bg-info/15">
        <span className="absolute inset-0 animate-status-pulse rounded-full bg-info/25" />
        <span className="relative h-1.5 w-1.5 rounded-full bg-info" />
      </span>
    )
  }
  return <span className="flex h-6 w-6 items-center justify-center rounded-full border border-white/12 bg-surface" />
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline gap-2.5 text-[12.5px]">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 text-foreground/90">{value}</span>
    </div>
  )
}

function ProtocolPipeline({ events, job }: { events: JobEvent[]; job?: Job }) {
  const byType = (type: string) => events.filter((event) => event.type === type)
  const firstOf = (type: string) => byType(type)[0]
  const lastOf = (type: string) => byType(type).at(-1)

  // How far the run has actually progressed, from the events themselves.
  const reached = events.reduce((furthest, event) => {
    const index = EVENT_STAGE[event.type]
    return index === undefined ? furthest : Math.max(furthest, index)
  }, 0)

  const status = job?.status
  const finishedOk = status ? TERMINAL_OK.has(status) : false
  const finishedBad = status ? TERMINAL_BAD.has(status) : false
  const halted = Boolean(lastOf('model_error')) || Boolean(job?.error)

  function stateFor(index: number): StageState {
    if (finishedOk) return 'done'
    if (index < reached) return 'done'
    if (index > reached) return 'pending'
    if (finishedBad || (halted && index === reached)) return 'failed'
    return 'active'
  }

  // ------------------------------------------------------------ stage details

  // `model_selected` carries the routing decision verbatim as its payload, but the
  // event envelope types `data` as Record<string, unknown> -- hence the widening cast.
  const routing = job?.routing ?? (firstOf('model_selected')?.data as unknown as Job['routing'])
  const fallback = firstOf('model_fallback')
  const modelError = lastOf('model_error')

  const planEvent = lastOf('plan_created')
  const planSteps = (planEvent?.data.steps as PlanStep[] | undefined) ?? job?.plan ?? []
  const replans = byType('replanning').length

  const toolStarts = byType('tool_started')
  const toolDone = byType('tool_completed')
  const approval = lastOf('approval_required')

  const verifyEvent = lastOf('verification_passed') ?? lastOf('verification_failed')
  const verification = (verifyEvent?.data as Verification | undefined) ?? job?.verification
  const checks = Object.entries(verification?.checks ?? {})

  const artifacts = job?.artifacts ?? []

  function detailFor(key: string, state: StageState): ReactNode {
    if (state === 'pending') return null

    if (key === 'received') {
      return <Row label="Prompt" value={<span className="line-clamp-2">{job?.task ?? '—'}</span>} />
    }

    if (key === 'routing') {
      if (modelError) return <Row label="Error" value={<span className="text-danger">{String(modelError.data.error ?? 'Model call failed')}</span>} />
      if (!routing) return <Row label="Status" value="Selecting a capability-matched model…" />
      return (
        <>
          <Row label="Model" value={<span className="font-mono">{routing.model_name || routing.model_id}</span>} />
          <Row label="Task type" value={routing.task_type?.replace(/_/g, ' ')} />
          {typeof routing.confidence === 'number' ? (
            <Row label="Confidence" value={`${Math.round(routing.confidence * 100)}%`} />
          ) : null}
          {routing.reason ? <Row label="Reason" value={routing.reason} /> : null}
          {fallback ? (
            <Row label="Fallback" value={<span className="text-warning">Preferred model unavailable — fell back</span>} />
          ) : null}
        </>
      )
    }

    if (key === 'planning') {
      if (!planSteps.length) return <Row label="Status" value="Drafting the execution plan…" />
      return (
        <>
          <Row label="Steps" value={`${planSteps.length}`} />
          {replans > 0 ? (
            <Row label="Re-planned" value={<span className="text-warning">{replans}× after failed verification</span>} />
          ) : null}
          <ol className="mt-2 flex flex-col gap-1">
            {planSteps.map((step, index) => (
              <li key={step.step_id ?? index} className="flex gap-2 text-[12.5px] text-foreground/80">
                <span className="shrink-0 text-muted-foreground">{index + 1}.</span>
                <span className="min-w-0">
                  {step.description}
                  {step.tool ? <span className="ml-1.5 font-mono text-[11px] text-accent">{step.tool}</span> : null}
                </span>
              </li>
            ))}
          </ol>
        </>
      )
    }

    if (key === 'execution') {
      if (!toolStarts.length) return <Row label="Status" value="Waiting for the first tool call…" />
      return (
        <>
          {approval && job?.status === 'awaiting_approval' ? (
            <Row label="Paused" value={<span className="text-warning">Awaiting human approval</span>} />
          ) : null}
          <div className="flex flex-col gap-1.5">
            {toolStarts.map((event) => {
              const callId = event.data.call_id as string
              const finished = toolDone.find((done) => done.data.call_id === callId)
              const failed = Boolean(finished?.data.error)
              const denied = event.data.policy_decision === 'deny'
              return (
                <div key={callId} className="flex items-center gap-2.5 text-[12.5px]">
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      failed || denied ? 'bg-danger' : finished ? 'bg-accent' : 'animate-status-pulse bg-info'
                    }`}
                  />
                  <span className="font-mono text-foreground/90">{String(event.data.tool)}</span>
                  <span className="ml-auto shrink-0 text-muted-foreground">
                    {denied ? 'denied by policy' : failed ? 'failed' : finished ? 'ok' : 'running…'}
                  </span>
                </div>
              )
            })}
          </div>
        </>
      )
    }

    if (key === 'verification') {
      if (!verification) return <Row label="Status" value="Checking the result against the task…" />
      const passed = checks.filter(([, ok]) => ok).length
      return (
        <>
          <Row
            label="Checks"
            value={
              <span className={verification.passed ? 'text-success' : 'text-warning'}>
                {passed}/{checks.length} passed
              </span>
            }
          />
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {checks.map(([name, ok]) => (
              <span
                key={name}
                className={`rounded-md border px-1.5 py-0.5 text-[11px] ${
                  ok ? 'border-success/30 bg-success/10 text-success' : 'border-warning/30 bg-warning/10 text-warning'
                }`}
              >
                {name.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
          {verification.notes?.length ? (
            <p className="mt-2 text-[12px] text-muted-foreground">{verification.notes.join(' · ')}</p>
          ) : null}
        </>
      )
    }

    if (key === 'delivery') {
      if (!artifacts.length) return <Row label="Status" value={finishedOk ? 'Answer delivered' : 'Assembling deliverables…'} />
      return (
        <div className="flex flex-col gap-1">
          {artifacts.map((artifact) => (
            <div key={artifact.artifact_id ?? artifact.name} className="flex items-center gap-2.5 text-[12.5px]">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span className="font-mono text-foreground/90">{artifact.name}</span>
            </div>
          ))}
        </div>
      )
    }

    return null
  }

  // Timestamp for a stage = when its first event landed.
  const stampFor = (index: number) =>
    clockOf(events.find((event) => EVENT_STAGE[event.type] === index)?.timestamp)

  return (
    <div className="border-hairline mt-4 rounded-2xl bg-surface px-5 py-5">
      <div className="flex items-center justify-between">
        <p className="label-micro">Protocol Pipeline</p>
        <p className="label-micro">
          {finishedOk ? 'Complete' : finishedBad ? 'Halted' : `Stage ${Math.min(reached + 1, STAGES.length)} of ${STAGES.length}`}
        </p>
      </div>

      <div className="mt-5 flex flex-col">
        {STAGES.map((stage, index) => {
          const state = stateFor(index)
          const detail = detailFor(stage.key, state)
          const stamp = stampFor(index)
          const isLast = index === STAGES.length - 1
          return (
            <div key={stage.key} className="flex gap-4">
              {/* rail */}
              <div className="flex flex-col items-center">
                <Node state={state} />
                {!isLast ? (
                  <div className="relative my-1 w-px flex-1 bg-white/8">
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: index < reached || finishedOk ? '100%' : 0 }}
                      transition={{ duration: 0.4, ease: 'easeOut' }}
                      className="absolute inset-x-0 top-0 bg-accent/50"
                    />
                  </div>
                ) : null}
              </div>

              {/* content */}
              <div className={`min-w-0 flex-1 ${isLast ? 'pb-0' : 'pb-5'}`}>
                <div className="flex items-baseline gap-3">
                  <p
                    className={`text-[13.5px] font-semibold ${
                      state === 'pending' ? 'text-muted-foreground' : state === 'failed' ? 'text-danger' : 'text-foreground'
                    }`}
                  >
                    {stage.label}
                  </p>
                  {stamp ? <span className="ml-auto shrink-0 font-mono text-[11px] text-muted-foreground">{stamp}</span> : null}
                </div>

                {detail ? (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.22 }}
                    className="mt-2 flex flex-col gap-1"
                  >
                    {detail}
                  </motion.div>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default ProtocolPipeline
