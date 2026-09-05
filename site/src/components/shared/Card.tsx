import { clsx } from 'clsx'
import { HTMLAttributes, forwardRef } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'glass' | 'glow' | 'elevated'
}

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = 'default', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx(
          'rounded-2xl transition-all duration-300',
          {
            'bg-card border border-border hover:border-border-strong hover:shadow-[0_8px_32px_rgba(0,0,0,0.35)]': variant === 'default',
            'glass-panel rounded-2xl': variant === 'glass',
            'glow-card rounded-2xl': variant === 'glow',
            'bg-card border border-border shadow-[0_8px_32px_rgba(0,0,0,0.25),0_1px_0_rgba(255,255,255,0.04)_inset]': variant === 'elevated',
          },
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('p-6 pb-0', className)} {...props} />
}
export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={clsx('text-lg font-semibold text-foreground tracking-tight', className)} {...props} />
}
export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={clsx('text-sm text-muted-fg mt-1.5 leading-relaxed', className)} {...props} />
}
export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('p-6', className)} {...props} />
}
export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('p-6 pt-0', className)} {...props} />
}

export default Card
