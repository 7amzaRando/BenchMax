import { clsx } from 'clsx'
import { HTMLAttributes } from 'react'

interface Props extends HTMLAttributes<HTMLSpanElement> {
  as?: 'span' | 'h1' | 'h2' | 'h3' | 'p'
  variant?: 'default' | 'warm'
}

export default function GradientText({ as: Tag = 'span', variant = 'default', className, children, ...props }: Props) {
  return (
    <Tag className={clsx(variant === 'warm' ? 'gradient-text-warm' : 'gradient-text', className)} {...props}>
      {children}
    </Tag>
  )
}
