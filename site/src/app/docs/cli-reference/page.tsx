import type { Metadata } from 'next'
import GradientText from '@/components/shared/GradientText'
import Badge from '@/components/shared/Badge'
import { commandCategories } from '@/lib/commands-data'

export const metadata: Metadata = {
  title: 'CLI Reference',
  description: 'CLI reference for BenchMax: 38 commands covering every REST endpoint, with --json and --wait support.',
}

export default function CliReferencePage() {
  const totalCommands = commandCategories.reduce((sum, cat) => sum + cat.commands.length, 0)
  return (
    <div>
      <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4"><GradientText as="span">CLI Reference</GradientText></h1>
      <p className="text-lg text-muted-fg max-w-2xl">{totalCommands} commands: every REST endpoint is a CLI command. Add <code className="text-primary">--json</code> for machine output, <code className="text-primary">--wait</code> to block until done.</p>
      <div className="rounded-xl bg-card border border-border p-4 mt-6 mb-8">
        <p className="text-sm text-muted-fg">
          <span className="font-semibold text-foreground">Usage:</span> <code className="font-mono text-foreground">py cli.py &lt;command&gt; [options]</code>
          {' · '}<code className="text-primary">BENCHMAX_URL</code> env or <code className="text-primary">py cli.py connect</code> configures the server address. Server auto-starts if not running.
        </p>
      </div>
      <div className="space-y-10">
        {commandCategories.map(cat => (
          <section key={cat.name}>
            <h2 className="text-xl font-bold tracking-tight">{cat.name}</h2>
            <p className="text-sm text-muted-fg mb-3">{cat.commands.length} command{cat.commands.length !== 1 ? 's' : ''}</p>
            <div className="space-y-3">
              {cat.commands.map(cmd => (
                <div key={cmd.name} className="rounded-xl border border-border bg-card p-4 hover:border-primary/15 transition-colors">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant="primary" className="font-mono text-xs">{cmd.name}</Badge>
                  </div>
                  <p className="text-sm text-muted-fg mb-2 leading-relaxed">{cmd.description}</p>
                  <div className="rounded-lg bg-background border border-border px-3 py-2 font-mono text-xs text-muted-fg overflow-x-auto">$ {cmd.example}</div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
