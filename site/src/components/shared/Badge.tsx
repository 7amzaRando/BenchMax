import { clsx } from 'clsx'
import { HTMLAttributes } from 'react'

type BadgeVariant = 'default' | 'primary' | 'secondary' | 'accent' | 'success' | 'warning' | 'danger' | 'outline' | 'muted'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: 'bg-muted text-muted-fg border border-border',
  primary: 'bg-primary/10 text-primary border border-primary/25',
  secondary: 'bg-secondary/10 text-secondary border border-secondary/25',
  accent: 'bg-accent/10 text-accent border border-accent/25',
  success: 'bg-success/10 text-success border border-success/25',
  warning: 'bg-warning/10 text-amber-300 border border-warning/25',
  danger: 'bg-danger/10 text-danger border border-danger/25',
  outline: 'bg-transparent border border-border text-muted-fg',
  muted: 'bg-white/[0.06] text-muted-fg border border-white/[0.06]',
}

export default function Badge({ className, variant = 'default', children, ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium leading-none',
        VARIANT_CLASSES[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}
