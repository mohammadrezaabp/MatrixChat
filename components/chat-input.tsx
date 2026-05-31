'use client'

import { useState, useRef, useEffect } from 'react'

interface ChatInputProps {
  onSubmit: (message: string) => void
  isLoading: boolean
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({ onSubmit, isLoading, disabled, placeholder }: ChatInputProps) {
  const [input, setInput] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isLoading && !disabled) {
      onSubmit(input.trim())
      setInput('')
      if (inputRef.current) {
        inputRef.current.style.height = 'auto'
      }
    }
  }

  return (
    <div className="rounded-3xl border border-border bg-card/60 p-3 shadow-[0_16px_40px_-24px_rgba(0,0,0,0.55)] sm:p-4">
      <div className={`rounded-2xl border transition-all ${
        isFocused ? 'border-primary shadow-lg shadow-primary/15' : 'border-border'
      }`}>
        <form onSubmit={handleSubmit} className="rounded-2xl bg-background/70 p-3">
          <div className="flex items-end gap-3">
            <textarea
              dir="ltr"
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e as any)
                }
              }}
              placeholder={placeholder || 'Type your message...'}
              disabled={isLoading || disabled}
              className="flex-1 min-h-8 max-h-40 resize-none bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              rows={1}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim() || disabled}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition-all whitespace-nowrap ${
                isLoading || !input.trim() || disabled
                  ? 'border-border text-muted-foreground cursor-not-allowed opacity-50'
                  : 'border-primary bg-primary text-background hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/20'
              }`}
            >
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
