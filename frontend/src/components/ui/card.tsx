import * as React from "react"
import { cn } from "@/lib/utils"

type CardVariant = 'default' | 'soft' | 'outline'

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { variant?: CardVariant }>(
  ({ className, variant = 'default', ...props }, ref) => {
    const styles =
      variant === 'soft'
        ? "rounded-xl border border-border bg-card shadow-soft"
        : variant === 'outline'
        ? "rounded-xl border border-border bg-card/50"
        : "rounded-xl border border-border bg-card shadow-card card-hover"
    return <div ref={ref} className={cn(styles, className)} {...props} />
  }
)
Card.displayName = "Card"

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col gap-1.5 p-5 pb-3", className)} {...props} />
  )
)
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-[13px] font-semibold tracking-tight leading-none flex items-center gap-2", className)} {...props} />
  )
)
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-[12.5px] leading-relaxed text-muted-foreground", className)} {...props} />
  )
)
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-5 pt-0", className)} {...props} />
  )
)
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-5 pt-0", className)} {...props} />
  )
)
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
