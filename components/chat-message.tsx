'use client'

import { useMemo, useState } from 'react'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  isLoading?: boolean
  isSql?: boolean
}

export function ChatMessage({ role, content, isLoading, isSql }: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = role === 'user'
  const logo = '/icon.svg'
  const userIcon = '/matrix-user.svg'

  const sqlLines = useMemo(() => {
    const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    // Some responses may contain literal escape sequences (e.g. "\\n") instead of real newlines.
    // Decode that shape only when the text is effectively single-line to preserve normal SQL strings.
    const decoded =
      !normalized.includes('\n') && /\\r\\n|\\n|\\r/.test(normalized)
        ? normalized.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\r/g, '\n')
        : normalized
    return decoded.split('\n')
  }, [content])

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
    <div className={`mb-4 flex animate-fadeIn ${isUser ? 'flex-row-reverse justify-start gap-1' : 'justify-start gap-1'}`} dir="ltr">
      {/* Avatar/Marker */}
      <div className="flex-shrink-0 flex h-14 w-14 items-center justify-center">
        {isUser ? (
          <img
            src={userIcon}
            alt="User Icon"
            className="h-12 w-12 rounded-lg object-cover matrix-user-effect"
            draggable="false"
          />
        ) : (
          <img src={logo} alt="AI Logo" className="h-16 w-16 rounded-xl shadow-2xl bg-black p-1" draggable="false" />
        )}
      </div>
      
      {/* Message Content */}
      <div className={`flex-1 ${isSql && !isUser ? 'max-w-[96%]' : 'max-w-[85%]'} flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={
            isSql && !isUser
              ? 'relative w-full max-w-3xl p-0'
              : `relative w-fit max-w-xs rounded-2xl border px-4 py-3 text-foreground md:max-w-md lg:max-w-lg ${
                  isUser
                    ? 'border-primary/40 bg-primary/5'
                    : 'border-border bg-card/80'
                }`
          }
        >
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
              <div className="resize overflow-auto rounded-xl border border-border/70 bg-background/70" style={{ minWidth: '280px', minHeight: '160px' }}>
                <ol className="matrix-scrollbar min-h-[160px] w-full list-none p-0 text-xs leading-5 font-mono text-foreground">
                  {sqlLines.map((line, idx) => (
                    <li key={idx} className="grid grid-cols-[2.75rem_minmax(0,1fr)]">
                      <div className="select-none border-r border-border/70 bg-background/80 px-2 py-2 text-right text-[11px] text-muted-foreground">
                        {idx + 1}
                      </div>
                      <pre dir="ltr" className="m-0 px-3 py-2 whitespace-pre-wrap break-words">
                        {line || ' '}
                      </pre>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words text-left text-sm md:text-base">
              {content}
            </p>
          )}
        </div>
        <div className={`mt-1 flex w-fit items-center gap-2 text-xs text-muted-foreground ${isUser ? 'self-end' : 'self-start'}`}>
          {/* Removed user/AI icon near copy icon */}
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
