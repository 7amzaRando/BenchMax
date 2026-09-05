import { memo } from 'react'

export const SkeletonLine = memo(function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-muted h-4 ${className}`} />
})

export const SkeletonCard = memo(function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <SkeletonLine className="w-1/3 h-5" />
      <SkeletonLine className="w-full" />
      <SkeletonLine className="w-2/3" />
    </div>
  )
})

export const SkeletonTable = memo(function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="bg-muted p-2">
        <SkeletonLine className="w-full h-3" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="p-2 border-t border-border">
          <SkeletonLine className="w-full h-3" />
        </div>
      ))}
    </div>
  )
})
