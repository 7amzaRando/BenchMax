import * as React from "react"
import * as ToastPrimitive from "@radix-ui/react-toast"
import { cn } from "@/lib/utils"

export interface ToastMessage {
  id: string
  title?: string
  description?: string
  variant?: "default" | "success" | "error" | "warning"
}

interface ToastContextType {
  toast: (message: Omit<ToastMessage, "id">) => void
}

const ToastContext = React.createContext<ToastContextType | undefined>(undefined)

export function useToast() {
  const context = React.useContext(ToastContext)
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider")
  }
  return context
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastMessage[]>([])

  const toast = React.useCallback(({ title, description, variant = "default" }: Omit<ToastMessage, "id">) => {
    const id = Math.random().toString(36).substring(2, 9)
    setToasts((prev) => [...prev, { id, title, description, variant }])
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        {toasts.map(({ id, title, description, variant }) => (
          <ToastPrimitive.Root
            key={id}
            onOpenChange={(open) => {
              if (!open) {
                setToasts((prev) => prev.filter((t) => t.id !== id))
              }
            }}
            className={cn(
              "fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-1 rounded-xl border p-4 shadow-xl transition-all duration-300 animate-fadeInUp",
              variant === "default" && "bg-card border-border text-foreground",
              variant === "default" && "bg-card border-l-4 border-l-border text-foreground",
              variant === "success" && "bg-card border-l-4 border-l-emerald-500 text-foreground",
              variant === "error" && "bg-card border-l-4 border-l-red-500 text-foreground",
              variant === "warning" && "bg-card border-l-4 border-l-amber-500 text-foreground"
            )}
          >
            {title && <ToastPrimitive.Title className="text-sm font-bold">{title}</ToastPrimitive.Title>}
            {description && (
              <ToastPrimitive.Description className="text-xs text-muted-foreground opacity-90">
                {description}
              </ToastPrimitive.Description>
            )}
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:top-auto sm:flex-col md:max-w-[420px]" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}
