import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold leading-none tracking-wide transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-white",
        soft: "border-transparent bg-[var(--primary-soft)] text-[var(--primary)] dark:text-[var(--primary-light)]",
        secondary: "border-transparent bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
        success: "border-transparent bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200/60 dark:border-emerald-800/50",
        warning: "border-transparent bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200/60 dark:border-amber-800/50",
        danger: "border-transparent bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300 border-red-200/60 dark:border-red-800/50",
        outline: "border-border text-muted-foreground bg-transparent",
        muted: "border-transparent bg-muted text-muted-foreground",
      },
    },
    defaultVariants: { variant: "soft" },
  }
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
