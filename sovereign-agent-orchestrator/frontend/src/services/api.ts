import type {
  AuthUser,
  Conversation,
  ConversationMessage,
  FileRecord,
  Job,
  JobEvent,
  JobSummary,
  KnowledgeSearchResult,
  LoginResponse,
  Readiness,
} from '../types/api'

export type { AuthUser, LoginResponse, FileRecord, Job, JobSummary, JobEvent, Conversation, ConversationMessage, KnowledgeSearchResult, Readiness }
// Kept for older imports written against the pre-rebuild api.ts, which exported the
// login/user type as `User` rather than `AuthUser`.
export type User = AuthUser

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8080/api/v1'

type ApiError = Error & { status?: number }

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
export const getReadiness = () => request<Readiness>('/ready')
export const devLogin = (username: string, password: string) => request<LoginResponse>('/auth/dev/login', { method: 'POST', body: JSON.stringify({ username, password }) })
export const getUploadScopes = (token: string) => request<{ scopes: string[] }>('/files/scopes', {}, token)
export const listFiles = (token: string) => request<{ data: FileRecord[] }>('/files', {}, token)
export const uploadFile = (file: File, scope: string, token: string) => { const body = new FormData(); body.append('file', file); body.append('scope', scope); return request<{ file_id: string; index: { tier: string } }>('/files', { method: 'POST', body }, token) }
export const deleteFile = (fileId: string, token: string) => request<{ file_id: string }>(`/files/${fileId}`, { method: 'DELETE' }, token)
export const searchKnowledge = (query: string, token: string) => request<{ data: KnowledgeSearchResult[] }>('/knowledge/search', { method: 'POST', body: JSON.stringify({ query, top_k: 8, metadata: {} }) }, token)
export const createAgentJob = (task: string, token: string, fileIds: string[] = []) => request<{ job_id: string; status: string }>('/agent/run', { method: 'POST', body: JSON.stringify({ task, user_context: {}, attachments: fileIds.map((file_id) => ({ file_id })) }) }, token)
export const listJobs = (token: string, limit = 20) => request<{ data: JobSummary[] }>(`/agent?limit=${limit}`, {}, token)
export const getJob = (jobId: string, token: string) => request<Job>(`/agent/${jobId}`, {}, token)

// Conversation-based chat (multi-turn, backs the Intelligence Feed). Distinct from
// createAgentJob/getJob above (single-shot task, no conversation) -- both create the
// same kind of job server-side, the conversation endpoints just also thread messages.
export const createConversation = (token: string, title = 'New conversation') => request<{ data: Conversation }>('/conversations', { method: 'POST', body: JSON.stringify({ title }) }, token)
export const listConversations = (token: string) => request<{ data: Conversation[] }>('/conversations', {}, token)
export const getConversation = (conversationId: string, token: string) => request<{ data: Conversation; messages: ConversationMessage[] }>(`/conversations/${conversationId}`, {}, token)
export const sendChatMessage = (message: string, token: string, conversationId?: string, fileIds: string[] = []) =>
  request<{ data: { job_id: string; conversation_id: string; status: string } }>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, conversation_id: conversationId, attachments: fileIds.map((file_id) => ({ file_id })) }),
  }, token)

export const approveJob = (jobId: string, approved: boolean, reviewerUserId: string, token: string) =>
  request<{ job_id: string; status: string }>(`/agent/${jobId}/approve`, { method: 'POST', body: JSON.stringify({ approved, reviewer_user_id: reviewerUserId }) }, token)
export const cancelJob = (jobId: string, token: string) => request<{ job_id: string; status: string }>(`/agent/${jobId}/cancel`, { method: 'POST' }, token)

// The events endpoint is a bearer-authenticated SSE stream, so it can't be read with
// EventSource (no custom headers). Read it by hand with fetch + a streaming reader
// instead, parsing "event:"/"data:" frames split on blank lines. Each frame's data
// line is the full stored envelope: {event_id, type, data, timestamp}.
export async function streamJobEvents(jobId: string, token: string, onEvent: (event: JobEvent) => void, signal?: AbortSignal) {
  const response = await fetch(`${API_BASE_URL}/agent/${jobId}/events`, { headers: { Authorization: `Bearer ${token}` }, signal })
  if (!response.ok || !response.body) throw new Error(`Event stream failed (${response.status})`)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const dataLine = frame.split('\n').find((line) => line.startsWith('data:'))
      if (!dataLine) continue
      try { onEvent(JSON.parse(dataLine.slice(5).trim()) as JobEvent) } catch { /* ignore malformed frame */ }
    }
  }
}
export async function downloadArtifact(jobId: string, artifactName: string, token: string) {
  const response = await fetch(`${API_BASE_URL}/agent/${jobId}/artifacts/${encodeURIComponent(artifactName)}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) throw new Error(`Artifact download failed (${response.status})`)
  return response.blob()
}
