import { useState, useEffect, useMemo, useRef, Fragment } from 'react'
import { useToast } from '@/components/ui/toast-provider'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CopyButton } from '@/components/ui/copy-button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { TurnCharts, ConversationViewer } from '@/components/TurnCharts'
import * as api from '@/lib/api'
import { useApp } from '@/lib/context'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'

const PAGE_SIZE = 25

export default function HistoryResultsTab({ onRerun }: { onRerun?: (model: string, benchmark: string, params: Record<string, unknown>) => void }) {
  const { state, dispatch } = useApp()
  const activeTab = state.activeTab
  const historyRefreshKey = state.historyRefreshKey
  const [runs, setRuns] = useState<api.HistoryEntry[]>([])
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
  const [runDetails, setRunDetails] = useState<api.RunDetails | null>(null)
  const [batchId, setBatchId] = useState('')
  const [batchSummary, setBatchSummary] = useState<api.BatchSummary | null>(null)
  const [compareIds, setCompareIds] = useState('')
  const [comparison, setComparison] = useState<api.ComparisonResult | null>(null)
  const [clearConfirm, setClearConfirm] = useState('')
  const [diffHtml, setDiffHtml] = useState('')
  const [selectedTask, setSelectedTask] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [sortColumn, setSortColumn] = useState<string>('Run ID')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [historyFilter, setHistoryFilter] = useState('')
  const [exportFormat, setExportFormat] = useState<'CSV' | 'JSON' | 'XLSX' | 'MD'>('CSV')
  const [page, setPage] = useState(0)
  const [sampleCategoryFilter, setSampleCategoryFilter] = useState('__all')
  const [depthResults, setDepthResults] = useState<api.DepthResult[]>([])
  const [editingNotes, setEditingNotes] = useState<number | null>(null)
  const [notesValue, setNotesValue] = useState('')
  const [showConversation, setShowConversation] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const { toast } = useToast()

  const sortedRuns = useMemo(() => {
    const sorted = [...runs].sort((a, b) => {
      const va = a[sortColumn as keyof api.HistoryEntry] ?? ''
      const vb = b[sortColumn as keyof api.HistoryEntry] ?? ''
      const numA = parseFloat(String(va).replace(/[^0-9.-]/g, ''))
      const numB = parseFloat(String(vb).replace(/[^0-9.-]/g, ''))
      if (!isNaN(numA) && !isNaN(numB)) return sortDir === 'asc' ? numA - numB : numB - numA
      return sortDir === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va))
    })
    return sorted
  }, [runs, sortColumn, sortDir])

  const filteredRuns = useMemo(() => {
    if (!historyFilter.trim()) return sortedRuns
    const q = historyFilter.toLowerCase()
    return sortedRuns.filter(r => (r.Model || '').toLowerCase().includes(q) || (r.Benchmark || '').toLowerCase().includes(q) || (r.Status || '').toLowerCase().includes(q))
  }, [sortedRuns, historyFilter])

  const totalPages = Math.max(1, Math.ceil(filteredRuns.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const paginatedRuns = filteredRuns.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE)
  useEffect(() => { setPage(0) }, [historyFilter])

  const mountedRef = useRef(true)
  useEffect(() => { return () => { mountedRef.current = false } }, [])
  function handleSort(col: string) { if (sortColumn === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortColumn(col); setSortDir('asc') } }
  useEffect(() => { if (activeTab === 'history') loadRuns() }, [activeTab])
  useEffect(() => { loadRuns() }, [historyRefreshKey])
  async function loadRuns() { try { setLoadError(null); const data = await api.loadHistory(); setRuns(data.runs || []) } catch { setLoadError('Failed to load history') } }
  const RESUMMABLE = ['PAUSED', 'HALTED', 'ERROR']
  async function handleResume(runId: number) {
    setLoadError(null)
    try { const res = await api.resumeRun(runId, {}); if (res.status?.startsWith('Run ') && !res.status.includes('Cannot resume')) toast({ title: 'Resumed', description: res.status, variant: 'success' }); else toast({ title: 'Resume failed', description: res.status, variant: 'error' }); loadRuns() } catch { setLoadError('Failed to resume'); toast({ title: 'Resume failed', description: 'Unexpected error', variant: 'error' }) }
  }
  const stats = useMemo(() => {
    const total = filteredRuns.length
    const completed = filteredRuns.filter(r => r.Status === 'COMPLETED').length
    const totalTokens = filteredRuns.reduce((sum, r) => sum + (r['Total Tokens'] || 0), 0)
    const benchmarks = [...new Set(filteredRuns.map(r => r.Benchmark))]
    const models = [...new Set(filteredRuns.map(r => r.Model))]
    let bestAcc = 0, bestModel = '—', bestBench = '—'
    for (const r of filteredRuns) { const acc = parseFloat((r.Accuracy || '0%').replace(/[^0-9.-]/g, '')); if (!isNaN(acc) && acc > bestAcc) { bestAcc = acc; bestModel = r.Model; bestBench = r.Benchmark } }
    return { total_runs: total, completed_runs: completed, total_tokens_generated: totalTokens, benchmarks_run: benchmarks, models_tested: models, best_accuracy: { model: bestModel, benchmark: bestBench, accuracy: bestAcc || '—' } }
  }, [filteredRuns])

  async function loadDetails(runId: number) {
    setSelectedRunId(runId); setDiffHtml(''); setRunDetails(null); setLoadError(null); setDepthResults([]); setSampleCategoryFilter('__all')
    try {
      const data = await api.loadRunDetails(runId)
      if (!mountedRef.current) return
      setRunDetails(data as any)
      if (data.samples?.length) setSelectedTask(data.samples[0].Task || data.samples[0].task_id || '')
      const isNIAHS = (data as any).benchmark_name === 'NIAHS' || data.summary?.includes('NIAHS')
      if (isNIAHS) { try { const d = await api.loadDepthResults(runId); if (mountedRef.current) setDepthResults(d.results || []) } catch {} }
    } catch { setLoadError('Failed to load run details') }
  }
  async function saveNotes(runId: number) {
    try { await api.updateRunNotes(runId, notesValue); setEditingNotes(null); setRuns(prev => prev.map(r => r['Run ID']===runId ? { ...r, Notes: notesValue }: r)); toast({ title: 'Notes saved', variant: 'default' }) } catch { toast({ title: 'Failed to save notes', variant: 'error' }) }
  }
  async function handleDiff() { if (!selectedRunId || !selectedTask) return; setLoadError(null); try { const data = await api.getDiff(selectedRunId, selectedTask); if (mountedRef.current) setDiffHtml(data.html) } catch { setLoadError('Failed to generate diff') } }
  useEffect(()=>{ setShowConversation(false)}, [selectedTask])
  async function loadBatch(id?: string){ const bid=(id || batchId).trim(); if(!bid) return; if(id) setBatchId(bid); setLoadError(null); try{ const d=await api.loadBatchSummary(bid); if(mountedRef.current){ setBatchSummary(d); setTimeout(()=>{ document.querySelector('#batch-summary')?.scrollIntoView({ behavior:'smooth', block:'center'})},100)} }catch{ setLoadError('Failed to load batch') } }
  async function handleCompare(){ if(!compareIds.trim()) return; setLoadError(null); try{ const d=await api.loadComparison(compareIds); if(mountedRef.current) setComparison(d)}catch{ setLoadError('Failed to compare') } }
  async function handleClear(){ setLoadError(null); try{ const d=await api.clearAllHistory(clearConfirm); if(mountedRef.current){ setRuns(d.history||[]); setClearConfirm(''); dispatch({ type:'INCREMENT_HISTORY_REFRESH'}) } }catch{ setLoadError('Failed to clear') } }
  // Group run-detail samples by per-question category (from scoring_details;
  // falls back to task-id prefix, then benchmark name, so single-category
  // benchmarks still show one group). Powers the category filter + headers.
  const sampleGroups = useMemo(() => {
    const samples: any[] = runDetails?.samples || []
    const benchName = runDetails?.benchmark_name || ''
    const catOf = (s: any): string => {
      const raw = s.category ?? s.Category ?? ''
      if (raw && raw !== 'unknown') return String(raw)
      const task = String(s.Task || s.task_id || '')
      if (task.includes('/')) return task.split('/')[0]
      return benchName || 'Uncategorized'
    }
    const map = new Map<string, any[]>()
    for (const s of samples) {
      const c = catOf(s)
      if (!map.has(c)) map.set(c, [])
      map.get(c)!.push(s)
    }
    const groups = [...map.entries()].map(([name, rows]) => {
      const correct = rows.filter((s: any) => s.Correct === '✅').length
      return { name, rows, correct, total: rows.length, pct: rows.length ? Math.round(correct / rows.length * 100) : 0 }
    })
    groups.sort((a, b) => a.name.localeCompare(b.name))
    return groups
  }, [runDetails])

  const visibleSampleGroups = useMemo(() => {
    if (sampleCategoryFilter === '__all') return sampleGroups
    return sampleGroups.filter(g => g.name === sampleCategoryFilter)
  }, [sampleGroups, sampleCategoryFilter])

  async function handleDeleteRun(runId:number){    try{ const d=await api.deleteLeaderboardEntry(runId); setRuns(prev=>prev.filter(r=>r['Run ID']!==runId)); if(selectedRunId===runId){ setSelectedRunId(null); setRunDetails(null)} dispatch({ type:'INCREMENT_HISTORY_REFRESH'}); toast({ title:'Run deleted', description:d.status||`Run ${runId} removed`, variant:'default'}) }catch(e:any){ toast({ title:'Delete failed', description:e.message, variant:'error'})}
    setDeleteTarget(null)
  }

  const batchSummaryData = batchSummary as Record<string, unknown> | null

  return (
    <div className="space-y-5 max-w-[1080px]">
      {/* stats */}
      <div className="grid grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label:'Total runs', value: stats.total_runs },
          { label:'Completed', value: stats.completed_runs },
          { label:'Total tokens', value: (stats.total_tokens_generated||0).toLocaleString() },
          { label:'Benchmarks', value: (stats.benchmarks_run||[]).length },
          { label:'Models', value: (stats.models_tested||[]).length },
          { label:'Best accuracy', value: stats.best_accuracy?.accuracy==='—' ? '—' : `${stats.best_accuracy?.accuracy}%` },
        ].map(s=>(
          <div key={s.label} className="rounded-xl border bg-card px-3.5 py-3">
            <div className="text-[11px] tracking-widest uppercase text-muted-foreground font-semibold">{s.label}</div>
            <div className="font-mono text-sm font-semibold mt-1">{s.value}</div>
          </div>
        ))}
      </div>

      {loadError && <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300 dark:border-red-900 px-3 py-2 text-xs">{loadError}</div>}

      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold tracking-tight">All runs</h2>
        <Badge variant="outline" className="font-mono">{filteredRuns.length}/{runs.length}</Badge>
        <div className="ml-auto flex gap-2 items-center">
          <select className="h-8 text-xs rounded-lg border bg-card px-2" value={exportFormat} onChange={e=>setExportFormat(e.target.value as any)}>
            <option value="CSV">CSV</option><option value="JSON">JSON</option><option value="XLSX">Excel</option><option value="MD">Markdown</option>
          </select>
          <Button variant="outline" size="sm" asChild>
            <a href={exportFormat==='MD' ? `/api/export/history/markdown` : `/api/export/history?format=${exportFormat}`} download>Export all</a>
          </Button>
          <Button variant="outline" size="sm" onClick={loadRuns}>Refresh</Button>
        </div>
      </div>

      <div className="flex gap-3 items-center">
        <Input placeholder="Filter by model, benchmark or status…" value={historyFilter} onChange={e=>setHistoryFilter(e.target.value)} className="h-8 text-xs max-w-sm" />
        <span className="text-xs text-muted-foreground hidden sm:inline">{filteredRuns.length} shown · {PAGE_SIZE}/page</span>
      </div>

      <Card>
        <CardContent className="p-0 overflow-auto max-h-[460px]">
          <table className="w-full text-sm min-w-[960px]">
            <thead className="bg-muted/70 sticky top-0 z-10 backdrop-blur text-[11px] tracking-widest uppercase">
              <tr className="border-b">
                {[
                  { k:'Run ID', label:'Run', w:'w-[72px]' },
                  { k:'Model', label:'Model', w:'min-w-[160px]' },
                  { k:'Benchmark', label:'Benchmark', w:'min-w-[170px]' },
                  { k:'Status', label:'Status', w:'w-[110px]' },
                  { k:'Progress', label:'Progress', w:'w-[110px]' },
                  { k:'Accuracy', label:'Accuracy', w:'w-[110px]' },
                  { k:'Avg TPS', label:'Speed', w:'w-[110px]' },
                  { k:'Created', label:'Created', w:'w-[130px]' },
                  { k:'Actions', label:'', w:'min-w-[160px]' },
                ].map(col=>(
                  <th key={col.k} className={`${col.w} px-3 py-2.5 text-left font-semibold text-muted-foreground whitespace-nowrap ${col.k!=='Actions' ? 'cursor-pointer hover:text-foreground' : ''}`} onClick={()=>col.k!=='Actions' && handleSort(col.k)}>
                    {col.label}{sortColumn===col.k && <span className="ml-1 text-primary">{sortDir==='asc'?'▲':'▼'}</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {paginatedRuns.map(r=>(
                <tr key={r['Run ID']} data-run-id={r['Run ID']} className={`group cursor-pointer ${selectedRunId===r['Run ID'] ? 'bg-primary/[0.06]' : 'hover:bg-muted/40'}`} onClick={()=>loadDetails(r['Run ID'])}>
                  <td className="px-3 py-3 font-mono text-xs font-medium"><span className="inline-flex items-center gap-1.5"><span className={`w-1.5 h-1.5 rounded-full ${r.Status==='COMPLETED'?'bg-emerald-500':r.Status==='ERROR'?'bg-red-500':r.Status==='RUNNING'?'bg-amber-500 animate-pulse':'bg-zinc-400'}`} />#{r['Run ID']}</span></td>
                  <td className="px-3 py-3"><div className="flex items-center gap-1.5 max-w-[180px]"><span className="truncate text-xs font-medium">{r.Model}</span><CopyButton value={r.Model} /></div>{r.Notes && r.Notes!=='—' && <div className="text-[11px] text-muted-foreground truncate max-w-[180px]">{r.Notes}</div>}</td>
                  <td className="px-3 py-3"><div className="text-xs font-medium leading-tight">{r.Benchmark}</div><div className="flex items-center gap-1.5 mt-1">{r.Benchmark==='NIAHS' ? (r['Context K'] && r['Context K']!=='—' ? <Badge variant="outline" className="text-[10px] font-mono" title={`NIAHS context length${r['Context Length'] && r['Context Length']!=='—' ? `: ${r['Context Length']} tokens` : ''}`}>{r['Context K']}</Badge> : <span className="text-[11px] text-muted-foreground">64K</span>) : null}{r.Batch && r.Batch!=='—' && <button className="text-[10px] text-muted-foreground hover:text-primary underline decoration-dotted underline-offset-2" title={`Load batch summary (${r.Batch})`} onClick={e=>{ e.stopPropagation(); loadBatch(String(r.Batch)) }}>batch</button>}</div></td>
                  <td className="px-3 py-3"><Badge variant={r.Status==='COMPLETED'?'success':r.Status==='ERROR'||r.Status==='FAILED'?'danger':r.Status==='RUNNING'?'warning':'secondary'} className="text-[11px]">{r.Status}</Badge></td>
                  <td className="px-3 py-3"><div className="text-xs font-mono">{r.Progress}</div><div className="w-full h-1 rounded-full bg-muted mt-1.5 overflow-hidden"><div className="h-full bg-primary" style={{ width:`${(()=>{ const [a,b]=String(r.Progress).split('/').map(Number); return b? Math.min(100,Math.round(a/b*100)):0})()}%`}} /></div></td>
                  <td className="px-3 py-3"><div className="text-xs font-semibold">{r.Accuracy}</div><div className="text-[11px] text-muted-foreground">{r.Benchmark==='NIAHS' && r.Needles && r.Needles!=='—' ? <span className="font-mono">{r.Needles}</span> : `${r['Avg Tokens'] ?? '—'} tok avg`}</div></td>
                  <td className="px-3 py-3"><div className="text-xs font-mono">{r['Avg TPS'] ?? '—'} <span className="text-muted-foreground">t/s</span></div><div className="text-[11px] font-mono text-muted-foreground">{r['Avg TTFT'] ?? '—'}s</div></td>
                  <td className="px-3 py-3 text-xs text-muted-foreground whitespace-nowrap"><div>{r.Created || '—'}</div>{r.Duration && r.Duration!=='—' && <div className="text-[11px]">{r.Duration}</div>}</td>
                  <td className="px-3 py-3" onClick={e=>e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="xs" onClick={()=>onRerun?.(r.Model, r.Benchmark, {})}>Re-run</Button>
                      {RESUMMABLE.includes(r.Status) && <Button variant="soft" size="xs" onClick={()=>handleResume(r['Run ID'])}>Resume</Button>}
                      <Button variant="ghost" size="xs" className="px-1.5 text-muted-foreground hover:text-red-600" onClick={()=>setDeleteTarget(r['Run ID'])}>✕</Button>
                    </div>
                    {editingNotes===r['Run ID'] ? (
                      <div className="flex gap-1 mt-1.5"><input className="flex-1 h-6 text-xs rounded border bg-card px-1.5" value={notesValue} onChange={e=>setNotesValue(e.target.value)} onKeyDown={e=>{ if(e.key==='Enter') saveNotes(r['Run ID']); if(e.key==='Escape') setEditingNotes(null)}} autoFocus placeholder="Notes…" /><Button variant="ghost" size="xs" onClick={()=>saveNotes(r['Run ID'])}>✓</Button></div>
                    ) : (
                      <button className="text-[11px] text-muted-foreground hover:text-primary mt-1 block text-left truncate max-w-[160px]" onClick={e=>{ e.stopPropagation(); setEditingNotes(r['Run ID']); setNotesValue(r.Notes||'')}}>{r.Notes ? `📝 ${r.Notes}` : '＋ notes'}</button>
                    )}
                  </td>
                </tr>
              ))}
              {!paginatedRuns.length && <tr><td colSpan={9} className="px-4 py-12 text-center text-sm text-muted-foreground">{historyFilter? 'No runs match filter' : 'No runs yet — start one from the Run tab.'}</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {filteredRuns.length > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={safePage===0} onClick={()=>setPage(p=>p-1)}>Previous</Button>
          <span className="text-xs text-muted-foreground font-mono">Page {safePage+1} / {totalPages}</span>
          <Button variant="outline" size="sm" disabled={safePage>=totalPages-1} onClick={()=>setPage(p=>p+1)}>Next</Button>
        </div>
      )}

      {runDetails && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                Run #{selectedRunId}
                {runDetails.benchmark_name==='NIAHS' && runDetails.context_length && <Badge variant="outline" className="font-mono text-xs" title={typeof runDetails.context_length==='number' ? `${runDetails.context_length.toLocaleString()} tokens` : String(runDetails.context_length)}>{typeof runDetails.context_length==='number' ? `${Math.floor((runDetails.context_length as number)/1024)}K` : String(runDetails.context_length)}</Badge>}
                {runDetails.benchmark_name && <Badge variant="soft">{runDetails.benchmark_name}</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-xs leading-relaxed text-muted-foreground whitespace-pre-wrap rounded-lg border bg-muted/30 p-3">{runDetails.summary}</div>
              <div className="flex gap-2">
                <select className="h-8 text-xs rounded-lg border bg-card px-2" value={exportFormat} onChange={e=>setExportFormat(e.target.value as any)}><option value="CSV">CSV</option><option value="JSON">JSON</option><option value="XLSX">Excel</option><option value="MD">Markdown</option></select>
                <Button variant="outline" size="sm" asChild><a href={exportFormat==='MD' ? `/api/export/runs/${selectedRunId}/markdown` : `/api/export/runs/${selectedRunId}?format=${exportFormat}`} download>Export run</a></Button>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold">Questions</span>
                <Badge variant="outline" className="font-mono">{runDetails.samples?.length || 0}</Badge>
                {sampleGroups.length > 1 && (
                  <select className="h-7 text-xs rounded-lg border bg-card px-2 ml-auto" value={sampleCategoryFilter} onChange={e=>setSampleCategoryFilter(e.target.value)}>
                    <option value="__all">All categories ({sampleGroups.length})</option>
                    {sampleGroups.map(g=><option key={g.name} value={g.name}>{g.name} — {g.correct}/{g.total} ({g.pct}%)</option>)}
                  </select>
                )}
              </div>
              <div className="overflow-auto rounded-lg border max-h-80">
                <table className="w-full text-sm">
                  <thead className="bg-muted/70 sticky top-0 text-xs">
                    <tr><th className="p-2 text-left font-semibold">Task</th><th className="p-2 text-left font-semibold">Result</th><th className="p-2 text-left font-semibold">TTFT</th><th className="p-2 text-left font-semibold">TPS</th><th className="p-2 text-left font-semibold">Elapsed</th><th className="p-2 text-left font-semibold">Error</th></tr>
                  </thead>
                  <tbody className="divide-y">
                    {visibleSampleGroups.map(g=>(
                      <Fragment key={`cat-${g.name}`}>
                        <tr className="bg-muted/50">
                          <td colSpan={6} className="px-2 py-1.5">
                            <div className="flex items-center gap-2">
                              <Badge variant="soft" className="text-[11px]">{g.name}</Badge>
                              <span className="text-[11px] font-mono text-muted-foreground">{g.correct}/{g.total} ({g.pct}%)</span>
                              <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden"><div className={`h-full ${g.pct>=80?'bg-emerald-500':g.pct>=50?'bg-amber-500':'bg-red-500'}`} style={{ width:`${g.pct}%` }} /></div>
                            </div>
                          </td>
                        </tr>
                        {g.rows.map((s:any,i:number)=>(
                          <tr key={`${g.name}-${i}`} className="hover:bg-muted/40">
                            <td className="p-2 font-mono text-xs">{s.Task || s.task_id}</td>
                            <td className="p-2">{s.Correct==='✅' ? '✅':'❌'}</td>
                            <td className="p-2 font-mono text-xs">{s['TTFT (s)'] || s.ttft || '—'}</td>
                            <td className="p-2 font-mono text-xs">{s.TPS || s.tps || '—'}</td>
                            <td className="p-2 font-mono text-xs">{s.Elapsed || s.elapsed_time || '—'}</td>
                            <td className="p-2 text-xs text-muted-foreground max-w-[220px] truncate" title={s.Error || s.error_message || ''}>{s.Error || s.error_message || '—'}</td>
                          </tr>
                        ))}
                      </Fragment>
                    ))}
                    {!visibleSampleGroups.length && <tr><td colSpan={6} className="p-4 text-center text-xs text-muted-foreground">No questions in this category</td></tr>}
                  </tbody>
                </table>
              </div>

              {runDetails.samples?.length>0 && (
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <label className="text-xs text-muted-foreground mb-1 block">Task for diff & conversation</label>
                    <select className="w-full h-8 rounded-lg border bg-card px-2 text-xs" value={selectedTask} onChange={e=>setSelectedTask(e.target.value)}>
                      {runDetails.samples.map((s:any)=>{ const tid=s.Task||s.task_id||''; const mark=s.Correct==='✅'?'✅':'❌'; return <option key={tid} value={tid}>{mark} {tid}</option>})}
                    </select>
                  </div>
                  <Button size="sm" onClick={handleDiff}>Generate diff</Button>
                </div>
              )}

              {diffHtml && (
                <div className="rounded-lg border overflow-hidden">
                  <div className="flex items-center justify-between px-3 py-2 bg-muted/50 border-b"><span className="text-xs font-semibold">Diff</span><button onClick={()=>setDiffHtml('')} className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted">Close</button></div>
                  <div className="p-3 overflow-auto max-h-[520px] text-xs" dangerouslySetInnerHTML={{ __html: diffHtml }} />
                </div>
              )}

              {(()=>{ const sel=runDetails.samples?.find((s:any)=>(s.Task||s.task_id)===selectedTask) as any; const raw=sel?.turns; let turns:any[]=[]; if(Array.isArray(raw)) turns=raw; else if(typeof raw==='string'){ try{ turns=JSON.parse(raw)}catch{}}; const isMultiTurn=turns && turns.length>0; if(!isMultiTurn) return null; const assistantTurns=turns.filter((t:any)=>t.role==='assistant' && t.turn>=0); return (
                <div className="space-y-3">
                  <Button variant="outline" size="sm" onClick={()=>setShowConversation(v=>!v)}>{showConversation ? 'Hide conversation' : `View conversation (${turns.length} msgs · ${assistantTurns.length} turns)`}</Button>
                  {showConversation && <Card><CardHeader><CardTitle className="text-sm">Conversation — {selectedTask}</CardTitle></CardHeader><CardContent><ConversationViewer turns={turns} /></CardContent></Card>}
                  <TurnCharts turns={turns} />
                </div>
              )})()}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {runDetails.token_chart?.length>0 ? (()=>{
                  const samples:any[]=runDetails.samples||[]; const n=samples.length||1; const totalTokens=samples.reduce((s:number,x:any)=>s+(x.Tokens ?? ((x.Thinking||0)+(x.Response||0))),0); const avgTotal=n?(totalTokens/n):0; const avgThink=n?samples.reduce((s:number,x:any)=>s+(x.Thinking||0),0)/n:0; const avgResp=n?samples.reduce((s:number,x:any)=>s+(x.Response||0),0)/n:0
                  return (
                    <Card><CardHeader className="pb-2"><CardTitle className="text-sm flex flex-wrap items-center gap-2">Token distribution <Badge variant="outline" className="font-mono text-[11px]">avg {avgTotal.toFixed(1)}</Badge><span className="text-[11px] text-muted-foreground font-normal">think {avgThink.toFixed(0)} · resp {avgResp.toFixed(0)}</span></CardTitle></CardHeader>
                      <CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={runDetails.token_chart} margin={{ bottom:40 }}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Task" hide /><YAxis stroke="var(--chart-axis)" fontSize={11} /><Tooltip /><Bar dataKey="Thinking" fill="var(--chart-thinking)" stackId="a" /><Bar dataKey="Response" fill="var(--chart-response)" stackId="a" /><ReferenceLine y={avgTotal} stroke="var(--chart-accuracy)" strokeDasharray="4 4" /></BarChart></ResponsiveContainer></CardContent>
                    </Card>
                  )
                })() : <Card><CardHeader><CardTitle className="text-sm">Token distribution</CardTitle></CardHeader><CardContent className="h-64 flex items-center justify-center text-sm text-muted-foreground">No samples yet</CardContent></Card>}

                {runDetails.ttft_histogram?.length>0 ? (()=>{
                  const vals=(runDetails.samples||[]).map((s:any)=>parseFloat(s['TTFT (s)']?? s.ttft ?? 0)).filter((v:number)=>v>0); const avg=vals.length? vals.reduce((a:number,b:number)=>a+b,0)/vals.length:0
                  return <Card><CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2">TTFT histogram <Badge variant="outline" className="font-mono text-[11px]">avg {avg.toFixed(3)}s</Badge></CardTitle></CardHeader><CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={runDetails.ttft_histogram}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="TTFT Range (s)" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} /><Tooltip /><Bar dataKey="Count" fill="var(--chart-ttft)" /></BarChart></ResponsiveContainer></CardContent></Card>
                })() : <Card><CardHeader><CardTitle className="text-sm">TTFT histogram</CardTitle></CardHeader><CardContent className="h-64 flex items-center justify-center text-sm text-muted-foreground">No samples yet</CardContent></Card>}

                {runDetails.tps_histogram?.length>0 ? (()=>{
                  const vals=(runDetails.samples||[]).map((s:any)=>parseFloat(s.TPS ?? s.tps ?? 0)).filter((v:number)=>v>0); const avg=vals.length? vals.reduce((a:number,b:number)=>a+b,0)/vals.length:0
                  return <Card><CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2">TPS histogram <Badge variant="outline" className="font-mono text-[11px]">avg {avg.toFixed(1)} tok/s</Badge></CardTitle></CardHeader><CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={runDetails.tps_histogram}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="TPS Range" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} /><Tooltip /><Bar dataKey="Count" fill="var(--chart-tps)" /></BarChart></ResponsiveContainer></CardContent></Card>
                })() : <Card><CardHeader><CardTitle className="text-sm">TPS histogram</CardTitle></CardHeader><CardContent className="h-64 flex items-center justify-center text-sm text-muted-foreground">No samples yet</CardContent></Card>}

                {runDetails.category_chart?.length>0 ? (
                  <Card><CardHeader><CardTitle className="text-sm">Category scores</CardTitle></CardHeader><CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={runDetails.category_chart}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Category" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} /><Tooltip /><Bar dataKey="Accuracy" fill="var(--chart-category)" /></BarChart></ResponsiveContainer></CardContent></Card>
                ) : <Card><CardHeader><CardTitle className="text-sm">Category scores</CardTitle></CardHeader><CardContent className="h-64 flex items-center justify-center text-sm text-muted-foreground">Single-category benchmark</CardContent></Card>}

                {depthResults.length>0 && (()=>{
                  const buckets=[10,25,50,75,90]; const data=buckets.map(d=>{ const samples=depthResults.filter(r=>Math.round(r.depth*100)===d); const correct=samples.filter(r=>r.correct).length; return { Depth:`${d}%`, Accuracy: samples.length? Math.round(correct/samples.length*100):0, Total:samples.length}}).filter(d=>d.Total>0)
                  return data.length? <Card><CardHeader><CardTitle className="text-sm">NIAHS — success by depth</CardTitle></CardHeader><CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Depth" stroke="var(--chart-axis)" /><YAxis stroke="var(--chart-axis)" domain={[0,100]} /><Tooltip formatter={(v:number)=>`${v}%`} /><Bar dataKey="Accuracy">{data.map((d,i)=><Cell key={i} fill={d.Accuracy>=80?'#10b981':d.Accuracy>=50?'#f59e0b':'#ef4444'} />)}</Bar></BarChart></ResponsiveContainer></CardContent></Card> : null
                })()}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader id="batch-summary"><CardTitle className="text-sm">Batch summary</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input placeholder="Batch ID (or click “batch” on a run above)" value={batchId} onChange={e=>setBatchId(e.target.value)} className="h-8 text-xs" />
            <Button size="sm" onClick={()=>loadBatch()}>Load</Button>
          </div>
          {batchSummaryData && (
            <div className="overflow-auto rounded-lg border max-h-[320px]">
              <table className="w-full text-xs">
                <thead className="bg-muted sticky top-0"><tr>{Array.isArray(batchSummaryData.summary) && batchSummaryData.summary.length>0 && Object.keys(batchSummaryData.summary[0] as Record<string,unknown>).map(k=><th key={k} className="p-2 text-left font-semibold">{k}</th>)}</tr></thead>
                <tbody className="divide-y">{Array.isArray(batchSummaryData.summary) && batchSummaryData.summary.map((r:unknown,i:number)=>{ const row=r as Record<string,unknown>; return <tr key={i} className="hover:bg-muted/40">{Object.values(row).map((v:unknown,j:number)=><td key={j} className="p-2 font-mono">{String(v ?? '—')}</td>)}</tr>})}</tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-sm">Cross-run comparison</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input placeholder="Run IDs, e.g. 1,2,3" value={compareIds} onChange={e=>setCompareIds(e.target.value)} className="h-8 text-xs" />
            <Button size="sm" onClick={handleCompare}>Compare</Button>
            {compareIds.trim() && <Button variant="outline" size="sm" asChild><a href={`/api/export/comparison?run_ids=${encodeURIComponent(compareIds)}&format=${exportFormat}`} download>Export</a></Button>}
          </div>
          {comparison && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {comparison.accuracy?.length>0 && <Card><CardHeader><CardTitle className="text-sm">Accuracy</CardTitle></CardHeader><CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={comparison.accuracy}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Run" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} /><Tooltip /><Bar dataKey="Accuracy %" fill="var(--chart-accuracy)" /></BarChart></ResponsiveContainer></CardContent></Card>}
              {comparison.latency?.length>0 && <Card><CardHeader><CardTitle className="text-sm">Latency</CardTitle></CardHeader><CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={comparison.latency}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Run" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} /><Tooltip /><Bar dataKey="Avg TPS" fill="var(--chart-latency-tps)" /><Bar dataKey="Avg TTFT" fill="var(--chart-latency-ttft)" /></BarChart></ResponsiveContainer></CardContent></Card>}
              {comparison.tokens?.length>0 && <Card><CardHeader><CardTitle className="text-sm">Tokens</CardTitle></CardHeader><CardContent className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={comparison.tokens}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Run" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} /><Tooltip /><Bar dataKey="Avg Tokens" fill="var(--chart-tokens)" /></BarChart></ResponsiveContainer></CardContent></Card>}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-sm">Danger zone</CardTitle></CardHeader>
        <CardContent className="flex gap-2">
          <Input placeholder='Type "CONFIRM" to clear all history' value={clearConfirm} onChange={e=>setClearConfirm(e.target.value)} className="h-8 text-xs" />
          <Button variant="destructive" size="sm" onClick={handleClear} disabled={clearConfirm!=='CONFIRM'}>Clear all</Button>
        </CardContent>
      </Card>

      <ConfirmDialog open={deleteTarget!==null} onOpenChange={o=>{ if(!o) setDeleteTarget(null)}} onConfirm={()=>{ if(deleteTarget!==null) handleDeleteRun(deleteTarget)}} title="Delete run" description={`Delete run #${deleteTarget}? This removes it from history and leaderboard and cannot be undone.`} confirmText="Delete" />
    </div>
  )
}
