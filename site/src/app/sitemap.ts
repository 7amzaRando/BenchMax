import { MetadataRoute } from 'next'
import { benchmarks } from '@/lib/benchmarks-data'

export const dynamic = 'force-static'

// keep in sync with metadataBase in app/layout.tsx
const BASE_URL = 'https://7amzarando.github.io/BenchMax'

export default function sitemap(): MetadataRoute.Sitemap {
  const staticPages = [
    '',
    '/benchmarks',
    '/features',
    '/docs',
    '/docs/getting-started',
    '/docs/api-reference',
    '/docs/cli-reference',
    '/docs/configuration',
    '/results',
    '/about',
  ]

  // derived from benchmarks-data so new benchmarks can never go missing here again
  const benchmarkSlugs = benchmarks.map(b => b.slug)

  const staticEntries = staticPages.map((path) => ({
    url: `${BASE_URL}${path}`,
    lastModified: new Date(),
    changeFrequency: 'monthly' as const,
    priority: path === '' ? 1.0 : 0.8,
  }))

  const benchmarkEntries = benchmarkSlugs.map((slug) => ({
    url: `${BASE_URL}/benchmarks/${slug}`,
    lastModified: new Date(),
    changeFrequency: 'monthly' as const,
    priority: 0.7,
  }))

  return [...staticEntries, ...benchmarkEntries]
}
