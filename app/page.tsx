'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { ChatMessage } from '@/components/chat-message'
import { ChatInput } from '@/components/chat-input'
import { ChatSidebar, type Mode, type ThreadSummary } from '@/components/chat-sidebar'

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
  messages: Message[]
  updatedAt: number
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const STORAGE_KEY = 'matrixchat.threads.v1'
const ACTIVE_KEY = 'matrixchat.activeId.v1'

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
    messages: [greeting(mode)],
    updatedAt: Date.now(),
  }
}

function deriveTitle(text: string): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean) return 'New chat'
  return clean.length > 48 ? clean.slice(0, 48) + '…' : clean
}

export default function ChatPage() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hydrated, setHydrated] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Hydrate from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const parsed: Thread[] = raw ? JSON.parse(raw) : []
      if (Array.isArray(parsed) && parsed.length > 0) {
        setThreads(parsed)
        const savedActive = localStorage.getItem(ACTIVE_KEY)
        const exists = parsed.find(t => t.id === savedActive)
        setActiveId(exists ? exists.id : parsed[0].id)
      } else {
        const t = newThread('chat')
        setThreads([t])
        setActiveId(t.id)
      }
    } catch {
      const t = newThread('chat')
      setThreads([t])
      setActiveId(t.id)
    }
    setHydrated(true)
  }, [])

  // Persist
  useEffect(() => {
    if (!hydrated) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(threads))
      if (activeId) localStorage.setItem(ACTIVE_KEY, activeId)
    } catch {}
  }, [threads, activeId, hydrated])

  const active = threads.find(t => t.id === activeId) || null

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

  const handleNewChat = (mode: Mode) => {
    const t = newThread(mode)
    setThreads(prev => [t, ...prev])
    setActiveId(t.id)
    setError(null)
  }

  const handleDelete = (id: string) => {
    setThreads(prev => {
      const next = prev.filter(t => t.id !== id)
      if (id === activeId) {
        if (next.length > 0) {
          setActiveId(next[0].id)
        } else {
          const t = newThread('chat')
          setActiveId(t.id)
          return [t]
        }
      }
      return next
    })
  }

  const summaries: ThreadSummary[] = threads.map(t => ({
    id: t.id,
    title: t.title,
    mode: t.mode,
    updatedAt: t.updatedAt,
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage, messages: historyForApi }),
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
        content: `[Error]\n${errorMessage}\n\nPlease check that the Python service is running and the MySqlSchema.sql file is available.`,
        isSql: false,
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main
      dir="ltr"
      lang="en"
      className="h-dvh flex bg-background text-foreground overflow-hidden"
    >
      <ChatSidebar
        threads={summaries}
        activeId={activeId}
        onSelect={(id) => {
          setActiveId(id)
          setError(null)
        }}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <div className="border-b border-border/70 bg-card/40 backdrop-blur">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3 pl-10 md:pl-0">
              <span className="text-sm font-semibold tracking-wide">
                {active?.mode === 'sql' ? 'Text to SQL' : 'Chat'}
              </span>
              {active && (
                <span className="line-clamp-1 text-xs text-muted-foreground">
                  {active.title}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => handleNewChat(active?.mode || 'chat')}
              className="inline-flex shrink-0 items-center gap-2 rounded-full border border-primary bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary transition-all hover:bg-primary hover:text-background"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              New
            </button>
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col min-h-0 px-4 py-6 sm:px-6 lg:px-8">
          <div className="matrix-scrollbar flex-1 min-h-0 overflow-y-auto space-y-4 rounded-3xl border border-border bg-card/35 p-4 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.65)] sm:p-6">
            {active?.messages.map((message) => (
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
            ))}
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
              placeholder={
                active?.mode === 'sql'
                  ? 'Describe the query you want...'
                  : 'Type your message...'
              }
            />
          </div>
        </div>
      </div>
    </main>
  )
}
