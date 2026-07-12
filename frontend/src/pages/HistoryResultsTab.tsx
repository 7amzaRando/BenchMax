import { useState, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CopyButton } from '@/components/ui/copy-button'
import * as api from '@/lib/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

export default function HistoryResultsTab({ onRerun, activeTab, historyRefreshKey }: { onRerun?: (model: string, benchmark: string, params: any) => void; activeTab?: string; historyRefreshKey?: number }) {
  const [runs, setRuns] = useState<api.HistoryEntry[]>([])
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
  const [runDetails, setRunDetails] = useState<api.RunDetails | null>(null)
  const [batchId, setBatchId] = useState('')
  const [batchSummary, setBatchSummary] = useState<any>(null)
  const [compareIds, setCompareIds] = useState('')
  const [comparison, setComparison] = useState<any>(null)
  const [clearConfirm, setClearConfirm] = useState('')
  const [diffHtml, setDiffHtml] = useState('')
  const [selectedTask, setSelectedTask] = useState('')
  const [sortColumn, setSortColumn] = useState<string>('Run ID')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [historyFilter, setHistoryFilter] = useState('')
  const [exportFormat, setExportFormat] = useState<'CSV' | 'JSON'>('CSV')
  const sortedRuns = useMemo(() => {
    const sorted = [...runs].sort((a, b) => {
      const va = a[sortColumn as keyof api.HistoryEntry] ?? ''
      const vb = b[sortColumn as keyof api.HistoryEntry] ?? ''
      const numA = parseFloat(String(va).replace(/[^0-9.-]/g, ''))
      const numB = parseFloat(String(vb).replace(/[^0-9.-]/g, ''))
      if (!isNaN(numA) && !isNaN(numB)) return sortDir === 'asc' ? numA - numB : numB - numA
      return sortDir === 'asc'
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va))
    })
    return sorted
  }, [runs, sortColumn, sortDir])

  const filteredRuns = useMemo(() => {
    if (!historyFilter.trim()) return sortedRuns
    const q = historyFilter.toLowerCase()
    return sortedRuns.filter(r => 
      (r.Model || '').toLowerCase().includes(q) ||
      (r.Benchmark || '').toLowerCase().includes(q) ||
      (r.Status || '').toLowerCase().includes(q)
    )
  }, [sortedRuns, historyFilter])

  function handleSort(col: string) {
    if (sortColumn === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortColumn(col); setSortDir('asc') }
  }

  useEffect(() => { loadRuns() }, [])
  useEffect(() => { if (activeTab === 'history') loadRuns() }, [activeTab])
  useEffect(() => { loadRuns() }, [historyRefreshKey])

  async function loadRuns() {
    try { const data = await api.loadHistory(); setRuns(data.runs || []) } catch { console.warn('Failed to load history') }
  }

  const stats = useMemo(() => {
    const total = filteredRuns.length
    const completed = filteredRuns.filter(r => r.Status === 'COMPLETED').length
    const totalTokens = filteredRuns.reduce((sum, r) => sum + (r['Total Tokens'] || 0), 0)
    const benchmarks = [...new Set(filteredRuns.map(r => r.Benchmark))]
    const models = [...new Set(filteredRuns.map(r => r.Model))]
    let bestAcc = 0, bestModel = '—', bestBench = '—'
    for (const r of filteredRuns) {
      const acc = parseFloat((r.Accuracy || '0%').replace(/[^0-9.-]/g, ''))
      if (!isNaN(acc) && acc > bestAcc) { bestAcc = acc; bestModel = r.Model; bestBench = r.Benchmark }
    }
    return {
      total_runs: total,
      completed_runs: completed,
      total_tokens_generated: totalTokens,
      benchmarks_run: benchmarks,
      models_tested: models,
      best_accuracy: { model: bestModel, benchmark: bestBench, accuracy: bestAcc || '—' },
    }
  }, [filteredRuns])

  async function loadDetails(runId: number) {
    setSelectedRunId(runId)
    setDiffHtml('')
    try {
      const data = await api.loadRunDetails(runId)
      setRunDetails(data)
      if (data.failed_tasks?.length) setSelectedTask(data.failed_tasks[0])
    } catch { console.warn('Failed to load run details') }
  }

  async function handleDiff() {
    if (!selectedRunId || !selectedTask) return
    try { const data = await api.getDiff(selectedRunId, selectedTask); setDiffHtml(data.html) } catch { console.warn('Failed to generate diff') }
  }

  async function loadBatch() {
    if (!batchId) return
    try { const data = await api.loadBatchSummary(batchId); setBatchSummary(data) } catch { console.warn('Failed to load batch summary') }
  }

  async function handleCompare() {
    if (!compareIds?.trim()) return
    try { const data = await api.loadComparison(compareIds); setComparison(data) } catch { console.warn('Failed to load comparison') }
  }

  async function handleClear() {
    try { const data = await api.clearAllHistory(clearConfirm); setRuns(data.history || []); setClearConfirm('') } catch { console.warn('Failed to clear history') }
  }

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid grid-cols-6 gap-3">
          <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Runs</div>
            <div className="font-mono text-sm mt-0.5">{stats.total_runs}</div>
          </div>
          <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Completed</div>
            <div className="font-mono text-sm mt-0.5">{stats.completed_runs}</div>
          </div>
          <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Tokens</div>
            <div className="font-mono text-sm mt-0.5">{stats.total_tokens_generated?.toLocaleString() || 0}</div>
          </div>
          <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Benchmarks</div>
            <div className="font-mono text-sm mt-0.5">{(stats.benchmarks_run || []).length}</div>
          </div>
          <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Models</div>
            <div className="font-mono text-sm mt-0.5">{(stats.models_tested || []).length}</div>
          </div>
          <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Best Accuracy</div>
            <div className="font-mono text-sm mt-0.5">{stats.best_accuracy?.accuracy === '—' ? '—' : `${stats.best_accuracy?.accuracy}%`}</div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold">All Runs</h2>
        <Button variant="outline" size="sm" onClick={loadRuns}>Refresh</Button>
        <div className="ml-auto flex gap-2 items-center">
          <select className="h-8 text-xs rounded-md border border-border bg-card px-2" value={exportFormat} onChange={e => setExportFormat(e.target.value as 'CSV' | 'JSON')}>
            <option value="CSV">CSV</option>
            <option value="JSON">JSON</option>
          </select>
          <Button variant="outline" size="sm" asChild>
            <a href={`/api/export/history?format=${exportFormat}`} download>Export All</a>
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Input placeholder="Filter by model, benchmark, or status..." value={historyFilter} onChange={e => setHistoryFilter(e.target.value)} className="h-8 text-xs max-w-xs" />
        <span className="text-xs text-muted-foreground">{filteredRuns.length}/{runs.length} runs</span>
      </div>

      <Card variant="glass">
        <CardContent className="p-0 overflow-auto max-h-72">
          <table className="w-full text-sm">
            <thead className="bg-muted sticky top-0">
              <tr>
                {['Run ID', 'Model', 'Benchmark', 'Status', 'Progress', 'Accuracy', 'Avg TPS', 'Avg TTFT', 'Avg Tokens', 'Duration', 'Batch', 'Created', 'Actions'].map(col => (
                  <th key={col} className="p-2 text-left cursor-pointer select-none hover:text-primary transition-colors" onClick={() => handleSort(col)}>
                    {col}{sortColumn === col && <span className="ml-1 text-primary">{sortDir === 'asc' ? '▲' : '▼'}</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map(r => (
                <tr key={r['Run ID']} className={`border-t border-border cursor-pointer hover:bg-primary/15 ${selectedRunId === r['Run ID'] ? 'bg-primary/20 border-primary/30' : ''}`} onClick={() => loadDetails(r['Run ID'])}>
                  <td className="p-2 font-mono text-xs"><span className="flex items-center gap-1"><CopyButton value={String(r['Run ID'])} />{r['Run ID']}</span></td>
                  <td className="p-2"><span className="flex items-center gap-1"><CopyButton value={r.Model} />{r.Model}</span></td>
                  <td className="p-2">{r.Benchmark}</td>
                  <td className="p-2"><Badge variant={r.Status === 'COMPLETED' ? 'default' : r.Status === 'ERROR' || r.Status === 'FAILED' ? 'destructive' : 'warning'}>{r.Status}</Badge></td>
                  <td className="p-2">{r.Progress}</td>
                  <td className="p-2">{r.Accuracy}</td>
                  <td className="p-2">{r['Avg TPS']}</td>
                  <td className="p-2">{r['Avg TTFT']}</td>
                  <td className="p-2">{r['Avg Tokens']}</td>
                  <td className="p-2 text-xs">{r.Duration || '—'}</td>
                  <td className="p-2 text-xs font-mono">{r.Batch ? (r.Batch.length > 8 ? r.Batch.slice(0, 8) + '…' : r.Batch) : '—'}</td>
                  <td className="p-2 text-xs">{r.Created}</td>
                  <td className="p-2"><Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); onRerun?.(r.Model, r.Benchmark, {}) }}>Re-run</Button></td>
                </tr>
              ))}
              {!filteredRuns.length && <tr><td colSpan={13} className="p-4 text-center text-muted-foreground">No runs found</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Renders when a history row is clicked to inspect details */}
      {runDetails && (
        <div className="space-y-4">
          <Card variant="glow">
            <CardHeader><CardTitle>Run #{selectedRunId}</CardTitle></CardHeader>
            <CardContent>
              <div className="text-sm whitespace-pre-wrap mb-4" dangerouslySetInnerHTML={{ __html: runDetails.summary }} />
              <div className="flex gap-2 mb-4">
                <select className="h-8 text-xs rounded-md border border-border bg-card px-2" value={exportFormat} onChange={e => setExportFormat(e.target.value as 'CSV' | 'JSON')}>
                  <option value="CSV">CSV</option>
                  <option value="JSON">JSON</option>
                </select>
                <Button variant="outline" size="sm" asChild>
                  <a href={`/api/export/runs/${selectedRunId}?format=${exportFormat}`} download>Export {exportFormat}</a>
                </Button>
              </div>
              <div className="overflow-auto max-h-80 mb-4">
                <table className="w-full text-sm">
                  <thead className="bg-muted sticky top-0">
                    <tr><th className="p-2 text-left">Task</th><th className="p-2 text-left">Result</th><th className="p-2 text-left">TTFT</th><th className="p-2 text-left">TPS</th><th className="p-2 text-left">Elapsed</th><th className="p-2 text-left">Error</th></tr>
                  </thead>
                  <tbody>
                    {runDetails.samples.map((s: any, i: number) => (
                      <tr key={i} className="border-t border-border">
                        <td className="p-2 font-mono text-xs">{s.Task || s.task_id}</td>
                        <td className="p-2">{s.Correct === '✅' ? '✅' : '❌'}</td>
                        <td className="p-2">{s['TTFT (s)'] || s.ttft || '—'}</td>
                        <td className="p-2">{s.TPS || s.tps || '—'}</td>
                        <td className="p-2">{s.Elapsed || s.elapsed_time || '—'}</td>
                        <td className="p-2 text-xs text-muted-foreground">{s.Error || s.error_message || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {runDetails.failed_tasks?.length > 0 && (
                <div className="flex gap-2 items-end mb-4">
                  <div className="flex-1">
                    <label className="text-xs text-muted-foreground mb-1 block">Failed Task</label>
                    <select className="w-full p-2 rounded-md border border-border bg-card" value={selectedTask} onChange={e => setSelectedTask(e.target.value)}>
                      {runDetails.failed_tasks.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <Button size="sm" onClick={handleDiff}>Generate Diff</Button>
                </div>
              )}
              {diffHtml && <div className="border border-border rounded-md p-4 overflow-auto max-h-96 text-xs" dangerouslySetInnerHTML={{ __html: diffHtml }} />}
              <div className="grid grid-cols-2 gap-4 mt-4">
                {runDetails.token_chart?.length > 0 && (
                  <Card><CardHeader><CardTitle className="text-sm">Token Distribution</CardTitle></CardHeader>
                    <CardContent className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={runDetails.token_chart} margin={{ bottom: 60 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />

                          <YAxis stroke="var(--chart-axis)" />
                          <Tooltip />
                          <Bar dataKey="Thinking" fill="#3B82F6" name="Thinking" stackId="a" />
                          <Bar dataKey="Response" fill="#10B981" name="Response" stackId="a" />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
                {runDetails.ttft_histogram?.length > 0 && (
                  <Card><CardHeader><CardTitle className="text-sm">TTFT Histogram</CardTitle></CardHeader>
                    <CardContent className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={runDetails.ttft_histogram}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                          <XAxis dataKey="TTFT Range (s)" stroke="var(--chart-axis)" /><YAxis stroke="var(--chart-axis)" />
                          <Tooltip /><Bar dataKey="Count" fill="#10B981" />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
                {runDetails.tps_histogram?.length > 0 && (
                  <Card><CardHeader><CardTitle className="text-sm">TPS Histogram</CardTitle></CardHeader>
                    <CardContent className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={runDetails.tps_histogram}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                          <XAxis dataKey="TPS Range" stroke="var(--chart-axis)" /><YAxis stroke="var(--chart-axis)" />
                          <Tooltip /><Bar dataKey="Count" fill="#F59E0B" />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
                {runDetails.category_chart?.length > 0 && (
                  <Card><CardHeader><CardTitle className="text-sm">Category Scores</CardTitle></CardHeader>
                    <CardContent className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={runDetails.category_chart}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                          <XAxis dataKey="Category" stroke="var(--chart-axis)" /><YAxis stroke="var(--chart-axis)" />
                          <Tooltip /><Bar dataKey="Accuracy" fill="#8B5CF6" name="Accuracy %" />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}



      <Card variant="glass">
        <CardHeader><CardTitle>Batch Summary</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-4">
            <Input placeholder="Batch ID" value={batchId} onChange={e => setBatchId(e.target.value)} />
            <Button onClick={loadBatch}>Load</Button>
          </div>
          {batchSummary && (
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>{batchSummary.summary?.length > 0 && Object.keys(batchSummary.summary[0]).map(k => <th key={k} className="p-2 text-left">{k}</th>)}</tr>
                </thead>
                <tbody>
                  {batchSummary.summary?.map((r: any, i: number) => (
                    <tr key={i} className="border-t border-border">
                      {Object.values(r).map((v: any, j: number) => <td key={j} className="p-2">{v}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader><CardTitle>Cross-Run Comparison</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-4">
            <Input placeholder="Run IDs (comma-separated, e.g. 1,2,3)" value={compareIds} onChange={e => setCompareIds(e.target.value)} />
            <Button onClick={handleCompare}>Compare</Button>
          </div>
          {comparison && (
            <div className="grid grid-cols-2 gap-4">
              {comparison.accuracy?.length > 0 && (
                <Card><CardHeader><CardTitle className="text-sm">Accuracy Comparison</CardTitle></CardHeader>
                  <CardContent className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={comparison.accuracy}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="Run" stroke="var(--chart-axis)" /><YAxis stroke="var(--chart-axis)" />
                        <Tooltip /><Bar dataKey="Accuracy %" fill="#3B82F6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              )}
              {comparison.latency?.length > 0 && (
                <Card><CardHeader><CardTitle className="text-sm">Latency Comparison</CardTitle></CardHeader>
                  <CardContent className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={comparison.latency}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="Run" stroke="var(--chart-axis)" /><YAxis stroke="var(--chart-axis)" />
                        <Tooltip />
                        <Bar dataKey="Avg TPS" fill="#10B981" name="Avg TPS" />
                        <Bar dataKey="Avg TTFT" fill="#F59E0B" name="Avg TTFT (s)" />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              )}
              {comparison.tokens?.length > 0 && (
                <Card><CardHeader><CardTitle className="text-sm">Token Comparison</CardTitle></CardHeader>
                  <CardContent className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={comparison.tokens}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="Run" stroke="var(--chart-axis)" /><YAxis stroke="var(--chart-axis)" />
                        <Tooltip /><Bar dataKey="Avg Tokens" fill="#8B5CF6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader><CardTitle>Clear All History</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input placeholder='Type "CONFIRM" to clear' value={clearConfirm} onChange={e => setClearConfirm(e.target.value)} />
            <Button variant="destructive" onClick={handleClear} disabled={clearConfirm !== 'CONFIRM'}>Clear All</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
