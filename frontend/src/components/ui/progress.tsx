import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"
import { cn } from "@/lib/utils"

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { variant?: 'default' | 'gradient' }
>(({ className, value, variant = 'gradient', ...props }, ref) => (
  <ProgressPrimitive.Root ref={ref} className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-muted", className)} {...props}>
    <ProgressPrimitive.Indicator className="h-full w-full flex-1 transition-all duration-500" style={{ transform: `translateX(-${100 - (value || 0)}%)` }}>
      {variant === 'gradient' ? (
        <div className="h-full w-full bg-gradient-to-r from-[var(--primary)] to-[var(--secondary)] rounded-full" />
      ) : (
        <div className="h-full bg-primary rounded-full" />
      )}
    </ProgressPrimitive.Indicator>
  </ProgressPrimitive.Root>
))
Progress.displayName = ProgressPrimitive.Root.displayName
export { Progress }
