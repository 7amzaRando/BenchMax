'use client'

import { Copy, Check } from 'lucide-react'
import { useState } from 'react'

interface CopyButtonProps {
  text: string
  className?: string
}

export default function CopyButton({ text, className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className={className}
      title="Copy to clipboard"
    >
      {copied ? <Check className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4" />}
    </button>
  )
}
