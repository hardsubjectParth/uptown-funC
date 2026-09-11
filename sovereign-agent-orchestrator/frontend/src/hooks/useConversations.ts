import useSWR from 'swr'
import { getConversation, listConversations } from '../services/api'
import { useAuth } from '../context/AuthContext'

export function useConversations() {
  const { token } = useAuth()
  const { data, error, isLoading, mutate } = useSWR(
    token ? ['conversations', token] : null,
    ([, authToken]) => listConversations(authToken),
    { refreshInterval: 15000 },
  )
  return { conversations: data?.data ?? [], error, isLoading, mutate }
}

export function useConversation(conversationId?: string) {
  const { token } = useAuth()
  const { data, error, isLoading, mutate } = useSWR(
    token && conversationId ? ['conversation', conversationId, token] : null,
    ([, id, authToken]) => getConversation(id, authToken),
    { refreshInterval: 4000 },
  )
  return { conversation: data?.data, messages: data?.messages ?? [], error, isLoading, mutate }
}
