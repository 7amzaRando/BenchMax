import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { Button } from "@/components/ui/button"

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  onConfirm: () => void
  confirmText?: string
  cancelText?: string
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  confirmText = "Confirm",
  cancelText = "Cancel",
}: ConfirmDialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
        <DialogPrimitive.Content className="fixed inset-0 z-50 flex items-center justify-center"><div className="w-full max-w-md mx-4 rounded-xl border border-primary/20 bg-card/95 p-6 shadow-2xl backdrop-blur-md animate-fadeInUp">
          <DialogPrimitive.Title className="text-lg font-bold text-foreground">
            {title}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="mt-2 text-sm text-muted-foreground">
            {description}
          </DialogPrimitive.Description>
          <div className="mt-6 flex justify-end gap-3">
            <DialogPrimitive.Close asChild>
              <Button variant="outline" size="sm">
                {cancelText}
              </Button>
            </DialogPrimitive.Close>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                onConfirm()
                onOpenChange(false)
              }}
            >
              {confirmText}
            </Button>
          </div>
        </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
