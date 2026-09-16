import type { Metadata } from 'next'
import BenchmarksClient from '@/components/benchmarks/BenchmarksClient'

export const metadata: Metadata = {
  title: 'All Benchmarks',
  description:
    'Browse all 30 BenchMax benchmarks across 12 categories: code, knowledge, math, reasoning, instruction following, safety, tool calling, vision, long context and more.',
}

export default function BenchmarksPage() {
  return <BenchmarksClient />
}
