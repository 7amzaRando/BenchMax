import type { Metadata } from 'next'
import HomeClient from '@/components/home/HomeClient'

export const metadata: Metadata = {
  title: 'BenchMax: Local LLM Benchmarking Suite',
  description:
    'Evaluate any LLM against 30 standardized benchmarks: 40k samples across code, knowledge, math, reasoning, vision, tool use and more. Works with LM Studio, Ollama, OpenAI and any compatible service. Free and open source (AGPL v3).',
}

export default function HomePage() {
  return <HomeClient />
}
