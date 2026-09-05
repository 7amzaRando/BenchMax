import { MetadataRoute } from 'next'

export const dynamic = 'force-static'

const BASE_URL = 'https://7amzaRando.github.io/BenchMax'

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
    '/leaderboard',
    '/about',
  ]

  const benchmarkSlugs = [
    'humaneval', 'mmlu-pro', 'ifeval', 'aime', 'bigcodebench',
    'bigcodebench-hard', 'bfcl', 'uncensor-bench', 'aider-polyglot',
    'longbench-v2', 'mmmu-pro', 'livebench', 'livecodebench',
    'benchmax-personal', 'benchmax-lite', 'benchmax-code', 'benchmax-reason',
    'writing-speed-test', 'coding-speed-test', 'benchmax-tectonic',
    'truthfulqa', 'hellaswag', 'winogrande', 'arc-challenge', 'commonsenseqa',
    'long-context-memory', 'niahs', 'gaia',
  ]

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
