import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg text-[13px] font-medium tracking-tight ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-white hover:bg-[var(--primary-dark)] shadow-sm hover:shadow-md active:scale-[0.98]",
        primary: "bg-primary text-white hover:bg-[var(--primary-dark)] shadow-sm hover:shadow-md active:scale-[0.98]",
        ghost: "text-muted-foreground hover:text-foreground hover:bg-muted",
        outline: "border border-border bg-card hover:bg-muted hover:border-[var(--border-strong)]",
        soft: "bg-[var(--primary-soft)] text-primary hover:brightness-[0.97] dark:hover:brightness-125",
        destructive: "bg-[var(--danger)] text-white hover:bg-red-600 shadow-sm",
        muted: "bg-muted text-muted-foreground hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline h-auto p-0",
      },
      size: {
        default: "h-9 px-4",
        sm: "h-7 px-3 text-xs rounded-md",
        lg: "h-10 px-6 text-[13.5px]",
        icon: "h-9 w-9",
        xs: "h-6 px-2 text-[11px] rounded-md",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
