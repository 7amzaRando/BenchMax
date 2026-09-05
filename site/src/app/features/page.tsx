import { Metadata } from 'next'
import Link from 'next/link'
import { Container, Shield, BarChart3, Cpu, Zap, GitBranch, Terminal, Trophy, Search, ArrowUpRight, Layers, Gauge } from 'lucide-react'
import Card from '@/components/shared/Card'
import Badge from '@/components/shared/Badge'
import GradientText from '@/components/shared/GradientText'
import Button from '@/components/shared/Button'
import { providers } from '@/lib/providers-data'

export const metadata: Metadata = {
  title: 'Features',
  description: 'What BenchMax can do: 30 benchmarks, 8 providers, safe code testing, live results, batch runs, and more.',
}

const SECTIONS = [
  {
    icon: Layers,
    title: '30 benchmarks in 12 categories',
    description: 'One place to test every skill that matters: coding, knowledge, math, reasoning, following instructions, safety, tool use, vision, long documents, truthfulness, speed, and overall ability.',
    highlights: [
      'Coding: Python tasks, real-world projects, and editing across 6 languages',
      'Knowledge: 12,000+ questions across science, history, and everyday topics',
      'Math: competition problems that need careful multi-step reasoning',
      'Instructions: checks whether the model actually follows formatting rules',
      'Tool use: 4,696 tasks that test calling functions correctly, including multi-step chats',
      'Agents: assistant-style tasks that use calculators, search, and other tools',
    ],
    link: '/benchmarks/',
    linkText: 'View all benchmarks',
  },
  {
    icon: Zap,
    title: '8 providers, local or cloud',
    description: 'Use the AI service you already have. Switching services is as easy as changing one address in the Connection tab.',
    providerTable: true,
  },
  {
    icon: Container,
    title: 'Coding tests run safely',
    description: 'Code written by a model is executed in an isolated sandbox, so it cannot touch your files or system. Most other tests need no setup at all.',
    highlights: [
      'Sandboxed testing for all 5 coding benchmarks',
      'One-click sandbox setup from the dashboard',
      'Clear guidance if setup is missing, never a silent failure',
      'Six programming languages supported for code editing tests',
    ],
  },
  {
    icon: BarChart3,
    title: 'Watch results as they happen',
    description: 'Every question reports its score and speed the moment it finishes. Follow along live, or come back later for charts and comparisons.',
    highlights: [
      'Accuracy for every benchmark, updated live',
      'Response speed: how many words per second the model produces',
      'Responsiveness: how fast the first word appears',
      'Token usage per question, with totals and averages',
    ],
  },
  {
    icon: Cpu,
    title: 'Your hardware at a glance',
    description: 'See how hard your computer is working during a run: processor, memory, graphics card load and video memory, all updating live.',
    highlights: [
      'Processor and memory usage, updated every few seconds',
      'Graphics card load and video memory',
      'Works with both NVIDIA and AMD cards',
      'Spot slowdowns and bottlenecks while testing',
    ],
  },
  {
    icon: GitBranch,
    title: 'Run batches, compare models',
    description: 'Test one model on many benchmarks, or many models on the same benchmarks, without babysitting. BenchMax works through the queue and lines up the results for comparison.',
    highlights: [
      'Chain several benchmarks into one batch',
      'Automatically switch between models and keep going',
      'Pause any run and resume exactly where it stopped',
      'Side-by-side charts: accuracy, speed, and responsiveness',
    ],
  },
  {
    icon: Shield,
    title: 'Stuck models do not slow you down',
    description: 'Sometimes a model repeats itself forever instead of answering. BenchMax notices, skips that question with a clear note, and keeps the run moving.',
    highlights: [
      'Automatic detection of repeating output',
      'Bad questions are skipped, the run continues',
      'Skipped questions are clearly marked in results',
      'Can be turned off in settings if you prefer',
    ],
  },
  {
    icon: Gauge,
    title: 'Speed checks and agent tasks',
    description: 'Beyond right-or-wrong tests: measure raw writing and coding speed, or watch a model solve multi-step tasks with tools.',
    highlights: [
      'Writing and coding speed checks (5 prompts each)',
      'Assistant-style tasks that use tools over multiple steps',
      'Step-by-step breakdowns plus the full conversation',
      'Long-document tests, from short articles to book-length context',
    ],
  },
  {
    icon: Trophy,
    title: 'Leaderboard and exports',
    description: 'Keep your best scores, share them online if you like, and export any result for reports or spreadsheets.',
    highlights: [
      'Local leaderboard, with optional online sync',
      'Export runs, batches, or history as CSV, JSON, or Markdown',
      'Compare two runs question by question',
      'Add your own notes to any run',
    ],
  },
  {
    icon: Terminal,
    title: 'Command line for automation',
    description: 'Prefer the terminal or want to script things? Every dashboard action has a matching command, with machine-readable output for scripts.',
    highlights: [
      'Start runs, check progress, export results, manage datasets',
      'Machine-readable output for scripts and agents',
      'Waits for completion on request, with live progress',
      'Full command list in the CLI Reference docs',
    ],
    link: '/docs/cli-reference/',
    linkText: 'CLI Reference',
  },
]

export default function FeaturesPage() {
  return (
    <section className="section-padding pt-24 md:pt-28 pb-16">
      <div className="container-narrow">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-3 py-1 text-xs font-semibold text-primary mb-4">Deep dive</div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">Every <GradientText>feature</GradientText></h1>
          <p className="text-muted-fg max-w-xl mx-auto mt-3">A tour of what BenchMax does for you. Technical detail (endpoints, commands, settings) lives in the docs.</p>
        </div>

        <div className="space-y-6">
          {SECTIONS.map((section, i) => (
            <Card key={section.title} variant="glow" className="p-7 md:p-8">
              <div className="flex items-start gap-4 mb-5">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary/15 to-secondary/15 border border-primary/15 flex items-center justify-center shrink-0">
                  <section.icon className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <div className="text-xs font-semibold tracking-widest uppercase text-muted-fg">Feature {i + 1} / {SECTIONS.length}</div>
                  <h2 className="text-xl font-bold tracking-tight mt-0.5">{section.title}</h2>
                </div>
              </div>

              <p className="text-muted-fg leading-relaxed max-w-3xl">{section.description}</p>

              {section.providerTable && (
                <div className="overflow-x-auto mt-6 rounded-xl border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-white/[0.03]">
                      <tr className="border-b border-border">
                        <th className="text-left py-3 px-4 font-semibold">Provider</th>
                        <th className="text-left py-3 px-4 font-semibold">Type</th>
                        <th className="text-left py-3 px-4 font-semibold">API key</th>
                        <th className="text-left py-3 px-4 font-semibold hidden sm:table-cell">URL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {providers.map(p => (
                        <tr key={p.name} className="border-b border-border/50 last:border-0">
                          <td className="py-3 px-4 font-medium">{p.name}</td>
                          <td className="py-3 px-4"><Badge variant={p.local ? 'success' : 'outline'} className="text-[10px]">{p.local ? 'Local' : 'Cloud'}</Badge></td>
                          <td className="py-3 px-4 text-muted-fg">{p.requiresApiKey ? 'Required' : 'None'}</td>
                          <td className="py-3 px-4 font-mono text-xs text-muted-fg hidden sm:table-cell">{p.url}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {section.highlights && (
                <ul className="space-y-2 mt-5">
                  {section.highlights.map(h => (
                    <li key={h} className="flex items-start gap-2 text-sm text-muted-fg leading-relaxed">
                      <span className="text-primary mt-0.5 shrink-0">▸</span><span>{h}</span>
                    </li>
                  ))}
                </ul>
              )}

              {section.link && (
                <Link href={section.link} className="inline-flex mt-6"><Button variant="outline" size="sm">{section.linkText} <ArrowUpRight className="w-3.5 h-3.5" /></Button></Link>
              )}
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
