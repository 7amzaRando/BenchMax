'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ExternalLink, Info } from 'lucide-react'
import GradientText from '@/components/shared/GradientText'
import Card, { CardContent } from '@/components/shared/Card'
import Badge from '@/components/shared/Badge'

// ---------------------------------------------------------------------------
// Real-world leaderboard, researched 2026-09-03
// Only includes benchmarks with a public official or well-maintained
// community leaderboard as of ~late Aug / early Sep 2026.
// Dates and sources are shown per row. Scores that are nearly saturated
// (HumanEval) are flagged: the benchmark is kept for history, not
// discrimination (cite: verdictpal, presenc.ai June 2026).
// ---------------------------------------------------------------------------

type Row = {
  model: string
  provider: string
  score: number // 0-100
  benchmark: string // exact benchmark name as in BenchMax
  category: 'Code' | 'Knowledge' | 'Instruction' | 'Tool-calling' | 'Composite' | 'Math'
  date: string // YYYY-MM-DD or YYYY-MM for source snapshot
  source: string // short source name
  sourceUrl: string
  note?: string
}

const LEADERBOARD: Row[] = [
  // -------- HumanEval (164 Python problems, pass@1), SATURATED ≥95% ----------
  // Best available dated, source-checked rows. Multiple frontier models >95%
  // as of June 2026; ordering inside the band is noise (presenc.ai June 10,
  // verdictpal, codesota).
  { model: 'Claude Opus 4.6', provider: 'Anthropic', score: 96.3, benchmark: 'HumanEval', category: 'Code', date: '2026-02-05', source: 'verdictpal / Codesota', sourceUrl: 'https://verdictpal.com/benchmarks/humaneval' },
  { model: 'GPT-5', provider: 'OpenAI', score: 95.1, benchmark: 'HumanEval', category: 'Code', date: '2025-12-11', source: 'Codesota', sourceUrl: 'https://www.codesota.com/browse/computer-code/code-generation/humaneval' },
  { model: 'o3', provider: 'OpenAI', score: 94.8, benchmark: 'HumanEval', category: 'Code', date: '2025-04-16', source: 'Codesota', sourceUrl: 'https://www.codesota.com/browse/computer-code/code-generation/humaneval' },
  { model: 'Gemini 3.5 Flash', provider: 'Google', score: 94.6, benchmark: 'HumanEval', category: 'Code', date: '2026-05-19', source: 'verdictpal', sourceUrl: 'https://verdictpal.com/benchmarks/humaneval' },
  { model: 'Claude Sonnet 4.6', provider: 'Anthropic', score: 94.1, benchmark: 'HumanEval', category: 'Code', date: '2026-02-17', source: 'verdictpal', sourceUrl: 'https://verdictpal.com/benchmarks/humaneval' },
  { model: 'Kimi K2.6', provider: 'Moonshot', score: 93.8, benchmark: 'HumanEval', category: 'Code', date: '2026-04-20', source: 'verdictpal', sourceUrl: 'https://verdictpal.com/benchmarks/humaneval' },
  { model: 'Qwen2.5-Coder-32B Instruct', provider: 'Alibaba', score: 92.7, benchmark: 'HumanEval', category: 'Code', date: '2025-03', source: 'Codesota', sourceUrl: 'https://www.codesota.com/browse/computer-code/code-generation/humaneval' },
  { model: 'DeepSeek-Coder-V2 Instruct', provider: 'DeepSeek', score: 90.2, benchmark: 'HumanEval', category: 'Code', date: '2024-06', source: 'Codesota', sourceUrl: 'https://www.codesota.com/browse/computer-code/code-generation/humaneval' },
  { model: 'GPT-4o', provider: 'OpenAI', score: 90.2, benchmark: 'HumanEval', category: 'Code', date: '2024-05-13', source: 'Codesota', sourceUrl: 'https://www.codesota.com/browse/computer-code/code-generation/humaneval' },
  { model: 'Llama 3.3 70B Instruct', provider: 'Meta', score: 88.4, benchmark: 'HumanEval', category: 'Code', date: '2024-12-06', source: 'Codesota', sourceUrl: 'https://www.codesota.com/browse/computer-code/code-generation/humaneval' },

  // -------- MMLU-Pro (12,032 Qs, 10 options) -----------------------------------
  // Top is Gemini 3 Pro Preview 89.8% (Sophon 340 models, pricepertoken Aug 30,
  // ArtificialAnalysis). BenchLM Aug 27: Qwen3.7 Max 89.6% / Claude Opus 4.5 89.5%.
  { model: 'Gemini 3 Pro Preview', provider: 'Google', score: 89.8, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2026-08-30', source: 'Sophon / ArtificialAnalysis / pricepertoken', sourceUrl: 'https://sophon.at/evals/mmlu-pro' },
  { model: 'Qwen3.7 Max', provider: 'Alibaba', score: 89.6, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2026-08-27', source: 'BenchLM.ai', sourceUrl: 'https://benchlm.ai/benchmarks/mmlu-pro' },
  { model: 'Claude Opus 4.5', provider: 'Anthropic', score: 89.5, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2026-08-27', source: 'BenchLM.ai', sourceUrl: 'https://benchlm.ai/benchmarks/mmlu-pro' },
  { model: 'Qwen3.7 Plus', provider: 'Alibaba', score: 88.5, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2026-08-27', source: 'BenchLM.ai', sourceUrl: 'https://benchlm.ai/benchmarks/mmlu-pro' },
  { model: 'DeepSeek V4 Pro', provider: 'DeepSeek', score: 87.5, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2026-04-24', source: 'BenchLM.ai', sourceUrl: 'https://benchlm.ai/benchmarks/mmlu-pro' },
  { model: 'GPT-5', provider: 'OpenAI', score: 86.5, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2026-08-22', source: 'AnotherWrapper', sourceUrl: 'https://anotherwrapper.com/tools/llm-pricing/evals/mmlu-pro' },
  { model: 'Kimi K2.5', provider: 'Moonshot', score: 87.1, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2026-01-27', source: 'BenchLM.ai', sourceUrl: 'https://benchlm.ai/benchmarks/mmlu-pro' },
  { model: 'Gemini 2.5 Pro', provider: 'Google', score: 86.4, benchmark: 'MMLU-Pro', category: 'Knowledge', date: '2025-03', source: 'ArtificialAnalysis', sourceUrl: 'https://artificialanalysis.ai/evaluations/mmlu-pro' },

  // -------- IFEval (541 prompts, prompt-level strict, 0-1, shown as %) -------
  // Leader 95.0% Qwen3.5-27B, unanimous across llm-stats (68 models),
  // AnotherWrapper Aug 22, AwesomeAgents Apr. Converted from 0.950.
  { model: 'Qwen3.5-27B', provider: 'Alibaba', score: 95.0, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'llm-stats / AnotherWrapper', sourceUrl: 'https://llm-stats.com/benchmarks/ifeval' },
  { model: 'Qwen3.7 Plus', provider: 'Alibaba', score: 94.6, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'AnotherWrapper / llm-stats', sourceUrl: 'https://anotherwrapper.com/tools/llm-pricing/evals/ifeval' },
  { model: 'Qwen3.7 Max', provider: 'Alibaba', score: 94.3, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'llm-stats', sourceUrl: 'https://llm-stats.com/benchmarks/ifeval' },
  { model: 'o3-mini', provider: 'OpenAI', score: 93.9, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'llm-stats', sourceUrl: 'https://llm-stats.com/benchmarks/ifeval' },
  { model: 'Qwen3.5-122B-A10B', provider: 'Alibaba', score: 93.4, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'llm-stats', sourceUrl: 'https://llm-stats.com/benchmarks/ifeval' },
  { model: 'Claude 3.7 Sonnet', provider: 'Anthropic', score: 93.2, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'llm-stats / AwesomeAgents', sourceUrl: 'https://awesomeagents.ai/leaderboards/instruction-following-leaderboard/' },
  { model: 'Gemma 3 27B', provider: 'Google', score: 90.4, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'llm-stats', sourceUrl: 'https://llm-stats.com/benchmarks/ifeval' },
  { model: 'Gemma 3 4B', provider: 'Google', score: 90.2, benchmark: 'IFEval', category: 'Instruction', date: '2026-08-22', source: 'AwesomeAgents / llm-stats', sourceUrl: 'https://awesomeagents.ai/leaderboards/instruction-following-leaderboard/' },

  // -------- BigCodeBench (1,140 tasks, calibrated pass@1) ----------------------
  // Full-set: Granite-4.0-H-Small 46.23 pass@1 is top on GenAIList (aggregated
  // official reports). BenchLM Sep 2 shows only 2 DeepSeek base code models
  // (59.2% / 56.8%), limited snapshot, listed separately. Hard-set handled
  // separately by BenchMax; shown for completeness.
  { model: 'Granite-4.0-H-Small', provider: 'IBM', score: 46.2, benchmark: 'BigCodeBench', category: 'Code', date: '2026-08', source: 'GenAIList (pass@1)', sourceUrl: 'https://genailist.net/benchmark/bigcodebench' },
  { model: 'Granite-4.0-H-Tiny', provider: 'IBM', score: 41.1, benchmark: 'BigCodeBench', category: 'Code', date: '2026-08', source: 'GenAIList', sourceUrl: 'https://genailist.net/benchmark/bigcodebench' },
  { model: 'Granite-4.0-H-Micro', provider: 'IBM', score: 37.9, benchmark: 'BigCodeBench', category: 'Code', date: '2026-08', source: 'GenAIList', sourceUrl: 'https://genailist.net/benchmark/bigcodebench' },
  { model: 'Claude Opus 4.5', provider: 'Anthropic', score: 35.1, benchmark: 'BigCodeBench-Hard', category: 'Code', date: '2026-03', source: 'SOTA2 (BigCodeBench-Hard)', sourceUrl: 'https://www.sota2.com/research/sota/code-generation-on-bigcodebench-hard' },
  { model: 'DeepSeek V4 Pro Base', provider: 'DeepSeek', score: 59.2, benchmark: 'BigCodeBench*', category: 'Code', date: '2026-09-02', source: 'BenchLM.ai (2-model view)', sourceUrl: 'https://benchlm.ai/benchmarks/bigcodebench', note: 'BenchLM mirrors only 2 DeepSeek base checkpoints; not full leaderboard' },

  // -------- BFCL V4 (Berkeley Function Calling, overall accuracy) --------------
  // Official board (gorilla.cs.berkeley.edu) updated 2026-04-12, 83 entries.
  // ModelCap tracks 31 of them: GLM 4.6 72.4 is top tracked. BenchLM/llm-stats
  // Sep snapshot: Qwen3.7 Max 75.0 / 0.750 (15 models). VerdictPal aggregates 20
  // rows with 88.7% top, different normalization; cited separately.
  { model: 'Qwen3.7 Max', provider: 'Alibaba', score: 75.0, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-09-02', source: 'BenchLM / llm-stats', sourceUrl: 'https://benchlm.ai/benchmarks/bfcl-v4' },
  { model: 'GLM 4.6', provider: 'Z.ai', score: 72.4, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-04-12', source: 'ModelCap (Berkeley official)', sourceUrl: 'https://modelcap.ai/benchmarks/bfcl' },
  { model: 'BTL-4', provider: 'Bad Theory Labs', score: 73.5, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-09-02', source: 'BenchLM', sourceUrl: 'https://benchlm.ai/benchmarks/bfcl-v4' },
  { model: 'Ling 3.0 Flash', provider: 'InclusionAI', score: 73.0, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-09-02', source: 'BenchLM', sourceUrl: 'https://benchlm.ai/benchmarks/bfcl-v4' },
  { model: 'Qwen3.7 Plus', provider: 'Alibaba', score: 72.9, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-09-02', source: 'BenchLM / llm-stats', sourceUrl: 'https://benchlm.ai/benchmarks/bfcl-v4' },
  { model: 'o3', provider: 'OpenAI', score: 63.1, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-04-12', source: 'ModelCap (Berkeley)', sourceUrl: 'https://modelcap.ai/benchmarks/bfcl' },
  { model: 'Gemini 2.5 Flash', provider: 'Google', score: 56.2, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-04-12', source: 'ModelCap (Berkeley)', sourceUrl: 'https://modelcap.ai/benchmarks/bfcl' },
  { model: 'Claude Sonnet 4.6', provider: 'Anthropic', score: 88.7, benchmark: 'BFCL V4', category: 'Tool-calling', date: '2026-04-15', source: 'VerdictPal (aggregated)', sourceUrl: 'https://verdictpal.com/benchmarks/bfcl', note: 'VerdictPal re-normalizes; compare only within source' },

  // -------- LiveBench (overall mean of 7 category averages, 2026-06-25) --------
  { model: 'Claude Fable 5.1 Max Effort', provider: 'Anthropic', score: 83.4, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai / BenchLM', sourceUrl: 'https://livebench.ai' },
  { model: 'Claude Fable 5 Max Effort', provider: 'Anthropic', score: 83.0, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai', sourceUrl: 'https://livebench.ai' },
  { model: 'GPT-5.6 Sol Max Effort', provider: 'OpenAI', score: 81.1, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai / BenchLM', sourceUrl: 'https://benchlm.ai/benchmarks/livebench' },
  { model: 'GPT-5.5 Thinking xHigh', provider: 'OpenAI', score: 80.2, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai', sourceUrl: 'https://livebench.ai' },
  { model: 'Claude Opus 5 Max Effort', provider: 'Anthropic', score: 80.1, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai', sourceUrl: 'https://livebench.ai' },
  { model: 'Kimi K3', provider: 'Moonshot', score: 79.2, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai', sourceUrl: 'https://livebench.ai' },
  { model: 'Gemini 3.7 Flash High', provider: 'Google', score: 78.8, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai', sourceUrl: 'https://livebench.ai' },
  { model: 'Qwen3.8 Max', provider: 'Alibaba', score: 78.5, benchmark: 'LiveBench', category: 'Composite', date: '2026-06-25', source: 'livebench.ai', sourceUrl: 'https://livebench.ai' },
]

const CATEGORIES = ['All', 'Code', 'Knowledge', 'Instruction', 'Tool-calling', 'Composite'] as const

function getAccuracyColor(score: number, benchmark: string) {
  // BigCodeBench is out of ~46 top, so scale differently
  if (benchmark.startsWith('BigCodeBench')) {
    if (score >= 40) return 'text-success'
    if (score >= 30) return 'text-warning'
    return 'text-danger'
  }
  if (score >= 90) return 'text-success'
  if (score >= 75) return 'text-warning'
  return 'text-danger'
}

function getRankBadge(rank: number) {
  if (rank === 1) return 'warning'
  if (rank === 2) return 'secondary'
  if (rank === 3) return 'accent'
  return 'outline'
}

export default function LeaderboardPage() {
  const [activeCategory, setActiveCategory] = useState<(typeof CATEGORIES)[number]>('All')
  const [activeBenchmark, setActiveBenchmark] = useState<string>('All')

  const benchmarksInCategory =
    activeCategory === 'All'
      ? Array.from(new Set(LEADERBOARD.map(r => r.benchmark))).sort()
      : Array.from(new Set(LEADERBOARD.filter(r => r.category === activeCategory).map(r => r.benchmark))).sort()

  const filtered =
    activeCategory === 'All' && activeBenchmark === 'All'
      ? LEADERBOARD
      : LEADERBOARD.filter(r => (activeCategory === 'All' || r.category === activeCategory) && (activeBenchmark === 'All' || r.benchmark === activeBenchmark))

  const sorted = [...filtered].sort((a, b) => b.score - a.score)

  return (
    <section className="section-padding pt-24 md:pt-28 pb-16">
      <div className="container-wide">
        <div className="mb-8">
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">
            <GradientText as="span">Leaderboard</GradientText>
          </h1>
          <p className="text-lg text-muted-fg max-w-3xl mt-3">
            Real scores from public leaderboards as of <strong className="text-foreground">Aug 30 to Sep 2, 2026</strong>. Every row links to its source. Researched 2026-09-03.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 px-3 py-1 text-xs font-medium text-amber-300">
              <Info className="w-3.5 h-3.5" /> HumanEval is saturated (&gt;95% for frontier). Use BigCodeBench / LiveCodeBench to separate models.
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => { setActiveCategory(cat); setActiveBenchmark('All') }}
              className={`px-3.5 py-1.5 rounded-full text-xs font-medium border transition-colors ${activeCategory === cat ? 'bg-foreground text-background border-foreground' : 'bg-card border-border text-muted-fg hover:text-foreground hover:border-border-strong'}`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => setActiveBenchmark('All')}
            className={`px-3 py-1 rounded-full text-xs font-medium border ${activeBenchmark === 'All' ? 'bg-primary text-white border-primary' : 'bg-card border-border text-muted-fg hover:text-foreground'}`}
          >
            All benchmarks
          </button>
          {benchmarksInCategory.map(b => (
            <button
              key={b}
              onClick={() => setActiveBenchmark(b)}
              className={`px-3 py-1 rounded-full text-xs font-medium border ${activeBenchmark === b ? 'bg-primary text-white border-primary' : 'bg-card border-border text-muted-fg hover:text-foreground'}`}
            >
              {b}
            </button>
          ))}
        </div>

        <div className="text-xs text-muted-fg mb-3">Showing {sorted.length} rows{activeCategory !== 'All' ? ` · ${activeCategory}` : ''}{activeBenchmark !== 'All' ? ` · ${activeBenchmark}` : ''}</div>

        <Card variant="glass" className="mb-8 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-white/[0.02]">
                  <th className="text-left py-3 px-3 text-muted-fg font-medium w-14">#</th>
                  <th className="text-left py-3 px-3 text-muted-fg font-medium">Model</th>
                  <th className="text-left py-3 px-3 text-muted-fg font-medium hidden sm:table-cell">Provider</th>
                  <th className="text-right py-3 px-3 text-muted-fg font-medium">Score</th>
                  <th className="text-left py-3 px-3 text-muted-fg font-medium hidden md:table-cell">Benchmark</th>
                  <th className="text-left py-3 px-3 text-muted-fg font-medium hidden lg:table-cell">Source</th>
                  <th className="text-right py-3 px-3 text-muted-fg font-medium hidden lg:table-cell">Date</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((entry, i) => (
                  <tr key={`${entry.model}-${entry.benchmark}-${entry.date}`} className="border-b border-border last:border-0 hover:bg-white/[0.02] transition-colors">
                    <td className="py-3.5 px-3">
                      <Badge variant={getRankBadge(i + 1) as any} className="font-mono text-xs">{i + 1}</Badge>
                    </td>
                    <td className="py-3.5 px-3">
                      <p className="font-medium text-foreground leading-tight">{entry.model}</p>
                      {entry.note && <p className="text-xs text-muted-fg mt-0.5">{entry.note}</p>}
                    </td>
                    <td className="py-3.5 px-3 text-muted-fg hidden sm:table-cell">{entry.provider}</td>
                    <td className="py-3.5 px-3 text-right">
                      <span className={`font-semibold font-mono ${getAccuracyColor(entry.score, entry.benchmark)}`}>{entry.score.toFixed(entry.score >= 10 ? 1 : 2)}%</span>
                    </td>
                    <td className="py-3.5 px-3 hidden md:table-cell">
                      <Badge variant="primary" className="text-xs">{entry.benchmark}</Badge>
                    </td>
                    <td className="py-3.5 px-3 hidden lg:table-cell">
                      <a href={entry.sourceUrl} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1 text-xs">
                        {entry.source} <ExternalLink className="w-3 h-3" />
                      </a>
                    </td>
                    <td className="py-3.5 px-3 text-right text-xs text-muted-fg hidden lg:table-cell whitespace-nowrap">{entry.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card variant="glass" className="p-6 mb-8">
          <h3 className="font-semibold mb-3 text-sm uppercase tracking-wider text-muted-fg">Methodology & caveats</h3>
          <ul className="text-sm text-muted-fg leading-relaxed space-y-2 list-disc list-inside">
            <li><strong className="text-foreground">Dates matter:</strong> snapshots are Aug 22 to Sep 2, 2026. Live leaderboards move weekly. Click a Source link to see the current top.</li>
            <li><strong className="text-foreground">HumanEval is saturated:</strong> ~12 frontier models now &gt;95% pass@1 (presenc.ai June 2026). Differences &lt;2pp are noise. Prefer BigCodeBench / LiveCodeBench / SWE-bench for code.</li>
            <li><strong className="text-foreground">BigCodeBench:</strong> Granite-4.0-H-Small 46.2% is top on the aggregated pass@1 board (GenAIList). BenchLM&apos;s 59.2% DeepSeek view is a 2-model mirror, not the full leaderboard.</li>
            <li><strong className="text-foreground">BFCL V4:</strong> official Berkeley board updated 2026-04-12 (83 entries). ModelCap tracks 31; BenchLM/llm-stats mirror 15. VerdictPal&apos;s 88.7% uses a different normalization, so compare only within source.</li>
            <li><strong className="text-foreground">IFEval / MMLU-Pro / LiveBench:</strong> tightly clustered at the top (for example, IFEval 90.2 to 95.0% across about 13 models). All listed scores are prompt-level strict or calibrated pass@1 as appropriate.</li>
          </ul>
          <div className="flex flex-wrap gap-3 text-xs mt-4">
            <a href="https://gorilla.cs.berkeley.edu/leaderboard.html" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1">Berkeley BFCL Official <ExternalLink className="w-3 h-3" /></a>
            <a href="https://livebench.ai" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1">LiveBench Official <ExternalLink className="w-3 h-3" /></a>
            <a href="https://bigcode-bench.github.io/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1">BigCodeBench Official <ExternalLink className="w-3 h-3" /></a>
            <a href="https://llm-stats.com/benchmarks/ifeval" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1">llm-stats IFEval <ExternalLink className="w-3 h-3" /></a>
            <a href="https://sophon.at/evals/mmlu-pro" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1">Sophon MMLU-Pro <ExternalLink className="w-3 h-3" /></a>
          </div>
        </Card>

        <Card variant="glow" className="p-8 text-center">
          <CardContent className="p-0">
            <h3 className="text-xl font-bold tracking-tight">Run your own benchmarks</h3>
            <p className="text-muted-fg mt-2 max-w-lg mx-auto">
              Reproduce any of these 30 benchmarks locally with nothing needed beyond your model. Compare your results with one table.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-6">
              <Link href="/docs/getting-started/" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold bg-foreground text-background hover:bg-white transition-colors">Get Started</Link>
              <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium border border-border text-muted-fg hover:text-foreground hover:bg-white/[0.06]">View on GitHub</a>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
