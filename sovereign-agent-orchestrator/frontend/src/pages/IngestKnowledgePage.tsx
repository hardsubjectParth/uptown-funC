import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFileScopes, useUploadFile } from '../hooks/useFiles'

// Scope keys and what tier they actually resolve to are the real mapping in
// app/access.py::UPLOAD_SCOPES, keyed by role -- reproduced here for display copy
// only (the upload call itself goes through the real backend, which enforces this
// server-side regardless of what's shown). Note the backend only accepts one scope
// per upload, so this renders as a single choice, not the spec's multi-checkbox --
// a file has exactly one visibility tier, not several.
const SCOPE_COPY: Record<string, string> = {
  private: 'Highly sensitive — visible only to your own tier.',
  restricted: 'Regional reports and operational data — visible to Higher tier and Admin.',
  everyone: 'Standard operating procedures — visible to every authorized tier.',
}

function IngestKnowledgePage() {
  const navigate = useNavigate()
  const scopes = useFileScopes()
  const upload = useUploadFile()
  const [file, setFile] = useState<File | null>(null)
  const [scope, setScope] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  useEffect(() => {
    if (!scope && scopes.length) setScope(scopes[0])
  }, [scopes, scope])

  async function beginIngestion() {
    if (!file || !scope) return
    setUploading(true)
    setError(null)
    setSuccess(null)
    try {
      await upload(file, scope)
      setSuccess(`${file.name} ingested successfully.`)
      setFile(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Ingestion failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <main className="flex-1 overflow-y-auto px-8 py-8">
      <h1 className="text-xl font-semibold text-foreground">Ingest Knowledge</h1>
      <p className="label-micro mt-1">Document Upload</p>

      <div className="mt-6 grid grid-cols-[1fr_260px] gap-6">
        <div>
          <label
            onDragOver={(event) => { event.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragOver(false)
              const dropped = event.dataTransfer.files?.[0]
              if (dropped) { setFile(dropped); setError(null); setSuccess(null) }
            }}
            className={`flex h-48 cursor-pointer flex-col items-center justify-center border border-dashed text-center transition-colors ${dragOver ? 'border-accent bg-accent/5' : 'border-white/16'}`}
          >
            <input
              type="file"
              hidden
              onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError(null); setSuccess(null) }}
            />
            <p className="text-sm text-foreground">{file ? file.name : 'Drop file to ingest'}</p>
            <p className="label-micro mt-2">Supports PDF, DOCX, PPTX, TXT, CSV</p>
          </label>

          <div className="mt-6">
            <p className="label-micro mb-2">Visibility Scope</p>
            <p className="mb-3 text-xs text-muted-foreground">Available scopes are determined by your authorization tier.</p>
            <div className="flex flex-col gap-2">
              {scopes.map((scopeOption) => (
                <label key={scopeOption} className="border-hairline flex cursor-pointer items-start gap-3 bg-surface px-3.5 py-3">
                  <input type="radio" name="scope" checked={scope === scopeOption} onChange={() => setScope(scopeOption)} className="mt-0.5 accent-[var(--color-accent)]" />
                  <span>
                    <span className="block text-sm text-foreground">{scopeOption === 'everyone' ? 'Everyone in lower tiers' : scopeOption[0].toUpperCase() + scopeOption.slice(1)}</span>
                    <span className="block text-xs text-muted-foreground">{SCOPE_COPY[scopeOption] ?? 'Visibility scope for uploaded documents.'}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          {error ? <p className="mt-4 text-xs text-danger">{error}</p> : null}
          {success ? <p className="mt-4 text-xs text-accent">{success}</p> : null}

          <button
            type="button"
            onClick={beginIngestion}
            disabled={!file || !scope || uploading}
            className="mt-6 bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50"
          >
            {uploading ? 'Ingesting…' : 'Begin Ingestion'}
          </button>
        </div>

        <div className="border-hairline h-fit bg-surface px-4 py-4">
          <p className="stat-number text-2xl font-semibold text-accent">99.9%</p>
          <p className="label-micro mt-1.5">Index Health</p>
          <p className="mt-3 text-xs text-muted-foreground">Knowledge vector space is synchronized.</p>
          <button type="button" onClick={() => navigate('/app/knowledge')} className="label-micro mt-4 text-accent hover:underline">
            View Knowledge Base →
          </button>
        </div>
      </div>
    </main>
  )
}

export default IngestKnowledgePage
