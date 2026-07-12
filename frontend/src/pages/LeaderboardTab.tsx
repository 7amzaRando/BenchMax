import { useState, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CopyButton } from '@/components/ui/copy-button'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import * as api from '@/lib/api'

function Medal({ rank }: { rank: number }) {
  if (rank === 1) return <span className="font-mono text-sm w-8 inline-block text-center font-bold text-yellow-400">1st</span>
  if (rank === 2) return <span className="font-mono text-sm w-8 inline-block text-center font-bold text-gray-400">2nd</span>
  if (rank === 3) return <span className="font-mono text-sm w-8 inline-block text-center font-bold text-orange-400">3rd</span>
  return <span className="font-mono text-sm w-8 inline-block text-center">{rank}</span>
}

const COLS: { key: keyof api.LeaderboardEntry; label: string; sortable: boolean }[] = [
  { key: 'Run ID', label: 'Run ID', sortable: true },
  { key: 'Model', label: 'Model', sortable: true },
  { key: 'Benchmark', label: 'Benchmark', sortable: true },
  { key: 'Accuracy', label: 'Accuracy', sortable: true },
  { key: 'Avg TPS', label: 'Avg TPS', sortable: true },
  { key: 'Avg TTFT', label: 'Avg TTFT', sortable: true },
  { key: 'Passed', label: 'Passed', sortable: true },
  { key: 'Tokens', label: 'Tokens', sortable: true },
  { key: 'Date', label: 'Date', sortable: true },
]

export default function LeaderboardTab({ onDelete }: { onDelete?: () => void }) {
  const [entries, setEntries] = useState<api.LeaderboardEntry[]>([])
  const [sortCol, setSortCol] = useState<keyof api.LeaderboardEntry>('Accuracy')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [filter, setFilter] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [keySaved, setKeySaved] = useState(false)
  const [syncStatus, setSyncStatus] = useState('')
  const [exportFormat, setExportFormat] = useState<'CSV' | 'JSON'>('CSV')
  const [showTrend, setShowTrend] = useState(false)
  const [trendModel, setTrendModel] = useState('')
  const [trendBenchmark, setTrendBenchmark] = useState('')
  const [hideQuickTests, setHideQuickTests] = useState(false)

  useEffect(() => {
    loadLeaderboard()
    api.getLeaderboardSettings().then(d => {
      if (d.api_key && !localStorage.getItem('lbApiKey')) {
        localStorage.setItem('lbApiKey', d.api_key)
        setKeySaved(true)
        setApiKey(d.api_key)
      }
    }).catch(() => console.warn('Failed to load API key'))
  }, [])

  async function loadLeaderboard() {
    try {
      const data = await api.loadLeaderboard()
      setEntries(data.leaderboard || [])
    } catch { console.warn('Failed to load leaderboard') }
  }

  // Filter entries by Run ID, Model name, or Benchmark name (case-insensitive)
  const filtered = useMemo(() => {
    if (!filter.trim()) return entries
    const q = filter.toLowerCase()
    return entries.filter(e =>
      String(e['Run ID']).includes(q) ||
      (e.Model || '').toLowerCase().includes(q) ||
      (e.Benchmark || '').toLowerCase().includes(q)
    )
  }, [entries, filter])

  // Sort entries by active column — numeric columns parse floats, Date column compares timestamps, strings use localeCompare
  const sorted = useMemo(() => {
    const s = [...filtered].sort((a, b) => {
      const va = a[sortCol] ?? ''
      const vb = b[sortCol] ?? ''
      if (sortCol === 'Date') {
        const da = new Date(String(va)).getTime()
        const db = new Date(String(vb)).getTime()
        if (!isNaN(da) && !isNaN(db)) return sortDir === 'asc' ? da - db : db - da
      }
      const na = parseFloat(String(va).replace(/[^0-9.-]/g, ''))
      const nb = parseFloat(String(vb).replace(/[^0-9.-]/g, ''))
      const cmp = !isNaN(na) && !isNaN(nb) ? na - nb : String(va).localeCompare(String(vb))
      return sortDir === 'asc' ? cmp : -cmp
    })
    return s
  }, [filtered, sortCol, sortDir])

  /** Cycles sort state: same column toggles asc/desc, new column sets desc by default. */
  function toggleSort(col: keyof api.LeaderboardEntry) {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('desc') }
  }

  async function handleDelete(runId: number) {
    try {
      const data = await api.deleteLeaderboardEntry(runId)
      setEntries(data.leaderboard || [])
      onDelete?.()
    } catch { console.warn('Failed to delete leaderboard entry') }
  }

  /** Persists the leaderboard API key to localStorage and server settings. */
  async function handleSaveKey() {
    if (!apiKey.trim()) return
    try {
      localStorage.setItem('lbApiKey', apiKey)
      const data = await api.saveLeaderboardSettings(apiKey)
      setSyncStatus(data.status)
      setKeySaved(true)
    } catch (e: any) { setSyncStatus(e.message) }
  }

  /** Syncs completed runs to the online Supabase leaderboard via the stored API key. */
  async function handleSync() {
    if (!apiKey.trim()) {
      setSyncStatus('❌ Enter your leaderboard API key first (contact the project author).')
      return
    }
    const key = apiKey || localStorage.getItem('lbApiKey') || ''
    try {
      localStorage.setItem('lbApiKey', key)
      const data = await api.syncLeaderboard(key)
      setSyncStatus(data.status)
    } catch (e: any) { setSyncStatus(e.message) }
  }

  function handleExportLB() {
    const data = exportFormat === 'CSV'
      ? 'Run ID,Model,Benchmark,Accuracy,Avg TPS,Avg TTFT,Passed,Tokens,Date\n' + sorted.map(e =>
          `"${e['Run ID']}","${e.Model}","${e.Benchmark}","${e.Accuracy}","${e['Avg TPS']}","${e['Avg TTFT']}","${e.Passed}","${e.Tokens}","${e.Date}"`
        ).join('\n')
      : JSON.stringify(sorted, null, 2)
    const blob = new Blob([data], { type: exportFormat === 'CSV' ? 'text/csv' : 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `leaderboard.${exportFormat.toLowerCase()}`
    a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4 flex-wrap">
        <h2 className="text-lg font-semibold">Leaderboard</h2>
        <Button variant="outline" size="sm" onClick={loadLeaderboard}>Refresh</Button>
        <Button variant={showTrend ? 'default' : 'outline'} size="sm" onClick={() => setShowTrend(!showTrend)}>
          {showTrend ? 'Hide Trend' : 'Trend'}
        </Button>
        <div className="flex items-center gap-2 ml-auto">
          <Input placeholder="Filter by model, benchmark, or ID..." value={filter} onChange={e => setFilter(e.target.value)} className="h-8 text-xs min-w-[200px]" />
          <select className="h-8 text-xs rounded-md border border-border bg-card px-2" value={exportFormat} onChange={e => setExportFormat(e.target.value as 'CSV' | 'JSON')}>
            <option value="CSV">CSV</option>
            <option value="JSON">JSON</option>
          </select>
          <Button variant="outline" size="sm" onClick={handleExportLB}>Export</Button>
        </div>
        <span className="text-xs text-muted-foreground">{sorted.length} of {entries.length}</span>
      </div>

      {showTrend && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              Performance Trend
              <select className="ml-2 h-7 text-xs rounded-md border border-border bg-card px-2" value={trendModel} onChange={e => setTrendModel(e.target.value)}>
                <option value="">Select model...</option>
                {[...new Set(entries.map(e => e.Model))].map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <select className="ml-2 h-7 text-xs rounded-md border border-border bg-card px-2" value={trendBenchmark} onChange={e => setTrendBenchmark(e.target.value)}>
                <option value="">All benchmarks</option>
                {[...new Set(entries.map(e => e.Benchmark))].map(b => <option key={b} value={b}>{b}</option>)}
              </select>
              <label className="flex items-center gap-1 text-xs ml-2 cursor-pointer select-none">
                <input type="checkbox" className="accent-primary" checked={hideQuickTests} onChange={e => setHideQuickTests(e.target.checked)} />
                Hide Quick Tests
              </label>
            </CardTitle>
          </CardHeader>
          <CardContent className={trendBenchmark && !trendModel ? 'h-48' : 'h-64'}>
            {trendModel ? (() => {
              const filtered = [...entries]
                .filter(e => {
                  if (trendModel && e.Model !== trendModel) return false
                  if (trendBenchmark && e.Benchmark !== trendBenchmark) return false
                  if (hideQuickTests && e.QuickTest) return false
                  return e.Date
                })
                .sort((a, b) => new Date(a.Date).getTime() - new Date(b.Date).getTime())
              if (filtered.length < 2) return <div className="text-sm text-muted-foreground text-center pt-8">Need at least 2 runs for a trend</div>
              const chartData = filtered.map(e => ({
                ...e,
                AccuracyNum: parseFloat(String(e.Accuracy).replace(/[^0-9.-]/g, ''))
              }))
              return (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                    <XAxis dataKey="Date" stroke="var(--chart-axis)" fontSize={11} />
                    <YAxis stroke="var(--chart-axis)" domain={[0, 100]} />
                    <Tooltip />
                    <Line type="monotone" dataKey="AccuracyNum" name="Accuracy %" stroke="#3B82F6" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              )
            })() : trendBenchmark ? (() => {
              const benchModels = [...new Set(entries
                .filter(e => e.Benchmark === trendBenchmark && e.Date && (!hideQuickTests || !e.QuickTest))
                .map(e => e.Model))]
              if (!benchModels.length) return <div className="text-sm text-muted-foreground text-center pt-8">No data for this benchmark</div>
              const grouped: Record<string, number[]> = {}
              entries.filter(e => e.Benchmark === trendBenchmark && e.Date && (!hideQuickTests || !e.QuickTest)).forEach(e => {
                const acc = parseFloat(String(e.Accuracy).replace(/[^0-9.-]/g, ''))
                if (!isNaN(acc)) {
                  if (!grouped[e.Model]) grouped[e.Model] = []
                  grouped[e.Model].push(acc)
                }
              })
              const barData = Object.entries(grouped).map(([model, vals]) => ({
                Model: model,
                AccuracyNum: Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10
              }))
              return (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                    <XAxis dataKey="Model" stroke="var(--chart-axis)" fontSize={11} />
                    <YAxis stroke="var(--chart-axis)" domain={[0, 100]} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="AccuracyNum" name="Accuracy %" fill="#8B5CF6" />
                  </BarChart>
                </ResponsiveContainer>
              )
            })() : <div className="text-sm text-muted-foreground text-center pt-8">Select a model to view accuracy trend over time, or select a benchmark to compare models</div>}
          </CardContent>
        </Card>
      )}

      <Card variant="glass">
        <CardContent className="p-0 overflow-auto max-h-[600px]">
          <table className="w-full text-sm">
            <thead className="bg-muted sticky top-0">
              <tr>
                <th className="p-2 text-left w-12">Rank</th>
                {COLS.map(c => (
                  <th key={c.key} className={`p-2 text-left ${c.sortable ? 'cursor-pointer select-none hover:text-primary' : ''}`} onClick={() => c.sortable && toggleSort(c.key)}>
                    {c.label}
                    {c.sortable && sortCol === c.key && <span className="ml-1 text-primary">{sortDir === 'asc' ? '▲' : '▼'}</span>}
                  </th>
                ))}
                <th className="p-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((e, i) => (
                <tr key={e['Run ID']} className={`border-t border-border ${i === 0 ? 'bg-yellow-900/20' : i === 1 ? 'bg-gray-400/20' : i === 2 ? 'bg-orange-900/20' : ''}`}>
                  <td className="p-2"><Medal rank={i + 1} /></td>
                  <td className="p-2 font-mono text-xs">{e['Run ID']}</td>
                  <td className="p-2">{e.Model} <CopyButton value={e.Model} /></td>
                  <td className="p-2">{e.Benchmark}</td>
                  <td className="p-2"><Badge variant={parseFloat(e.Accuracy) >= 80 ? 'default' : parseFloat(e.Accuracy) >= 50 ? 'secondary' : 'destructive'}>{e.Accuracy}</Badge></td>
                  <td className="p-2">{e['Avg TPS']}</td>
                  <td className="p-2">{e['Avg TTFT']}</td>
                  <td className="p-2">{e.Passed}</td>
                  <td className="p-2">{e.Tokens}</td>
                  <td className="p-2 text-xs">{e.Date}</td>
                  <td className="p-2">
                    <Button variant="destructive" size="sm" onClick={() => handleDelete(e['Run ID'])}>Delete</Button>
                  </td>
                </tr>
              ))}
              {!sorted.length && (
                <tr><td colSpan={12} className="p-4 text-center text-muted-foreground">{filter ? 'No runs match filter' : 'No completed runs yet'}</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card variant="glow">
        <CardHeader><CardTitle>Online Sync</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <div className="flex-1">
              <Input
                type="password"
                placeholder="Leaderboard API Key"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
              />
            </div>
            <Button variant="outline" onClick={handleSaveKey}>Save Key</Button>
            <Button onClick={handleSync} disabled={!apiKey.trim()}>{!apiKey.trim() ? 'Enter key, then click Save' : 'Sync to Online'}</Button>
          </div>
          {syncStatus && (
            <div className={`text-sm px-3 py-2 rounded-md border ${syncStatus.includes('Error') || syncStatus.includes('failed') || syncStatus.includes('❌') || syncStatus.includes('first') || syncStatus.includes('enter') || syncStatus.includes('Synced 0/') ? 'bg-red-900/30 text-red-300 border-red-800 dark:text-red-300 text-red-700 dark:border-red-800 border-red-300' : syncStatus.includes('✅') ? 'bg-green-900/30 text-green-300 border-green-800 dark:text-green-300 text-green-700 dark:border-green-800 border-green-300' : 'bg-muted text-muted-foreground'}`}>
              {syncStatus}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
