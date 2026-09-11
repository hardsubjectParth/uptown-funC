import { useState } from 'react'
import { downloadArtifact } from '../../services/api'
import type { JobArtifact } from '../../types/api'
import { useAuth } from '../../context/AuthContext'
import { fileVisual, formatSize, relativeTime } from './fileVisual'
import { TONE } from './IconTile'
import { DownloadIcon } from '../shell/icons'

type ArtifactCardProps = {
  jobId: string
  artifact: JobArtifact
  generatedAt?: string
  /** `preview` is the tall thumbnail form used in the Intelligence Feed rail. */
  layout?: 'list' | 'grid' | 'preview'
}

function ArtifactCard({ jobId, artifact, generatedAt, layout = 'list' }: ArtifactCardProps) {
  const { token } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const visual = fileVisual(artifact.name)
  const typeTag = (artifact.name.split('.').pop() || 'file').toUpperCase()
  const generated = generatedAt ? relativeTime(generatedAt) : null

  async function download() {
    if (!token) return
    setError(null)
    try {
      const blob = await downloadArtifact(jobId, artifact.name, token)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = artifact.name
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Download failed')
    }
  }

  const meta = [typeTag, formatSize(artifact.size_bytes), generated ? `Generated ${generated}` : null]
    .filter(Boolean)
    .join(' · ')

  if (layout === 'preview') {
    return (
      <div>
        <button
          type="button"
          onClick={download}
          title={`Download ${artifact.name}`}
          className="group relative flex h-[190px] w-full items-center justify-center overflow-hidden rounded-2xl border border-white/8 bg-surface transition-colors hover:border-accent/40"
          style={{
            backgroundImage: 'radial-gradient(rgba(255,255,255,0.05) 1px, transparent 1px)',
            backgroundSize: '11px 11px',
          }}
        >
          <visual.Icon size={52} className="text-white/14 transition group-hover:text-white/25" />
          <span className="absolute right-3 bottom-3 flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground opacity-0 transition-opacity group-hover:opacity-100">
            <DownloadIcon size={15} />
          </span>
        </button>
        <p className="mt-3 truncate text-[14px] font-semibold text-foreground" title={artifact.name}>{artifact.name}</p>
        <p className="label-micro mt-1">{meta}</p>
        {error ? <p className="mt-1 text-xs text-danger">{error}</p> : null}
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={download}
      className={`border-hairline group w-full rounded-xl bg-surface px-4 py-3 text-left transition-colors hover:border-accent/50 ${
        layout === 'grid' ? '' : 'flex items-center justify-between gap-4'
      }`}
    >
      <span className="flex min-w-0 items-center gap-3">
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border"
          style={{ color: TONE[visual.tone].color, background: TONE[visual.tone].bg, borderColor: TONE[visual.tone].border }}
        >
          <visual.Icon size={17} />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-foreground">{artifact.name}</span>
          <span className="label-micro mt-0.5 block">{meta}</span>
          {error ? <span className="mt-1 block text-xs text-danger">{error}</span> : null}
        </span>
      </span>
      <span className="label-micro shrink-0 text-accent opacity-0 transition-opacity group-hover:opacity-100">Download</span>
    </button>
  )
}

export default ArtifactCard
