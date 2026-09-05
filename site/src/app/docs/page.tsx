import type { Metadata } from 'next'
import Link from 'next/link'
import { Zap, Code, Terminal, Settings, ArrowRight } from 'lucide-react'
import GradientText from '@/components/shared/GradientText'
import Card, { CardTitle, CardDescription, CardContent } from '@/components/shared/Card'

export const metadata: Metadata = {
  title: 'Documentation',
  description: 'Everything you need to get started with BenchMax: installation, API reference, CLI, and configuration.',
}

const SECTIONS = [
  {
    href: '/docs/getting-started/',
    icon: Zap,
    title: 'Getting Started',
    description: 'Install BenchMax and run your first benchmark in under 5 minutes.',
  },
  {
    href: '/docs/api-reference/',
    icon: Code,
    title: 'API Reference',
    description: '43 REST endpoints (45 with /health & /shutdown): runs, batch, model queue, export, leaderboard, datasets, telemetry.',
  },
  {
    href: '/docs/cli-reference/',
    icon: Terminal,
    title: 'CLI Reference',
    description: '38 commands: every REST endpoint as a CLI command, with --json & --wait.',
  },
  {
    href: '/docs/configuration/',
    icon: Settings,
    title: 'Configuration',
    description: 'Environment variables, provider presets, and sandbox settings.',
  },
]

export default function DocsPage() {
  return (
    <div>
      <h1 className="text-4xl md:text-5xl font-bold mb-4">
        <GradientText as="span">Documentation</GradientText>
      </h1>
      <p className="text-lg text-muted-fg mb-12 max-w-2xl">
        Guides, references, and configuration docs for BenchMax, the local LLM benchmarking suite.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {SECTIONS.map((section) => (
          <Link key={section.href} href={section.href}>
            <Card variant="glow" className="p-6 h-full cursor-pointer group">
              <CardContent className="p-0">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center mb-4">
                  <section.icon className="w-5 h-5 text-primary" />
                </div>
                <CardTitle className="group-hover:text-primary transition-colors mb-2">
                  {section.title}
                </CardTitle>
                <CardDescription className="mb-4">
                  {section.description}
                </CardDescription>
                <span className="inline-flex items-center gap-1 text-sm text-primary font-medium">
                  Read more <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
