import { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowLeft, Container, ExternalLink, Sparkles } from 'lucide-react'
import Card from '@/components/shared/Card'
import Badge from '@/components/shared/Badge'
import GradientText from '@/components/shared/GradientText'
import CopyButton from '@/components/shared/CopyButton'
import { benchmarks, getBenchmarkBySlug, CATEGORY_LABELS, CATEGORY_COLORS } from '@/lib/benchmarks-data'

interface PageProps { params: Promise<{ slug: string }> }

export function generateStaticParams() { return benchmarks.map(b => ({ slug: b.slug })) }

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params
  const bench = getBenchmarkBySlug(slug)
  if (!bench) return { title: 'Benchmark Not Found' }
  return {
    title: `${bench.name} Benchmark`,
    description: bench.description,
    openGraph: { title: `${bench.name} | BenchMax`, description: bench.description },
  }
}

export default async function BenchmarkDetailPage({ params }: PageProps) {
  const { slug } = await params
  const bench = getBenchmarkBySlug(slug)
  if (!bench) notFound()

  const related = benchmarks.filter(b => b.category === bench.category && b.slug !== bench.slug).slice(0, 4)
  const cliCommand = `py cli.py run --benchmark "${bench.name}" --model <model-id> --wait`

  return (
    <section className="section-padding pt-24 md:pt-28 pb-16">
      <div className="container-narrow">
        <Link href="/benchmarks/" className="inline-flex items-center gap-1.5 text-sm text-muted-fg hover:text-foreground transition-colors mb-6">
          <ArrowLeft className="w-4 h-4" /> All Benchmarks
        </Link>

        <Card variant="elevated" className="relative overflow-hidden p-7 md:p-9 mb-8">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.07] via-transparent to-secondary/[0.05] pointer-events-none" />
          <div className="relative">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <Badge variant={(CATEGORY_COLORS[bench.category] as any) || 'default'}>{CATEGORY_LABELS[bench.category]}</Badge>
              <span className="text-sm text-muted-fg">{bench.samples.toLocaleString()} samples</span>
              {bench.docker ? (
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary"><Container className="w-3.5 h-3.5" /> Needs sandbox setup</span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-success/10 border border-success/20 text-success"><Sparkles className="w-3.5 h-3.5" /> No setup needed</span>
              )}
              <span className="text-xs text-muted-fg">· {bench.source}</span>
            </div>

            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight"><GradientText>{bench.name}</GradientText></h1>
            <p className="text-sm font-medium text-muted-fg mt-1">{bench.subtitle}</p>
            <p className="text-muted-fg leading-relaxed mt-4 max-w-2xl">{bench.description}</p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-8">
              <div className="rounded-xl bg-background border border-border p-4">
                <div className="text-xs font-semibold tracking-widest uppercase text-muted-fg">How it is scored</div>
                <div className="text-sm font-medium mt-1 leading-relaxed">{bench.scoring}</div>
              </div>
              <div className="rounded-xl bg-background border border-border p-4">
                <div className="text-xs font-semibold tracking-widest uppercase text-muted-fg">Source</div>
                <div className="text-sm font-medium mt-1">{bench.source}</div>
              </div>
              <div className="rounded-xl bg-background border border-border p-4">
                <div className="text-xs font-semibold tracking-widest uppercase text-muted-fg">Samples</div>
                <div className="text-sm font-medium mt-1">{bench.samples.toLocaleString()}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mt-6">
              {bench.tags.map(tag => (
                <span key={tag} className="text-xs px-3 py-1 rounded-full bg-white/[0.06] border border-white/[0.06] text-muted-fg">{tag}</span>
              ))}
            </div>

            <div className="mt-8 rounded-xl code-surface p-4 flex items-center gap-3">
              <code className="flex-1 text-sm font-mono text-foreground overflow-x-auto">{cliCommand}</code>
              <CopyButton text={cliCommand} className="shrink-0 p-2.5 rounded-xl bg-card border border-border text-muted-fg hover:text-foreground hover:border-primary/30 transition-colors" />
            </div>
            {bench.docker && (
              <p className="text-xs text-muted-fg mt-3">This test runs code, so it needs the safe sandbox first. <Link href="/docs/getting-started/" className="text-primary hover:underline">Setup takes a few minutes.</Link></p>
            )}
          </div>
        </Card>

        {related.length > 0 && (
          <div>
            <h2 className="text-xl font-bold tracking-tight mb-4">Related <GradientText>{CATEGORY_LABELS[bench.category]}</GradientText></h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {related.map(rb => (
                <Link key={rb.slug} href={`/benchmarks/${rb.slug}/`}>
                  <Card variant="default" className="p-5 h-full group">
                    <Badge variant={(CATEGORY_COLORS[rb.category] as any) || 'default'} className="mb-2">{CATEGORY_LABELS[rb.category]}</Badge>
                    <h3 className="font-semibold group-hover:text-primary transition-colors">{rb.name}</h3>
                    <p className="text-xs text-muted-fg mt-1">{rb.subtitle}</p>
                    <p className="text-xs text-muted-fg/70 mt-1">{rb.samples.toLocaleString()} samples</p>
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
