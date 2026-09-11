import { useState } from 'react'
import { downloadArtifact } from '../services/api'
import { useAuth } from '../context/AuthContext'

type ArtifactListProps = {
  jobId: string
  artifacts: Array<{ name: string }>
}

// Shared by every place a job's artifacts show up (New Task, Tasks, the standalone
// Artifacts lookup page) so "download" only has one real implementation.
function ArtifactList({ jobId, artifacts }: ArtifactListProps) {
  const { token } = useAuth()
  const [error, setError] = useState<string | null>(null)

  async function save(name: string) {
    if (!token) return
    setError(null)
    try {
      const blob = await downloadArtifact(jobId, name, token)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = name
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Download failed')
    }
  }

  if (!artifacts.length) return null

  return (
    <div className="artifact-list">
      {artifacts.map((artifact) => (
        <div className="artifact-card" key={artifact.name}>
          <span className="artifact-name">{artifact.name}</span>
          <button className="card-action" type="button" onClick={() => save(artifact.name)}>Download</button>
        </div>
      ))}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </div>
  )
}

export default ArtifactList
