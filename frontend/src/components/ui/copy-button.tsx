import * as React from "react"
import { Button } from "@/components/ui/button"

interface CopyButtonProps {
  value: string
  className?: string
}

export function CopyButton({ value, className }: CopyButtonProps) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = React.useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.warn("Failed to copy text", err)
    }
  }, [value])

  return (
    <Button
      variant="ghost"
      size="sm"
      className={`h-5 w-5 p-0 text-muted-foreground hover:text-foreground ${className}`}
      onClick={handleCopy}
      title="Copy to clipboard"
    >
      {copied ? (
        <span className="text-[10px] text-green-400 font-bold">✓</span>
      ) : (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </Button>
  )
}
