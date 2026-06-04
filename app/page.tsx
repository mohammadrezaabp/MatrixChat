'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { ChatMessage } from '@/components/chat-message'
import { ChatInput } from '@/components/chat-input'
import { ChatSidebar, type Mode, type SchemaSummary, type ThreadSummary } from '@/components/chat-sidebar'
import { sanitizeDownloadBasename } from '@/lib/download'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  isSql?: boolean
  sqlStatus?: string
}

interface Thread {
  id: string
  title: string
  mode: Mode
  schemaId?: string | null
  sqlModel?: string | null
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
  faq: string
  updatedAt: number
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const ACTIVE_THREAD_STORAGE_KEY = 'construct.activeThreadId'
const WELCOME_TEXT = 'Welcome to Construct...'
const DEEPSEEK_SQL_PROVIDER = 'deepseek'
const OLLAMA_SQL_PROVIDER = 'ollama'

function formatSqlStatus(intent?: string | null, cached?: boolean): string | undefined {
  if (cached) return 'Instant reply (cached)'
  if (intent === 'refine') return 'Refining previous query'
  if (intent === 'enhance') return 'Optimizing previous query'
  return undefined
}

const SQL_MODEL_OPTIONS = [
  { id: DEEPSEEK_SQL_PROVIDER, title: 'DeepSeek-V4-Pro' },
  { id: OLLAMA_SQL_PROVIDER, title: 'Ollama qwen2.5-coder:7b-instruct-q4_K_M' },
] as const

function formatSqlModelTitle(model: string | null | undefined) {
  return SQL_MODEL_OPTIONS.find((option) => option.id === model)?.title || 'DeepSeek-V4-Pro'
}

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function nextUpdatedAt(previous: number) {
  return Math.max(Date.now(), previous + 1)
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
    sqlModel: mode === 'sql' ? DEEPSEEK_SQL_PROVIDER : null,
    messages: [greeting(mode)],
    updatedAt: Date.now(),
  }
}

function deriveTitle(text: string): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean) return 'New chat'
  return clean.length > 48 ? clean.slice(0, 48) + '…' : clean
}

function findUserPromptBefore(messages: Message[], index: number): string {
  for (let i = index - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'user' && messages[i].content.trim()) {
      return messages[i].content.trim()
    }
  }
  return 'query'
}

function sqlDownloadFilenameForMessage(messages: Message[], index: number): string {
  const sqlIndex =
    messages.slice(0, index + 1).filter(m => m.role === 'assistant' && m.isSql && m.content.trim())
      .length || 1
  const base = sanitizeDownloadBasename(findUserPromptBefore(messages, index))
  return `${base}-${sqlIndex}.sql`
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

function parseContentDispositionFilename(header: string | null, fallback: string): string {
  if (!header) return fallback
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const plainMatch = header.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1]?.trim() || fallback
}

async function apiExportThreadSql(threadId: string, fallbackTitle: string): Promise<void> {
  const res = await fetch(`${API_URL}/threads/${threadId}/export`, { credentials: 'include' })
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(
      typeof errorData.detail === 'string'
        ? errorData.detail
        : `Export failed: ${res.status}`
    )
  }
  const blob = await res.blob()
  const filename = parseContentDispositionFilename(
    res.headers.get('Content-Disposition'),
    `${fallbackTitle.replace(/[^\w\-]+/g, '-').slice(0, 80) || 'queries'}.sql`
  )
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
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

async function apiUpdateProfile(params: {
  currentPassword: string
  username?: string
  newPassword?: string
}): Promise<AuthUser> {
  const res = await fetch(`${API_URL}/auth/profile`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to update profile: ${res.status}`)
  }
  return res.json()
}

async function apiListSchemas(): Promise<UserSchema[]> {
  const res = await fetch(`${API_URL}/schemas`, { credentials: 'include' })
  if (!res.ok) throw new Error(`Failed to load schemas: ${res.status}`)
  return res.json()
}

async function apiCreateSchema(title: string, schema: string, faq: string): Promise<UserSchema> {
  const res = await fetch(`${API_URL}/schemas`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, schema, faq }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to create schema: ${res.status}`)
  }
  return res.json()
}

async function apiUpdateSchema(id: string, title: string, schema: string, faq: string): Promise<UserSchema> {
  const res = await fetch(`${API_URL}/schemas/${id}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, schema, faq }),
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
  const [sendingThreads, setSendingThreads] = useState<Record<string, boolean>>({})
  const [error, setError] = useState<string | null>(null)
  const [schemas, setSchemas] = useState<UserSchema[]>([])
  const [schemaTitle, setSchemaTitle] = useState('')
  const [schemaText, setSchemaText] = useState('')
  const [schemaFaqText, setSchemaFaqText] = useState('')
  const [editingSchemaId, setEditingSchemaId] = useState<string | null>(null)
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [sqlThreadSchemaPickerOpen, setSqlThreadSchemaPickerOpen] = useState(false)
  const [selectedSchemaForNewSqlThread, setSelectedSchemaForNewSqlThread] = useState<string | null>(null)
  const [selectedModelForNewSqlThread, setSelectedModelForNewSqlThread] = useState<string>(DEEPSEEK_SQL_PROVIDER)
  const [schemaDropdownOpen, setSchemaDropdownOpen] = useState(false)
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [createSqlThreadOnSchemaSave, setCreateSqlThreadOnSchemaSave] = useState(false)
  const [isSavingSchema, setIsSavingSchema] = useState(false)
  const [profileEditorOpen, setProfileEditorOpen] = useState(false)
  const [profileUsername, setProfileUsername] = useState('')
  const [profileCurrentPassword, setProfileCurrentPassword] = useState('')
  const [profileNewPassword, setProfileNewPassword] = useState('')
  const [profileConfirmPassword, setProfileConfirmPassword] = useState('')
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [hydrated, setHydrated] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)
  const [typedWelcome, setTypedWelcome] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const schemaTextAreaRef = useRef<HTMLTextAreaElement>(null)
  const schemaGutterRef = useRef<HTMLDivElement>(null)
  const hasHydratedRef = useRef(false)
  // Track which thread id was last saved so we only PUT when something changed.
  const lastSaved = useRef<Record<string, number>>({})

  const markBackendOffline = useCallback((message?: string) => {
    setBackendOnline(false)
    if (message) setError(message)
  }, [])

  // Validate auth and load threads on mount.
  useEffect(() => {
    let cancelled = false
    const storedActiveId =
      typeof window !== 'undefined'
        ? window.localStorage.getItem(ACTIVE_THREAD_STORAGE_KEY)
        : null

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
        setThreads(loaded)
        const hasStoredActive =
          !!storedActiveId && loaded.some((thread) => thread.id === storedActiveId)
        setActiveId(hasStoredActive ? storedActiveId : null)
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

  useEffect(() => {
    if (hydrated) {
      hasHydratedRef.current = true
    }
  }, [hydrated])

  useEffect(() => {
    if (!hasHydratedRef.current) return
    if (typeof window === 'undefined') return
    if (activeId) {
      window.localStorage.setItem(ACTIVE_THREAD_STORAGE_KEY, activeId)
    } else {
      window.localStorage.removeItem(ACTIVE_THREAD_STORAGE_KEY)
    }
  }, [activeId])

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
  const activeThreadIsSending = !!active && !!sendingThreads[active.id]

  const findRetryPrompt = useCallback((messages: Message[], fromIndex: number): string | null => {
    for (let i = fromIndex - 1; i >= 0; i -= 1) {
      const candidate = messages[i]
      if (candidate.role === 'user' && candidate.content.trim()) {
        return candidate.content
      }
    }
    return null
  }, [])

  useEffect(() => {
    if (activeId) {
      setTypedWelcome(WELCOME_TEXT)
      return
    }

    setTypedWelcome('')
    let i = 0
    const timer = window.setInterval(() => {
      i += 1
      setTypedWelcome(WELCOME_TEXT.slice(0, i))
      if (i >= WELCOME_TEXT.length) {
        window.clearInterval(timer)
      }
    }, 65)

    return () => window.clearInterval(timer)
  }, [activeId])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [active?.messages.length, active?.id])

  const updateActive = useCallback(
    (mut: (t: Thread) => Thread) => {
      setThreads(prev => prev.map(t => (t.id === activeId ? mut(t) : t)))
    },
    [activeId]
  )

  const startSqlThreadWithSchema = useCallback((schemaId: string, sqlModel: string) => {
    const t = newThread('sql')
    t.schemaId = schemaId
    t.sqlModel = sqlModel
    setThreads(prev => [t, ...prev])
    setActiveId(t.id)
    setSqlThreadSchemaPickerOpen(false)
    setSchemaDropdownOpen(false)
    setModelDropdownOpen(false)
    setCreateSqlThreadOnSchemaSave(false)
    setError(null)
  }, [])

  useEffect(() => {
    if (!sqlThreadSchemaPickerOpen) return
    if (schemas.length === 0) {
      setSelectedSchemaForNewSqlThread(null)
      return
    }
    const isSelectedValid = !!selectedSchemaForNewSqlThread && schemas.some((s) => s.id === selectedSchemaForNewSqlThread)
    if (!isSelectedValid) {
      setSelectedSchemaForNewSqlThread(schemas[0].id)
    }
    if (!SQL_MODEL_OPTIONS.some((m) => m.id === selectedModelForNewSqlThread)) {
      setSelectedModelForNewSqlThread(DEEPSEEK_SQL_PROVIDER)
    }
  }, [sqlThreadSchemaPickerOpen, schemas, selectedSchemaForNewSqlThread, selectedModelForNewSqlThread])

  const handleNewChat = (mode: Mode) => {
    if (mode === 'sql') {
      if (schemas.length === 0) {
        setSelectedModelForNewSqlThread(DEEPSEEK_SQL_PROVIDER)
        setCreateSqlThreadOnSchemaSave(true)
        setSqlThreadSchemaPickerOpen(false)
        handleCreateSchema()
        return
      }
      setSelectedSchemaForNewSqlThread(schemas[0].id)
      setSelectedModelForNewSqlThread(DEEPSEEK_SQL_PROVIDER)
      setSqlThreadSchemaPickerOpen(true)
      setError(null)
      return
    }

    const t = newThread(mode)
    setThreads(prev => [t, ...prev])
    setActiveId(t.id)
    setError(null)
  }

  const handleDelete = (id: string) => {
    if (backendOnline) {
      apiDeleteThread(id).catch(() => {
        markBackendOffline()
      })
    }
    setSendingThreads(prev => {
      if (!prev[id]) return prev
      const next = { ...prev }
      delete next[id]
      return next
    })
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

  const handleExportThread = async (id: string) => {
    const thread = threads.find(t => t.id === id)
    if (!thread || thread.mode !== 'sql') return
    try {
      await apiExportThreadSql(id, thread.title)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export queries')
    }
  }

  const summaries: ThreadSummary[] = threads.map(t => ({
    id: t.id,
    title: t.title,
    mode: t.mode,
    schemaId: t.schemaId,
    sqlModel: t.sqlModel,
    updatedAt: t.updatedAt,
  }))

  const schemaSummaries: SchemaSummary[] = schemas.map(s => ({
    id: s.id,
    title: s.title,
    updatedAt: s.updatedAt,
  }))

  const handleSendMessage = async (userMessage: string, threadOverride?: Thread) => {
    const targetThread = threadOverride || active
    if (!targetThread) {
      const starter = newThread('chat')
      setThreads(prev => [starter, ...prev])
      setActiveId(starter.id)
      setError(null)
      await handleChatStream(userMessage, starter)
      return
    }

    if (targetThread.mode === 'sql') {
      await handleTextToSql(userMessage, targetThread)
    } else {
      await handleChatStream(userMessage, targetThread)
    }
  }

  const handleEditUserMessage = async (messageId: string, newContent: string) => {
    if (!active || activeThreadIsSending) return
    const index = active.messages.findIndex(m => m.id === messageId)
    if (index < 0 || active.messages[index].role !== 'user') return

    const truncated: Thread = {
      ...active,
      messages: active.messages.slice(0, index),
      updatedAt: nextUpdatedAt(active.updatedAt),
    }

    setThreads(prev => prev.map(t => (t.id === active.id ? truncated : t)))
    setError(null)
    await handleSendMessage(newContent, truncated)
  }

  const setThreadSending = useCallback((threadId: string, sending: boolean) => {
    setSendingThreads(prev => {
      if (sending) {
        if (prev[threadId]) return prev
        return { ...prev, [threadId]: true }
      }

      if (!prev[threadId]) return prev
      const next = { ...prev }
      delete next[threadId]
      return next
    })
  }, [])

  const handleChatStream = async (userMessage: string, threadOverride?: Thread) => {
    const targetThread = threadOverride || active
    if (!targetThread) return
    setError(null)

    const activeThreadId = targetThread.id
    if (sendingThreads[activeThreadId]) return
    setThreadSending(activeThreadId, true)
    const userMsg: Message = { id: uid(), role: 'user', content: userMessage }
    const assistantId = uid()
    const assistantMsg: Message = { id: assistantId, role: 'assistant', content: '' }

    const historyForApi = targetThread.messages
      .filter(m => m.content)
      .map(m => ({ role: m.role, content: m.content }))
      .concat([{ role: 'user', content: userMessage }])

    const isFirstUserMessage = !targetThread.messages.some(m => m.role === 'user')

    setThreads(prev =>
      prev.map(t =>
        t.id === activeThreadId
          ? {
              ...t,
              title: isFirstUserMessage ? deriveTitle(userMessage) : t.title,
              messages: [...t.messages, userMsg, assistantMsg],
              updatedAt: nextUpdatedAt(t.updatedAt),
            }
          : t
      )
    )

    const patchAssistant = (content: string) => {
      setThreads(prev =>
        prev.map(t =>
          t.id === activeThreadId
            ? {
                ...t,
                messages: t.messages.map(m =>
                  m.id === assistantId ? { ...m, content } : m
                ),
                updatedAt: nextUpdatedAt(t.updatedAt),
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
      setThreadSending(activeThreadId, false)
    }
  }

  const handleTextToSql = async (userMessage: string, threadOverride?: Thread) => {
    const targetThread = threadOverride || active
    if (!targetThread) return
    if (!targetThread.schemaId) {
      setSqlThreadSchemaPickerOpen(true)
      setError('This SQL thread has no schema. Start a new SQL thread and choose a schema.')
      return
    }

    setError(null)

    const activeThreadId = targetThread.id
    if (sendingThreads[activeThreadId]) return
    setThreadSending(activeThreadId, true)
    const userMsg: Message = { id: uid(), role: 'user', content: userMessage }
    const assistantId = uid()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isSql: true,
    }
    const isFirstUserMessage = !targetThread.messages.some(m => m.role === 'user')

    setThreads(prev =>
      prev.map(t =>
        t.id === activeThreadId
          ? {
              ...t,
              title: isFirstUserMessage ? deriveTitle(userMessage) : t.title,
              messages: [...t.messages, userMsg, assistantMsg],
              updatedAt: nextUpdatedAt(t.updatedAt),
            }
          : t
      )
    )

    const patchAssistant = (patch: Partial<Message>) => {
      setThreads(prev =>
        prev.map(t =>
          t.id === activeThreadId
            ? {
                ...t,
                messages: t.messages.map(m =>
                  m.id === assistantId ? { ...m, ...patch } : m
                ),
                updatedAt: nextUpdatedAt(t.updatedAt),
              }
            : t
        )
      )
    }

    try {
      const historyForApi = targetThread.messages
        .filter(m => m.content)
        .map(m => ({ role: m.role, content: m.content, isSql: !!m.isSql }))
        .concat([{ role: 'user', content: userMessage, isSql: false }])

      const response = await fetch(`${API_URL}/text-to-sql`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMessage,
          schemaId: targetThread.schemaId,
          model: targetThread.sqlModel || DEEPSEEK_SQL_PROVIDER,
          threadId: activeThreadId,
          assistantMessageId: assistantId,
          messages: historyForApi,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `API error: ${response.status}`)
      }

      const data = await response.json()
      patchAssistant({
        content: data.sql,
        isSql: true,
        sqlStatus: formatSqlStatus(data.intent, data.cached),
      })
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'SQL generation failed.'
      setError(errorMessage)
      patchAssistant({
        content: `[Error]\n${errorMessage}\n\n`,
        isSql: false,
      })
    } finally {
      setThreadSending(activeThreadId, false)
    }
  }

  const handleCreateSchema = () => {
    setEditingSchemaId(null)
    setSchemaTitle('')
    setSchemaText('')
    setSchemaFaqText('')
    setSchemaEditorOpen(true)
    setError(null)
  }

  const handleEditSchema = (schemaId: string) => {
    const found = schemas.find(s => s.id === schemaId)
    if (!found) return
    setEditingSchemaId(found.id)
    setSchemaTitle(found.title)
    setSchemaText(found.schema)
    setSchemaFaqText(found.faq || '')
    setSchemaEditorOpen(true)
    setError(null)
  }

  const handleDeleteSchema = async (schemaId: string) => {
    try {
      await apiDeleteSchema(schemaId)
      setSchemas(prev => prev.filter(s => s.id !== schemaId))
      if (editingSchemaId === schemaId) {
        setEditingSchemaId(null)
        setSchemaTitle('')
        setSchemaText('')
        setSchemaFaqText('')
        setSchemaEditorOpen(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete schema')
    }
  }

  const handleSaveSchema = async () => {
    const title = schemaTitle.trim()
    const schemaBody = schemaText.trim()
    const faqBody = schemaFaqText.trim()
    if (title.length < 2) {
      setError('Schema title must be at least 2 characters.')
      return
    }
    if (!schemaBody) {
      setError('Schema cannot be empty.')
      return
    }

    setIsSavingSchema(true)
    setError(null)
    try {
      const saved = editingSchemaId
        ? await apiUpdateSchema(editingSchemaId, title, schemaBody, faqBody)
        : await apiCreateSchema(title, schemaBody, faqBody)

      setSchemas(prev => {
        const without = prev.filter(s => s.id !== saved.id)
        return [saved, ...without]
      })

      if (createSqlThreadOnSchemaSave) {
        startSqlThreadWithSchema(saved.id, selectedModelForNewSqlThread)
      }

      setEditingSchemaId(saved.id)
      setSchemaTitle(saved.title)
      setSchemaText(saved.schema)
      setSchemaFaqText(saved.faq || '')
      setSchemaEditorOpen(false)
      setCreateSqlThreadOnSchemaSave(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schema')
    } finally {
      setIsSavingSchema(false)
    }
  }

  const handleSchemaEditorKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Tab') return
    e.preventDefault()

    const target = e.currentTarget
    const start = target.selectionStart
    const end = target.selectionEnd
    const nextValue = `${schemaText.slice(0, start)}  ${schemaText.slice(end)}`

    setSchemaText(nextValue)
    requestAnimationFrame(() => {
      if (!schemaTextAreaRef.current) return
      schemaTextAreaRef.current.selectionStart = start + 2
      schemaTextAreaRef.current.selectionEnd = start + 2
    })
  }

  const handleSchemaEditorScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (!schemaGutterRef.current) return
    schemaGutterRef.current.scrollTop = e.currentTarget.scrollTop
  }

  const handleInsertSchemaTemplate = () => {
    if (schemaText.trim()) return
    setSchemaText(
      'CREATE TABLE users (\n' +
        '  id INT PRIMARY KEY,\n' +
        '  username VARCHAR(100) NOT NULL,\n' +
        '  email VARCHAR(255),\n' +
        '  created_at TIMESTAMP\n' +
        ');\n\n' +
        'CREATE TABLE orders (\n' +
        '  id INT PRIMARY KEY,\n' +
        '  user_id INT NOT NULL,\n' +
        '  total_amount DECIMAL(10,2),\n' +
        '  created_at TIMESTAMP,\n' +
        '  FOREIGN KEY (user_id) REFERENCES users(id)\n' +
        ');'
    )
    requestAnimationFrame(() => schemaTextAreaRef.current?.focus())
  }

  const handleLogout = async () => {
    try {
      await apiLogout()
    } finally {
      router.replace('/login')
    }
  }

  const handleCloseActive = () => {
    setActiveId(null)
    setError(null)
  }

  const handleOpenProfileEditor = () => {
    setProfileUsername(user?.username || '')
    setProfileCurrentPassword('')
    setProfileNewPassword('')
    setProfileConfirmPassword('')
    setProfileEditorOpen(true)
    setError(null)
  }

  const handleSaveProfile = async () => {
    const username = profileUsername.trim().toLowerCase()
    const currentPassword = profileCurrentPassword
    const newPassword = profileNewPassword

    if (!currentPassword) {
      setError('Enter your current password to save profile changes.')
      return
    }

    if (newPassword && newPassword !== profileConfirmPassword) {
      setError('New password and confirmation do not match.')
      return
    }

    const usernameChanged = !!user && username !== user.username
    const passwordChanged = newPassword.length > 0
    if (!usernameChanged && !passwordChanged) {
      setError('No profile changes were provided.')
      return
    }

    setIsSavingProfile(true)
    setError(null)
    try {
      const updated = await apiUpdateProfile({
        currentPassword,
        username,
        newPassword: passwordChanged ? newPassword : undefined,
      })
      setUser(updated)
      setProfileEditorOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update profile')
    } finally {
      setIsSavingProfile(false)
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
        username={user?.username}
        activeId={activeId}
        onSelect={(id) => {
          setActiveId(id)
          setError(null)
        }}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
        onExport={handleExportThread}
        onCreateSchema={handleCreateSchema}
        onEditSchema={handleEditSchema}
        onDeleteSchema={handleDeleteSchema}
        onEditProfile={handleOpenProfileEditor}
        onLogout={handleLogout}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <div className="mx-auto flex w-full max-w-5xl flex-1 min-h-0 flex-col px-4 py-6 sm:px-6 lg:px-8">
          {active && (
            <div className="mb-4 flex items-center justify-between gap-2">
              {active.mode === 'sql' && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-border bg-background/50 px-3 py-1.5 text-xs font-medium text-foreground">
                    Schema: {schemaSummaries.find((schema) => schema.id === active.schemaId)?.title || 'Unknown schema'}
                  </span>
                  <span className="rounded-full border border-border bg-background/50 px-3 py-1.5 text-xs font-medium text-foreground">
                    Model: {formatSqlModelTitle(active.sqlModel)}
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleExportThread(active.id)}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/50 px-3 py-1.5 text-xs font-medium text-foreground transition-all hover:border-primary hover:bg-primary/10"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
                      <path d="M12 3v12m0 0l4-4m-4 4L8 11" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                      <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Export SQL
                  </button>
                </div>
              )}
              <button
                type="button"
                onClick={handleCloseActive}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-background/50 px-3 py-1.5 text-xs font-medium text-foreground transition-all hover:border-primary"
              >
                X
              </button>
            </div>
          )}

          {!active ? (
            <div className="flex flex-1 min-h-0 flex-col items-center justify-center p-6 text-center">
              <p className="font-mono text-4xl font-bold uppercase tracking-[0.12em] text-primary drop-shadow-[0_0_10px_rgba(34,197,94,0.35)] sm:text-4xl md:text-5xl">
                {typedWelcome}
                <span
                  className={`ml-1 inline-block text-primary/80 ${
                    typedWelcome.length >= WELCOME_TEXT.length ? 'animate-pulse' : ''
                  }`}
                >
                  |
                </span>
              </p>
              <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={() => handleNewChat('sql')}
                  className="rounded-xl border border-primary bg-primary/10 px-4 py-2 text-sm font-medium text-primary transition-all hover:bg-primary/20"
                >
                  Add New Text to SQL
                </button>
                <button
                  type="button"
                  onClick={() => handleNewChat('chat')}
                                    className="rounded-xl border border-border bg-background/60 px-4 py-2 text-sm font-medium text-foreground transition-all hover:border-primary hover:bg-background/80"
                >
                  Add New Chat
                </button>
              </div>
            </div>
          ) : (
            <div className="matrix-scrollbar flex-1 min-h-0 overflow-y-auto space-y-4 rounded-3xl border border-border bg-card/35 p-4 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.65)] sm:p-6">
              {active.messages.map((message, index) => {
                const isAssistantError =
                  message.role === 'assistant' && message.content.trim().startsWith('[Error]')
                const retryPrompt = isAssistantError
                  ? findRetryPrompt(active.messages, index)
                  : null

                const isSqlAssistant =
                  message.role === 'assistant' &&
                  !!message.isSql &&
                  !!message.content.trim() &&
                  !isAssistantError

                return (
                  <ChatMessage
                    key={message.id}
                    role={message.role}
                    content={message.content}
                    isSql={message.isSql}
                    statusHint={message.sqlStatus}
                    sqlDownloadFilename={
                      isSqlAssistant
                        ? sqlDownloadFilenameForMessage(active.messages, index)
                        : undefined
                    }
                    isLoading={
                      activeThreadIsSending &&
                      message.role === 'assistant' &&
                      !message.content
                    }
                    onEditResend={
                      message.role === 'user' && message.content.trim()
                        ? newContent => {
                            void handleEditUserMessage(message.id, newContent)
                          }
                        : undefined
                    }
                    editDisabled={activeThreadIsSending}
                    onRetry={
                      retryPrompt
                        ? () => {
                            void handleSendMessage(retryPrompt)
                          }
                        : undefined
                    }
                    retryDisabled={activeThreadIsSending}
                  />
                )
              })}
              <div ref={messagesEndRef} />
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-2xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              <span className="font-semibold">Error:</span> {error}
            </div>
          )}

          {active && (
            <div className="pt-4">
              <ChatInput
                onSubmit={handleSendMessage}
                isLoading={activeThreadIsSending}
                disabled={activeThreadIsSending}
                placeholder={
                  active.mode === 'sql'
                    ? 'Describe the query you want...'
                    : 'Type your message...'
                }
              />
            </div>
          )}
        </div>
      </div>

      {sqlThreadSchemaPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            aria-label="Close schema picker"
            onClick={() => {
              setSqlThreadSchemaPickerOpen(false)
              setSchemaDropdownOpen(false)
              setModelDropdownOpen(false)
              setCreateSqlThreadOnSchemaSave(false)
            }}
            className="absolute inset-0 bg-black/60"
          />
          <div className="relative z-10 w-full max-w-lg rounded-2xl border border-border bg-card p-4 shadow-2xl sm:p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium">Choose Schema</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  A Text to SQL thread is permanently bound to one schema.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSqlThreadSchemaPickerOpen(false)
                  setSchemaDropdownOpen(false)
                  setModelDropdownOpen(false)
                  setCreateSqlThreadOnSchemaSave(false)
                }}
                className="rounded-md border border-border bg-background/40 px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
              >
                Close
              </button>
            </div>

            <div className="space-y-2">
              {schemaSummaries.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border/70 px-3 py-4 text-xs text-muted-foreground">
                  No schemas yet. Add one to start a SQL thread.
                </p>
              ) : (
                <>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => {
                        setSchemaDropdownOpen((v) => !v)
                        setModelDropdownOpen(false)
                      }}
                      className="inline-flex w-full items-center justify-between gap-2 rounded-xl border border-border bg-background/50 px-3 py-2 text-sm text-foreground transition-all hover:border-primary"
                    >
                      <span className="truncate">
                        {schemaSummaries.find((schema) => schema.id === selectedSchemaForNewSqlThread)?.title || 'Choose schema'}
                      </span>
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        aria-hidden
                        className={`transition-transform ${schemaDropdownOpen ? 'rotate-180' : ''}`}
                      >
                        <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </button>
                    {schemaDropdownOpen && (
                      <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-56 overflow-y-auto rounded-xl border border-border bg-card shadow-lg">
                        {schemaSummaries.map((schema) => (
                          <button
                            key={schema.id}
                            type="button"
                            onClick={() => {
                              setSelectedSchemaForNewSqlThread(schema.id)
                              setSchemaDropdownOpen(false)
                            }}
                            className={`block w-full px-3 py-2 text-left text-sm transition-colors hover:bg-background/60 ${selectedSchemaForNewSqlThread === schema.id ? 'bg-primary/10 text-foreground' : 'text-muted-foreground'}`}
                          >
                            {schema.title}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => {
                        setModelDropdownOpen((v) => !v)
                        setSchemaDropdownOpen(false)
                      }}
                      className="inline-flex w-full items-center justify-between gap-2 rounded-xl border border-border bg-background/50 px-3 py-2 text-sm text-foreground transition-all hover:border-primary"
                    >
                      <span className="truncate">
                        {SQL_MODEL_OPTIONS.find((m) => m.id === selectedModelForNewSqlThread)?.title || 'Choose model'}
                      </span>
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        aria-hidden
                        className={`transition-transform ${modelDropdownOpen ? 'rotate-180' : ''}`}
                      >
                        <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </button>
                    {modelDropdownOpen && (
                      <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-56 overflow-y-auto rounded-xl border border-border bg-card shadow-lg">
                        {SQL_MODEL_OPTIONS.map((modelOption) => (
                          <button
                            key={modelOption.id}
                            type="button"
                            onClick={() => {
                              setSelectedModelForNewSqlThread(modelOption.id)
                              setModelDropdownOpen(false)
                            }}
                            className={`block w-full px-3 py-2 text-left text-sm transition-colors hover:bg-background/60 ${selectedModelForNewSqlThread === modelOption.id ? 'bg-primary/10 text-foreground' : 'text-muted-foreground'}`}
                          >
                            {modelOption.title}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (!selectedSchemaForNewSqlThread) return
                  startSqlThreadWithSchema(selectedSchemaForNewSqlThread, selectedModelForNewSqlThread)
                }}
                disabled={!selectedSchemaForNewSqlThread}
                className="rounded-xl border border-primary bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-70"
              >
                Create Text to SQL Thread
              </button>
              <button
                type="button"
                onClick={() => {
                  setCreateSqlThreadOnSchemaSave(true)
                  setSqlThreadSchemaPickerOpen(false)
                  setSchemaDropdownOpen(false)
                  setModelDropdownOpen(false)
                  handleCreateSchema()
                }}
                className="rounded-xl border border-primary bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
              >
                Add New Schema
              </button>
            </div>
          </div>
        </div>
      )}

      {schemaEditorOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            aria-label="Close schema editor"
            onClick={() => {
              setSchemaEditorOpen(false)
              setCreateSqlThreadOnSchemaSave(false)
            }}
            className="absolute inset-0 bg-black/60"
          />
          <div className="relative z-10 flex h-[78vh] min-h-[460px] w-[92vw] min-w-[320px] max-w-4xl max-h-[90vh] resize flex-col overflow-hidden rounded-2xl border border-border bg-card p-4 shadow-2xl sm:p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium">
                  {editingSchemaId ? 'Edit SQL Schema' : 'Add SQL Schema'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Schemas are stored per account. Add a title, paste CREATE TABLE statements, and optional FAQ notes.
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground/80">
                  Tip: drag the bottom-right corner to resize this editor.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSchemaEditorOpen(false)
                  setCreateSqlThreadOnSchemaSave(false)
                }}
                className="rounded-md border border-border bg-background/40 px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
              >
                Close
              </button>
            </div>

            <input
              value={schemaTitle}
              onChange={(e) => setSchemaTitle(e.target.value)}
              className="mb-3 w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="Schema title (e.g., Brokerage DB)"
            />

            <div className="flex-1 overflow-hidden rounded-xl border border-border bg-background/80">
              <div className="flex items-center justify-between border-b border-border/70 bg-background/60 px-3 py-1.5">
                <span className="text-[11px] font-medium text-muted-foreground">SQL Editor</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={handleInsertSchemaTemplate}
                    className="rounded-md border border-border bg-background/40 px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                  >
                    Insert Template
                  </button>
                  <button
                    type="button"
                    onClick={() => setSchemaText('')}
                    className="rounded-md border border-border bg-background/40 px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                  >
                    Clear
                  </button>
                </div>
              </div>
              <div className="flex h-full min-h-56">
                <div
                  ref={schemaGutterRef}
                  className="w-10 shrink-0 select-none overflow-hidden border-r border-border/70 bg-background/60 px-2 py-2 text-right text-[11px] leading-5 text-muted-foreground"
                >
                  {Array.from({ length: Math.max(1, schemaText.split('\n').length) }).map((_, idx) => (
                    <div key={idx}>{idx + 1}</div>
                  ))}
                </div>
                <textarea
                  ref={schemaTextAreaRef}
                  value={schemaText}
                  onChange={(e) => setSchemaText(e.target.value)}
                  onKeyDown={handleSchemaEditorKeyDown}
                  onScroll={handleSchemaEditorScroll}
                  className="matrix-scrollbar h-full w-full resize-none bg-background/40 px-3 py-2 text-xs leading-5 font-mono outline-none"
                  placeholder="CREATE TABLE Users (\n  id INT PRIMARY KEY,\n  username VARCHAR(100) NOT NULL\n);"
                  spellCheck={false}
                  autoCorrect="off"
                  autoCapitalize="off"
                  autoComplete="off"
                  wrap="off"
                />
              </div>
            </div>

            <div className="mt-3">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Schema FAQ (Markdown)</label>
              <textarea
                value={schemaFaqText}
                onChange={(e) => setSchemaFaqText(e.target.value)}
                className="matrix-scrollbar h-28 w-full resize-y rounded-xl border border-border bg-background/60 px-3 py-2 text-xs leading-5 outline-none focus:border-primary"
                placeholder={
                  'Example:\n- customers.status: active | inactive\n- orders.total_amount is in USD\n- Use created_at for time filtering'
                }
                spellCheck={false}
              />
            </div>

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
                onClick={() => {
                  setSchemaEditorOpen(false)
                  setCreateSqlThreadOnSchemaSave(false)
                }}
                className="rounded-xl border border-border bg-background/40 px-3 py-1.5 text-xs text-muted-foreground"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {profileEditorOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            aria-label="Close profile editor"
            onClick={() => setProfileEditorOpen(false)}
            className="absolute inset-0 bg-black/60"
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl border border-border bg-card p-4 shadow-2xl sm:p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium">Edit Profile</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Change your username or password.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setProfileEditorOpen(false)}
                className="rounded-md border border-border bg-background/40 px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
              >
                Close
              </button>
            </div>

            <label className="mb-1 block text-xs text-muted-foreground">Username</label>
            <input
              value={profileUsername}
              onChange={(e) => setProfileUsername(e.target.value)}
              className="mb-3 w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="Username"
            />

            <label className="mb-1 block text-xs text-muted-foreground">Current password</label>
            <input
              type="password"
              value={profileCurrentPassword}
              onChange={(e) => setProfileCurrentPassword(e.target.value)}
              className="mb-3 w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="Required to save changes"
            />

            <label className="mb-1 block text-xs text-muted-foreground">New password (optional)</label>
            <input
              type="password"
              value={profileNewPassword}
              onChange={(e) => setProfileNewPassword(e.target.value)}
              className="mb-3 w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="Leave empty to keep current password"
            />

            <label className="mb-1 block text-xs text-muted-foreground">Confirm new password</label>
            <input
              type="password"
              value={profileConfirmPassword}
              onChange={(e) => setProfileConfirmPassword(e.target.value)}
              className="w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="Repeat new password"
            />

            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={handleSaveProfile}
                disabled={isSavingProfile}
                className="rounded-xl border border-primary bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isSavingProfile ? 'Saving...' : 'Save Profile'}
              </button>
              <button
                type="button"
                onClick={() => setProfileEditorOpen(false)}
                className="rounded-xl border border-border bg-background/40 px-3 py-1.5 text-xs text-muted-foreground"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
