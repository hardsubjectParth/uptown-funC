import useSWR from 'swr'
import { getReadiness } from '../services/api'

// Drives the Knowledge Base rail's "Index Health" readout. The number is the share
// of real readiness checks currently passing (database, workspace, disk headroom,
// and -- in ollama mode -- whether the chat and embedding models are installed), so
// a degraded backend visibly drops the gauge instead of always reading 99.9%.
export function useIndexHealth() {
  const { data } = useSWR('readiness', getReadiness, { refreshInterval: 30000, shouldRetryOnError: false })
  const checks = Object.values(data?.checks ?? {})
  const passing = checks.filter(Boolean).length
  const percent = checks.length ? Math.round((passing / checks.length) * 1000) / 10 : null
  return {
    percent,
    degraded: data?.status === 'degraded',
    errors: data?.errors ?? [],
    failing: Object.entries(data?.checks ?? {}).filter(([, ok]) => !ok).map(([name]) => name),
  }
}
