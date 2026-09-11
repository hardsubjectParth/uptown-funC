import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { getUploadScopes, listFiles, searchKnowledge, uploadFile } from '../services/api'
import type { FileRecord } from '../services/api'
import { useAuth } from '../context/AuthContext'

type Hit = { content: string; metadata: Record<string, string>; score: number }

function formatFileSize(bytes?: number) {
  if (!bytes || bytes <= 0) return 'Unknown size'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function KnowledgeBase() {
  const { token } = useAuth()
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<Hit[]>([])
  const [error, setError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [scopes, setScopes] = useState<string[]>([])
  const [scope, setScope] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)
  const [files, setFiles] = useState<FileRecord[]>([])

  useEffect(() => {
    if (!token) return
    listFiles(token).then((result) => setFiles(result.data)).catch((cause) => console.error('Unable to load files:', cause))
  }, [token])

  useEffect(() => {
    if (!token) return
    getUploadScopes(token)
      .then((result) => { setScopes(result.scopes); setScope(result.scopes[0] ?? '') })
      .catch((cause) => setUploadError(cause instanceof Error ? cause.message : 'Unable to load upload scopes'))
  }, [token])

  async function handleUpload() {
    if (!token || !file || !scope) return
    setUploading(true); setUploadError(null); setUploadSuccess(null)
    try {
      await uploadFile(file, scope, token)
      setUploadSuccess(`${file.name} uploaded successfully.`)
      setFile(null)
      const refreshed = await listFiles(token)
      setFiles(refreshed.data)
    } catch (cause) {
      setUploadError(cause instanceof Error ? cause.message : 'Upload failed')
    } finally { setUploading(false) }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !query.trim()) return
    setSearching(true); setError(null)
    try { setHits((await searchKnowledge(query.trim(), token)).data) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Search failed') }
    finally { setSearching(false) }
  }

  return (
    <main className="knowledge-page">
      <section className="knowledge-header">
        <div>
          <p className="eyebrow">ORGANIZATIONAL KNOWLEDGE</p>
          <h1>Knowledge Base</h1>
          <p className="dashboard-subtitle">Search information available within your authorized access scope.</p>
        </div>
      </section>

      <section className="knowledge-upload">
        <div className="section-heading">
          <div>
            <p className="card-label">ADD KNOWLEDGE</p>
            <h2>Upload a document</h2>
            <p className="helper-text">Uploaded documents become searchable organizational knowledge.</p>
          </div>
        </div>

        <div className="upload-row">
          <label className="file-picker">
            <span>{file ? file.name : 'Choose a file'}</span>
            <input type="file" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setUploadError(null); setUploadSuccess(null) }} />
          </label>

          <select value={scope} onChange={(event) => setScope(event.target.value)} disabled={scopes.length === 0} aria-label="Knowledge visibility">
            {scopes.map((availableScope) => <option key={availableScope} value={availableScope}>{availableScope === 'everyone' ? 'Everyone in lower tiers' : availableScope}</option>)}
          </select>

          <button className="new-task-button" type="button" onClick={handleUpload} disabled={!file || !scope || uploading}>
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>

        {uploadError ? <p className="form-error" role="alert">{uploadError}</p> : null}
        {uploadSuccess ? <p className="form-success" role="status">{uploadSuccess}</p> : null}
      </section>

      <section className="knowledge-results">
        <div className="section-heading">
          <p className="card-label">YOUR DOCUMENTS</p>
          <span className="helper-text">{files.length} document{files.length === 1 ? '' : 's'}</span>
        </div>

        {files.length > 0 ? (
          <div className="knowledge-result-list">
            {files.map((item) => (
              <article className="knowledge-result" key={item.id}>
                <div className="document-icon">{item.metadata.mime_type?.includes('pdf') ? 'PDF' : 'DOC'}</div>
                <div className="document-info">
                  <h2>{item.name}</h2>
                  <div className="document-meta">
                    <span>{formatFileSize(item.metadata.size_bytes)}</span>
                    <span className="meta-separator">·</span>
                    <span>{item.metadata.mime_type ?? 'Unknown type'}</span>
                  </div>
                </div>
                <span className="visibility-badge">
                  {item.metadata.visibility_tier ? item.metadata.visibility_tier.charAt(0).toUpperCase() + item.metadata.visibility_tier.slice(1) : 'Authorized'}
                </span>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">No documents have been uploaded yet.</p>
        )}
      </section>

      <section className="knowledge-search">
        <form onSubmit={handleSearch}>
          <label htmlFor="query">Search knowledge</label>
          <div className="knowledge-search-row">
            <input id="query" type="text" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your authorized knowledge…" required />
            <button className="new-task-button" type="submit" disabled={searching}>{searching ? 'Searching…' : 'Search'}</button>
          </div>
        </form>
      </section>

      {error ? <p className="form-error" role="alert">{error}</p> : null}

      {hits.length > 0 ? (
        <section className="knowledge-results" aria-live="polite">
          <div className="section-heading">
            <p className="card-label">SEARCH RESULTS</p>
            <span className="helper-text">{hits.length} result{hits.length === 1 ? '' : 's'}</span>
          </div>

          <div className="knowledge-result-list">
            {hits.map((hit, index) => (
              <article className="knowledge-result" key={`${hit.metadata.file_id ?? 'hit'}-${index}`}>
                <div className="knowledge-result-header">
                  <div>
                    <h2>{hit.metadata.name ?? 'Knowledge result'}</h2>
                    <p className="helper-text">{hit.metadata.visibility_tier ?? 'Authorized'}</p>
                  </div>
                  <span className="result-score">{hit.score.toFixed(2)}</span>
                </div>
                <p>{hit.content}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  )
}

export default KnowledgeBase
