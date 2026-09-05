import { useState, useEffect, useRef, useMemo, type ReactNode } from 'react'
import { useToast } from '@/components/ui/toast-provider'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { AlertDialog, type DialogAction } from '@/components/ui/alert-dialog'
import * as api from '@/lib/api'
import { useApp } from '@/lib/context'

type BenchMeta = { label: string; name: string; category: string; docker: boolean; samples: number; short: string }
const CATEGORY_ORDER = ["All","Coding","Reasoning","Knowledge","Instruction","Tool-Use","Long-Context","Vision","Composite","Safety","Speed"]

export default function RunBenchmarkTab() {
  const { state, dispatch } = useApp()
  const { connection, activeRunId, activeBatchId, runStatus, pendingRerun, activeTab } = state
  const { toast } = useToast()
  const queueNotifiedRef = useRef(false)
  const [benchmarks, setBenchmarks] = useState<BenchMeta[]>([])
  const [selectedBenchmark, setSelectedBenchmark] = useState('')
  const [quickTest, setQuickTest] = useState(false)
  const [temperature, setTemperature] = useState(0)
  const [useCustomTemp, setUseCustomTemp] = useState(false)
  const [maxTokens, setMaxTokens] = useState(8192)
  const [systemPrompt, setSystemPrompt] = useState("You are a precise AI assistant. Follow instructions exactly. Give direct, concise answers without preamble or explanation.")
  const [selectedBatchBenches, setSelectedBatchBenches] = useState<string[]>([])
  const [runMsg, setRunMsg] = useState('')
  const [contextWindow, setContextWindow] = useState('N/A')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [disableRepDetection, setDisableRepDetection] = useState(false)
  const [contextLength, setContextLength] = useState(65536)
  const [mode, setMode] = useState<'single' | 'batch' | 'model-queue'>('single')
  const [benchSearch, setBenchSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('All')
  const [modelSearch, setModelSearch] = useState('')
  const [selectedQueueModels, setSelectedQueueModels] = useState<string[]>([])
  const [queueState, setQueueState] = useState<Record<string, unknown> | null>(null)
  const [liveOverride, setLiveOverride] = useState<Record<string, unknown> | null>(null)
  const [haltConfirmOpen, setHaltConfirmOpen] = useState(false)
  const [queueHaltConfirmOpen, setQueueHaltConfirmOpen] = useState(false)
  const [queueSkipConfirmOpen, setQueueSkipConfirmOpen] = useState(false)
  const [errorDialog, setErrorDialog] = useState<{ open: boolean; title: string; description: ReactNode; actions?: DialogAction[] }>({ open: false, title: '', description: '' })
  const mountedRef = useRef(true)

  const openError = (title: string, description: ReactNode, actions?: DialogAction[]) => setErrorDialog({ open: true, title, description, actions })
  const closeError = () => setErrorDialog(d => ({ ...d, open: false }))

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false } }, [])
  useEffect(() => {
    if (pendingRerun) {
      setSelectedBenchmark(pendingRerun.benchmark)
      dispatch({ type: 'SET_CONNECTION', payload: { selectedModel: pendingRerun.model } })
      dispatch({ type: 'SET_PENDING_RERUN', payload: null })
    }
  }, [pendingRerun, dispatch])
  useEffect(() => { setLiveOverride(null) }, [runStatus])

  async function handleRefresh() {
    if (!activeRunId) return
    try {
      const d = await api.getRunStatus(activeRunId)
      setLiveOverride({
        status: d.status, current_index: d.current_index, total_samples: d.total_samples,
        accuracy: d.accuracy_display || `${d.accuracy}%`, avg_tps: `${d.avg_tps} t/s`, avg_ttft: `${d.avg_ttft} s`,
        token_stats: (() => { const tk = (d.thinking_tokens || 0) + (d.response_tokens || 0); const tp = tk ? Math.round((d.thinking_tokens||0)/tk*100):0; const rp = tk? Math.round((d.response_tokens||0)/tk*100):0; return `🧠 ${tp}% · 💬 ${rp}% · Σ ${tk}` })(),
        progress: d.total_samples ? d.current_index / d.total_samples : 0,
      })
    } catch {}
  }

  useEffect(() => {
    let mounted = true
    api.getBenchmarks().then(d => {
      const list = (d.benchmarks || []) as BenchMeta[]
      if (!mounted) return
      setBenchmarks(list)
      setSelectedBenchmark(prev => (prev && list.some(b => b.name === prev) ? prev : list[0]?.name ?? prev))
    }).catch(()=>{})
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!connection.selectedModel && connection.models.length > 0) dispatch({ type: 'SET_CONNECTION', payload: { selectedModel: connection.models[0] } })
  }, [connection.models, connection.selectedModel, dispatch])

  useEffect(() => {
    const m = connection.metadata?.[connection.selectedModel] as any
    const ctx = m?.context_length || m?.max_context_length || m?.context_window
    setContextWindow(ctx ? String(ctx) : 'N/A')
  }, [connection.selectedModel, connection.metadata])

  const localRunStatus = runStatus?.run_progress ? {
    status: runStatus.run_progress.status_md || '', accuracy: runStatus.run_progress.accuracy || '0%', avg_tps: runStatus.run_progress.avg_tps || '—', avg_ttft: runStatus.run_progress.avg_ttft || '—', token_stats: runStatus.run_progress.token_stats || '—', progress: runStatus.run_progress.progress || 0,
  } : null
  const activeBatchData = runStatus?.batch_progress?.batch_id ? {
    batch_id: runStatus.batch_progress.batch_id, completed: runStatus.batch_progress.completed, total: runStatus.batch_progress.total, current_benchmark: runStatus.batch_progress.current_benchmark, eta: runStatus.batch_progress.eta, progress: runStatus.batch_progress.progress,
  } : null

  useEffect(() => {
    if (mode !== 'model-queue') { setQueueState(null); queueNotifiedRef.current = false; return }
    if (activeTab && activeTab !== 'run') return
    const id = setInterval(async () => {
      if (!mountedRef.current) return
      try {
        const data = await api.getActiveModelQueue()
        if (!mountedRef.current) return
        setQueueState(data as Record<string, unknown>)
        if ((data.status === 'completed' || data.status === 'failed' || data.status === 'halted') && !queueNotifiedRef.current) {
          queueNotifiedRef.current = true
          toast({ title: "Model queue finished", description: `Queue ${data.status}: ${data.current_model_index}/${data.total_models} models`, variant: data.status === 'completed' ? 'success' : 'warning' })
        }
      } catch {}
    }, 3000)
    return () => clearInterval(id)
  }, [mode, toast, activeTab])

  const categories = useMemo(() => {
    const cats = new Set(benchmarks.map(b => b.category))
    return CATEGORY_ORDER.filter(c => c === 'All' || cats.has(c))
  }, [benchmarks])

  const filteredBenches = useMemo(() => {
    let list = benchmarks
    if (categoryFilter !== 'All') list = list.filter(b => b.category === categoryFilter)
    if (benchSearch.trim()) {
      const q = benchSearch.toLowerCase()
      list = list.filter(b => b.name.toLowerCase().includes(q) || b.label.toLowerCase().includes(q) || b.short.toLowerCase().includes(q))
    }
    return list
  }, [benchmarks, benchSearch, categoryFilter])

  const needsDocker = useMemo(() => {
    const names = mode === 'single' ? [selectedBenchmark] : selectedBatchBenches
    return names.some(n => benchmarks.find(b => b.name === n)?.docker)
  }, [mode, selectedBenchmark, selectedBatchBenches, benchmarks])

  async function handleStart() {
    if (mode !== 'model-queue' && !connection.selectedModel) { openError('No model selected', 'Connect and select a model first.'); return }
    const benchNames = mode === 'single' ? [selectedBenchmark] : selectedBatchBenches
    if (!benchNames.length || (mode === 'single' && !selectedBenchmark)) { openError('No benchmark selected', 'Select at least one benchmark.'); return }
    try {
      const { ok, issues } = await api.checkRunReadiness({ benchmarks: benchNames, quick_test: quickTest })
      if (!ok) {
        const actions: DialogAction[] = []
        if (issues.some(i => i.action === 'install_dataset')) actions.push({ label: 'Install datasets', variant: 'soft', onClick: async () => { closeError(); try { await api.installAllDatasets(); toast({ title: 'Install started', description: 'Datasets installing in background.', variant: 'success' }) } catch (e:any){ toast({ title:'Install failed', description:e.message, variant:'error'}) } } })
        if (issues.some(i => i.action === 'download_runtime')) actions.push({ label: 'Build Docker image', variant: 'soft', onClick: async () => { closeError(); try { const r = await api.downloadRuntimes(); toast({ title:'Docker', description:r.status, variant:'success'}) } catch(e:any){ toast({ title:'Build failed', description:e.message, variant:'error'}) } } })
        openError('Cannot start', (<div className="space-y-2"><p className="text-sm">Resolve these first:</p><ul className="list-disc pl-5 space-y-1 text-sm">{issues.map((i,idx)=><li key={idx}>{i.message}</li>)}</ul></div>), actions.length? actions: undefined)
        return
      }
    } catch {}
    try {
      if (mode === 'model-queue') {
        if (!selectedQueueModels.length || !selectedBatchBenches.length) { setRunMsg('Select at least one model and one benchmark.'); return }
        const r = await api.startModelQueue({ models: selectedQueueModels, benchmarks: selectedBatchBenches, api_url: connection.apiUrl, api_key: connection.apiKey, temperature: useCustomTemp ? temperature/100 : undefined, max_tokens: maxTokens, system_prompt: systemPrompt, quick_test: quickTest, disable_repetition_detection: disableRepDetection, context_length: contextLength })
        dispatch({ type: 'SET_ACTIVE_RUN_ID', payload: null }); dispatch({ type: 'SET_ACTIVE_BATCH_ID', payload: null }); setRunMsg(r.message)
      } else if (mode === 'batch' && selectedBatchBenches.length >= 2) {
        const r = await api.startBatch({ model: connection.selectedModel, benchmarks: selectedBatchBenches, api_url: connection.apiUrl, api_key: connection.apiKey, temperature: useCustomTemp ? temperature/100 : undefined, max_tokens: maxTokens, system_prompt: systemPrompt, quick_test: quickTest, disable_repetition_detection: disableRepDetection, context_length: contextLength })
        if (r.run_id) dispatch({ type:'SET_ACTIVE_RUN_ID', payload:r.run_id}); if (r.batch_id) dispatch({ type:'SET_ACTIVE_BATCH_ID', payload:r.batch_id}); setRunMsg(r.message)
      } else {
        const r = await api.startRun({ model: connection.selectedModel, benchmark: selectedBenchmark, api_url: connection.apiUrl, api_key: connection.apiKey, temperature: useCustomTemp ? temperature/100 : undefined, max_tokens: maxTokens, system_prompt: systemPrompt, quick_test: quickTest, disable_repetition_detection: disableRepDetection, context_length: contextLength })
        dispatch({ type:'SET_ACTIVE_RUN_ID', payload:r.run_id}); dispatch({ type:'SET_ACTIVE_BATCH_ID', payload:null}); setRunMsg(r.message)
      }
    } catch (e:any) { openError('Failed to start', e.message) }
  }

  async function handlePause(){ if(!activeRunId) return; try{ const r=await api.pauseRun(activeRunId); setRunMsg(r.status)}catch{ setRunMsg('Pause failed')} }
  async function handleResume(){ if(!activeRunId) return; try{ const r=await api.resumeRun(activeRunId,{ api_url:connection.apiUrl, api_key:connection.apiKey, temperature: useCustomTemp? temperature/100:undefined, max_tokens:maxTokens, system_prompt:systemPrompt, quick_test:quickTest, disable_repetition_detection:disableRepDetection, context_length:contextLength}); setRunMsg(r.status)}catch{ setRunMsg('Resume failed')} }
  async function handleHalt(){ if(!activeRunId) return; try{ const r=await api.haltRun(activeRunId); setRunMsg(r.status)}catch{ setRunMsg('Halt failed')} }
  async function handleHaltModelQueue(){ try{ const r=await api.haltModelQueue(); setRunMsg(r.status)}catch{ setRunMsg('Halt queue failed')} }
  async function handleSkipModelQueue(){ try{ const r=await api.skipModelQueue(); setRunMsg(r.status)}catch{ setRunMsg('Skip failed')} }

  const displayStatus = liveOverride || localRunStatus
  const selBenchMeta = benchmarks.find(b => b.name === selectedBenchmark)

  return (
    <div className="space-y-5 max-w-[1080px]">
      {/* header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-semibold border ${connection.connected ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900' : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-900'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connection.connected ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            {connection.connected ? (connection.selectedModel ? connection.selectedModel.slice(0,28) : 'Connected') : 'Not connected'}
          </div>
          {needsDocker && <Badge variant="warning">🐳 Docker required</Badge>}
          <span className="hidden sm:inline text-xs font-mono text-muted-foreground border px-2 py-1 rounded-full bg-card">ctx {contextWindow}</span>
        </div>
        <div className="flex rounded-xl border bg-card p-1 gap-1">
          {(['single','batch','model-queue'] as const).map(m => (
            <button key={m} onClick={()=>setMode(m)} className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${mode===m ? 'bg-primary text-white shadow-sm' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}>
              {m==='single' ? 'Single' : m==='batch' ? 'Batch' : 'Model queue'}
            </button>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-[14px]">
            {mode==='single' ? 'Run a benchmark' : mode==='batch' ? 'Batch — one model, many benchmarks' : 'Model queue — many models × many benchmarks'}
            {mode==='batch' && selectedBatchBenches.length>0 && <Badge variant="soft" className="ml-2">{selectedBatchBenches.length} selected</Badge>}
            {mode==='model-queue' && <Badge variant="soft" className="ml-2">{selectedQueueModels.length} models · {selectedBatchBenches.length} benchmarks</Badge>}
          </CardTitle>
          <CardDescription>
            {mode==='single' && selBenchMeta ? `${selBenchMeta.category} · ${selBenchMeta.samples.toLocaleString()} samples · ${selBenchMeta.short}` : null}
            {mode==='batch' ? 'Runs benchmarks sequentially with live ETA and per-benchmark accuracy.' : null}
            {mode==='model-queue' ? 'Loads each model, runs all selected benchmarks, then unloads — fully automatic.' : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
            {/* model */}
            <div className="space-y-3">
              <div className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground">{mode==='model-queue' ? 'Models' : 'Model'}</div>
              {mode==='model-queue' ? (
                <div className="space-y-2">
                  <Input placeholder="Filter models…" value={modelSearch} onChange={e=>setModelSearch(e.target.value)} className="h-8 text-xs" />
                  <div className="max-h-[220px] overflow-auto rounded-lg border divide-y bg-card">
                    {(modelSearch ? connection.models.filter(m=>m.toLowerCase().includes(modelSearch.toLowerCase())) : connection.models).map(m=>(
                      <label key={m} className={`flex items-center gap-2 px-3 py-2 text-xs cursor-pointer ${selectedQueueModels.includes(m) ? 'bg-primary/10' : 'hover:bg-muted/50'}`}>
                        <input type="checkbox" checked={selectedQueueModels.includes(m)} onChange={e=> e.target.checked ? setSelectedQueueModels(p=>[...p,m]) : setSelectedQueueModels(p=>p.filter(x=>x!==m))} className="rounded" />
                        <span className="truncate font-mono">{m}</span>
                      </label>
                    ))}
                    {!connection.models.length && <div className="text-xs text-muted-foreground p-4 text-center">No models — connect first</div>}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="xs" className="flex-1" onClick={()=>setSelectedQueueModels([...connection.models])}>Select all</Button>
                    <Button variant="outline" size="xs" className="flex-1" onClick={()=>setSelectedQueueModels([])}>Clear</Button>
                  </div>
                </div>
              ) : (
                <>
                  <select className="flex h-9 w-full rounded-lg border bg-card px-3 text-sm" value={connection.selectedModel} onChange={e=>dispatch({ type:'SET_CONNECTION', payload:{ selectedModel:e.target.value }})} disabled={!connection.connected}>
                    {connection.models.map(m=><option key={m} value={m}>{m}</option>)}
                    {!connection.models.length && <option value="">No model — connect first</option>}
                  </select>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                    <input type="checkbox" checked={quickTest} onChange={e=>setQuickTest(e.target.checked)} className="rounded" />
                    Quick test — 5 samples per benchmark
                  </label>
                </>
              )}
              {mode!=='model-queue' && (
                <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer pt-1">
                  <input type="checkbox" checked={quickTest} onChange={e=>setQuickTest(e.target.checked)} className="rounded hidden" />
                </label>
              )}
              {mode==='model-queue' && (
                <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                  <input type="checkbox" checked={quickTest} onChange={e=>setQuickTest(e.target.checked)} className="rounded" />
                  Quick test (5 per benchmark)
                </label>
              )}
            </div>

            {/* benchmarks */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground">Benchmarks</div>
                {(mode==='batch'||mode==='model-queue') && <span className="text-xs text-muted-foreground font-mono">{selectedBatchBenches.length} selected</span>}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {categories.map(cat=>(
                  <button key={cat} onClick={()=>setCategoryFilter(cat)} className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${categoryFilter===cat ? 'bg-primary text-white border-primary' : 'bg-card border-border text-muted-foreground hover:border-[var(--border-strong)] hover:text-foreground'}`}>{cat}</button>
                ))}
              </div>
              <Input placeholder="Search benchmarks…" value={benchSearch} onChange={e=>setBenchSearch(e.target.value)} className="h-8 text-xs" />
              {mode==='single' ? (
                <div className="space-y-2">
                  <select className="flex h-9 w-full rounded-lg border bg-card px-3 text-sm" value={selectedBenchmark} onChange={e=>setSelectedBenchmark(e.target.value)}>
                    {filteredBenches.map(b=><option key={b.name} value={b.name}>{b.name} — {b.short} · {b.samples.toLocaleString()} {b.docker ? '🐳':''}</option>)}
                  </select>
                  {selBenchMeta && (
                    <div className="flex flex-wrap items-center gap-2 text-xs px-3 py-2.5 rounded-lg border bg-muted/40">
                      <Badge variant="outline" className="text-[11px]">{selBenchMeta.category}</Badge>
                      <span className="font-mono">{selBenchMeta.samples.toLocaleString()} samples</span>
                      {selBenchMeta.docker && <Badge variant="warning" className="text-[11px]">Docker</Badge>}
                      <span className="ml-auto text-muted-foreground truncate hidden sm:inline">{selBenchMeta.short}</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="max-h-[260px] overflow-auto rounded-lg border divide-y bg-card">
                  {filteredBenches.map(b=>{
                    const checked = selectedBatchBenches.includes(b.name)
                    return (
                      <label key={b.name} className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer ${checked? 'bg-primary/10' : 'hover:bg-muted/50'}`}>
                        <input type="checkbox" checked={checked} onChange={e=> e.target.checked ? setSelectedBatchBenches(p=>[...p,b.name]) : setSelectedBatchBenches(p=>p.filter(x=>x!==b.name))} className="rounded" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-semibold truncate">{b.name}</span>
                            <Badge variant="outline" className="text-[10px] hidden sm:inline-flex">{b.category}</Badge>
                            {b.docker && <span className="text-[11px]">🐳</span>}
                          </div>
                          <div className="text-[11px] text-muted-foreground truncate">{b.short} · {b.samples.toLocaleString()}</div>
                        </div>
                      </label>
                    )
                  })}
                  {!filteredBenches.length && <div className="text-xs text-muted-foreground p-4 text-center">No benchmarks match.</div>}
                </div>
              )}
            </div>
          </div>

          {/* advanced */}
          <div className="border-t pt-4">
            <button onClick={()=>setShowAdvanced(!showAdvanced)} className="text-xs font-semibold text-primary hover:underline flex items-center gap-1.5">
              <span className="text-[10px]">{showAdvanced ? '▾' : '▸'}</span> {showAdvanced ? 'Hide' : 'Show'} advanced settings
            </button>
            {showAdvanced && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-5 p-4 rounded-xl border bg-muted/30">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 text-xs font-semibold">
                      <input type="checkbox" checked={useCustomTemp} onChange={e=>setUseCustomTemp(e.target.checked)} className="rounded" />
                      Custom temperature
                    </label>
                    {useCustomTemp ? (
                      <div className="pl-6 space-y-1">
                        <div className="flex justify-between text-xs text-muted-foreground"><span>Temperature</span><span className="font-mono">{temperature}</span></div>
                        <input type="range" min={0} max={100} step={5} value={temperature} onChange={e=>setTemperature(parseInt(e.target.value))} className="w-full accent-[var(--primary)]" />
                      </div>
                    ) : <p className="pl-6 text-xs text-muted-foreground">Uses model default (recommended).</p>}
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold"><span>Max tokens</span><span className="font-mono text-muted-foreground">{maxTokens.toLocaleString()}</span></div>
                    <input type="range" min={256} max={32768} step={256} value={maxTokens} onChange={e=>setMaxTokens(parseInt(e.target.value))} className="w-full accent-[var(--primary)]" />
                    <div className="flex justify-between text-[11px] text-muted-foreground font-mono"><span>256</span><span>32K</span></div>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold"><span>Context length (NIAHS)</span><span className="font-mono text-muted-foreground">{contextLength.toLocaleString()}</span></div>
                    <input type="range" min={1024} max={250000} step={1024} value={contextLength} onChange={e=>setContextLength(parseInt(e.target.value))} className="w-full accent-[var(--primary)]" />
                    <div className="flex justify-between text-[11px] text-muted-foreground font-mono"><span>1K</span><span>250K</span></div>
                  </div>
                  <label className="flex items-start gap-2 text-xs text-muted-foreground cursor-pointer">
                    <input type="checkbox" checked={disableRepDetection} onChange={e=>setDisableRepDetection(e.target.checked)} className="rounded mt-0.5" />
                    <span>Disable loop detection <span className="text-amber-600">(loops waste tokens)</span></span>
                  </label>
                </div>
                <div className="md:col-span-2 space-y-1.5">
                  <label className="text-xs font-semibold">System prompt</label>
                  <textarea className="w-full h-20 rounded-lg border bg-card p-3 text-xs font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40" value={systemPrompt} onChange={e=>setSystemPrompt(e.target.value)} placeholder="System instructions…" />
                </div>
              </div>
            )}
          </div>

          {/* actions */}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            {mode!=='model-queue' ? (
              <>
                <Button size="lg" onClick={handleStart} disabled={!connection.connected || (mode==='batch' && selectedBatchBenches.length < 2)} className="min-w-[170px]">
                  {mode==='batch' ? `Start batch (${selectedBatchBenches.length})` : 'Start benchmark'}
                </Button>
                {mode==='batch' && selectedBatchBenches.length < 2 && <span className="text-xs text-amber-600">Select at least 2 benchmarks</span>}
              </>
            ) : (
              <>
                <Button size="lg" onClick={handleStart} disabled={!connection.connected || !selectedQueueModels.length || !selectedBatchBenches.length} className="min-w-[210px]">
                  Start queue ({selectedQueueModels.length}×{selectedBatchBenches.length})
                </Button>
                {(!selectedQueueModels.length || !selectedBatchBenches.length) && <span className="text-xs text-muted-foreground">Select models + benchmarks</span>}
              </>
            )}
            {mode!=='model-queue' && activeRunId && (
              <div className="flex gap-1.5">
                <Button variant="outline" size="sm" onClick={handlePause} title="Pause">⏸</Button>
                <Button variant="outline" size="sm" onClick={handleResume} title="Resume">▶</Button>
                <Button variant="destructive" size="sm" onClick={()=>setHaltConfirmOpen(true)}>⏹ Halt</Button>
              </div>
            )}
            {mode==='model-queue' && queueState && !['completed','failed','idle'].includes(queueState.status as string) && (
              <div className="flex gap-1.5">
                <Button variant="outline" size="sm" onClick={()=>setQueueSkipConfirmOpen(true)}>⏭ Skip</Button>
                <Button variant="destructive" size="sm" onClick={()=>setQueueHaltConfirmOpen(true)}>⏹ Halt queue</Button>
              </div>
            )}
            <span className="ml-auto text-xs text-muted-foreground max-w-[260px] truncate hidden sm:inline">{runMsg}</span>
          </div>

          <ConfirmDialog open={haltConfirmOpen} onOpenChange={setHaltConfirmOpen} onConfirm={()=>{ handleHalt(); setHaltConfirmOpen(false)}} title="Halt run?" description="Partial results are preserved. This cannot be resumed." />
          <ConfirmDialog open={queueHaltConfirmOpen} onOpenChange={setQueueHaltConfirmOpen} onConfirm={()=>{ handleHaltModelQueue(); setQueueHaltConfirmOpen(false)}} title="Halt model queue?" description="Current model will be unloaded and queue stopped." />
          <ConfirmDialog open={queueSkipConfirmOpen} onOpenChange={setQueueSkipConfirmOpen} onConfirm={()=>{ handleSkipModelQueue(); setQueueSkipConfirmOpen(false)}} title="Skip model?" confirmText="Skip" description="Skip current model and move to next." />
          <AlertDialog open={errorDialog.open} onOpenChange={o=>setErrorDialog(d=>({...d, open:o}))} title={errorDialog.title} description={errorDialog.description} actions={errorDialog.actions} />
        </CardContent>
      </Card>

      {mode==='model-queue' && queueState && ['running','completed','failed','halted'].includes(queueState.status as string) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${queueState.status==='running' ? 'bg-emerald-500 animate-pulse' : queueState.status==='completed' ? 'bg-emerald-600' : 'bg-red-500'}`} />
              Model queue — {(queueState.queue_id as string)?.slice(0,8) || '…'}
              <Badge variant={queueState.status==='running' ? 'warning' : queueState.status==='completed' ? 'success' : 'danger'} className="ml-1 capitalize">{queueState.status as string}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={(queueState.total_models as number)>0 ? (((queueState.current_model_index as number)+(queueState.status==='running'?1:0))/(queueState.total_models as number))*100 : 0} />
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">Models</div><div className="font-mono text-sm mt-1">{queueState.status==='running' ? (queueState.current_model_index as number)+1 : (queueState.current_model_index as number)}/{queueState.total_models as number}</div></div>
              <div className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">Current model</div><div className="font-mono text-xs mt-1 truncate">{(queueState.models as string[])?.[queueState.current_model_index as number] || '—'}</div></div>
              <div className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">Current benchmark</div><div className="font-mono text-xs mt-1 truncate">{(queueState.current_benchmark as string) || '—'}</div></div>
              <div className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">Status</div><div className="font-mono text-xs mt-1 truncate">{(queueState.message as string) || '—'}</div></div>
            </div>
            {queueState.accuracy!==undefined && (
              <>
                {(queueState.total_samples as number)>0 && <Progress value={((queueState.sample_progress as number||0)/(queueState.total_samples as number))*100} className="h-1" />}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { label:'Throughput', value: queueState.avg_tps },
                    { label:'TTFT', value: queueState.avg_ttft },
                    { label:'Accuracy', value: queueState.accuracy },
                    { label:'Tokens', value: (queueState.token_stats as string) || '—' },
                  ].map(m=>(
                    <div key={m.label} className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">{m.label}</div><div className="font-mono text-sm mt-1">{String(m.value)}</div></div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {mode!=='model-queue' && displayStatus && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${(displayStatus as any).status?.includes('RUNNING') ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-400'}`} />
              Live progress
              <span className="text-xs font-normal text-muted-foreground truncate hidden sm:inline">{(displayStatus as any).status}</span>
              <Button variant="outline" size="xs" className="ml-auto" onClick={handleRefresh}>↻ Refresh</Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={((displayStatus as any).progress || 0)*100} />
            {runStatus?.live_turn && (
              <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-primary/10 border border-primary/20 text-xs">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                <span className="font-semibold">Turn {runStatus.live_turn.turn}/{runStatus.live_turn.max_turns}</span>
                <span className="text-muted-foreground">· {Math.round(runStatus.live_turn.elapsed)}s</span>
                <Progress value={(runStatus.live_turn.turn/runStatus.live_turn.max_turns)*100} className="flex-1 h-1.5 ml-2" />
              </div>
            )}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                { label:'Throughput', value:(displayStatus as any).avg_tps },
                { label:'TTFT', value:(displayStatus as any).avg_ttft },
                { label:'Accuracy', value:(displayStatus as any).accuracy },
                { label:'Tokens', value:(displayStatus as any).token_stats || '—' },
              ].map(m=>(
                <div key={m.label} className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">{m.label}</div><div className="font-mono text-sm mt-1">{String(m.value)}</div></div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {mode!=='model-queue' && activeBatchData && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
              Batch — {(activeBatchData.batch_id as string)?.slice(0,8)}
              <span className="text-xs font-normal text-muted-foreground">{activeBatchData.completed as number}/{activeBatchData.total as number} completed</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={(activeBatchData.progress as number)*100} />
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">Current</div><div className="font-mono text-xs mt-1 truncate">{(activeBatchData.current_benchmark as string) || '—'}</div></div>
              <div className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">Completed</div><div className="font-mono text-sm mt-1">{activeBatchData.completed as number}/{activeBatchData.total as number}</div></div>
              <div className="rounded-lg border bg-muted/40 px-3 py-2.5"><div className="text-[10px] tracking-widest uppercase text-muted-foreground">ETA</div><div className="font-mono text-sm mt-1">{(activeBatchData.eta as string) || '—'}</div></div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
