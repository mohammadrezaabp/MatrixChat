'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { ChatMessage } from '@/components/chat-message'
import { ChatInput } from '@/components/chat-input'
import { ChatSidebar, type Mode, type SchemaSummary, type ThreadSummary } from '@/components/chat-sidebar'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  isSql?: boolean
}

interface Thread {
  id: string
  title: string
  mode: Mode
  schemaId?: string | null
  messages: Message[]
  updatedAt: number
}

interface AuthUser {
  id: string
  username: string
}

interface UserSchema {
  id: string
  title: string
  schema: string
  updatedAt: number
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function greeting(mode: Mode): Message {
  return {
    id: uid(),
    role: 'assistant',
    content:
      mode === 'sql'
        ? 'Describe the data you want in plain English and I will turn it into a SQL query.'
        : 'Ask me anything in English. I can help answer questions, explain ideas, or draft text.',
  }
}

function newThread(mode: Mode): Thread {
  return {
    id: uid(),
    title: mode === 'sql' ? 'New SQL query' : 'New chat',
    mode,
    schemaId: null,
    messages: [greeting(mode)],
    updatedAt: Date.now(),
  }
}

function deriveTitle(text: string): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean) return 'New chat'
  return clean.length > 48 ? clean.slice(0, 48) + '…' : clean
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function apiListThreads(): Promise<Thread[]> {
  const res = await fetch(`${API_URL}/threads`, { credentials: 'include' })
  if (!res.ok) throw new Error(`Failed to load threads: ${res.status}`)
  return res.json()
}

async function apiSaveThread(thread: Thread): Promise<void> {
  const res = await fetch(`${API_URL}/threads/${thread.id}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread }),
  })
  if (!res.ok) throw new Error(`Failed to save thread: ${res.status}`)
}

async function apiDeleteThread(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/threads/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) throw new Error(`Failed to delete thread: ${res.status}`)
}

async function apiMe(): Promise<AuthUser> {
  const res = await fetch(`${API_URL}/auth/me`, { credentials: 'include' })
  if (!res.ok) throw new Error('Not authenticated')
  return res.json()
}

async function apiLogout(): Promise<void> {
  await fetch(`${API_URL}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  })
}

async function apiListSchemas(): Promise<UserSchema[]> {
  const res = await fetch(`${API_URL}/schemas`, { credentials: 'include' })
  if (!res.ok) throw new Error(`Failed to load schemas: ${res.status}`)
  return res.json()
}

async function apiCreateSchema(title: string, schema: string): Promise<UserSchema> {
  const res = await fetch(`${API_URL}/schemas`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, schema }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to create schema: ${res.status}`)
  }
  return res.json()
}

async function apiUpdateSchema(id: string, title: string, schema: string): Promise<UserSchema> {
  const res = await fetch(`${API_URL}/schemas/${id}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, schema }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to update schema: ${res.status}`)
  }
  return res.json()
}

async function apiDeleteSchema(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/schemas/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to delete schema: ${res.status}`)
  }
}

export default function ChatPage() {
  const router = useRouter()
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [schemas, setSchemas] = useState<UserSchema[]>([])
  const [selectedSchemaId, setSelectedSchemaId] = useState<string | null>(null)
  const [schemaTitle, setSchemaTitle] = useState('')
  const [schemaText, setSchemaText] = useState('')
  const [editingSchemaId, setEditingSchemaId] = useState<string | null>(null)
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [isSavingSchema, setIsSavingSchema] = useState(false)
  const [hydrated, setHydrated] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  // Track which thread id was last saved so we only PUT when something changed.
  const lastSaved = useRef<Record<string, number>>({})

  const markBackendOffline = useCallback((message?: string) => {
    setBackendOnline(false)
    if (message) setError(message)
  }, [])

  // Validate auth and load threads on mount.
  useEffect(() => {
    let cancelled = false

    const init = async () => {
      try {
        const me = await apiMe()
        if (cancelled) return
        setUser(me)

        const [loaded, loadedSchemas] = await Promise.all([
          apiListThreads(),
          apiListSchemas(),
        ])
        if (cancelled) return

        setSchemas(loadedSchemas)

        setBackendOnline(true)
        if (loaded.length > 0) {
          setThreads(loaded)
          setActiveId(loaded[0].id)
          if (loaded[0].mode === 'sql' && loaded[0].schemaId) {
            setSelectedSchemaId(loaded[0].schemaId)
          }
        } else {
          setThreads([])
          setActiveId(null)
        }
      } catch {
        if (cancelled) return
        router.replace('/login')
      } finally {
        if (!cancelled) setHydrated(true)
      }
    }

    init()

    return () => {
      cancelled = true
    }
  }, [router, markBackendOffline])

  // Persist changed threads to backend (only when backend is reachable)
  useEffect(() => {
    if (!hydrated || !backendOnline) return
    for (const t of threads) {
      if (lastSaved.current[t.id] !== t.updatedAt) {
        lastSaved.current[t.id] = t.updatedAt
        apiSaveThread(t).catch(() => {
          markBackendOffline()
        })
      }
    }
  }, [threads, hydrated, backendOnline, markBackendOffline])

  const active = threads.find(t => t.id === activeId) || null

  useEffect(() => {
    if (active?.mode === 'sql') {
      setSelectedSchemaId(active.schemaId || null)
    }
  }, [active?.id, active?.mode, active?.schemaId])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [active?.messages.length, active?.id])

  // Onboarding: when entering SQL mode with no saved schema, open schema editor.
  useEffect(() => {
    if (!hydrated || !user) return
    if (active?.mode === 'sql' && !active.schemaId) {
      setSchemaEditorOpen(true)
    }
  }, [active?.id, active?.mode, active?.schemaId, hydrated, user])

  const updateActive = useCallback(
    (mut: (t: Thread) => Thread) => {
      setThreads(prev => prev.map(t => (t.id === activeId ? mut(t) : t)))
    },
    [activeId]
  )

  const handleNewChat = (mode: Mode) => {
    const t = newThread(mode)
    if (mode === 'sql') {
      t.schemaId = selectedSchemaId
    }
    setThreads(prev => [t, ...prev])
    setActiveId(t.id)
    setError(null)
    if (backendOnline) {
      apiSaveThread(t).catch(() => {
        markBackendOffline()
      })
    }
  }

  const handleDelete = (id: string) => {
    if (backendOnline) {
      apiDeleteThread(id).catch(() => {
        markBackendOffline()
      })
    }
    setThreads(prev => {
      const next = prev.filter(t => t.id !== id)
      if (id === activeId) {
        if (next.length > 0) {
          setActiveId(next[0].id)
        } else {
          setActiveId(null)
          return []
        }
      }
      return next
    })
  }

  const summaries: ThreadSummary[] = threads.map(t => ({
    id: t.id,
    title: t.title,
    mode: t.mode,
    schemaId: t.schemaId,
    updatedAt: t.updatedAt,
  }))

  const schemaSummaries: SchemaSummary[] = schemas.map(s => ({
    id: s.id,
    title: s.title,
    updatedAt: s.updatedAt,
  }))

  const handleSendMessage = async (userMessage: string) => {
    if (!active) return
    if (active.mode === 'sql') {
      await handleTextToSql(userMessage)
    } else {
      await handleChatStream(userMessage)
    }
  }

  const handleChatStream = async (userMessage: string) => {
    if (!active) return
    setError(null)
    setIsLoading(true)

    const activeThreadId = active.id
    const userMsg: Message = { id: uid(), role: 'user', content: userMessage }
    const assistantId = uid()
    const assistantMsg: Message = { id: assistantId, role: 'assistant', content: '' }

    const historyForApi = active.messages
      .filter(m => m.content)
      .map(m => ({ role: m.role, content: m.content }))
      .concat([{ role: 'user', content: userMessage }])

    const isFirstUserMessage = !active.messages.some(m => m.role === 'user')

    updateActive(t => ({
      ...t,
      title: isFirstUserMessage ? deriveTitle(userMessage) : t.title,
      messages: [...t.messages, userMsg, assistantMsg],
      updatedAt: Date.now(),
    }))

    const patchAssistant = (content: string) => {
      setThreads(prev =>
        prev.map(t =>
          t.id === activeThreadId
            ? {
                ...t,
                messages: t.messages.map(m =>
                  m.id === assistantId ? { ...m, content } : m
                ),
                updatedAt: Date.now(),
              }
            : t
        )
      )
    }

    try {
      const response = await fetch(`${API_URL}/chat-stream`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: historyForApi,
          temperature: 0.7,
          top_p: 0.9,
        }),
      })

      if (!response.ok || !response.body) {
        const text = await response.text().catch(() => '')
        throw new Error(text || `API error: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let acc = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let nlIdx: number
        while ((nlIdx = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, nlIdx).trim()
          buffer = buffer.slice(nlIdx + 1)
          if (!line) continue
          let obj: any
          try {
            obj = JSON.parse(line)
          } catch {
            continue
          }
          if (obj.error) throw new Error(obj.error)
          if (typeof obj.delta === 'string' && obj.delta) {
            acc += obj.delta
            patchAssistant(acc)
          }
        }
      }

      if (!acc) patchAssistant('[No response from model]')
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'No response received.'
      setError(errorMessage)
      patchAssistant(
        `[Error]\n${errorMessage}\n\nMake sure the Python service is running on port 8000 and Ollama is available.`
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleTextToSql = async (userMessage: string) => {
    if (!active) return
    if (!active.schemaId) {
      setSchemaEditorOpen(true)
      setError('Select a schema for this SQL conversation first.')
      return
    }

    setError(null)
    setIsLoading(true)

    const activeThreadId = active.id
    const userMsg: Message = { id: uid(), role: 'user', content: userMessage }
    const assistantId = uid()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isSql: true,
    }
    const isFirstUserMessage = !active.messages.some(m => m.role === 'user')

    updateActive(t => ({
      ...t,
      title: isFirstUserMessage ? deriveTitle(userMessage) : t.title,
      messages: [...t.messages, userMsg, assistantMsg],
      updatedAt: Date.now(),
    }))

    const patchAssistant = (patch: Partial<Message>) => {
      setThreads(prev =>
        prev.map(t =>
          t.id === activeThreadId
            ? {
                ...t,
                messages: t.messages.map(m =>
                  m.id === assistantId ? { ...m, ...patch } : m
                ),
                updatedAt: Date.now(),
              }
            : t
        )
      )
    }

    try {
      const historyForApi = active.messages
        .filter(m => m.content)
        .map(m => ({ role: m.role, content: m.content, isSql: !!m.isSql }))
        .concat([{ role: 'user', content: userMessage, isSql: false }])

      const response = await fetch(`${API_URL}/text-to-sql`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMessage,
          schemaId: active.schemaId,
          messages: historyForApi,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `API error: ${response.status}`)
      }

      const data = await response.json()
      patchAssistant({ content: data.sql, isSql: true })
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'SQL generation failed.'
      setError(errorMessage)
      patchAssistant({
        content: `[Error]\n${errorMessage}\n\nPlease check that the Python service is running and a valid schema is selected.`,
        isSql: false,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectSchema = (schemaId: string) => {
    setSelectedSchemaId(schemaId)
    setSchemaEditorOpen(false)
    setError(null)

    if (active && active.mode === 'sql') {
      updateActive(t => ({ ...t, schemaId, updatedAt: Date.now() }))
      return
    }

    const t = newThread('sql')
    t.schemaId = schemaId
    setThreads(prev => [t, ...prev])
    setActiveId(t.id)
  }

  const handleCreateSchema = () => {
    setEditingSchemaId(null)
    setSchemaTitle('')
    setSchemaText('')
    setSchemaEditorOpen(true)
    setError(null)
  }

  const handleEditSchema = (schemaId: string) => {
    const found = schemas.find(s => s.id === schemaId)
    if (!found) return
    setEditingSchemaId(found.id)
    setSchemaTitle(found.title)
    setSchemaText(found.schema)
    setSchemaEditorOpen(true)
    setError(null)
  }

  const handleDeleteSchema = async (schemaId: string) => {
    try {
      await apiDeleteSchema(schemaId)
      setSchemas(prev => prev.filter(s => s.id !== schemaId))
      setThreads(prev => prev.map(t => (t.schemaId === schemaId ? { ...t, schemaId: null } : t)))
      if (selectedSchemaId === schemaId) setSelectedSchemaId(null)
      if (editingSchemaId === schemaId) {
        setEditingSchemaId(null)
        setSchemaTitle('')
        setSchemaText('')
        setSchemaEditorOpen(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete schema')
    }
  }

  const handleSaveSchema = async () => {
    const title = schemaTitle.trim()
    const trimmed = schemaText.trim()
    if (title.length < 2) {
      setError('Schema title must be at least 2 characters.')
      return
    }
    if (!trimmed) {
      setError('Schema cannot be empty.')
      return
    }

    setIsSavingSchema(true)
    setError(null)
    try {
      const saved = editingSchemaId
        ? await apiUpdateSchema(editingSchemaId, title, trimmed)
        : await apiCreateSchema(title, trimmed)

      setSchemas(prev => {
        const without = prev.filter(s => s.id !== saved.id)
        return [saved, ...without]
      })
      setSelectedSchemaId(saved.id)
      if (active?.mode === 'sql') {
        updateActive(t => ({ ...t, schemaId: saved.id, updatedAt: Date.now() }))
      }

      setEditingSchemaId(saved.id)
      setSchemaTitle(saved.title)
      setSchemaText(saved.schema)
      setSchemaEditorOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schema')
    } finally {
      setIsSavingSchema(false)
    }
  }

  const handleLogout = async () => {
    try {
      await apiLogout()
    } finally {
      router.replace('/login')
    }
  }

  if (!hydrated) {
    return (
      <main className="grid h-dvh place-items-center bg-background text-foreground">
        <p className="text-sm text-muted-foreground">Loading session...</p>
      </main>
    )
  }

  if (!user) {
    return (
      <main className="grid h-dvh place-items-center bg-background text-foreground">
        <p className="text-sm text-muted-foreground">Redirecting to login...</p>
      </main>
    )
  }

  return (
    <main
      dir="ltr"
      lang="en"
      className="h-dvh flex bg-background text-foreground overflow-hidden"
    >
      <ChatSidebar
        threads={summaries}
        schemas={schemaSummaries}
        selectedSchemaId={selectedSchemaId}
        activeId={activeId}
        onSelect={(id) => {
          setActiveId(id)
          setError(null)
        }}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
        onSelectSchema={handleSelectSchema}
        onCreateSchema={handleCreateSchema}
        onEditSchema={handleEditSchema}
        onDeleteSchema={handleDeleteSchema}
        onLogout={handleLogout}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <div className="border-b border-border/70 bg-card/40 backdrop-blur">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3 pl-10 md:pl-0">
              <span className="text-sm font-semibold tracking-wide">
                {!active ? 'Choose a conversation type' : active.mode === 'sql' ? 'Text to SQL' : 'Chat'}
              </span>
              {active?.mode === 'sql' && !active.schemaId && (
                <span className="rounded-full border border-amber-500/50 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                  Schema required
                </span>
              )}
              {user && (
                <span className="text-xs text-muted-foreground">@{user.username}</span>
              )}
              {active && (
                <span className="line-clamp-1 text-xs text-muted-foreground">
                  {active.title}
                </span>
              )}
            </div>
          
            {active?.mode === 'sql' && (
              <button
                type="button"
                onClick={() => {
                  if (active.schemaId) {
                    handleEditSchema(active.schemaId)
                  } else {
                    handleCreateSchema()
                  }
                }}
                className="inline-flex shrink-0 items-center gap-2 rounded-full border border-border bg-background/50 px-3 py-1.5 text-xs font-medium text-foreground transition-all hover:border-primary"
              >
                {active.schemaId ? 'Edit Selected Schema' : 'Add Schema'}
              </button>
            )}
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col min-h-0 px-4 py-6 sm:px-6 lg:px-8">
          {active?.mode === 'sql' && schemaEditorOpen && (
            <div className="mb-4 rounded-2xl border border-border bg-card/60 p-4">
              <p className="mb-2 text-sm font-medium">SQL Schema</p>
              <p className="mb-3 text-xs text-muted-foreground">
                Schemas are stored per account. Add a title and paste CREATE TABLE statements.
              </p>
              <input
                value={schemaTitle}
                onChange={(e) => setSchemaTitle(e.target.value)}
                className="mb-3 w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="Schema title (e.g., Brokerage DB)"
              />
              <textarea
                value={schemaText}
                onChange={(e) => setSchemaText(e.target.value)}
                className="matrix-scrollbar min-h-40 w-full resize-y rounded-xl border border-border bg-background/60 px-3 py-2 text-xs font-mono outline-none focus:border-primary"
                placeholder="CREATE TABLE Users (...);"
              />
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleSaveSchema}
                  disabled={isSavingSchema}
                  className="rounded-xl border border-primary bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isSavingSchema ? 'Saving...' : editingSchemaId ? 'Update Schema' : 'Create Schema'}
                </button>
                <button
                  type="button"
                  onClick={() => setSchemaEditorOpen(false)}
                  className="rounded-xl border border-border bg-background/40 px-3 py-1.5 text-xs text-muted-foreground"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          <div className="matrix-scrollbar flex-1 min-h-0 overflow-y-auto space-y-4 rounded-3xl border border-border bg-card/35 p-4 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.65)] sm:p-6">
            {!active ? (
              <div className="flex h-full min-h-56 flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border/80 bg-background/20 p-6 text-center">
                <p className="text-sm text-muted-foreground">
                  Start by choosing what you want to create.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleNewChat('chat')}
                    className="rounded-xl border border-primary bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary"
                  >
                    New Chat
                  </button>
                  <button
                    type="button"
                    onClick={() => handleNewChat('sql')}
                    className="rounded-xl border border-border bg-background/60 px-3 py-1.5 text-xs font-medium text-foreground hover:border-primary"
                  >
                    New Text to SQL
                  </button>
                </div>
              </div>
            ) : (
              active.messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  role={message.role}
                  content={message.content}
                  isSql={message.isSql}
                  isLoading={
                    isLoading &&
                    message.role === 'assistant' &&
                    !message.content
                  }
                />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {error && (
            <div className="mt-4 rounded-2xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              <span className="font-semibold">Error:</span> {error}
            </div>
          )}

          <div className="pt-4">
            <ChatInput
              onSubmit={handleSendMessage}
              isLoading={isLoading}
              disabled={!active}
              placeholder={
                active?.mode === 'sql'
                  ? 'Describe the query you want...'
                  : active
                    ? 'Type your message...'
                    : 'Choose a conversation type to begin...'
              }
            />
          </div>
        </div>
      </div>
    </main>
  )
}
