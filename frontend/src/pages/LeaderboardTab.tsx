import { useState, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CopyButton } from '@/components/ui/copy-button'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import * as api from '@/lib/api'
import { useApp } from '@/lib/context'

function getSyncStyle(status: string): string {
  const isError = status.includes('Error') || status.includes('failed') || status.includes('❌') || status.includes('first') || status.includes('enter') || status.includes('Synced 0/')
  const isSuccess = status.includes('✅')
  if (isError) return 'text-xs px-3 py-2 rounded-lg border bg-red-50 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-300 dark:border-red-900'
  if (isSuccess) return 'text-xs px-3 py-2 rounded-lg border bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900'
  return 'text-xs px-3 py-2 rounded-lg border bg-muted text-muted-foreground'
}
function Medal({ rank }: { rank: number }) {
  if (rank === 1) return <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-400 text-white text-xs font-bold">1</span>
  if (rank === 2) return <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-zinc-400 text-white text-xs font-bold">2</span>
  if (rank === 3) return <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-700 text-white text-xs font-bold">3</span>
  return <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-muted text-muted-foreground text-xs font-mono">{rank}</span>
}
const COLS: { key: keyof api.LeaderboardEntry; label: string; sortable: boolean }[] = [
  { key: 'Run ID', label: 'Run', sortable: true },
  { key: 'Model', label: 'Model', sortable: true },
  { key: 'Benchmark', label: 'Benchmark', sortable: true },
  { key: 'Accuracy', label: 'Accuracy', sortable: true },
  { key: 'Avg TPS', label: 'TPS', sortable: true },
  { key: 'Avg TTFT', label: 'TTFT', sortable: true },
  { key: 'Passed', label: 'Passed', sortable: true },
  { key: 'Tokens', label: 'Tokens', sortable: true },
  { key: 'Date', label: 'Date', sortable: true },
]

export default function LeaderboardTab({ onDelete }: { onDelete?: () => void }) {
  const { state: appState, dispatch } = useApp()
  const historyRefreshKey = appState.historyRefreshKey
  const [entries, setEntries] = useState<api.LeaderboardEntry[]>([])
  const [sortCol, setSortCol] = useState<keyof api.LeaderboardEntry>('Accuracy')
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc')
  const [filter, setFilter] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [keyExists, setKeyExists] = useState(false)
  const [syncStatus, setSyncStatus] = useState('')
  const [exportFormat, setExportFormat] = useState<'CSV'|'JSON'|'XLSX'>('CSV')
  const [showTrend, setShowTrend] = useState(false)
  const [trendModel, setTrendModel] = useState('')
  const [trendBenchmark, setTrendBenchmark] = useState('')
  const [hideQuickTests, setHideQuickTests] = useState(false)

  useEffect(()=>{ loadLeaderboard()}, [historyRefreshKey])
  useEffect(()=>{ api.getLeaderboardSettings().then(d=>{ const k=d.api_key||''; if(k.includes('*')) setKeyExists(true); else if(k){ setKeyExists(true); localStorage.setItem('lbApiKey',k); setApiKey(k)} else setKeyExists(false)}).catch(()=>{})},[])

  async function loadLeaderboard(){ try{ const d=await api.loadLeaderboard(); setEntries(d.leaderboard||[])}catch{ setSyncStatus('Failed to load leaderboard')} }

  const filtered = useMemo(()=>{
    let list=entries
    if(hideQuickTests) list=list.filter(e=>!e.QuickTest)
    if(!filter.trim()) return list
    const q=filter.toLowerCase()
    return list.filter(e=> String(e['Run ID']).includes(q) || (e.Model||'').toLowerCase().includes(q) || (e.Benchmark||'').toLowerCase().includes(q))
  },[entries, filter, hideQuickTests])

  const sorted = useMemo(()=>{
    const s=[...filtered].sort((a,b)=>{
      const va=a[sortCol]??''; const vb=b[sortCol]??''
      if(sortCol==='Date'){ const da=new Date(String(va)).getTime(); const db=new Date(String(vb)).getTime(); if(!isNaN(da)&&!isNaN(db)) return sortDir==='asc'? da-db : db-da }
      const na=parseFloat(String(va).replace(/[^0-9.-]/g,'')); const nb=parseFloat(String(vb).replace(/[^0-9.-]/g,''))
      const cmp=!isNaN(na)&&!isNaN(nb) ? na-nb : String(va).localeCompare(String(vb))
      return sortDir==='asc'? cmp : -cmp
    })
    return s
  },[filtered, sortCol, sortDir])

  function toggleSort(col: keyof api.LeaderboardEntry){ if(sortCol===col) setSortDir(d=>d==='asc'?'desc':'asc'); else { setSortCol(col); setSortDir('desc') } }
  async function handleDelete(runId:number){ try{ const d=await api.deleteLeaderboardEntry(runId); setEntries(d.leaderboard||[]); onDelete?.(); dispatch({ type:'INCREMENT_HISTORY_REFRESH'}) }catch{ setSyncStatus('Failed to delete entry') } }
  function handleViewInHistory(runId:number){ dispatch({ type:'SET_ACTIVE_TAB', payload:'history'}); setTimeout(()=>{ document.querySelector(`[data-run-id="${runId}"]`)?.scrollIntoView({ behavior:'smooth', block:'center'})},300)}
  async function handleSaveKey(){
    const v=apiKey.trim(); if(!v || v.includes('*')) return
    try{ localStorage.setItem('lbApiKey',v); const d=await api.saveLeaderboardSettings(v); setSyncStatus(d.status); setKeyExists(true)}catch(e:any){ setSyncStatus(e.message)}
  }
  async function handleSync(){
    if(!apiKey.trim() || apiKey.includes('*')){ setSyncStatus('❌ Enter your leaderboard API key first (contact the project author).'); return}
    const key=apiKey || localStorage.getItem('lbApiKey') || ''
    try{ localStorage.setItem('lbApiKey',key); const d=await api.syncLeaderboard(key); setSyncStatus(d.status)}catch(e:any){ setSyncStatus(e.message)}
  }
  function handleExportLB(){
    const data=exportFormat==='CSV' ? 'Run ID,Model,Benchmark,Accuracy,Avg TPS,Avg TTFT,Passed,Tokens,Date\n'+sorted.map(e=>`"${e['Run ID']}","${e.Model}","${e.Benchmark}","${e.Accuracy}","${e['Avg TPS']}","${e['Avg TTFT']}","${e.Passed}","${e.Tokens}","${e.Date}"`).join('\n') : JSON.stringify(sorted,null,2)
    const blob=new Blob([data],{ type: exportFormat==='CSV'?'text/csv':'application/json'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`leaderboard.${exportFormat.toLowerCase()}`; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-5 max-w-[1080px]">
      {/* header */}
      <div className="rounded-xl border bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent dark:from-amber-500/15 dark:via-orange-500/10 p-4 flex flex-wrap items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white shadow-sm">🏆</div>
        <div>
          <h2 className="text-sm font-bold tracking-tight font-display">Leaderboard</h2>
          <p className="text-xs text-muted-foreground">Completed runs ranked by accuracy. Compare models, track trends, and sync to the community board.</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="soft">{entries.length} entries</Badge>
          <Badge variant="outline" className="hidden sm:inline-flex font-mono">30 benchmarks</Badge>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input placeholder="Filter by model, benchmark or ID…" value={filter} onChange={e=>setFilter(e.target.value)} className="h-8 text-xs max-w-[260px]" />
        <label className="flex items-center gap-1.5 text-xs cursor-pointer"><input type="checkbox" checked={hideQuickTests} onChange={e=>setHideQuickTests(e.target.checked)} className="rounded" /> Hide quick tests</label>
        <div className="ml-auto flex gap-2 items-center">
          <select className="h-8 text-xs rounded-lg border bg-card px-2" value={exportFormat} onChange={e=>setExportFormat(e.target.value as any)}><option value="CSV">CSV</option><option value="JSON">JSON</option><option value="XLSX">Excel</option></select>
          <Button variant="outline" size="sm" onClick={handleExportLB}>Export</Button>
          <Button variant="outline" size="sm" asChild><a href={`/api/export/leaderboard?format=${exportFormat}`} download>Server export</a></Button>
          <Button variant="outline" size="sm" onClick={loadLeaderboard}>Refresh</Button>
          <Button variant={showTrend?'default':'outline'} size="sm" onClick={()=>setShowTrend(!showTrend)}>{showTrend?'Hide trend':'Trend'}</Button>
        </div>
        <span className="text-xs text-muted-foreground font-mono w-full sm:w-auto">{sorted.length} / {entries.length}</span>
      </div>

      {showTrend && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex flex-wrap items-center gap-2">
              Performance trend
              <select className="h-7 text-xs rounded-lg border bg-card px-2" value={trendModel} onChange={e=>setTrendModel(e.target.value)}><option value="">Select model…</option>{[...new Set(entries.map(e=>e.Model))].map(m=><option key={m} value={m}>{m}</option>)}</select>
              <select className="h-7 text-xs rounded-lg border bg-card px-2" value={trendBenchmark} onChange={e=>setTrendBenchmark(e.target.value)}><option value="">All benchmarks</option>{[...new Set(entries.map(e=>e.Benchmark))].map(b=><option key={b} value={b}>{b}</option>)}</select>
            </CardTitle>
            <CardDescription>Accuracy over time per model, or average accuracy per model for a benchmark.</CardDescription>
          </CardHeader>
          <CardContent className={trendBenchmark && !trendModel ? 'h-52' : 'h-64'}>
            {trendModel ? (()=>{
              const filtered=[...entries].filter(e=>{ if(trendModel && e.Model!==trendModel) return false; if(trendBenchmark && e.Benchmark!==trendBenchmark) return false; if(hideQuickTests && e.QuickTest) return false; return !!e.Date}).sort((a,b)=> new Date(a.Date).getTime() - new Date(b.Date).getTime())
              if(filtered.length<2) return <div className="text-sm text-muted-foreground text-center pt-10">Need at least 2 runs for a trend.</div>
              const data=filtered.map(e=>({ ...e, AccuracyNum: parseFloat(String(e.Accuracy).replace(/[^0-9.-]/g,'')) }))
              return <ResponsiveContainer width="100%" height="100%"><LineChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Date" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} domain={[0,100]} /><Tooltip /><Line type="monotone" dataKey="AccuracyNum" name="Accuracy %" stroke="var(--chart-accuracy)" strokeWidth={2} dot={{ r:3 }} /></LineChart></ResponsiveContainer>
            })() : trendBenchmark ? (()=>{
              const models=[...new Set(entries.filter(e=> e.Benchmark===trendBenchmark && e.Date && (!hideQuickTests || !e.QuickTest)).map(e=>e.Model))]
              if(!models.length) return <div className="text-sm text-muted-foreground text-center pt-10">No data for this benchmark.</div>
              const grouped:Record<string,number[]>={}; entries.filter(e=> e.Benchmark===trendBenchmark && e.Date && (!hideQuickTests || !e.QuickTest)).forEach(e=>{ const acc=parseFloat(String(e.Accuracy).replace(/[^0-9.-]/g,'')); if(!isNaN(acc)){ if(!grouped[e.Model]) grouped[e.Model]=[]; grouped[e.Model].push(acc)}})
              const barData=Object.entries(grouped).map(([model,vals])=>({ Model: model.length>18? model.slice(0,18)+'…': model, AccuracyNum: Math.round((vals.reduce((a,b)=>a+b,0)/vals.length)*10)/10}))
              return <ResponsiveContainer width="100%" height="100%"><BarChart data={barData}><CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" /><XAxis dataKey="Model" stroke="var(--chart-axis)" fontSize={11} /><YAxis stroke="var(--chart-axis)" fontSize={11} domain={[0,100]} /><Tooltip /><Legend /><Bar dataKey="AccuracyNum" name="Accuracy %" fill="var(--chart-category)" /></BarChart></ResponsiveContainer>
            })() : <div className="text-sm text-muted-foreground text-center pt-10">Select a model to see accuracy over time, or a benchmark to compare models.</div>}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0 overflow-auto max-h-[560px]">
          <table className="w-full text-sm">
            <thead className="bg-muted/70 sticky top-0 backdrop-blur text-[11px] tracking-widest uppercase">
              <tr>
                <th className="p-2.5 text-left w-14">Rank</th>
                {COLS.map(c=>(
                  <th key={String(c.key)} className={`p-2.5 text-left font-semibold text-muted-foreground whitespace-nowrap ${c.sortable?'cursor-pointer hover:text-foreground':''}`} onClick={()=>c.sortable && toggleSort(c.key as any)}>
                    {c.label}{c.sortable && sortCol===c.key && <span className="ml-1 text-primary">{sortDir==='asc'?'▲':'▼'}</span>}
                  </th>
                ))}
                <th className="p-2.5 text-left">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {sorted.map((e,i)=>(
                <tr key={e['Run ID']} className={`hover:bg-muted/40 ${i===0?'bg-amber-50/60 dark:bg-amber-950/15': i===1?'bg-zinc-50 dark:bg-zinc-900/30': i===2?'bg-orange-50/50 dark:bg-orange-950/10':''}`}>
                  <td className="p-2"><Medal rank={i+1} /></td>
                  <td className="p-2 font-mono text-xs">{e['Run ID']}</td>
                  <td className="p-2"><span className="inline-flex items-center gap-1.5 text-xs font-medium truncate max-w-[160px]">{e.Model}<CopyButton value={e.Model} /></span></td>
                  <td className="p-2 text-xs"><span className="inline-flex items-center gap-1.5">{e.Benchmark}{e.Benchmark==='NIAHS' && e['Context K'] && e['Context K']!=='—' && <Badge variant="outline" className="text-[10px] px-1 py-0 font-mono" title="NIAHS context length">{e['Context K']}</Badge>}</span></td>
                  <td className="p-2"><Badge variant={parseFloat(e.Accuracy)>=80 ? 'success' : parseFloat(e.Accuracy)>=50 ? 'soft' : 'danger'} className="text-[11px]">{e.Accuracy}</Badge></td>
                  <td className="p-2 font-mono text-xs">{e['Avg TPS']}</td>
                  <td className="p-2 font-mono text-xs">{e['Avg TTFT']}</td>
                  <td className="p-2 text-xs">{e.Passed}</td>
                  <td className="p-2 font-mono text-xs">{e.Tokens}</td>
                  <td className="p-2 text-xs whitespace-nowrap">{e.Date}</td>
                  <td className="p-2"><div className="flex gap-1"><Button variant="outline" size="xs" onClick={()=>handleViewInHistory(e['Run ID'])}>View</Button><Button variant="ghost" size="xs" className="text-muted-foreground hover:text-red-600" onClick={()=>handleDelete(e['Run ID'])}>Delete</Button></div></td>
                </tr>
              ))}
              {!sorted.length && <tr><td colSpan={11} className="p-8 text-center text-sm text-muted-foreground">{filter? 'No entries match filter.' : 'No completed runs yet. Complete a benchmark to appear here.'}</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Online sync</CardTitle>
          <CardDescription>Sync completed runs to the community Supabase leaderboard. Needs an API key from the project author.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input type="password" placeholder={keyExists ? 'Key saved — type to replace' : 'Leaderboard API key'} value={apiKey} onChange={e=>setApiKey(e.target.value)} className="font-mono text-xs" />
            {keyExists && <span className="text-xs text-emerald-600 dark:text-emerald-400 self-center hidden sm:inline">✓ Saved</span>}
            <Button variant="outline" size="sm" onClick={handleSaveKey}>Save</Button>
            <Button size="sm" onClick={handleSync} disabled={!apiKey.trim()}>Sync</Button>
          </div>
          {syncStatus && <div className={getSyncStyle(syncStatus)}>{syncStatus}</div>}
          <p className="text-[11px] text-muted-foreground">Runs are private until you sync. Sync is idempotent — re-syncing updates existing entries.</p>
        </CardContent>
      </Card>
    </div>
  )
}
