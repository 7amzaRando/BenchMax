import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium ring-offset-background transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-white hover:bg-primary/80 hover:shadow-lg hover:shadow-primary/25 hover:-translate-y-0.5",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/80 hover:shadow-lg hover:shadow-red-500/20 hover:-translate-y-0.5",
        outline: "border-2 border-primary/30 bg-primary/[0.02] text-foreground hover:bg-primary/10 hover:border-primary/60 transition-all duration-300",
        secondary: "bg-secondary/20 text-white hover:bg-secondary/35 hover:-translate-y-0.5 transition-all duration-300",
        ghost: "text-foreground/70 hover:text-primary hover:bg-primary/10 transition-all duration-300",
        link: "text-primary underline-offset-4 hover:underline",
        glow: "bg-gradient-to-r from-[var(--primary)] to-[var(--secondary)] text-white hover:shadow-[0_0_24px_rgba(99,102,241,0.45)] hover:scale-[1.03] transition-all duration-300",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-12 rounded-lg px-8 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
