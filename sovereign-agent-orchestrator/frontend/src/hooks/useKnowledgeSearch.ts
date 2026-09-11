import { useState } from 'react'
import { searchKnowledge } from '../services/api'
import type { KnowledgeSearchResult } from '../types/api'
import { useAuth } from '../context/AuthContext'

export function useKnowledgeSearch() {
  const { token } = useAuth()
  const [results, setResults] = useState<KnowledgeSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function search(query: string) {
    if (!token || !query.trim()) return
    setSearching(true)
    setError(null)
    try {
      setResults((await searchKnowledge(query.trim(), token)).data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Search failed')
    } finally {
      setSearching(false)
    }
  }

  return { results, search, searching, error }
}
