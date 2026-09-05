import * as React from "react"
import { cn } from "@/lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-lg border border-border bg-card px-3 py-2 text-[13px] placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:border-primary/40 focus-visible:bg-card transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      ref={ref}
      {...props}
    />
  )
)
Input.displayName = "Input"
export { Input }
