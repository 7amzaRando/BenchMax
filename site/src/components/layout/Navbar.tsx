'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Zap, Menu, X, Github } from 'lucide-react'
import { clsx } from 'clsx'

const NAV_LINKS = [
  { href: '/benchmarks/', label: 'Benchmarks' },
  { href: '/features/', label: 'Features' },
  { href: '/docs/', label: 'Docs' },
  { href: '/results/', label: 'Results' },
  { href: '/leaderboard/', label: 'Leaderboard' },
  { href: '/about/', label: 'About' },
]

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const pathname = usePathname()

  const isActive = (href: string) => pathname === href || pathname.startsWith(href)

  return (
    <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/[0.06] bg-background/70 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-primary/15 to-transparent pointer-events-none" />
      <div className="container-wide px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-[64px]">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary via-[#6366f1] to-secondary flex items-center justify-center shadow-[0_2px_12px_rgba(99,102,241,0.35)] group-hover:shadow-[0_4px_20px_rgba(99,102,241,0.45)] transition-shadow">
              <Zap className="w-[18px] h-[18px] text-white" strokeWidth={2.5} />
            </div>
            <span className="text-[17px] font-bold tracking-tight text-foreground">BenchMax</span>
            <span className="hidden sm:inline-flex items-center rounded-full bg-white/[0.07] border border-white/[0.08] px-2 py-0.5 text-[10px] font-semibold tracking-widest uppercase text-muted-fg ml-1">AGPL v3</span>
          </Link>

          <div className="hidden lg:flex items-center gap-1">
            {NAV_LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={clsx(
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  isActive(href) ? 'text-foreground bg-white/[0.08] border border-white/[0.08]' : 'text-muted-fg hover:text-foreground hover:bg-white/[0.06]'
                )}
              >
                {label}
              </Link>
            ))}
          </div>

          <div className="hidden lg:flex items-center gap-2">
            <a
              href="https://github.com/7amzaRando/BenchMax"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium text-muted-fg hover:text-foreground hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08] transition-colors"
            >
              <Github className="w-4 h-4" />
              GitHub
            </a>
            <Link
              href="/docs/getting-started/"
              className="inline-flex items-center justify-center px-5 py-2 rounded-full text-sm font-semibold bg-foreground text-background hover:bg-white transition-colors shadow-[0_2px_10px_rgba(0,0,0,0.25)]"
            >
              Get Started
            </Link>
          </div>

          <button
            aria-label="Toggle menu"
            className="lg:hidden p-2 rounded-xl text-muted-fg hover:text-foreground hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08]"
            onClick={() => setOpen(!open)}
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="lg:hidden border-t border-white/[0.06] bg-background-elevated/95 backdrop-blur-xl">
          <div className="px-4 py-4 space-y-1">
            {NAV_LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={clsx(
                  'block px-3 py-2.5 rounded-xl text-sm font-medium transition-colors',
                  isActive(href) ? 'text-foreground bg-white/[0.08]' : 'text-muted-fg hover:text-foreground hover:bg-white/[0.05]'
                )}
              >
                {label}
              </Link>
            ))}
            <div className="pt-3 mt-3 border-t border-white/[0.06] flex gap-2">
              <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noopener noreferrer" className="flex-1 inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-full text-sm font-medium bg-white/[0.07] text-foreground border border-white/[0.08]">
                <Github className="w-4 h-4" /> GitHub
              </a>
              <Link href="/docs/getting-started/" onClick={() => setOpen(false)} className="flex-1 inline-flex items-center justify-center px-4 py-2.5 rounded-full text-sm font-semibold bg-foreground text-background">
                Get Started
              </Link>
            </div>
          </div>
        </div>
      )}
    </nav>
  )
}
