import type { Metadata } from 'next'
import LeaderboardClient from '@/components/leaderboard/LeaderboardClient'

export const metadata: Metadata = {
  title: 'Leaderboard',
  description:
    'Real LLM scores from public leaderboards (HumanEval, MMLU-Pro, IFEval, BigCodeBench, BFCL, LiveBench), with sources and dates. Reproduce any of them locally with BenchMax.',
}

export default function LeaderboardPage() {
  return <LeaderboardClient />
}
