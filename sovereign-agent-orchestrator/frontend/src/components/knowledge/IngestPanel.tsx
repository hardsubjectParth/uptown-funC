import { useState } from 'react'
import { useFileScopes, useUploadFile } from '../../hooks/useFiles'
import { useIndexHealth } from '../../hooks/useSystem'
import { useAuth } from '../../context/AuthContext'
import { UploadCloudIcon, ShieldIcon, UserIcon, UsersIcon } from '../shell/icons'
import type { Role } from '../../types/api'

// Scope keys, and which tier database each resolves to, are the real mapping in
// app/access.py::UPLOAD_SCOPES keyed by role -- reproduced here for display copy
// only (the upload itself goes through the backend, which enforces this server-side
// regardless of what's rendered). The backend accepts exactly one scope per upload,
// so this is a single choice, not a multi-select: a file has one visibility tier.
const SCOPE_COPY: Record<string, { title: string; description: string; Icon: typeof ShieldIcon }> = {
  private: { title: 'Tier-Private', description: 'Highly sensitive — visible only to your own tier.', Icon: ShieldIcon },
  restricted: { title: 'Executive Team', description: 'Regional reports and market data — visible to Higher tier and Admin.', Icon: UserIcon },
  everyone: { title: 'General Staff', description: 'Standard operating procedures — visible to every authorized tier.', Icon: UsersIcon },
}

// 'private' means a different database per role (admin -> admin tier, lower ->
// lower tier), so the label says which one rather than a flat "Private".
const PRIVATE_TITLE: Record<Role, string> = {
  admin: 'Admin-Only',
  higher: 'Higher-Only',
  lower: 'Lower Tier Only',
}

function IngestPanel({ onIngested }: { onIngested?: () => void }) {
  const { user } = useAuth()
  const scopes = useFileScopes()
  const upload = useUploadFile()
  const health = useIndexHealth()
  const [file, setFile] = useState<File | null>(null)
  const [scope, setScope] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  // Seed from the first scope the backend says this role may use, once that
  // (authenticated) call resolves. `scope` is user-editable state, so it has to be
  // seeded rather than derived -- done during render, not in an effect, so the
  // panel never paints a frame with nothing selected.
  const [seeded, setSeeded] = useState(false)
  if (!seeded && scopes.length > 0) {
    setSeeded(true)
    setScope(scopes[0])
  }

  async function beginIngestion() {
    if (!file || !scope) return
    setUploading(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await upload(file, scope)
      setSuccess(`${file.name} ingested into the ${result.index.tier} tier.`)
      setFile(null)
      onIngested?.()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Ingestion failed')
    } finally {
      setUploading(false)
    }
  }

  function titleFor(scopeKey: string) {
    if (scopeKey === 'private' && user) return PRIVATE_TITLE[user.role]
    return SCOPE_COPY[scopeKey]?.title ?? scopeKey
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="scroll-slim min-h-0 flex-1 overflow-y-auto px-6 py-6">
        <p className="label-micro">Document Upload</p>

        <label
          onDragOver={(event) => { event.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragOver(false)
            const dropped = event.dataTransfer.files?.[0]
            if (dropped) { setFile(dropped); setError(null); setSuccess(null) }
          }}
          className={`mt-4 flex h-56 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-5 text-center transition-colors ${
            dragOver ? 'border-accent bg-accent/5' : 'border-white/14 hover:border-white/25'
          }`}
        >
          <input
            type="file"
            hidden
            onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError(null); setSuccess(null) }}
          />
          <UploadCloudIcon size={38} className="text-muted-foreground" />
          <p className="mt-4 text-[15px] font-semibold break-all text-foreground">{file ? file.name : 'Drop file to ingest'}</p>
          <p className="label-micro mt-2">Supports PDF, DOCX, PPTX, TXT, CSV</p>
        </label>

        <p className="label-micro mt-8">Visibility Scope</p>
        <div className="mt-4 flex flex-col gap-2.5">
          {scopes.length === 0 ? <p className="text-xs text-muted-foreground">Loading authorized scopes…</p> : null}
          {scopes.map((scopeOption) => {
            const copy = SCOPE_COPY[scopeOption]
            const Icon = copy?.Icon ?? ShieldIcon
            const selected = scope === scopeOption
            return (
              <label
                key={scopeOption}
                className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3.5 transition-colors ${
                  selected ? 'border-accent/40 bg-primary/45' : 'border-white/7 bg-surface hover:border-white/14'
                }`}
              >
                <input
                  type="radio"
                  name="scope"
                  className="sr-only"
                  checked={selected}
                  onChange={() => setScope(scopeOption)}
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-[14px] font-semibold text-foreground">{titleFor(scopeOption)}</span>
                  <span className="mt-0.5 block text-[12px] text-muted-foreground">
                    {copy?.description ?? 'Visibility scope for uploaded documents.'}
                  </span>
                </span>
                <Icon size={17} className={selected ? 'text-accent' : 'text-muted-foreground'} />
              </label>
            )
          })}
        </div>

        <p className="mt-4 text-[12px] text-muted-foreground italic">
          Available scopes are determined by your authorization tier.
        </p>

        {error ? <p className="mt-4 text-xs text-danger">{error}</p> : null}
        {success ? <p className="mt-4 text-xs text-accent">{success}</p> : null}

        <button
          type="button"
          onClick={beginIngestion}
          disabled={!file || !scope || uploading}
          className="mt-6 w-full rounded-xl bg-primary px-4 py-4 text-[15px] font-semibold text-primary-foreground transition hover:bg-primary-hover disabled:opacity-40"
        >
          {uploading ? 'Ingesting…' : 'Begin Ingestion'}
        </button>
      </div>

      <div className="shrink-0 border-t border-white/7 px-6 py-5">
        <div className="flex items-baseline justify-between">
          <span className="label-micro">Index Health</span>
          <span className={`stat-number text-[13px] font-semibold ${health.degraded ? 'text-warning' : 'text-foreground'}`}>
            {health.percent === null ? '—' : `${health.percent}%`}
          </span>
        </div>
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/8">
          <div
            className={`h-full rounded-full transition-[width] duration-500 ease-out ${health.degraded ? 'bg-warning' : 'bg-accent'}`}
            style={{ width: `${health.percent ?? 0}%` }}
          />
        </div>
        <p className="mt-3 text-center text-[12px] text-muted-foreground italic">
          {health.degraded
            ? `Degraded: ${health.failing.join(', ')}.`
            : 'Knowledge vector space is synchronized.'}
        </p>
      </div>
    </div>
  )
}

export default IngestPanel
