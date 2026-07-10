import { cn } from '@/lib/utils'

interface StatusIndicatorProps {
  status: 'idle' | 'running' | 'completed' | 'error';
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function StatusIndicator({
  status,
  label,
  size = 'md',
  className,
}: StatusIndicatorProps) {
  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  }

  const colorMap = {
    idle: 'bg-muted-fg',
    running: 'bg-success animate-pulse',
    completed: 'bg-success shadow-[0_0_8px_rgba(16,185,129,0.6)]',
    error: 'bg-destructive animate-shake',
  }

  return (
    <div className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className={cn(
          "rounded-full flex-shrink-0 transition-all duration-300",
          sizeClasses[size],
          colorMap[status]
        )}
      />
      {label && (
        <span className={`text-xs font-medium ${status === 'running' ? 'text-success animate-pulse' : status === 'error' ? 'text-destructive' : ''}`}>
          {label}
        </span>
      )}
    </div>
  )
}
