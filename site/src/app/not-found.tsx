import Link from 'next/link'
import GradientText from '@/components/shared/GradientText'

export default function NotFound() {
  return (
    <section className="section-padding pt-24 md:pt-28 pb-16">
      <div className="container-narrow text-center">
        <div className="text-6xl font-extrabold tracking-tight">
          <GradientText>404</GradientText>
        </div>
        <h1 className="text-2xl font-bold mt-4">Page not found</h1>
        <p className="text-muted-fg mt-2 max-w-md mx-auto">
          This page does not exist. Try the benchmarks list or the docs instead.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/benchmarks/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold bg-foreground text-background hover:bg-white transition-colors"
          >
            All Benchmarks
          </Link>
          <Link
            href="/docs/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium border border-border text-muted-fg hover:text-foreground hover:bg-white/[0.06]"
          >
            Documentation
          </Link>
        </div>
      </div>
    </section>
  )
}
