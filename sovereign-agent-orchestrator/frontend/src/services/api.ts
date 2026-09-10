const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8080/api/v1'

type ApiError = Error & { status?: number }

export type User = { id: string; role: 'admin' | 'higher' | 'lower'; tenant_id: string }
export type LoginResponse = { access_token: string; token_type: 'bearer'; expires_in: number; user: User }
export type FileRecord = { id: string; name: string; metadata: { visibility_tier?: string; size_bytes?: number }; created_at?: string }
export type Job = { job_id: string; task: string; status: string; artifacts: Array<{ name: string }>; final_answer?: string; error?: string }

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  if (!response.ok) {
    const error = new Error((await response.json().catch(() => null))?.detail ?? `Request failed (${response.status})`) as ApiError
    error.status = response.status
    throw error
  }
  return response.json() as Promise<T>
}

export const healthCheck = () => request<{ status: string }>('/health')
export const devLogin = (username: string, password: string) => request<LoginResponse>('/auth/dev/login', { method: 'POST', body: JSON.stringify({ username, password }) })
export const getUploadScopes = (token: string) => request<{ scopes: string[] }>('/files/scopes', {}, token)
export const listFiles = (token: string) => request<{ data: FileRecord[] }>('/files', {}, token)
export const uploadFile = (file: File, scope: string, token: string) => { const body = new FormData(); body.append('file', file); body.append('scope', scope); return request<{ file_id: string; index: { tier: string } }>('/files', { method: 'POST', body }, token) }
export const searchKnowledge = (query: string, token: string) => request<{ data: Array<{ content: string; metadata: Record<string, string>; score: number }> }>('/knowledge/search', { method: 'POST', body: JSON.stringify({ query, top_k: 8, metadata: {} }) }, token)
export const createAgentJob = (task: string, token: string, fileIds: string[] = []) => request<{ job_id: string; status: string }>('/agent/run', { method: 'POST', body: JSON.stringify({ task, user_context: {}, attachments: fileIds.map((file_id) => ({ file_id })) }) }, token)
export const getJob = (jobId: string, token: string) => request<Job>(`/agent/${jobId}`, {}, token)
export const jobEventsUrl = (jobId: string, token: string) => `${API_BASE_URL}/agent/${jobId}/events?access_token=${encodeURIComponent(token)}`
export async function downloadArtifact(jobId: string, artifactName: string, token: string) {
  const response = await fetch(`${API_BASE_URL}/agent/${jobId}/artifacts/${encodeURIComponent(artifactName)}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) throw new Error(`Artifact download failed (${response.status})`)
  return response.blob()
}
