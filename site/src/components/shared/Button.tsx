import { clsx } from 'clsx'
import { ButtonHTMLAttributes, forwardRef } from 'react'

type Variant = 'primary' | 'glow' | 'outline' | 'ghost' | 'subtle'
type Size = 'sm' | 'md' | 'lg'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

const VARIANT: Record<Variant, string> = {
  primary: 'bg-foreground text-background hover:bg-white shadow-[0_1px_0_rgba(255,255,255,0.08)_inset,0_4px_16px_rgba(0,0,0,0.3)]',
  glow: 'bg-gradient-to-r from-primary to-[#4f46e5] text-white shadow-[0_4px_24px_rgba(99,102,241,0.35),0_1px_0_rgba(255,255,255,0.15)_inset] hover:shadow-[0_6px_32px_rgba(99,102,241,0.45)] hover:brightness-[1.05]',
  outline: 'bg-transparent border border-border text-foreground hover:bg-white/[0.06] hover:border-border-strong',
  ghost: 'bg-transparent text-muted-fg hover:text-foreground hover:bg-white/[0.06]',
  subtle: 'bg-white/[0.06] border border-white/[0.08] text-foreground hover:bg-white/[0.10]',
}

const SIZE: Record<Size, string> = {
  sm: 'px-3.5 py-1.5 text-xs font-medium rounded-full',
  md: 'px-5 py-2.5 text-sm font-medium rounded-full',
  lg: 'px-7 py-3 text-sm font-semibold rounded-full',
}

const Button = forwardRef<HTMLButtonElement, Props>(
  ({ className, variant = 'primary', size = 'md', children, ...props }, ref) => (
    <button
      ref={ref}
      className={clsx(
        'inline-flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none',
        VARIANT[variant],
        SIZE[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
)
Button.displayName = 'Button'
export default Button
