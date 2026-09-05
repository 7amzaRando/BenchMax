import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { Button } from "@/components/ui/button"

type ButtonVariant = NonNullable<React.ComponentProps<typeof Button>["variant"]>

export interface DialogAction {
  label: string
  onClick: () => void
  variant?: ButtonVariant
}

interface AlertDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: React.ReactNode
  actions?: DialogAction[]
}

export function AlertDialog({ open, onOpenChange, title, description, actions }: AlertDialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
        <DialogPrimitive.Content className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="w-full max-w-md mx-4 rounded-xl border border-red-500/30 bg-card/95 p-6 shadow-2xl backdrop-blur-md animate-fadeInUp">
            <DialogPrimitive.Title className="text-lg font-bold text-foreground">
              {title}
            </DialogPrimitive.Title>
            <DialogPrimitive.Description className="mt-2 text-sm text-muted-foreground">
              {description}
            </DialogPrimitive.Description>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <DialogPrimitive.Close asChild>
                <Button variant="outline" size="sm">Dismiss</Button>
              </DialogPrimitive.Close>
              {actions?.map((a) => (
                <Button key={a.label} variant={a.variant || "destructive"} size="sm" onClick={a.onClick}>
                  {a.label}
                </Button>
              ))}
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
