'use client'

import Link from 'next/link'
import { Zap, Play, Shield, BarChart3, Trophy, Terminal, Cpu, GitBranch, Container, Layers, Sparkles, ArrowRight, Check, Copy, ChevronRight } from 'lucide-react'
import { motion } from 'framer-motion'
import GradientText from '@/components/shared/GradientText'
import Card from '@/components/shared/Card'
import Badge from '@/components/shared/Badge'
import Button from '@/components/shared/Button'
import { benchmarks, CATEGORY_COLORS, TOTAL_BENCHMARKS, TOTAL_SAMPLES_DISPLAY } from '@/lib/benchmarks-data'
import { providers } from '@/lib/providers-data'
import { SITE_STATS } from '@/lib/site-stats'
import { useState } from 'react'

const FEATURES = [
  {
    icon: Container,
    title: 'Safe code testing, automatically',
    description: 'Coding tests run in an isolated sandbox so bad code cannot harm your machine. Everything else runs directly with no extra setup.',
  },
  {
    icon: Shield,
    title: 'Fair scores you can trust',
    description: 'Code is actually executed against hidden tests, instructions are checked with official graders, and tool calls are verified structurally. No guesswork.',
  },
  {
    icon: GitBranch,
    title: 'Test many models, hands-free',
    description: 'Queue up benchmarks or whole sets of models and let BenchMax work through them. Pause and resume anytime, with live progress and side-by-side comparisons.',
  },
  {
    icon: Cpu,
    title: 'See speed and hardware live',
    description: 'Watch accuracy, response speed, and your CPU / GPU load update in real time while a run is in progress.',
  },
  {
    icon: Terminal,
    title: 'Stuck models do not waste your time',
    description: 'If a model starts repeating itself, BenchMax spots the loop, skips that question, and keeps the run moving.',
  },
  {
    icon: Layers,
    title: '30 benchmarks, 12 categories',
    description: 'Coding, knowledge, math, reasoning, instructions, safety, tool use, vision, long documents and more, all in one place.',
  },
]

const TOP_BENCHMARKS = benchmarks.slice(0, 12)

const ARCH_STEPS = [
  { label: 'Connect a model', detail: 'LM Studio, Ollama, OpenAI or any compatible service', accent: 'primary' },
  { label: 'Pick a benchmark', detail: 'Choose what to test: coding, knowledge, reasoning and more', accent: 'secondary' },
  { label: 'BenchMax runs it', detail: 'Every question is asked, checked and scored automatically', accent: 'accent' },
  { label: 'Explore results', detail: 'Charts, comparisons and a leaderboard, live as it runs', accent: 'success' },
]

const fade = { hidden: { opacity: 0, y: 16 }, visible: { opacity: 1, y: 0 } }
const stagger = { hidden: {}, visible: { transition: { staggerChildren: 0.07 } } }

function TerminalPreview() {
  const [copied, setCopied] = useState(false)
  const cmd = 'py cli.py run --benchmark HumanEval --model qwen2.5-7b --wait'
  return (
    <div className="code-surface rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-white/[0.03]">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-[#ff5f56] border border-black/10" />
          <span className="w-3 h-3 rounded-full bg-[#ffbd2e] border border-black/10" />
          <span className="w-3 h-3 rounded-full bg-[#27c93f] border border-black/10" />
          <span className="ml-3 text-xs font-mono text-muted-fg">benchmax run 42 · HumanEval</span>
        </div>
        <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-muted-fg"><span className="w-2 h-2 rounded-full bg-success animate-pulse-subtle" /> streaming</span>
      </div>
      <div className="p-4 sm:p-5 font-mono text-xs leading-relaxed">
        <div className="text-muted-fg">$ {cmd}</div>
        <div className="mt-3 space-y-1.5">
          <div className="flex justify-between"><span className="text-muted-fg">HumanEval/0</span><span className="text-success">PASS</span><span className="text-muted-fg">42.3 t/s · TTFT 180ms</span></div>
          <div className="flex justify-between"><span className="text-muted-fg">HumanEval/1</span><span className="text-success">PASS</span><span className="text-muted-fg">38.7 t/s · TTFT 210ms</span></div>
          <div className="flex justify-between"><span className="text-muted-fg">HumanEval/2</span><span className="text-danger">FAIL</span><span className="text-muted-fg">41.1 t/s · TTFT 195ms</span></div>
          <div className="h-px bg-white/[0.06] my-2" />
          <div className="flex items-center gap-2 text-foreground"><span className="text-primary">▸</span> Accuracy <span className="font-semibold">66.7%</span> <span className="text-muted-fg">· Avg TPS 40.2 · Avg TTFT 195ms</span></div>
        </div>
      </div>
      <div className="px-4 py-2.5 bg-white/[0.03] border-t border-white/[0.06] flex items-center justify-between gap-2">
        <code className="text-xs font-mono text-muted-fg truncate">{cmd}</code>
        <button
          onClick={() => { navigator.clipboard.writeText(cmd); setCopied(true); setTimeout(() => setCopied(false), 1400) }}
          className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white text-background text-xs font-semibold hover:bg-white/90 transition-colors"
        >
          {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
        </button>
      </div>
    </div>
  )
}

export default function HomePage() {
  return (
    <>
      {/* HERO: editorial split */}
      <section className="relative pt-10 md:pt-16 pb-10">
        <div className="container-wide px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-10 lg:gap-8 items-center">
            {/* copy */}
            <motion.div initial="hidden" animate="visible" variants={stagger} className="text-left">
              <motion.div variants={fade} transition={{ duration: 0.5 }} className="flex flex-wrap items-center gap-2 mb-5">
                <span className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-3 py-1 text-xs font-semibold text-primary">
                  <Sparkles className="w-3.5 h-3.5" /> Free & open-source · AGPL v3
                </span>
                <span className="inline-flex items-center rounded-full bg-white/[0.06] border border-white/[0.08] px-3 py-1 text-xs font-medium text-muted-fg">v1.1 · 30 benchmarks</span>
              </motion.div>

              <motion.h1 variants={fade} transition={{ duration: 0.55, delay: 0.05 }} className="text-[40px] sm:text-[52px] lg:text-[58px] font-extrabold leading-[0.95] tracking-[-0.03em]">
                Benchmark
                <br />
                <GradientText as="span">any LLM</GradientText>
                <br />
                <span className="text-foreground">locally.</span>
              </motion.h1>

              <motion.p variants={fade} transition={{ duration: 0.55, delay: 0.12 }} className="mt-5 text-[17px] leading-relaxed text-muted-fg max-w-xl">
                Point BenchMax at <span className="text-foreground font-medium">LM Studio, Ollama, OpenAI</span> or any compatible AI service. 30 ready-made tests measure how good your model really is (coding, knowledge, reasoning and more), all on your machine.
              </motion.p>

              <motion.div variants={fade} transition={{ duration: 0.55, delay: 0.18 }} className="mt-7 flex flex-wrap items-center gap-3">
                <Link href="/docs/getting-started/">
                  <Button variant="glow" size="lg"><Zap className="w-4 h-4" /> Get Started <ArrowRight className="w-4 h-4 opacity-70" /></Button>
                </Link>
                <Link href="/benchmarks/">
                  <Button variant="outline" size="lg">View Benchmarks <ChevronRight className="w-4 h-4" /></Button>
                </Link>
                <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm font-medium text-muted-fg hover:text-foreground transition-colors px-2">
                  GitHub <ArrowRight className="w-3.5 h-3.5" />
                </a>
              </motion.div>

              <motion.div variants={fade} transition={{ duration: 0.55, delay: 0.22 }} className="mt-6 flex flex-wrap gap-2 text-xs text-muted-fg">
                <span className="inline-flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-success" /> Most tests work out of the box</span>
                <span className="opacity-40">·</span>
                <span className="inline-flex items-center gap-1.5"><Container className="w-3.5 h-3.5 text-primary" /> Coding tests run safely isolated</span>
              </motion.div>
            </motion.div>

            {/* visual */}
            <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }} className="relative">
              <div className="absolute -inset-4 bg-gradient-to-br from-primary/10 via-primary/5 to-secondary/10 blur-2xl rounded-[2rem] pointer-events-none" />
              <div className="relative">
                <TerminalPreview />
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {[
                    { k: 'TTFT', v: '~180 ms', sub: 'time to first token' },
                    { k: 'TPS', v: '40 t/s', sub: 'avg throughput' },
                    { k: 'Tokens', v: '2.1k', sub: 'per sample avg' },
                  ].map(s => (
                    <div key={s.k} className="rounded-xl bg-card border border-border px-3 py-3">
                      <div className="text-[11px] font-semibold tracking-widest uppercase text-muted-fg">{s.k}</div>
                      <div className="text-sm font-bold text-foreground mt-0.5">{s.v}</div>
                      <div className="text-xs text-muted-fg">{s.sub}</div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* STATS: glass pills */}
      <section className="pb-10">
        <div className="container-wide px-4 sm:px-6 lg:px-8">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-60px' }} variants={stagger} className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {SITE_STATS.map(s => (
              <motion.div key={s.label} variants={fade} transition={{ duration: 0.45 }}>
                <div className="rounded-2xl glass-panel px-5 py-5">
                  <div className="text-2xl md:text-3xl font-extrabold tracking-tight gradient-text">{s.value}</div>
                  <div className="text-sm font-semibold text-foreground mt-1">{s.label}</div>
                  <div className="text-xs text-muted-fg">{s.sublabel}</div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ARCHITECTURE STRIP */}
      <section className="pb-10">
        <div className="container-wide px-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-border bg-card overflow-hidden">
            <div className="grid lg:grid-cols-[280px_1fr] gap-0">
              <div className="p-6 lg:p-7 border-b lg:border-b-0 lg:border-r border-border">
                <div className="eyebrow mb-3">Architecture</div>
                <h3 className="text-lg font-bold leading-tight">Runs on <span className="gradient-text">your own computer</span></h3>
                <p className="text-sm text-muted-fg mt-2 leading-relaxed">Everything happens locally: your models, your results, your hardware. No cloud uploads, no hosted services.</p>
                <Link href="/docs/getting-started/" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline mt-4">Get started in 5 minutes <ChevronRight className="w-4 h-4" /></Link>
              </div>
              <div className="p-4 sm:p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {ARCH_STEPS.map(step => (
                  <div key={step.label} className="rounded-xl bg-background border border-border p-4">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center mb-3">
                      <Layers className="w-4 h-4 text-primary" />
                    </div>
                    <div className="text-sm font-semibold">{step.label}</div>
                    <div className="text-xs text-muted-fg mt-1 leading-relaxed">{step.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="pb-12">
        <div className="container-narrow px-4 sm:px-6 lg:px-8">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} variants={stagger}>
              <motion.div variants={fade} className="max-w-2xl mx-auto text-center mb-10">
                <div className="eyebrow justify-center mb-3">Why BenchMax</div>
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight">Everything you need to <GradientText>measure</GradientText></h2>
                <p className="text-muted-fg mt-3">From coding tests to speed checks: a complete toolkit that runs entirely on your machine.</p>
              </motion.div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {FEATURES.map(f => (
                <motion.div key={f.title} variants={fade} transition={{ duration: 0.45 }}>
                  <Card variant="glow" className="p-6 h-full">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-secondary/15 border border-primary/15 flex items-center justify-center mb-4">
                      <f.icon className="w-5 h-5 text-primary" />
                    </div>
                    <h3 className="text-[15px] font-semibold tracking-tight">{f.title}</h3>
                    <p className="text-sm text-muted-fg leading-relaxed mt-1.5">{f.description}</p>
                  </Card>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* BENCHMARKS SHOWCASE */}
      <section className="pb-12">
        <div className="container-wide px-4 sm:px-6 lg:px-8">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} variants={stagger}>
            <motion.div variants={fade} className="flex flex-wrap items-end justify-between gap-4 mb-6">
              <div>
                <div className="eyebrow mb-2">Benchmarks</div>
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight"><GradientText>{TOTAL_BENCHMARKS} benchmarks</GradientText> · {TOTAL_SAMPLES_DISPLAY} samples</h2>
                <p className="text-muted-fg mt-2 max-w-xl">Coding, knowledge, math, reasoning, vision, tool use, long documents and more. Each one scored fairly and transparently.</p>
              </div>
              <Link href="/benchmarks/" className="hidden sm:inline-flex items-center gap-1.5 px-5 py-2.5 rounded-full bg-white/[0.07] border border-white/[0.08] text-sm font-medium text-foreground hover:bg-white/[0.10] transition-colors">
                View all {TOTAL_BENCHMARKS} <ArrowRight className="w-4 h-4" />
              </Link>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {TOP_BENCHMARKS.map(b => (
                <motion.div key={b.slug} variants={fade} transition={{ duration: 0.4 }}>
                  <Link href={`/benchmarks/${b.slug}/`}>
                    <Card variant="default" className="p-4 h-full group">
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <Badge variant={(CATEGORY_COLORS[b.category] as any) || 'default'}>{b.category}</Badge>
                        {b.docker && <span title="Needs the safe sandbox (one-click setup)" className="inline-flex items-center gap-1 text-[10px] font-semibold tracking-wide uppercase px-2 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary"><Container className="w-3 h-3" /> Sandbox</span>}
                      </div>
                      <h3 className="font-semibold leading-tight group-hover:text-primary transition-colors">{b.name}</h3>
                      <p className="text-xs text-muted-fg mt-1">{b.subtitle}</p>
                      <p className="text-xs text-muted-fg/80 mt-1">{b.samples.toLocaleString()} samples</p>
                    </Card>
                  </Link>
                </motion.div>
              ))}
            </div>
            <div className="sm:hidden text-center mt-6">
              <Link href="/benchmarks/"><Button variant="outline">View all {TOTAL_BENCHMARKS} benchmarks</Button></Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* PROVIDERS */}
      <section className="pb-12">
        <div className="container-narrow px-4 sm:px-6 lg:px-8">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} variants={stagger}>
            <motion.div variants={fade} className="text-center mb-8">
              <div className="eyebrow justify-center mb-3">Providers</div>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight">Works with <GradientText>8 providers</GradientText></h2>
              <p className="text-muted-fg max-w-xl mx-auto mt-2">Local or cloud. If it works with AI apps, it works with BenchMax. Switching is as easy as changing one address.</p>
            </motion.div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {providers.map(p => (
                <motion.div key={p.name} variants={fade} transition={{ duration: 0.35 }}>
                  <Card variant="glass" className="p-5 text-center h-full">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-secondary/15 border border-primary/15 flex items-center justify-center mx-auto mb-3">
                      <span className="text-sm font-bold text-primary">{p.name[0]}</span>
                    </div>
                    <h3 className="font-semibold text-sm">{p.name}</h3>
                    <p className="text-xs text-muted-fg mt-1 line-clamp-2">{p.description}</p>
                    <Badge variant={p.local ? 'success' : 'outline'} className="mt-2 text-[10px]">{p.local ? 'Local · no key' : 'Cloud · key required'}</Badge>
                  </Card>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="pb-14">
        <div className="container-narrow px-4 sm:px-6 lg:px-8">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} variants={fade}>
            <Card variant="elevated" className="relative overflow-hidden p-8 md:p-10">
              <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.08] via-transparent to-secondary/[0.07] pointer-events-none" />
              <div className="absolute -top-24 -right-24 w-[420px] h-[420px] rounded-full blur-[80px] bg-primary/10 pointer-events-none" />
              <div className="relative grid lg:grid-cols-[1.1fr_0.9fr] gap-8 items-center">
                <div>
                  <h2 className="text-3xl md:text-4xl font-bold tracking-tight">Ready to <GradientText>benchmark</GradientText>?</h2>
                  <p className="text-muted-fg mt-3 max-w-lg">Download, install, and run your first test in under 5 minutes. No hosted services, no uploads.</p>
                  <div className="mt-6 flex flex-wrap gap-3">
                    <Link href="/docs/getting-started/"><Button variant="glow" size="lg"><Zap className="w-4 h-4" /> Get Started</Button></Link>
                    <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noopener noreferrer"><Button variant="outline" size="lg">View on GitHub</Button></a>
                  </div>
                  <p className="text-xs text-muted-fg mt-4">New to coding tests? BenchMax sets up its safe sandbox for you. <Link href="/docs/getting-started/" className="text-primary hover:underline">See the setup guide</Link>.</p>
                </div>
                <div className="code-surface rounded-xl p-4 font-mono text-xs leading-relaxed overflow-x-auto">
                  <div className="text-muted-fg">$ git clone https://github.com/7amzaRando/BenchMax.git</div>
                  <div className="text-muted-fg">$ cd BenchMax && python -m venv .venv</div>
                  <div className="text-muted-fg">$ .venv/Scripts/pip install -r backend/requirements.txt</div>
                  <div className="text-muted-fg">$ cd frontend && npm install && npm run build && cd ..</div>
                  <div className="text-primary">$ .venv/Scripts/uvicorn backend.main:app --port 8000</div>
                  <div className="text-muted-fg mt-2"># → http://localhost:8000</div>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </section>
    </>
  )
}
