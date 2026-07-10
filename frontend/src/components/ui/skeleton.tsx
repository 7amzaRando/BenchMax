import React from 'react'
import { cn } from '@/lib/utils'

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'text' | 'circle' | 'rect';
  width?: string;
  height?: string;
}

export default function Skeleton({ className, variant = 'rect', width, height, ...props }: SkeletonProps) {
  const styles: Record<string, React.CSSProperties> = {
    text: { minHeight: '1rem', borderRadius: '.5rem' },
    circle: { borderRadius: '9999px', minWidth: width || '1rem', minHeight: height || '1rem' },
    rect: { borderRadius: '.5rem', width: width, height: height || 'auto' },
  }

  return (
    <div
      className={cn(
        "animate-shimmer bg-glass-highlight rounded",
        variant === 'text' && styles.text,
        variant === 'circle' && styles.circle,
        variant === 'rect' && styles.rect,
        className
      )}
      style={{ ...styles[variant], width: width, height: height }}
      {...props}
    />
  )
}
