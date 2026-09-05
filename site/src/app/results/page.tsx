import type { Metadata } from 'next'
import GradientText from '@/components/shared/GradientText'
import Card, { CardTitle, CardDescription, CardContent } from '@/components/shared/Card'
import Badge from '@/components/shared/Badge'

export const metadata: Metadata = {
  title: 'Results',
  description: 'Example benchmark comparison and metric explainers for BenchMax.',
}

const EXAMPLE_RUNS = [
  {
    model: 'DeepSeek-R1-Distill-Qwen-7B',
    benchmark: 'HumanEval',
    accuracy: 82.3,
    avgTps: 45.2,
    avgTtft: 0.82,
    totalTokens: 128400,
    status: 'completed' as const,
  },
  {
    model: 'Qwen-2.5-Coder-7B-Instruct',
    benchmark: 'HumanEval',
    accuracy: 79.8,
    avgTps: 52.1,
    avgTtft: 0.65,
    totalTokens: 115200,
    status: 'completed' as const,
  },
  {
    model: 'Llama-3.1-8B-Instruct',
    benchmark: 'HumanEval',
    accuracy: 68.1,
    avgTps: 38.7,
    avgTtft: 1.12,
    totalTokens: 142000,
    status: 'completed' as const,
  },
]

const METRICS = [
  {
    name: 'Accuracy',
    description: 'Share of questions the model gets right. For coding tests, that means the written code passes all hidden tests.',
    range: '0% to 100%',
  },
  {
    name: 'TTFT (Time to First Token)',
    description: 'How long the model takes to start responding. Lower is better, and it is what makes a model feel snappy.',
    range: '0.1s to 5s+',
  },
  {
    name: 'TPS (Tokens per Second)',
    description: 'Writing speed: how many words per second the model produces. Higher is better. Depends on model size, hardware, and settings.',
    range: '10 to 100+',
  },
  {
    name: 'Thinking Tokens',
    description: 'Words spent on internal reasoning before answering. Reasoning models think step by step here before giving the final answer.',
    range: '0 to 32K+',
  },
  {
    name: 'Response Tokens',
    description: 'Length of the final answer. Code answers include the written function; quiz answers are usually a single letter.',
    range: '1 to 8K+',
  },
]

function getAccuracyColor(accuracy: number) {
  if (accuracy >= 80) return 'text-success'
  if (accuracy >= 60) return 'text-warning'
  return 'text-danger'
}

export default function ResultsPage() {
  return (
    <section className="section-padding">
      <div className="container-narrow">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            <GradientText as="span">Results</GradientText>
          </h1>
          <p className="text-lg text-muted-fg max-w-2xl">
            Example comparison of three models on the HumanEval benchmark. Run your own benchmarks to see real results.
          </p>
        </div>

        {/* Comparison Table */}
        <div className="mb-16">
          <h2 className="text-2xl font-bold mb-6">Model Comparison</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-muted-fg font-medium">Model</th>
                  <th className="text-left py-3 px-4 text-muted-fg font-medium">Benchmark</th>
                  <th className="text-right py-3 px-4 text-muted-fg font-medium">Accuracy</th>
                  <th className="text-right py-3 px-4 text-muted-fg font-medium">Avg TPS</th>
                  <th className="text-right py-3 px-4 text-muted-fg font-medium">Avg TTFT</th>
                  <th className="text-right py-3 px-4 text-muted-fg font-medium">Tokens</th>
                </tr>
              </thead>
              <tbody>
                {EXAMPLE_RUNS.map((run) => (
                  <tr key={run.model} className="border-b border-border hover:bg-white/[0.02] transition-colors">
                    <td className="py-4 px-4">
                      <p className="font-medium text-foreground">{run.model}</p>
                    </td>
                    <td className="py-4 px-4">
                      <Badge variant="primary">{run.benchmark}</Badge>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span className={`font-semibold ${getAccuracyColor(run.accuracy)}`}>
                        {run.accuracy}%
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right font-mono text-muted-fg">{run.avgTps}</td>
                    <td className="py-4 px-4 text-right font-mono text-muted-fg">{run.avgTtft}s</td>
                    <td className="py-4 px-4 text-right font-mono text-muted-fg">{run.totalTokens.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Metric Explainers */}
        <div>
          <h2 className="text-2xl font-bold mb-6">Understanding the Metrics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {METRICS.map((metric) => (
              <Card key={metric.name} variant="glass" className="p-5">
                <CardContent className="p-0">
                  <div className="flex items-center justify-between mb-2">
                    <CardTitle className="text-base">{metric.name}</CardTitle>
                    <Badge variant="outline" className="text-xs font-mono">{metric.range}</Badge>
                  </div>
                  <CardDescription className="leading-relaxed">
                    {metric.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="mt-16 text-center">
          <Card variant="glow" className="p-8">
            <CardContent className="p-0">
              <h3 className="text-xl font-bold mb-2">Run Your Own Benchmarks</h3>
              <p className="text-muted-fg mb-4">
                Connect to any model and run 30 standardized benchmarks locally.
              </p>
              <a
                href="/docs/getting-started/"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium bg-gradient-to-r from-primary to-secondary text-white hover:shadow-lg hover:shadow-primary/25 transition-all"
              >
                Get Started
              </a>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  )
}
