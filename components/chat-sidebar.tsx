'use client'

import { useState } from 'react'

export type Mode = 'chat' | 'sql'

export interface ThreadSummary {
  id: string
  title: string
  mode: Mode
  schemaId?: string | null
  updatedAt: number
}

export interface SchemaSummary {
  id: string
  title: string
  updatedAt: number
}

interface ChatSidebarProps {
  threads: ThreadSummary[]
  schemas: SchemaSummary[]
  username?: string | null
  onEditProfile?: () => void
  selectedSchemaId: string | null
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: (mode: Mode) => void
  onDelete: (id: string) => void
  onSelectSchema: (id: string) => void
  onCreateSchema: () => void
  onEditSchema: (id: string) => void
  onDeleteSchema: (id: string) => void
  onLogout?: () => void
}

function formatRelative(ts: number) {
  const diff = Date.now() - ts
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(ts).toLocaleDateString()
}

export function ChatSidebar({
  threads,
  schemas,
  username,
  selectedSchemaId,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onSelectSchema,
  onCreateSchema,
  onEditSchema,
  onDeleteSchema,
  onLogout,
  onEditProfile,
}: ChatSidebarProps) {
  const [open, setOpen] = useState(false)
  const [newOpen, setNewOpen] = useState(false)
  const [schemasOpen, setSchemasOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [sqlOpen, setSqlOpen] = useState(false)
  const [schemasExpanded, setSchemasExpanded] = useState(false)
  const [chatExpanded, setChatExpanded] = useState(false)
  const [sqlExpanded, setSqlExpanded] = useState(false)
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)

  const sorted = [...threads].sort((a, b) => b.updatedAt - a.updatedAt)
  const chatThreads = sorted.filter(t => t.mode === 'chat')
  const sqlThreads = sorted.filter(t => t.mode === 'sql')
  const sortedSchemas = [...schemas].sort((a, b) => b.updatedAt - a.updatedAt)

  const visibleSchemas = sortedSchemas.slice(0, 3)
  const extraSchemas = sortedSchemas.slice(3)
  const visibleChatThreads = chatThreads.slice(0, 3)
  const extraChatThreads = chatThreads.slice(3)
  const visibleSqlThreads = sqlThreads.slice(0, 3)
  const extraSqlThreads = sqlThreads.slice(3)
  const chatCount = chatThreads.length
  const sqlCount = sqlThreads.length
  const schemaCount = sortedSchemas.length

  const renderItem = (t: ThreadSummary) => (
    <li key={t.id}>
      <div
        className={`group relative flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-all ${
          activeId === t.id
            ? 'border-primary/80 bg-primary/10 text-foreground shadow-sm shadow-primary/20'
            : 'border-border/60 bg-background/50 text-foreground hover:border-border hover:bg-card/80'
        }`}
      >
        <button
          type="button"
          onClick={() => {
            onSelect(t.id)
            setOpen(false)
          }}
          className="flex flex-1 flex-col items-start text-left"
        >
          <span className="line-clamp-1 w-full">{t.title}</span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {t.mode === 'sql' ? 'SQL' : 'Chat'} · {formatRelative(t.updatedAt)}
          </span>
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            if (confirm('Delete this conversation?')) onDelete(t.id)
          }}
          aria-label="Delete"
          className="rounded-md p-1 text-muted-foreground opacity-80 transition-opacity hover:bg-destructive/10 hover:text-destructive md:opacity-0 md:group-hover:opacity-100"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m2 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6h12z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </li>
  )

  const renderSchemaItem = (s: SchemaSummary) => (
    <li key={s.id}>
      <div
        className={`group relative flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-all ${
          selectedSchemaId === s.id
            ? 'border-primary/80 bg-primary/10 text-foreground shadow-sm shadow-primary/20'
            : 'border-border/60 bg-background/50 text-foreground hover:border-border hover:bg-card/80'
        }`}
      >
        <button
          type="button"
          onClick={() => {
            onSelectSchema(s.id)
            setOpen(false)
          }}
          className="flex flex-1 flex-col items-start text-left"
        >
          <span className="line-clamp-1 w-full">{s.title}</span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {formatRelative(s.updatedAt)}
          </span>
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onEditSchema(s.id)
            setOpen(false)
          }}
          aria-label="Edit schema"
          className="rounded-md p-1 text-muted-foreground opacity-80 transition-opacity hover:bg-background/60 hover:text-foreground md:opacity-0 md:group-hover:opacity-100"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M4 20h4l10-10a2 2 0 0 0-4-4L4 16v4z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            if (confirm('Delete this schema?')) onDeleteSchema(s.id)
          }}
          aria-label="Delete schema"
          className="rounded-md p-1 text-muted-foreground opacity-80 transition-opacity hover:bg-destructive/10 hover:text-destructive md:opacity-0 md:group-hover:opacity-100"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m2 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6h12z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </li>
  )

  const sidebarBody = (
    <>
      <div className="relative">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setNewOpen(v => !v)}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-primary bg-primary px-3 py-2 text-sm font-medium text-background shadow-md shadow-primary/20 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/30"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            New Chat
          </button>
       
        </div>
        {newOpen && (
          <div className="absolute left-0 right-0 top-full z-10 mt-1 overflow-hidden rounded-xl border border-border bg-card shadow-lg">
            <button
              type="button"
              onClick={() => {
                onNewChat('chat')
                setNewOpen(false)
                setOpen(false)
              }}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-background/60"
            >
              + New Chat
            </button>
            <button
              type="button"
              onClick={() => {
                onNewChat('sql')
                setNewOpen(false)
                setOpen(false)
              }}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-background/60"
            >
              + New Text to SQL
            </button>
          </div>
        )}
      </div>

      <div className="matrix-scrollbar mt-4 flex-1 min-h-0 overflow-y-auto pr-1">
        <div className="space-y-4">
          {sorted.length === 0 && (
            <p className="px-2 py-2 text-center text-xs text-muted-foreground">
              No conversations yet. Create one above.
            </p>
          )}

          <div className="rounded-2xl border border-border/70 bg-background/25 p-2">
            <button
              type="button"
              onClick={() => setSqlOpen(v => !v)}
              className="mb-2 flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-background/50 hover:text-foreground"
            >
              <span>Text to SQL</span>
              <span className="inline-flex items-center gap-2">
                <span className="rounded-full border border-border bg-background/70 px-2 py-0.5 text-[10px] font-medium normal-case tracking-normal text-muted-foreground">
                  {sqlCount}
                </span>
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden
                  className={`transition-transform ${sqlOpen ? 'rotate-90' : ''}`}
                >
                  <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </button>
            {sqlOpen && (
              <div className="space-y-2">
                {sqlThreads.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-border/80 px-2 py-3 text-center text-xs text-muted-foreground">
                    No SQL conversations yet.
                  </p>
                ) : (
                  <>
                    <ul className="space-y-1">
                      {visibleSqlThreads.map(renderItem)}
                      {sqlExpanded && extraSqlThreads.map(renderItem)}
                    </ul>
                    {extraSqlThreads.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setSqlExpanded(v => !v)}
                        className="inline-flex w-full items-center justify-center gap-1 rounded-lg border border-dashed border-border/80 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-background/40 hover:text-foreground"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden className={`${sqlExpanded ? 'rotate-180' : ''} transition-transform`}>
                          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        {sqlExpanded ? `Show less (${extraSqlThreads.length})` : `Show more (${extraSqlThreads.length})`}
                      </button>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-border/70 bg-background/25 p-2">
            <button
              type="button"
              onClick={() => setChatOpen(v => !v)}
              className="mb-2 flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-background/50 hover:text-foreground"
            >
              <span>Chat</span>
              <span className="inline-flex items-center gap-2">
                <span className="rounded-full border border-border bg-background/70 px-2 py-0.5 text-[10px] font-medium normal-case tracking-normal text-muted-foreground">
                  {chatCount}
                </span>
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden
                  className={`transition-transform ${chatOpen ? 'rotate-90' : ''}`}
                >
                  <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </button>
            {chatOpen && (
              <div className="space-y-2">
                {chatThreads.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-border/80 px-2 py-3 text-center text-xs text-muted-foreground">
                    No chat conversations yet.
                  </p>
                ) : (
                  <>
                    <ul className="space-y-1">
                      {visibleChatThreads.map(renderItem)}
                      {chatExpanded && extraChatThreads.map(renderItem)}
                    </ul>
                    {extraChatThreads.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setChatExpanded(v => !v)}
                        className="inline-flex w-full items-center justify-center gap-1 rounded-lg border border-dashed border-border/80 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-background/40 hover:text-foreground"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden className={`${chatExpanded ? 'rotate-180' : ''} transition-transform`}>
                          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        {chatExpanded ? `Show less (${extraChatThreads.length})` : `Show more (${extraChatThreads.length})`}
                      </button>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-border/70 bg-background/25 p-2">
            <div className="mb-2 flex items-center justify-between px-1">
              <button
                type="button"
                onClick={() => setSchemasOpen(v => !v)}
                className="flex flex-1 items-center justify-between rounded-xl px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-background/50 hover:text-foreground"
              >
                <span>Schemas</span>
                <span className="inline-flex items-center gap-2">
                  <span className="rounded-full border border-border bg-background/70 px-2 py-0.5 text-[10px] font-medium normal-case tracking-normal text-muted-foreground">
                    {schemaCount}
                  </span>
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden
                    className={`transition-transform ${schemasOpen ? 'rotate-90' : ''}`}
                  >
                    <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              </button>
              <button
                type="button"
                onClick={() => {
                  onCreateSchema()
                  setOpen(false)
                }}
                className="ml-2 rounded-lg border border-border bg-background/40 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-background/70 hover:text-foreground"
              >
                Add
              </button>
            </div>

            {schemasOpen &&
              (schemas.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border/80 px-2 py-3 text-center text-xs text-muted-foreground">
                  No schemas yet.
                </p>
              ) : (
                <div className="space-y-2">
                  <ul className="space-y-1">
                    {visibleSchemas.map(renderSchemaItem)}
                    {schemasExpanded && extraSchemas.map(renderSchemaItem)}
                  </ul>
                  {extraSchemas.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSchemasExpanded(v => !v)}
                      className="inline-flex w-full items-center justify-center gap-1 rounded-lg border border-dashed border-border/80 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-background/40 hover:text-foreground"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden className={`${schemasExpanded ? 'rotate-180' : ''} transition-transform`}>
                        <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      {schemasExpanded ? `Show less (${extraSchemas.length})` : `Show more (${extraSchemas.length})`}
                    </button>
                  )}
                </div>
              ))}
          </div>
        </div>
      </div>
    </>
  )

  return (
    <>
      {/* Mobile toggle */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open conversations"
        className="fixed left-3 top-3 z-30 inline-flex items-center justify-center rounded-lg border border-border bg-card/80 p-2 backdrop-blur md:hidden"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {/* Desktop sidebar */}
      <aside className="hidden h-dvh w-72 shrink-0 flex-col border-r border-border/70 bg-card/40 p-4 backdrop-blur md:flex">
        <div className="mb-4 px-1 text-center">
          <span className="text-lg font-semibold tracking-wide text-foreground">Construct</span>
        </div>
        {sidebarBody}
        {onLogout && (
          <div className="relative mt-3 border-t border-border/70 pt-3">
            {username && (
              <div className="mb-2">
                <button
                  type="button"
                  onClick={() => setProfileMenuOpen(v => !v)}
                  className="flex w-full items-center justify-between rounded-lg border border-border bg-background/30 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-background/60 hover:text-foreground"
                >
                  <span>@{username}</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden className={`transition-transform ${profileMenuOpen ? 'rotate-180' : ''}`}>
                    <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                {profileMenuOpen && (
                  <div className="mt-1 overflow-hidden rounded-lg border border-border bg-card">
                    <button
                      type="button"
                      onClick={() => {
                        setProfileMenuOpen(false)
                        onEditProfile?.()
                      }}
                      className="block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-background/60"
                    >
                      Edit Profile
                    </button>
                  </div>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={onLogout}
              className="w-full rounded-xl border border-border bg-background/40 px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-background/70 hover:text-foreground"
            >
              Logout
            </button>
          </div>
        )}
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 flex h-full w-72 flex-col border-r border-border bg-card p-4 shadow-xl">
            <div className="mb-4 flex items-center justify-between px-1">
              <span className="text-sm font-semibold tracking-wide text-foreground">Construct</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="rounded-md p-1 text-muted-foreground hover:bg-background/60"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                  <path d="M6 6l12 12M6 18L18 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            {sidebarBody}
            {onLogout && (
              <div className="relative mt-3 border-t border-border/70 pt-3">
                {username && (
                  <div className="mb-2">
                    <button
                      type="button"
                      onClick={() => setProfileMenuOpen(v => !v)}
                      className="flex w-full items-center justify-between rounded-lg border border-border bg-background/30 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-background/60 hover:text-foreground"
                    >
                      <span>@{username}</span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden className={`transition-transform ${profileMenuOpen ? 'rotate-180' : ''}`}>
                        <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </button>
                    {profileMenuOpen && (
                      <div className="mt-1 overflow-hidden rounded-lg border border-border bg-card">
                        <button
                          type="button"
                          onClick={() => {
                            setProfileMenuOpen(false)
                            onEditProfile?.()
                            setOpen(false)
                          }}
                          className="block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-background/60"
                        >
                          Edit Profile
                        </button>
                      </div>
                    )}
                  </div>
                )}
                <button
                  type="button"
                  onClick={onLogout}
                  className="w-full rounded-xl border border-border bg-background/40 px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-background/70 hover:text-foreground"
                >
                  Logout
                </button>
              </div>
            )}
          </aside>
        </div>
      )}
    </>
  )
}
