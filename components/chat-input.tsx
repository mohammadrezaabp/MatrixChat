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
    <div className="border-t-2 border-primary pt-4">
      <div className={`border-2 transition-all ${
        isFocused ? 'border-primary shadow-lg shadow-primary/50' : 'border-muted'
      }`}>
        <form onSubmit={handleSubmit} className="bg-input p-3">
          <div className="flex gap-2 items-end">
            <span className="text-primary text-sm font-mono">{'>'}</span>
            <textarea
              dir="rtl"
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
              placeholder={placeholder || 'پیام خود را وارد کنید...'}
              disabled={isLoading || disabled}
              className="flex-1 bg-transparent text-primary placeholder-muted-foreground outline-none resize-none font-mono text-sm min-h-6 max-h-32 text-right"
              rows={1}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim() || disabled}
              className={`px-3 py-1 border-2 font-bold text-xs transition-all whitespace-nowrap ${
                isLoading || !input.trim() || disabled
                  ? 'border-muted text-muted-foreground cursor-not-allowed opacity-50'
                  : 'border-primary text-primary hover:bg-primary hover:text-black hover:shadow-lg hover:shadow-primary/50'
              }`}
            >
              {isLoading ? 'در حال پردازش...' : 'ارسال'}
            </button>
          </div>
        </form>
      </div>
      <div className="text-xs text-muted-foreground mt-2 text-left">
        برای ارسال اینتر بزنید | شیفت+اینتر برای خط جدید
      </div>
    </div>
  )
}
