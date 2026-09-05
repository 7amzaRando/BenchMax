import type { Metadata } from 'next'
import DocsSidebar from '@/components/docs/DocsSidebar'

export const metadata: Metadata = {
  title: 'Documentation',
  description: 'BenchMax documentation: getting started, API reference, CLI reference, and configuration guides.',
}

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <section className="section-padding">
      <div className="container-wide">
        <div className="flex flex-col lg:flex-row gap-8 lg:gap-12">
          <DocsSidebar />
          <div className="flex-1 min-w-0 max-w-4xl">
            {children}
          </div>
        </div>
      </div>
    </section>
  )
}
