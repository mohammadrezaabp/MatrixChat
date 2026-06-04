'use client'

import { useEffect, useMemo, useState } from 'react'
import { downloadTextFile } from '@/lib/download'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  isLoading?: boolean
  isSql?: boolean
  statusHint?: string
  sqlDownloadFilename?: string
  onEditResend?: (newContent: string) => void
  editDisabled?: boolean
  onRetry?: () => void
  retryDisabled?: boolean
}

export function ChatMessage({
  role,
  content,
  isLoading,
  isSql,
  statusHint,
  sqlDownloadFilename,
  onEditResend,
  editDisabled,
  onRetry,
  retryDisabled,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editDraft, setEditDraft] = useState(content)
  const isUser = role === 'user'
  const isAssistantError = !isUser && content.trim().startsWith('[Error]')
  const canEdit = isUser && !isLoading && !!onEditResend && !!content.trim()
  const canDownloadSql =
    !isUser && !!isSql && !isLoading && !!content.trim() && !isAssistantError
  const logo = '/icon.svg'
  const userIcon = '/matrix-user.svg'

  useEffect(() => {
    if (!isEditing) {
      setEditDraft(content)
    }
  }, [content, isEditing])

  const sqlLines = useMemo(() => {
    const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
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

  const handleDownloadSql = () => {
    const body = content.trim().endsWith(';') ? content.trim() : `${content.trim()};`
    downloadTextFile(body, sqlDownloadFilename || 'query.sql')
  }

  const handleCancelEdit = () => {
    setEditDraft(content)
    setIsEditing(false)
  }

  const handleSubmitEdit = () => {
    const next = editDraft.trim()
    if (!next || editDisabled) return
    setIsEditing(false)
    onEditResend?.(next)
  }

  const actionButtonClass =
    'inline-flex h-5 w-5 items-center justify-center rounded-sm border border-border/80 bg-transparent text-muted-foreground transition-colors duration-150 hover:bg-muted/60 hover:text-foreground'

  return (
    <div className={`mb-4 flex animate-fadeIn ${isUser ? 'flex-row-reverse justify-start gap-1' : 'justify-start gap-1'}`} dir="ltr">
      <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center">
        {isUser ? (
          <img
            src={userIcon}
            alt="User Icon"
            className="matrix-user-effect h-12 w-12 rounded-lg object-cover"
            draggable="false"
          />
        ) : (
          <img src={logo} alt="AI Logo" className="h-16 w-16 rounded-xl bg-black p-1 shadow-2xl" draggable="false" />
        )}
      </div>

      <div className={`flex-1 ${isSql && !isUser ? 'max-w-[96%]' : 'max-w-[85%]'} flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={
            isSql && !isUser && !isEditing
              ? 'relative w-full max-w-3xl p-0'
              : `relative w-fit max-w-xs rounded-2xl border px-4 py-3 text-foreground md:max-w-md lg:max-w-lg ${
                  isUser
                    ? 'border-primary/40 bg-primary/5'
                    : 'border-border bg-card/80'
                } ${isEditing && isUser ? 'w-full max-w-lg' : ''}`
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
          ) : isEditing && isUser ? (
            <div className="w-full min-w-[240px]">
              <textarea
                dir="ltr"
                value={editDraft}
                onChange={e => setEditDraft(e.target.value)}
                disabled={editDisabled}
                rows={4}
                className="matrix-scrollbar w-full resize-y rounded-lg border border-border/80 bg-background/80 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
              />
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  disabled={editDisabled}
                  className="rounded-lg border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-background/60"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSubmitEdit}
                  disabled={editDisabled || !editDraft.trim()}
                  className="rounded-lg border border-primary bg-primary/10 px-3 py-1 text-xs font-medium text-primary hover:bg-primary/20 disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </div>
          ) : isSql && !isUser ? (
            <div className="w-full">
              <div
                className="resize overflow-auto rounded-xl border border-border/70 bg-background/70"
                style={{ minWidth: '280px', minHeight: '160px' }}
              >
                <ol className="matrix-scrollbar min-h-[160px] w-full list-none p-0 font-mono text-xs leading-5 text-foreground">
                  {sqlLines.map((line, idx) => (
                    <li key={idx} className="grid grid-cols-[2.75rem_minmax(0,1fr)]">
                      <div className="select-none border-r border-border/70 bg-background/80 px-2 py-2 text-right text-[11px] text-muted-foreground">
                        {idx + 1}
                      </div>
                      <pre dir="ltr" className="m-0 whitespace-pre-wrap break-words px-3 py-2">
                        {line || ' '}
                      </pre>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words text-left text-sm md:text-base">{content}</p>
          )}
        </div>

        <div
          className={`mt-1 flex w-fit flex-wrap items-center gap-2 text-xs text-muted-foreground ${
            isUser ? 'self-end' : 'self-start'
          }`}
        >
          {statusHint && !isLoading && !isEditing && (
            <span className="text-[11px] text-muted-foreground/90">{statusHint}</span>
          )}

          {isAssistantError && onRetry && (
            <button
              type="button"
              onClick={onRetry}
              disabled={!!retryDisabled}
              aria-label="Retry"
              className="inline-flex items-center justify-center rounded-sm border border-border/80 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M20 11a8 8 0 1 0-2.34 5.66" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M20 4v7h-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}

          {canEdit && !isEditing && (
            <button
              type="button"
              onClick={() => setIsEditing(true)}
              disabled={editDisabled}
              aria-label="Edit message"
              title="Edit and resend"
              className={actionButtonClass}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M4 20h4l10-10a2 2 0 0 0-4-4L4 16v4z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}

          {canDownloadSql && (
            <button
              type="button"
              onClick={handleDownloadSql}
              aria-label="Download SQL"
              title="Download this query"
              className={actionButtonClass}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M12 3v12m0 0l4-4m-4 4L8 11" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}

          {content && !isLoading && !isEditing && (
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
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
                  <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
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
