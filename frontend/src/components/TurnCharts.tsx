import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface TurnEntry {
  turn: number
  role: string
  content: string
  tps?: number
  ttft?: number
  thinking_tokens?: number
  response_tokens?: number
  prompt_tokens?: number
  elapsed_time?: number
}

export function TurnCharts({ turns }: { turns: TurnEntry[] }) {
  const assistantTurns = turns.filter(t => t.role === 'assistant' && t.turn >= 0)
  if (assistantTurns.length <= 1) return null

  const tpsData = assistantTurns.map(t => ({
    Turn: `T${t.turn + 1}`,
    TPS: t.tps ?? 0,
    Tokens: (t.response_tokens ?? 0) + (t.thinking_tokens ?? 0),
  }))

  const ttftData = assistantTurns.map(t => ({
    Turn: `T${t.turn + 1}`,
    TTFT: t.ttft ?? 0,
  }))

  return (
    <div className="grid grid-cols-2 gap-4">
      <Card>
        <CardHeader><CardTitle className="text-sm">Per-Turn TPS</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={tpsData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis dataKey="Turn" stroke="var(--chart-axis)" />
              <YAxis stroke="var(--chart-axis)" />
              <Tooltip />
              <Bar dataKey="TPS" fill="var(--chart-tps)" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-sm">Per-Turn TTFT</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={ttftData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis dataKey="Turn" stroke="var(--chart-axis)" />
              <YAxis stroke="var(--chart-axis)" />
              <Tooltip />
              <Bar dataKey="TTFT" fill="var(--chart-ttft)" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}

export function ConversationViewer({ turns }: { turns: TurnEntry[] }) {
  if (!turns || turns.length === 0) return null

  // Filter out seeded -1 turns for display count, but show if present
  const displayTurns = turns

  return (
    <div className="space-y-2 max-h-[500px] overflow-auto p-1">
      {displayTurns.map((t, i) => {
        const isUser = t.role === 'user'
        const isAssistant = t.role === 'assistant'
        const isTool = t.role === 'tool'
        const bg = isUser ? 'bg-blue-500/10 border-blue-500/30' : isTool ? 'bg-amber-500/10 border-amber-500/30' : 'bg-green-500/10 border-green-500/30'
        const badge = isUser ? 'User' : isTool ? `Tool${t.tool ? ` · ${t.tool}` : ''}` : `Assistant${t.turn >= 0 ? ` · T${t.turn + 1}` : ''}`
        const badgeColor = isUser ? 'text-blue-400' : isTool ? 'text-amber-400' : 'text-green-400'
        return (
          <div key={i} className={`rounded-lg border p-3 ${bg}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-medium ${badgeColor}`}>{badge}</span>
              {isAssistant && t.tps !== undefined && (
                <span className="text-[10px] text-muted-foreground font-mono">{t.tps?.toFixed(1)} t/s · {t.ttft?.toFixed(2)}s · {(t.response_tokens ?? 0) + (t.thinking_tokens ?? 0)} tok</span>
              )}
            </div>
            <div className="text-sm whitespace-pre-wrap break-words font-mono text-xs leading-relaxed max-h-48 overflow-auto">
              {t.content.length > 4000 ? t.content.slice(0, 4000) + '…' : t.content}
            </div>
          </div>
        )
      })}
    </div>
  )
}
