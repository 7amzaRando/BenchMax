import { useState, useEffect, useRef } from 'react'
import { useToast } from '@/components/ui/toast-provider'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import * as api from '@/lib/api'

interface Props {
  connection: {
    apiUrl: string
    apiKey: string
    connected: boolean
    models: string[]
    selectedModel: string
    metadata: Record<string, any>
  }
  setConnection: React.Dispatch<React.SetStateAction<Props['connection']>>
  activeRunId: number | null
  setActiveRunId: (id: number | null) => void
  activeBatchId: string | null
  setActiveBatchId: (id: string | null) => void
  runStatus: any
  pendingRerun?: { model: string; benchmark: string; params: any } | null
  clearPendingRerun?: () => void
}

const DOCKER_BENCHMARKS = ['HumanEval', 'BigCodeBench', 'BigCodeBench-Hard', 'LiveBench', 'Aider Polyglot']

const BENCHMARK_INFO: Record<string, { description: string; docker: boolean; count: string }> = {
  'HumanEval':        { description: 'Code generation tests (164 problems)', docker: true, count: '164' },
  'MMLU-Pro':          { description: 'Massive Multitask Language Understanding (12,032 questions)', docker: false, count: '12,032' },
  'IFEval':            { description: 'Instruction Following Evaluation (541 prompts)', docker: false, count: '541' },
  'AIME':              { description: 'American Invitational Math Exam (90 questions)', docker: false, count: '90' },
  'BigCodeBench':      { description: 'BigCode programming benchmark (1,140 questions)', docker: true, count: '1,140' },
  'BigCodeBench-Hard': { description: 'Hard subset of BigCodeBench (148 questions)', docker: true, count: '148' },
  'BFCL':              { description: 'Berkeley Function Calling Leaderboard (~3,678 questions)', docker: false, count: '~3,678' },
  'MCP-Bench':         { description: 'MCP Tool Calling benchmark (~200 questions)', docker: false, count: '~200' },
  'Safety':            { description: 'Safety & Refusal — Uncensor + OR-Bench (~125 questions)', docker: false, count: '~125' },
  'LongBench-v2':      { description: 'Long-context QA benchmark (503 questions)', docker: false, count: '503' },
  'Aider Polyglot':    { description: 'Multi-language code editing benchmark (225 problems)', docker: true, count: '225' },
  'MMMU-Pro':          { description: 'Multimodal MCQ benchmark (~1,700 questions)', docker: false, count: '~1,700' },
  'LiveBench':         { description: '6-category meta-benchmark (1,436 questions, 23 sub-tasks)', docker: true, count: '1,436' },
  'BenchMax Personal': { description: 'Composite BMS benchmark (100 questions, 5 dimensions)', docker: false, count: '100' },
  'BenchMax Lite':     { description: 'All-round MCQ benchmark (50 questions)', docker: false, count: '50' },
  'BenchMax Code':     { description: 'Coding MCQ benchmark (100 questions)', docker: false, count: '100' },
  'BenchMax Reason':   { description: 'Reasoning MCQ benchmark (100 questions)', docker: false, count: '100' },
  'Writing Speed Test':{ description: 'Creative writing & RP speed test (5 prompts)', docker: false, count: '5' },
  'Coding Speed Test': { description: 'Code generation speed test (5 prompts)', docker: false, count: '5' },
  'BenchMax Tectonic': { description: '300-question composite benchmark (5 categories)', docker: false, count: '300' },
  'TruthfulQA':        { description: 'Truthfulness evaluation MCQ (817 questions)', docker: false, count: '817' },
}

export default function RunBenchmarkTab({ connection, setConnection, activeRunId, setActiveRunId, activeBatchId, setActiveBatchId, runStatus, pendingRerun, clearPendingRerun }: Props) {
  const { toast } = useToast()
  const queueNotifiedRef = useRef(false)
  const [benchmarks, setBenchmarks] = useState<{ label: string; name: string }[]>([])
  const [selectedBenchmark, setSelectedBenchmark] = useState('HumanEval')
  const [quickTest, setQuickTest] = useState(true)
  const [temperature, setTemperature] = useState(0)
  const [useCustomTemp, setUseCustomTemp] = useState(false)
  const [maxTokens, setMaxTokens] = useState(8192)
  const [systemPrompt, setSystemPrompt] = useState("You are a precise AI assistant. Follow instructions exactly. Give direct, concise answers without preamble or explanation.")
  const [selectedBatchBenches, setSelectedBatchBenches] = useState<string[]>([])
  const [runMsg, setRunMsg] = useState('')
  const [contextWindow, setContextWindow] = useState('N/A')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [mode, setMode] = useState<'single' | 'batch' | 'model-queue'>('single')
  const [benchSearch, setBenchSearch] = useState('')
  const [selectedQueueModels, setSelectedQueueModels] = useState<string[]>([])
  const [queueState, setQueueState] = useState<any>(null)
  const [liveOverride, setLiveOverride] = useState<any>(null)
  const [haltConfirmOpen, setHaltConfirmOpen] = useState(false)
  const [queueHaltConfirmOpen, setQueueHaltConfirmOpen] = useState(false)
  const [queueSkipConfirmOpen, setQueueSkipConfirmOpen] = useState(false)

  useEffect(() => {
    if (pendingRerun) {
      setSelectedBenchmark(pendingRerun.benchmark)
      setConnection(prev => ({ ...prev, selectedModel: pendingRerun.model }))
      clearPendingRerun?.()
    }
  }, [pendingRerun])

  useEffect(() => { setLiveOverride(null) }, [runStatus])

  async function handleRefresh() {
    if (!activeRunId) return
    try {
      const d = await api.getRunStatus(activeRunId)
      setLiveOverride({
        status: d.status,
        current_index: d.current_index,
        total_samples: d.total_samples,
        accuracy: d.accuracy_display || `${d.accuracy}%`,
        avg_tps: `${d.avg_tps} t/s`,
        avg_ttft: `${d.avg_ttft} s`,
        token_stats: (() => {
          const tk = (d.thinking_tokens || 0) + (d.response_tokens || 0)
          const thinkPct = tk ? Math.round((d.thinking_tokens || 0) / tk * 100) : 0
          const respPct = tk ? Math.round((d.response_tokens || 0) / tk * 100) : 0
          return `🧠 ${thinkPct}% | 💬 ${respPct}% | Σ ${tk}`
        })(),
        progress: d.total_samples ? d.current_index / d.total_samples : 0,
      })
    } catch { console.warn('handleRefresh failed') }
  }

  useEffect(() => {
    api.getBenchmarks().then(d => setBenchmarks(d.benchmarks || [])).catch(() => { console.warn('getBenchmarks failed') })
  }, [])

  useEffect(() => {
    if (!connection.selectedModel && connection.models.length > 0) {
      setConnection(prev => ({ ...prev, selectedModel: connection.models[0] }))
    }
  }, [connection.models])

  useEffect(() => {
    if (connection.metadata?.[connection.selectedModel]) {
      const m = connection.metadata[connection.selectedModel]
      const ctx = m?.context_length || m?.max_context_length || m?.context_window
      if (ctx) setContextWindow(String(ctx))
    } else {
      api.getConnectionMetadata().then(d => {
        const ctx = d?.context_length || d?.max_context_length
        if (ctx) setContextWindow(String(ctx))
      }).catch(() => console.warn('Failed to get context window'))
    }
  }, [connection.selectedModel, connection.metadata])

  // Derive run status from the main poll in App.tsx (runs at 3s)
  const localRunStatus = runStatus?.run_progress ? {
    status: runStatus.run_progress.status_md || '',
    current_index: 0, total_samples: 0,
    accuracy: runStatus.run_progress.accuracy || '0%',
    avg_tps: runStatus.run_progress.avg_tps || '0 t/s',
    avg_ttft: runStatus.run_progress.avg_ttft || '0 s',
    token_stats: runStatus.run_progress.token_stats || '—',
    progress: runStatus.run_progress.progress || 0,
  } : null

  const activeBatchData = runStatus?.batch_progress?.batch_id ? {
    batch_id: runStatus.batch_progress.batch_id,
    active: true,
    completed: runStatus.batch_progress.completed,
    total: runStatus.batch_progress.total,
    current_benchmark: runStatus.batch_progress.current_benchmark,
    eta: runStatus.batch_progress.eta,
    progress: runStatus.batch_progress.progress,
  } : null

  useEffect(() => {
    if (mode !== 'model-queue') { setQueueState(null); queueNotifiedRef.current = false; return }
    const interval = setInterval(async () => {
      try {
        const data = await api.getActiveModelQueue()
        setQueueState(data)
        if ((data.status === 'completed' || data.status === 'failed' || data.status === 'halted') && !queueNotifiedRef.current) {
          queueNotifiedRef.current = true
          toast({
            title: "Model Queue Finished",
            description: `Queue ${data.status}: ${data.current_model_index}/${data.total_models} models processed`,
            variant: data.status === 'completed' ? 'success' : 'warning'
          })
        }
      } catch { console.warn('getActiveModelQueue failed') }
      }, 3000)
    return () => clearInterval(interval)
  }, [mode, toast])

  const filteredBenches = benchmarks.filter(b =>
    b.label.toLowerCase().includes(benchSearch.toLowerCase())
  )

  const needsDocker = DOCKER_BENCHMARKS.some(b => selectedBenchmark.includes(b))

  function getQuantization(modelId: string): string {
    const m = connection.metadata?.[modelId]
    return m?.quantization || ''
  }

  async function handleStart() {
    if (!connection.selectedModel && mode !== 'model-queue') return
    try {
      if (mode === 'model-queue') {
        if (selectedQueueModels.length === 0 || selectedBatchBenches.length === 0) {
          setRunMsg('Select at least one model and one benchmark.')
          return
        }
        const quant = getQuantization(selectedQueueModels[0])
        const result = await api.startModelQueue({
          models: selectedQueueModels,
          benchmarks: selectedBatchBenches,
          api_url: connection.apiUrl, api_key: connection.apiKey,
          temperature: useCustomTemp ? temperature / 100 : undefined, max_tokens: maxTokens,
          system_prompt: systemPrompt, quick_test: quickTest,
          quantization: quant,
        })
        setActiveRunId(null)
        setActiveBatchId(null)
        setRunMsg(result.message)
      } else if (mode === 'batch' && selectedBatchBenches.length >= 2) {
        const quant = getQuantization(connection.selectedModel)
        const result = await api.startBatch({
          model: connection.selectedModel, benchmarks: selectedBatchBenches,
          api_url: connection.apiUrl, api_key: connection.apiKey,
          temperature: useCustomTemp ? temperature / 100 : undefined, max_tokens: maxTokens,
          system_prompt: systemPrompt, quick_test: quickTest,
          quantization: quant,
        })
        if (result.run_id) setActiveRunId(result.run_id)
        if (result.batch_id) setActiveBatchId(result.batch_id)
        setRunMsg(result.message)
      } else {
        const quant = getQuantization(connection.selectedModel)
        const result = await api.startRun({
          model: connection.selectedModel,
          benchmark: selectedBenchmark,
          api_url: connection.apiUrl,
          api_key: connection.apiKey,
          temperature: useCustomTemp ? temperature / 100 : undefined,
          max_tokens: maxTokens,
          system_prompt: systemPrompt,
          quick_test: quickTest,
          quantization: quant,
        })
        setActiveRunId(result.run_id)
        setActiveBatchId(null)
        setRunMsg(result.message)
      }
    } catch (e: any) { setRunMsg(`Error: ${e.message}`) }
  }

  async function handlePause() {
    if (!activeRunId) return
    try { const r = await api.pauseRun(activeRunId); setRunMsg(r.status) } catch { console.warn('pauseRun failed') }
  }

  async function handleResume() {
    if (!activeRunId) return
    try {
      const r = await api.resumeRun(activeRunId, {
        api_url: connection.apiUrl, api_key: connection.apiKey,
        temperature: useCustomTemp ? temperature / 100 : undefined, max_tokens: maxTokens,
        system_prompt: systemPrompt, quick_test: quickTest,
      })
      setRunMsg(r.status)
    } catch { console.warn('resumeRun failed') }
  }

  async function handleHalt() {
    if (!activeRunId) return
    try { const r = await api.haltRun(activeRunId); setRunMsg(r.status) } catch { console.warn('haltRun failed') }
  }

  async function handleHaltModelQueue() {
    try { const r = await api.haltModelQueue(); setRunMsg(r.status) } catch { console.warn('haltModelQueue failed') }
  }

  async function handleSkipModelQueue() {
    try { const r = await api.skipModelQueue(); setRunMsg(r.status) } catch { console.warn('skipModelQueue failed') }
  }

  const status = localRunStatus || (runStatus?.run_progress ? {
    status: runStatus.run_progress.status_md || '',
    current_index: 0, total_samples: 0,
    accuracy: runStatus.run_progress.accuracy || '0%',
    avg_tps: runStatus.run_progress.avg_tps || '0 t/s',
    avg_ttft: runStatus.run_progress.avg_ttft || '0 s',
    token_stats: runStatus.run_progress.token_stats || '—',
    progress: 0,
  } : null)

  const displayStatus = liveOverride || status

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${connection.connected ? 'bg-green-500/10 text-green-600 dark:text-green-300 border border-green-500/30' : 'bg-red-500/10 text-red-600 dark:text-red-300 border border-red-500/30'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connection.connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
            {connection.connected ? 'Connected' : 'Disconnected'}
          </div>
          {connection.selectedModel && mode !== 'model-queue' && (
            <span className="text-xs text-muted-foreground font-mono">{connection.selectedModel}</span>
          )}
        </div>
        <div className="flex bg-card/80 border border-border rounded-lg p-0.5">
          <button onClick={() => setMode('single')} className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${mode === 'single' ? 'bg-primary text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>Single</button>
          <button onClick={() => setMode('batch')} className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${mode === 'batch' ? 'bg-primary text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>Batch</button>
          <button onClick={() => setMode('model-queue')} className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${mode === 'model-queue' ? 'bg-primary text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>Model Queue</button>
        </div>
      </div>

      <Card variant="glow">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            {mode === 'single' ? 'Run Benchmark' : mode === 'batch' ? 'Batch Queue' : 'Model Queue'}
            {mode === 'batch' && selectedBatchBenches.length >= 2 && (
              <Badge variant="default">{selectedBatchBenches.length} selected</Badge>
            )}
            {mode === 'model-queue' && selectedQueueModels.length > 0 && (
              <Badge variant="default">{selectedQueueModels.length} models</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Model selection row */}
          <div className="grid grid-cols-[1fr_2fr] gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                {mode === 'model-queue' ? 'Models (select all to test)' : 'Model'}
              </label>
              {mode === 'model-queue' ? (
                <div className="space-y-1.5">
                  <Input placeholder="Search models..." value={benchSearch} onChange={e => setBenchSearch(e.target.value)} className="h-8 text-xs" />
                  <div className="max-h-36 overflow-y-auto border border-border rounded-md p-1 space-y-0.5 bg-card/50">
                    {(benchSearch
                      ? connection.models.filter(m => m.toLowerCase().includes(benchSearch.toLowerCase()))
                      : connection.models
                    ).map(m => (
                      <label key={m} className={`flex items-center gap-2 px-2 py-1 rounded text-xs cursor-pointer transition-colors ${selectedQueueModels.includes(m) ? 'bg-primary/20 text-primary' : 'hover:bg-accent/10'}`}>
                        <input type="checkbox" checked={selectedQueueModels.includes(m)} onChange={e => {
                          if (e.target.checked) setSelectedQueueModels(prev => [...prev, m])
                          else setSelectedQueueModels(prev => prev.filter(x => x !== m))
                        }} className="rounded" />
                        <span className="truncate">{m}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ) : (
                <select className="flex h-9 w-full rounded-md border border-border bg-card px-2.5 py-1.5 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={connection.selectedModel} onChange={e => setConnection(prev => ({ ...prev, selectedModel: e.target.value }))} disabled={!connection.connected}>
                  {connection.models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              )}
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-muted-foreground">Benchmark(s)</label>
                {(mode === 'batch' || mode === 'model-queue') && (
                  <span className="text-[10px] text-muted-foreground">Click to select multiple</span>
                )}
              </div>
              {mode === 'single' ? (
                <select className="flex h-9 w-full rounded-md border border-border bg-card px-2.5 py-1.5 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={selectedBenchmark} onChange={e => setSelectedBenchmark(e.target.value)}>
                  {benchmarks.map(b => <option key={b.name} value={b.name} title={BENCHMARK_INFO[b.name]?.description || b.label}>{b.label}</option>)}
                </select>
              ) : (
                <div className="space-y-1.5">
                  <Input placeholder="Search benchmarks..." value={benchSearch} onChange={e => setBenchSearch(e.target.value)} className="h-8 text-xs" />
                  <div className="max-h-36 overflow-y-auto border border-border rounded-md p-1 space-y-0.5 bg-card/50">
                    {filteredBenches.map(b => {
                      const info = BENCHMARK_INFO[b.name]
                      return (
                        <label key={b.name} className={`flex items-center gap-2 px-2 py-1 rounded text-xs cursor-pointer transition-colors ${selectedBatchBenches.includes(b.name) ? 'bg-primary/20 text-primary' : 'hover:bg-accent/10'}`} title={info?.description || b.label}>
                          <input type="checkbox" checked={selectedBatchBenches.includes(b.name)} onChange={e => { if (e.target.checked) setSelectedBatchBenches(prev => [...prev, b.name]); else setSelectedBatchBenches(prev => prev.filter(x => x !== b.name)) }} className="rounded" />
                          <span className="truncate">{b.label}</span>
                          {info?.docker && <span className="text-[10px] px-1 py-0.5 rounded bg-blue-900/30 text-blue-300 border border-blue-700/40 leading-none">Docker</span>}
                        </label>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Quick test */}
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={quickTest} onChange={e => setQuickTest(e.target.checked)} className="rounded" />
            Quick test (5 questions per benchmark)
          </label>

          {/* Docker warning */}
          {mode === 'single' && needsDocker && (
            <div className="text-xs px-3 py-2 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-300 border border-amber-500/30 flex items-center gap-2">
              <span>⚠️</span> This benchmark requires Docker
            </div>
          )}

          {/* Advanced toggle */}
          <div className="border-t border-border pt-3">
            <button onClick={() => setShowAdvanced(!showAdvanced)} className="text-xs text-primary hover:underline flex items-center gap-1">
              {showAdvanced ? '▼' : '▶'} {showAdvanced ? 'Hide' : 'Show'} advanced settings
            </button>
            {showAdvanced && (
              <div className="mt-3 grid grid-cols-2 gap-4 p-4 rounded-lg bg-card/50 border border-border">
                <div className="space-y-1.5">
                  <label className="flex items-center gap-2 text-xs text-muted-foreground col-span-2">
                    <input type="checkbox" checked={useCustomTemp} onChange={e => setUseCustomTemp(e.target.checked)} className="rounded" />
                    Use custom temperature
                  </label>
                  {useCustomTemp && (
                    <>
                      <label className="text-xs text-muted-foreground">Temperature: {temperature}%</label>
                      <input type="range" min={0} max={100} step={5} value={temperature} onChange={e => setTemperature(parseInt(e.target.value))} className="w-full" />
                    </>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">Max Tokens: {maxTokens}</label>
                  <input type="range" min={256} max={32768} step={256} value={maxTokens} onChange={e => setMaxTokens(parseInt(e.target.value))} className="w-full" />
                </div>
                <div className="col-span-2 space-y-1.5">
                  <label className="text-xs text-muted-foreground">System Prompt</label>
                  <textarea className="w-full h-16 rounded-md border border-border bg-card p-2 text-xs font-mono resize-none" value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)} />
                </div>
              </div>
            )}
          </div>

          {/* Action row */}
          <div className="flex items-center gap-2">
            {mode !== 'model-queue' && (
              <>
                <Button variant="glow" onClick={handleStart} disabled={!connection.connected || (mode === 'batch' && selectedBatchBenches.length < 2)}>
                  {mode === 'batch' ? `Start Batch (${selectedBatchBenches.length})` : 'Start Benchmark'}
                </Button>
                {mode === 'batch' && selectedBatchBenches.length < 2 && (
                  <span className="text-xs text-muted-foreground">Select at least 2 benchmarks</span>
                )}
              </>
            )}
            {mode === 'model-queue' && (
              <>
                <Button variant="glow" onClick={handleStart} disabled={!connection.connected || selectedQueueModels.length === 0 || selectedBatchBenches.length === 0}>
                  Start Model Queue ({selectedQueueModels.length} models x {selectedBatchBenches.length} benches)
                </Button>
                {(selectedQueueModels.length === 0 || selectedBatchBenches.length === 0) && (
                  <span className="text-xs text-muted-foreground">Select at least one model and one benchmark</span>
                )}
              </>
            )}
            {mode !== 'model-queue' && activeRunId && (
              <div className="flex gap-1.5 ml-2">
                <Button variant="secondary" size="sm" onClick={handlePause} title="Pause">⏸</Button>
                <Button variant="secondary" size="sm" onClick={handleResume} title="Resume">▶</Button>
                <Button variant="destructive" size="sm" onClick={() => setHaltConfirmOpen(true)} title="Halt">⏹</Button>
              </div>
            )}
            {mode === 'model-queue' && queueState && !['completed', 'failed', 'idle'].includes(queueState.status) && (
              <div className="flex gap-1.5 ml-2">
                <Button variant="secondary" size="sm" onClick={() => setQueueSkipConfirmOpen(true)} title="Skip current model" className="border-amber-500/50 text-amber-400 hover:bg-amber-900/30">⏭ Skip Model</Button>
                <Button variant="destructive" size="sm" onClick={() => setQueueHaltConfirmOpen(true)} title="Halt Model Queue">⏹ Halt Queue</Button>
              </div>
            )}
            <div className="text-xs text-muted-foreground font-mono">CTX: {contextWindow}</div>
            {runMsg && <span className="text-xs text-muted-foreground ml-auto">{runMsg}</span>}
          </div>

          <ConfirmDialog
            open={haltConfirmOpen}
            onOpenChange={setHaltConfirmOpen}
            onConfirm={() => { handleHalt(); setHaltConfirmOpen(false) }}
            title="Halt Run"
            description="Are you sure you want to halt this run? This action cannot be undone. Partial results will be preserved."
          />
          <ConfirmDialog
            open={queueHaltConfirmOpen}
            onOpenChange={setQueueHaltConfirmOpen}
            onConfirm={() => { handleHaltModelQueue(); setQueueHaltConfirmOpen(false) }}
            title="Halt Model Queue"
            description="Are you sure you want to halt the model queue? Current model will be unloaded. Partial results will be preserved."
          />
          <ConfirmDialog
            open={queueSkipConfirmOpen}
            onOpenChange={setQueueSkipConfirmOpen}
            onConfirm={() => { handleSkipModelQueue(); setQueueSkipConfirmOpen(false) }}
            title="Skip Current Model"
            confirmText="Skip"
            description="Skip the current model and move to the next one. Current benchmark will be halted and the model will be unloaded."
          />
        </CardContent>
      </Card>

      {mode === 'model-queue' && queueState && (queueState.status === 'running' || queueState.status === 'completed' || queueState.status === 'failed' || queueState.status === 'halted') && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${queueState.status === 'running' ? 'bg-green-400 animate-pulse' : queueState.status === 'completed' ? 'bg-green-500' : 'bg-red-400'}`} />
              Model Queue — {queueState.queue_id?.slice(0, 8) || '...'}
              <span className="text-xs font-normal text-muted-foreground">{queueState.status}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={queueState.total_models > 0 ? (queueState.current_model_index / queueState.total_models) * 100 : 0} className="w-full h-2" variant="gradient" />
            <div className="grid grid-cols-4 gap-3">
              <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Models</div>
                <div className="font-mono text-sm mt-0.5">{queueState.current_model_index}/{queueState.total_models}</div>
              </div>
              <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Current Model</div>
                <div className="font-mono text-sm mt-0.5">{queueState.models?.[queueState.current_model_index] || '—'}</div>
              </div>
              <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Current Benchmark</div>
                <div className="font-mono text-sm mt-0.5 truncate">{queueState.current_benchmark || '—'}</div>
              </div>
              <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Message</div>
                <div className="font-mono text-sm mt-0.5 truncate">{queueState.message || '—'}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Rendered only when displayStatus is truthy */}
      {mode !== 'model-queue' && (displayStatus) && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${displayStatus.status?.includes('RUNNING') ? 'bg-green-400 animate-pulse' : 'bg-muted-foreground'}`} />
              Live Progress
              <span className="text-xs font-normal text-muted-foreground">{displayStatus.status}</span>
              <Button variant="secondary" size="sm" className="ml-auto h-6 px-2 text-xs" onClick={handleRefresh} title="Refresh progress now">↻ Refresh</Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={(displayStatus.progress || 0) * 100} className="w-full h-2" variant="gradient" />
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'Throughput', value: displayStatus.avg_tps },
                { label: 'TTFT', value: displayStatus.avg_ttft },
                { label: 'Accuracy', value: displayStatus.accuracy },
                { label: 'Tokens', value: displayStatus.token_stats || '—' },
              ].map(m => (
                <div key={m.label} className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{m.label}</div>
                  <div className="font-mono text-sm mt-0.5">{m.value}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {mode !== 'model-queue' && activeBatchData?.active && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
              Batch Progress — {activeBatchData.batch_id?.slice(0, 8)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={activeBatchData.progress * 100} className="w-full h-2" variant="gradient" />
            <div className="grid grid-cols-3 gap-3">
              <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Completed</div>
                <div className="font-mono text-sm mt-0.5">{activeBatchData.completed}/{activeBatchData.total}</div>
              </div>
              <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Current</div>
                <div className="font-mono text-sm mt-0.5">{activeBatchData.current_benchmark || '—'}</div>
              </div>
              <div className="px-3 py-2 rounded-lg bg-card/60 border border-border/60">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">ETA</div>
                <div className="font-mono text-sm mt-0.5">{activeBatchData.eta || '—'}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
