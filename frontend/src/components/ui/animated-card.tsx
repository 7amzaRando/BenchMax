import React from 'react'
import { cn } from '@/lib/utils'

interface AnimatedCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  variant?: 'default' | 'glow' | 'glass';
  showBorder?: boolean;
  children: React.ReactNode;
}

export default function AnimatedCard({
  className,
  title,
  description,
  variant = 'default',
  showBorder = true,
  children,
  ...props
}: AnimatedCardProps) {
  const baseStyles = cn(
    "rounded-xl transition-all duration-300",
    variant === 'glow' && "backdrop-blur-xl bg-card border border-primary/20 shadow-lg hover:shadow-2xl hover:shadow-primary/10 hover:-translate-y-1 hover:border-primary/40",
    variant === 'glass' && "backdrop-blur-2xl bg-card border border-primary/10 rounded-xl shadow-lg",
    showBorder && variant !== 'glow' && !className?.includes('border') && "rounded-xl border border-border bg-card shadow-sm hover:shadow-md"
  )

  return (
    <div className={cn(baseStyles, className)} {...props}>
      {(title || description) && (
        <div className="px-6 pt-6 pb-2">
          {title && <h3 className="text-base font-semibold text-foreground">{title}</h3>}
          {description && <p className="text-xs text-muted-fg mt-1">{description}</p>}
        </div>
      )}
      <div className="px-6 pt-0 pb-6">
        {children}
      </div>
    </div>
  )
}
