import { NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../../context/AuthContext'
import { useConversations } from '../../hooks/useConversations'
import { RANK } from './rank'
import { FeedIcon, KnowledgeIcon, TasksIcon, ArtifactsIcon } from './icons'
import { createConversation } from '../../services/api'
import type { Conversation } from '../../types/api'

const NAV = [
  { to: '/app/feed', label: 'Intelligence Feed', Icon: FeedIcon },
  { to: '/app/knowledge', label: 'Knowledge Base', Icon: KnowledgeIcon },
  { to: '/app/tasks', label: 'Agent Tasks', Icon: TasksIcon },
  { to: '/app/artifacts', label: 'Artifacts', Icon: ArtifactsIcon },
]

function isToday(iso: string) {
  const date = new Date(iso)
  const now = new Date()
  return date.toDateString() === now.toDateString()
}

function isWithinDays(iso: string, days: number) {
  const diff = Date.now() - new Date(iso).getTime()
  return diff >= 0 && diff <= days * 24 * 60 * 60 * 1000
}

function groupSessions(conversations: Conversation[]) {
  const today: Conversation[] = []
  const previous7: Conversation[] = []
  const older: Conversation[] = []
  for (const conversation of conversations) {
    if (isToday(conversation.updated_at)) today.push(conversation)
    else if (isWithinDays(conversation.updated_at, 7)) previous7.push(conversation)
    else older.push(conversation)
  }
  return { today, previous7, older }
}

function Sidebar() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()
  const { conversations, mutate } = useConversations()
  const { today, previous7, older } = groupSessions(conversations)
  const rank = user ? RANK[user.role] : RANK.lower

  function signOut() {
    logout()
    navigate('/login', { replace: true })
  }

  async function newSession() {
    if (!token) return
    const created = await createConversation(token, 'New session')
    mutate()
    navigate(`/app/feed/${created.data.id}`)
  }

  const sessionGroups: Array<[string, Conversation[]]> = [
    ['Today', today],
    ['Previous 7 Days', previous7],
    ...(older.length ? [['Earlier', older] as [string, Conversation[]]] : []),
  ]

  return (
    <aside className="flex h-screen w-[260px] shrink-0 flex-col border-r border-white/8 bg-black/40 p-5">
      <div className="px-1">
        <h1 className="text-base font-semibold tracking-tight text-foreground">Sovereign AI</h1>
      </div>

      <nav className="mt-8 flex flex-col gap-0.5" aria-label="Main navigation">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
                isActive ? 'bg-surface-raised text-accent' : 'text-muted-foreground hover:text-foreground hover:bg-surface'
              }`
            }
          >
            <Icon />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="my-5 border-t border-white/8" />

      <div className="flex gap-2">
        <button type="button" onClick={newSession} className="flex-1 border border-accent/50 px-3 py-2 text-xs font-medium text-accent transition hover:bg-accent/10">
          New Session
        </button>
        <button type="button" className="flex-1 border border-white/12 px-3 py-2 text-xs font-medium text-muted-foreground transition hover:text-foreground">
          Archive
        </button>
      </div>

      <div className="mt-5 flex-1 overflow-y-auto">
        {sessionGroups.map(([heading, items]) =>
          items.length ? (
            <div key={heading} className="mb-4">
              <p className="label-micro mb-1.5 px-1">{heading}</p>
              <div className="flex flex-col gap-0.5">
                {items.map((conversation) => (
                  <NavLink
                    key={conversation.id}
                    to={`/app/feed/${conversation.id}`}
                    className="relative block px-3 py-1.5 text-sm text-foreground/90 hover:bg-surface"
                  >
                    {({ isActive }) => (
                      <>
                        {isActive ? (
                          <motion.span layoutId="session-active" className="absolute inset-y-0 left-0 w-0.5 bg-accent" />
                        ) : null}
                        <span className="block truncate">{conversation.title}</span>
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ) : null,
        )}
        {conversations.length === 0 ? <p className="px-1 text-xs text-muted-foreground">No sessions yet.</p> : null}
      </div>

      <div className="mt-auto pt-4">
        <div className="border-hairline bg-surface px-3 py-2.5">
          <p className="text-sm font-medium text-foreground">{rank.name}</p>
          <p className="label-micro mt-0.5">{rank.subtitle}</p>
        </div>
        <button type="button" onClick={signOut} className="mt-2 w-full border border-white/12 px-3 py-2 text-xs text-muted-foreground transition hover:text-foreground">
          Sign Out
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
