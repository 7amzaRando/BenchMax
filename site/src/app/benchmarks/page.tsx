'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { Search, Container, ArrowRight } from 'lucide-react'
import Card from '@/components/shared/Card'
import Badge from '@/components/shared/Badge'
import GradientText from '@/components/shared/GradientText'
import { benchmarks, ALL_CATEGORIES, CATEGORY_LABELS, CATEGORY_COLORS, TOTAL_BENCHMARKS, TOTAL_SAMPLES_DISPLAY, type BenchmarkCategory } from '@/lib/benchmarks-data'

const fade = { hidden: { opacity: 0, y: 14 }, visible: { opacity: 1, y: 0 } }
const stagger = { hidden: {}, visible: { transition: { staggerChildren: 0.035 } } }

export default function BenchmarksPage() {
  const [activeCategory, setActiveCategory] = useState<BenchmarkCategory | 'all'>('all')
  const [search, setSearch] = useState('')
  const [dockerOnly, setDockerOnly] = useState(false)

  const filtered = useMemo(() => {
    return benchmarks.filter(b => {
      const catOk = activeCategory === 'all' || b.category === activeCategory
      const q = search.toLowerCase()
      const searchOk = !q || b.name.toLowerCase().includes(q) || b.description.toLowerCase().includes(q) || b.tags.some(t => t.includes(q)) || b.subtitle.toLowerCase().includes(q)
      const dockerOk = !dockerOnly || b.docker
      return catOk && searchOk && dockerOk
    })
  }, [activeCategory, search, dockerOnly])

  const totalFiltered = filtered.reduce((s, b) => s + b.samples, 0)

  return (
    <section className="section-padding pt-24 md:pt-28 pb-16">
      <div className="container-wide">
        <motion.div initial="hidden" animate="visible" variants={stagger}>
          <motion.div variants={fade} className="text-center mb-8">
            <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-3 py-1 text-xs font-semibold text-primary mb-4">
              {TOTAL_BENCHMARKS} benchmarks · {TOTAL_SAMPLES_DISPLAY} samples
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">
              All <GradientText>Benchmarks</GradientText>
            </h1>
            <p className="text-muted-fg max-w-2xl mx-auto mt-3">
              12 categories, from coding to long documents. Most work out of the box; coding tests use a safe sandbox.
            </p>
          </motion.div>

          {/* controls */}
          <motion.div variants={fade} className="flex flex-col lg:flex-row gap-3 items-stretch lg:items-center justify-between mb-6">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-fg" />
              <input
                type="text"
                placeholder="Search by name, description or tag…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-full bg-card border border-border text-foreground placeholder:text-muted-fg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-muted-fg cursor-pointer select-none">
              <input type="checkbox" checked={dockerOnly} onChange={e => setDockerOnly(e.target.checked)} className="rounded border-border bg-card" />
              <Container className="w-4 h-4 text-primary" /> Needs sandbox only (5)
            </label>
          </motion.div>

          <motion.div variants={fade} className="flex flex-wrap gap-2 mb-8">
            <button
              onClick={() => setActiveCategory('all')}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${activeCategory === 'all' ? 'bg-foreground text-background border-foreground' : 'bg-card border-border text-muted-fg hover:text-foreground hover:border-border-strong'}`}
            >
              All · {TOTAL_BENCHMARKS}
            </button>
            {ALL_CATEGORIES.map(cat => {
              const count = benchmarks.filter(b => b.category === cat).length
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${activeCategory === cat ? 'bg-foreground text-background border-foreground' : 'bg-card border-border text-muted-fg hover:text-foreground hover:border-border-strong'}`}
                >
                  {CATEGORY_LABELS[cat]} · {count}
                </button>
              )
            })}
          </motion.div>

          <div className="text-xs text-muted-fg mb-4">
            Showing {filtered.length} benchmarks · {totalFiltered.toLocaleString()} samples
            {dockerOnly && ' · needs sandbox setup'}
          </div>

          <motion.div
            key={`${activeCategory}-${search}-${dockerOnly}`}
            initial="hidden"
            animate="visible"
            variants={stagger}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          >
            {filtered.map(b => (
              <motion.div key={b.slug} variants={fade} transition={{ duration: 0.35 }}>
                <Link href={`/benchmarks/${b.slug}/`}>
                  <Card variant="default" className="p-5 h-full group">
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <Badge variant={(CATEGORY_COLORS[b.category] as any) || 'default'}>{CATEGORY_LABELS[b.category]}</Badge>
                      <span className="text-xs text-muted-fg">{b.samples.toLocaleString()}</span>
                    </div>
                    <h3 className="font-semibold leading-tight group-hover:text-primary transition-colors">{b.name}</h3>
                    <p className="text-xs text-muted-fg mt-1">{b.subtitle}</p>
                    <p className="text-xs text-muted-fg/80 leading-relaxed mt-2 line-clamp-2">{b.description}</p>
                    <div className="mt-3 flex items-center justify-between">
                      <span className="text-xs text-muted-fg">{b.source}</span>
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">View <ArrowRight className="w-3 h-3" /></span>
                    </div>
                    {b.docker && <div className="mt-3 inline-flex items-center gap-1 text-[10px] font-semibold tracking-wide uppercase px-2 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary"><Container className="w-3 h-3" /> Sandbox setup needed</div>}
                  </Card>
                </Link>
              </motion.div>
            ))}
          </motion.div>

          {filtered.length === 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-16 rounded-2xl border border-dashed border-border bg-card/50 mt-6">
              <p className="text-muted-fg">No benchmarks match your filters.</p>
              <button onClick={() => { setSearch(''); setActiveCategory('all'); setDockerOnly(false) }} className="mt-3 text-sm font-medium text-primary hover:underline">Clear filters</button>
            </motion.div>
          )}
        </motion.div>
      </div>
    </section>
  )
}
