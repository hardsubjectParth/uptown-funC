import { useState } from 'react'
import type { FormEvent } from 'react'
import { searchKnowledge } from '../services/api'
import { useAuth } from '../context/AuthContext'

type Hit = { content: string; metadata: Record<string, string>; score: number }

function KnowledgeBase() {
  const { token } = useAuth()
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<Hit[]>([])
  const [error, setError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !query.trim()) return
    setSearching(true); setError(null)
    try { setHits((await searchKnowledge(query.trim(), token)).data) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Search failed') }
    finally { setSearching(false) }
  }

  return <main>
    <h1>Knowledge Base</h1><p>Searches only the pgvector database tiers your signed-in role can access.</p>
    <form className="task-form" onSubmit={handleSearch}>
      <label htmlFor="query">Search query</label>
      <textarea id="query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your authorized knowledge…" required />
      <button className="new-task-button" type="submit" disabled={searching}>{searching ? 'Searching…' : 'Search knowledge'}</button>
    </form>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <section aria-live="polite">{hits.map((hit, index) => <article className="task-card" key={`${hit.metadata.file_id ?? 'hit'}-${index}`}><h2>{hit.metadata.name ?? 'Knowledge result'}</h2><p>{hit.content}</p><p className="helper-text">Tier: {hit.metadata.visibility_tier ?? 'authorized'} · score {hit.score.toFixed(2)}</p></article>)}</section>
  </main>
}

export default KnowledgeBase
