'use client'

import { useState } from 'react'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  isLoading?: boolean
  isSql?: boolean
}

export function ChatMessage({ role, content, isLoading, isSql }: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = role === 'user'

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Copy failed', error)
    }
  }
  
  return (
    <div className={`mb-4 flex animate-fadeIn ${isUser ? 'flex-row-reverse justify-start gap-2' : 'justify-start gap-4'}`} dir="ltr">
      {/* Avatar/Marker */}
      <div className={`flex-shrink-0 flex h-9 w-9 items-center justify-center rounded-full border ${
        isUser 
          ? 'border-primary/60 bg-primary/10 text-primary' 
          : 'border-secondary/60 bg-secondary/10 text-secondary'
      }`}>
        <span className="text-xs font-semibold">{isUser ? 'You' : 'AI'}</span>
      </div>
      
      {/* Message Content */}
      <div className={`flex-1 max-w-[85%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`relative w-fit max-w-xs rounded-2xl border px-4 py-3 md:max-w-md lg:max-w-lg ${
          isUser
            ? 'border-primary/40 bg-primary/5 text-foreground'
            : 'border-border bg-card/80 text-foreground'
        }`}>
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="inline-flex gap-1">
                <span className="animate-pulse">▮</span>
                <span className="animate-pulse animation-delay-100">▮</span>
                <span className="animate-pulse animation-delay-200">▮</span>
              </span>
              <span>Thinking...</span>
            </div>
          ) : isSql ? (
            <div className="w-full">
              <pre dir="ltr" className="min-h-[120px] overflow-x-auto whitespace-pre-wrap break-words border-t border-t-transparent px-3 pb-3 pt-6 text-sm font-mono text-foreground">
                {content}
              </pre>
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words text-left text-sm md:text-base">
              {content}
            </p>
          )}
        </div>
        <div className={`mt-1 flex w-fit items-center gap-2 text-xs text-muted-foreground ${isUser ? 'self-end' : 'self-start'}`}>
          <span>{isUser ? 'You' : 'Ai Assistant'}</span>
          {content && !isLoading && (
            <button
              type="button"
              onClick={handleCopy}
              aria-label={copied ? 'Copied' : 'Copy'}
              className={`inline-flex h-5 w-5 items-center justify-center rounded-sm border transition-colors duration-150 ${
                copied
                  ? 'border-green-500/80 bg-green-500/15 text-green-400'
                  : 'border-border/80 bg-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground'
              }`}
            >
              {copied ? (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                  <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                  <rect x="9" y="9" width="10" height="12" rx="2" stroke="currentColor" strokeWidth="1.7" />
                  <path d="M7 15H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v1" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
