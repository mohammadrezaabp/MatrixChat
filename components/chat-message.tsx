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
      console.error('کپی ناموفق بود', error)
    }
  }
  
  return (
    <div className={`flex gap-4 mb-4 animate-fadeIn ${isUser ? 'flex-row-reverse' : ''}`} dir="rtl">
      {/* Avatar/Marker */}
      <div className={`flex-shrink-0 w-8 h-8 flex items-center justify-center border-2 ${
        isUser 
          ? 'border-primary text-primary' 
          : 'border-secondary text-secondary'
      }`}>
        <span className="text-xs font-bold">{isUser ? '>' : '$'}</span>
      </div>
      
      {/* Message Content */}
      <div className="flex-1 text-right">
        <div className={`relative inline-block max-w-xs md:max-w-md lg:max-w-lg px-4 py-2 border-2 ${
          isUser
            ? 'border-primary bg-black text-primary'
            : 'border-secondary bg-black text-secondary'
        }`}>
          {isSql ? (
            <div className="relative group w-full">
              <button
                type="button"
                onClick={handleCopy}
                aria-label={copied ? 'کپی شد' : 'کپی'}
                className={`absolute top-2 right-2 z-10 flex items-center justify-center w-9 h-9 rounded-md transition-all duration-150 border ${
                  copied
                    ? 'bg-green-900/60 border-green-600 text-green-300 shadow-[0_8px_24px_-8px_rgba(16,185,129,0.4)]'
                    : 'bg-black/60 border-slate-700 text-slate-200 opacity-0 group-hover:opacity-100 hover:bg-slate-800/90 hover:scale-105'
                }`}
              >
                {copied ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                    <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                    <rect x="9" y="9" width="10" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
                    <path d="M7 15H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>

              {/* Success tooltip */}
              {copied && (
                <div className="absolute top-2 right-12 z-20 rounded bg-green-900/90 px-2 py-1 text-xs text-green-100">
                  کپی شد
                </div>
              )}

              <div className="mb-2" />
              <pre dir="ltr" className="min-h-[120px] overflow-x-auto whitespace-pre-wrap break-words text-sm font-mono text-slate-100 pb-3 px-3 pt-6 border-t border-t-transparent">
                {content}
              </pre>
            </div>
          ) : (
            <p className="text-sm md:text-base whitespace-pre-wrap break-words">
              {isLoading ? (
                <span className="inline-flex gap-1">
                  <span className="animate-pulse">▮</span>
                  <span className="animate-pulse animation-delay-100">▮</span>
                  <span className="animate-pulse animation-delay-200">▮</span>
                </span>
              ) : (
                content
              )}
            </p>
          )}
        </div>
        <div className={`text-xs mt-1 ${isUser ? 'text-muted-foreground mr-2' : 'text-muted-foreground ml-2'}`}>
          {isUser ? 'کاربر' : 'لاما'}
        </div>
      </div>
    </div>
  )
}
