import Link from 'next/link'
import { Zap, Github, ExternalLink } from 'lucide-react'

const FOOTER_LINKS: Record<string, { href: string; label: string; external?: boolean }[]> = {
  Product: [
    { href: '/benchmarks/', label: '30 Benchmarks' },
    { href: '/features/', label: 'Features' },
    { href: '/results/', label: 'Results' },
    { href: '/leaderboard/', label: 'Leaderboard' },
  ],
  Resources: [
    { href: '/docs/', label: 'Documentation' },
    { href: '/docs/getting-started/', label: 'Getting Started' },
    { href: '/docs/api-reference/', label: 'API Reference' },
    { href: '/docs/cli-reference/', label: 'CLI Reference' },
  ],
  Project: [
    { href: '/about/', label: 'About' },
    { href: 'https://github.com/7amzaRando/BenchMax', label: 'GitHub', external: true },
    { href: 'https://github.com/7amzaRando/BenchMax/blob/main/LICENSE', label: 'License (AGPL v3)', external: true },
  ],
}

export default function Footer() {
  return (
    <footer className="relative border-t border-white/[0.06] bg-background-elevated/40">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
      <div className="container-wide px-4 sm:px-6 lg:px-8 py-12 md:py-14">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-10 mb-10">
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-[0_4px_16px_rgba(99,102,241,0.3)]">
                <Zap className="w-[18px] h-[18px] text-white" strokeWidth={2.5} />
              </div>
              <span className="text-lg font-bold tracking-tight gradient-text">BenchMax</span>
            </Link>
            <p className="text-sm text-muted-fg leading-relaxed max-w-xs">
              Local LLM benchmarking: 30 tests, 40k questions, 8 providers. Safe sandboxed code tests. Free and open source.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="pill bg-white/[0.06] border-white/[0.08] text-muted-fg">AGPL v3</span>
              <span className="pill bg-primary/10 border-primary/20 text-primary">v1.1</span>
            </div>
          </div>

          {Object.entries(FOOTER_LINKS).map(([category, links]) => (
            <div key={category}>
              <h3 className="text-xs font-semibold tracking-widest uppercase text-foreground/80 mb-3">{category}</h3>
              <ul className="space-y-2.5">
                {links.map(({ href, label, external }) => (
                  <li key={href}>
                    {external ? (
                      <a href={href} target="_blank" rel="noopener noreferrer" className="text-sm text-muted-fg hover:text-foreground transition-colors inline-flex items-center gap-1">
                        {label} <ExternalLink className="w-3 h-3 opacity-60" />
                      </a>
                    ) : (
                      <Link href={href} className="text-sm text-muted-fg hover:text-foreground transition-colors">{label}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 border-t border-white/[0.06]">
          <p className="text-xs text-muted-fg">
            Created by{' '}
            <a href="https://github.com/7amzaRando" target="_blank" rel="noopener noreferrer" className="text-foreground hover:text-primary transition-colors font-medium">Rando</a>
            {' · '}© 2026 · Licensed under AGPL v3.
          </p>
          <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-muted-fg hover:text-foreground transition-colors">
            <Github className="w-5 h-5" />
            <span className="text-sm font-medium">7amzaRando/BenchMax</span>
          </a>
        </div>
      </div>
    </footer>
  )
}
