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
      content: `[سیستم آماده است]
خوش آمدید به ماتریکس چت نسخه 1.0
متصل به: Llama 3.2
وضعیت: آنلاین
حالت‌ها: چت | متن به SQL
پیام خود را وارد کرده و اینتر بزنید...`
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
        content: newMode === 'sql' 
          ? `کوئری خود را به زبان طبیعی توصیف کنید و من آن را به SQL تبدیل می‌کنم. برای مثال: "لیست تمام کاربران را که در ماه گذشته ثبت نام کرده‌اند نشان بده."`
          : `سلام...سوال خود را بپرسید یا در مورد هر موضوعی چت کنید. من اینجا هستم تا کمک کنم!`
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
        throw new Error(errorData.detail || `خطای API: ${response.status}`)
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
      const errorMessage = err instanceof Error ? err.message : 'پاسخی دریافت نشد'
      setError(errorMessage)
      
      // Remove loading message on error
      setMessages(prev => prev.filter(msg => msg.role !== 'assistant' || msg.content))
      
      // Add error message
      setMessages(prev => [...prev, {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: `[خطا]\n${errorMessage}\n\nلطفاً بررسی کنید که سرویس پایتون روی پورت 8000 در حال اجرا باشد و Ollama در دسترس باشد.`
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
        throw new Error(errorData.detail || `خطای API: ${response.status}`)
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
      const errorMessage = err instanceof Error ? err.message : 'خطا در تولید SQL'
      setError(errorMessage)
      
      // Add error message
      setMessages(prev => [...prev, {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: `[خطا]\n${errorMessage}\n\nلطفاً بررسی کنید سرویس پایتون در حال اجرا باشد و فایل MySqlSchema.sql موجود باشد.`
      }])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main dir="rtl" lang="fa" className="h-screen flex flex-col bg-background text-foreground">
      {/* Header */}
      <div className="border-b-2 border-primary px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold font-mono text-primary glitch" data-text="ماتریکس چت">
            ماتریکس چت
          </h1>
          <div className="flex gap-2">
            <button
              onClick={() => handleModeChange('chat')}
              className={`px-4 py-2 border-2 font-mono text-sm transition-all ${
                mode === 'chat'
                  ? 'border-primary bg-primary text-background'
                  : 'border-muted hover:border-primary'
              }`}
            >
              چت
            </button>
            <button
              onClick={() => handleModeChange('sql')}
              className={`px-4 py-2 border-2 font-mono text-sm transition-all ${
                mode === 'sql'
                  ? 'border-primary bg-primary text-background'
                  : 'border-muted hover:border-primary'
              }`}
            >
              متن به SQL
            </button>
          </div>
        </div>
        <p className="text-sm text-secondary">
          {'> '} {mode === 'sql' ? 'حالت متن به SQL' : 'حالت چت'} | متصل به Llama 3.2
        </p>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4" dir="rtl">
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

      {/* Error Display */}
      {error && (
        <div className="mx-6 mb-4 p-3 border-2 border-destructive bg-black text-destructive text-sm">
          <span className="font-bold">⚠ خطا:</span> {error}
        </div>
      )}

      {/* Input Area */}
      <div className="px-6 pb-6">
        <ChatInput 
          onSubmit={handleSendMessage}
          isLoading={isLoading}
          placeholder={mode === 'sql' ? 'کوئری خود را به زبان طبیعی بنویسید...' : 'پیام خود را وارد کنید...'}
        />
      </div>
    </main>
  )
}
