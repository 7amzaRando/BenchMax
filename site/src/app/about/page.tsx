import type { Metadata } from 'next'
import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import GradientText from '@/components/shared/GradientText'
import Card, { CardContent } from '@/components/shared/Card'
import Badge from '@/components/shared/Badge'

export const metadata: Metadata = {
  title: 'About',
  description: 'About BenchMax, the open-source local LLM benchmarking suite by Rando (AGPL v3).',
}

const DEPENDENCIES = [
  { name: 'FastAPI', role: 'Runs the app and its data services' },
  { name: 'React 19', role: 'The dashboard you click through' },
  { name: 'TypeScript + Vite', role: 'Builds the dashboard' },
  { name: 'SQLite', role: 'Stores your runs and results on your machine' },
  { name: 'Docker', role: 'Isolates coding tests from your system' },
  { name: 'Hardware sensors', role: 'Reads CPU, memory, and graphics stats live' },
  { name: 'Tailwind CSS', role: 'Styles the dashboard and this site' },
  { name: 'Framer Motion', role: 'Animations on this site' },
]

export default function AboutPage() {
  return (
    <section className="section-padding">
      <div className="container-narrow">
        <div className="mb-10">
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4">
            <GradientText as="span">About BenchMax</GradientText>
          </h1>
          <p className="text-lg text-muted-fg max-w-2xl">A local LLM benchmarking suite built for transparency, reproducibility, and the open-source community.</p>
        </div>

        <div className="mb-12">
          <h2 className="text-2xl font-bold tracking-tight mb-4">The project</h2>
          <div className="rounded-2xl bg-card border border-border p-6 space-y-4 text-muted-fg leading-relaxed">
            <p>
              BenchMax started from a simple frustration: evaluating local LLMs meant stitching together multiple tools, each with its own quirks.
              Some benchmarks needed Docker, others had gated datasets or cloud-only APIs. None gave a unified view across every dimension.
            </p>
            <p>
              The goal: one tool that runs every major benchmark, scores each one fairly, and works on any machine.
              Most tests run with zero extra setup; coding tests use a safe sandbox with a clear setup guide.
            </p>
            <p>
              Today BenchMax includes <strong className="text-foreground">30 benchmarks</strong> and <strong className="text-foreground">40k samples</strong> across code, knowledge, math, reasoning, instruction following, safety, tool use, speed, long documents, vision, truthfulness and composite scoring. Everything runs locally, with no cloud calls during evaluation.
            </p>
          </div>
        </div>

        <div className="mb-12">
          <h2 className="text-2xl font-bold tracking-tight mb-4">Creator</h2>
          <Card variant="glow" className="p-6">
            <CardContent className="p-0">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center shrink-0 border border-primary/15">
                  <span className="text-xl font-bold gradient-text">R</span>
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Rando</h3>
                  <p className="text-sm text-muted-fg mt-1 leading-relaxed">Developer and maintainer of BenchMax: backend, frontend, all 30 benchmarks, graders, sandbox, CLI and this site.</p>
                  <a href="https://github.com/7amzaRando" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline mt-3">
                    github.com/7amzaRando <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mb-12">
          <h2 className="text-2xl font-bold tracking-tight mb-4">License</h2>
          <Card variant="glass" className="p-6">
            <CardContent className="p-0">
              <div className="flex items-center gap-2 mb-3">
                <Badge variant="primary">AGPL v3</Badge>
                <span className="text-xs text-muted-fg">Commercial license available</span>
              </div>
              <p className="text-sm text-muted-fg leading-relaxed">
                BenchMax is released under the <strong className="text-foreground">GNU Affero General Public License v3.0</strong>. Free to use, modify and distribute under its terms. If you run BenchMax as a network service you must provide the source to your users. Contact the author for commercial licensing.
              </p>
              <a href="https://github.com/7amzaRando/BenchMax/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline mt-3">
                View LICENSE on GitHub <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </CardContent>
          </Card>
        </div>

        <div className="mb-12">
          <h2 className="text-2xl font-bold tracking-tight mb-4">Credits & dependencies</h2>
          <p className="text-sm text-muted-fg mb-4">BenchMax stands on the shoulders of giants.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {DEPENDENCIES.map(dep => (
              <div key={dep.name} className="rounded-xl bg-card border border-border p-4">
                <p className="font-semibold text-sm">{dep.name}</p>
                <p className="text-xs text-muted-fg mt-1 leading-relaxed">{dep.role}</p>
              </div>
            ))}
          </div>
          <div className="rounded-xl bg-card border border-border p-4 mt-3">
            <p className="text-sm text-muted-fg leading-relaxed">
              <strong className="text-foreground">Benchmark datasets:</strong> HumanEval (OpenAI), MMLU-Pro (TIGER-Lab), IFEval (Google), AIME (AoPS/MATH), BigCodeBench (BigCode), BFCL (Berkeley), UncensorBench, LiveBench, LiveCodeBench, TruthfulQA, HellaSWAG / WinoGrande / ARC (Allen AI), CommonSenseQA (Talmor et al.), Aider Polyglot (Exercism), LongBench-v2 (THUDM), MMMU-Pro, LOCOMO, GAIA, and BenchMax originals (Personal, Lite, Code, Reason, Tectonic, NIAHS, Speed Tests).
            </p>
          </div>
        </div>

        <Card variant="glow" className="p-8 text-center">
          <CardContent className="p-0">
            <h3 className="text-xl font-bold tracking-tight">Open source</h3>
            <p className="text-muted-fg mt-2 max-w-xl mx-auto">Free, open-source and community-driven. Issues, PRs and benchmark ideas are welcome.</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-6">
              <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold bg-foreground text-background hover:bg-white transition-colors">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" /></svg>
                View on GitHub
              </a>
              <Link href="/docs/getting-started/" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium border border-border text-foreground hover:bg-white/[0.06]">Read the Docs</Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
