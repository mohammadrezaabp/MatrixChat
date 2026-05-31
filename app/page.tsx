'use client'

import { useState, useEffect, useRef } from 'react'
import { ChatMessage } from '@/components/chat-message'
import { ChatInput } from '@/components/chat-input'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  isSql?: boolean
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Mode = 'chat' | 'sql'

export default function ChatPage() {
  const [mode, setMode] = useState<Mode>('chat')
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '0',
      role: 'assistant',
      content: 'System ready. Ask a question in English or switch to Text to SQL to generate a MySQL query.'
    }
  ])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleModeChange = (newMode: Mode) => {
    setMode(newMode)
    setMessages([
      {
        id: Date.now().toString(),
        role: 'assistant',
        content:
          newMode === 'sql'
            ? 'Describe the data you want in plain English and I will turn it into a SQL query.'
            : 'Ask me anything in English. I can help answer questions, explain ideas, or draft text.'
      }
    ])
    setError(null)
  }

  const handleSendMessage = async (userMessage: string) => {
    if (mode === 'sql') {
      await handleTextToSql(userMessage)
    } else {
      await handleChat(userMessage)
    }
  }

  const handleChat = async (userMessage: string) => {
    // Add user message
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userMessage
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)
    setError(null)

    try {
      // Add loading message
      const loadingId = (Date.now() + 1).toString()
      const loadingMsg: Message = {
        id: loadingId,
        role: 'assistant',
        content: ''
      }
      setMessages(prev => [...prev, loadingMsg])

      // Call backend API
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: messages.map(msg => ({
            role: msg.role,
            content: msg.content
          })).concat([{
            role: 'user',
            content: userMessage
          }]),
          model: 'llama3.2',
          temperature: 0.7,
          top_p: 0.9
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `API error: ${response.status}`)
      }

      const data = await response.json()
      
      // Replace loading message with actual response
      setMessages(prev => 
        prev.map(msg => 
          msg.id === loadingId 
            ? { ...msg, content: data.response }
            : msg
        )
      )
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'No response received.'
      setError(errorMessage)
      
      // Remove loading message on error
      setMessages(prev => prev.filter(msg => msg.role !== 'assistant' || msg.content))
      
      // Add error message
      setMessages(prev => [...prev, {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: `[Error]\n${errorMessage}\n\nPlease make sure the Python service is running on port 8000 and Ollama is available.`
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleTextToSql = async (userMessage: string) => {
    // Add user message
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userMessage
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_URL}/text-to-sql`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: userMessage,
          model: 'llama3.2'
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `API error: ${response.status}`)
      }

      const data = await response.json()
      
      // Add SQL response with syntax highlighting
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.sql,
        isSql: true
      }])
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'SQL generation failed.'
      setError(errorMessage)
      
      // Add error message
      setMessages(prev => [...prev, {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: `[Error]\n${errorMessage}\n\nPlease check that the Python service is running and the MySqlSchema.sql file is available.`
      }])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main dir="ltr" lang="en" className="min-h-screen flex flex-col bg-background text-foreground">
      <div className="border-b border-border/70 bg-card/40 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-5 sm:px-6 lg:px-8">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleModeChange('chat')}
              className={`rounded-full border px-4 py-2 text-sm transition-all ${
                mode === 'chat'
                  ? 'border-primary bg-primary text-background shadow-md shadow-primary/20'
                  : 'border-border bg-background/70 text-foreground hover:border-primary/60 hover:bg-card'
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => handleModeChange('sql')}
              className={`rounded-full border px-4 py-2 text-sm transition-all ${
                mode === 'sql'
                  ? 'border-primary bg-primary text-background shadow-md shadow-primary/20'
                  : 'border-border bg-background/70 text-foreground hover:border-primary/60 hover:bg-card'
              }`}
            >
              Text to SQL
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex-1 overflow-y-auto space-y-4 rounded-3xl border border-border bg-card/35 p-4 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.65)] sm:p-6">
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              role={message.role}
              content={message.content}
              isSql={message.isSql}
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
            placeholder={mode === 'sql' ? 'Describe the query you want...' : 'Type your message...'}
          />
        </div>
      </div>
    </main>
  )
}
