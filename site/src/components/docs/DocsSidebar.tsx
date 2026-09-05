'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { clsx } from 'clsx'
import { BookOpen, Zap, Terminal, Code, Settings } from 'lucide-react'

const NAV_LINKS = [
  { href: '/docs/getting-started/', label: 'Getting Started', icon: Zap },
  { href: '/docs/api-reference/', label: 'API Reference', icon: Code },
  { href: '/docs/cli-reference/', label: 'CLI Reference', icon: Terminal },
  { href: '/docs/configuration/', label: 'Configuration', icon: Settings },
]

export default function DocsSidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-full lg:w-64 shrink-0">
      <nav className="sticky top-24 space-y-1">
        <div className="flex items-center gap-2 px-3 py-2 mb-4">
          <BookOpen className="w-5 h-5 text-primary" />
          <span className="font-semibold text-foreground">Documentation</span>
        </div>
        {NAV_LINKS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'text-primary bg-primary/10'
                  : 'text-muted-fg hover:text-foreground hover:bg-white/5'
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
