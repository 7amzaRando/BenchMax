import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { getTelemetry } from '@/lib/api'
import { useApp } from '@/lib/context'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

function MetricChart({ title, data, dataKey, color, unit, desc }: { title: string; data: { t: number; [k: string]: number }[]; dataKey?: string; color?: string; unit?: string; desc?: string }) {
  const c = color || 'var(--chart-cpu)'
  const key = dataKey || 'v'
  const gid = `g-${title.replace(/\W/g,'')}`
  const latest = data.length ? data[data.length-1][key] : 0
  const max = data.length ? Math.max(...data.map(d=>d[key])) : 0
  const min = data.length ? Math.min(...data.map(d=>d[key])) : 0
  return (
    <div className="rounded-xl border bg-card p-4 overflow-hidden relative">
      <div className="absolute inset-0 opacity-[0.06] pointer-events-none" style={{ background: `radial-gradient(520px 200px at 85% 0%, ${c}, transparent 60%)` }} />
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold tracking-wide">{title}</div>
          {desc && <div className="text-[11px] text-muted-foreground mt-0.5">{desc}</div>}
          <div className="text-[22px] font-bold tracking-tight leading-none mt-2" style={{ color: c }}>{latest.toFixed(1)}<span className="text-[13px] font-medium text-muted-foreground ml-1">{unit}</span></div>
        </div>
        <div className="text-right text-[11px] font-mono leading-none space-y-1 text-muted-foreground">
          <div>max {max.toFixed(0)}{unit}</div>
          <div>min {min.toFixed(0)}{unit}</div>
        </div>
      </div>
      <div className="mt-3 -mx-1">
        <ResponsiveContainer width="100%" height={96}>
          <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c} stopOpacity={0.28} />
                <stop offset="100%" stopColor={c} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="t" hide />
            <YAxis hide domain={[0,100]} />
            <Tooltip
              contentStyle={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 10, fontSize: 12 }}
              formatter={(v:number)=>[`${v.toFixed(1)}${unit||''}`, title]}
              labelFormatter={()=>''}
            />
            <Area type="monotone" dataKey={key} stroke={c} strokeWidth={2} fill={`url(#${gid})`} isAnimationActive={false} dot={false} activeDot={{ r: 3, fill: c, strokeWidth: 0 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function HardwareTab() {
  const { state, dispatch } = useApp()
  const history = state.hardwareHistory
  const tick = state.hardwareTick
  const [current, setCurrent] = useState<import('@/lib/api').TelemetryData | null>(null)

  useEffect(() => {
    let cancelled = false
    async function fetchCurrent(){ try{ const t=await getTelemetry(); if(!cancelled) setCurrent(t)}catch{}}
    fetchCurrent(); const id=setInterval(fetchCurrent,3000)
    return ()=>{ cancelled=true; clearInterval(id)}
  }, [])

  useEffect(() => {
    if (history.length && !current) {
      const last = history[history.length-1]
      setCurrent(prev => prev ?? { cpu_percent:last.cpu, ram_percent:last.ram, ram_used_gb:0, ram_total_gb:0, gpu_available: last.gpu>0||last.vram>0, gpu_name:null, gpu_load:last.gpu, vram_used_mb:0, vram_total_mb:0, vram_percent:last.vram } as any)
    }
  }, [history, current])

  const gpuAvail = current?.gpu_available
  const paused = state.telemetryPaused

  return (
    <div className="space-y-5 max-w-[1080px]">
      <div className="rounded-xl border bg-card p-4 flex flex-wrap items-center gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Real-time host telemetry</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Live metrics · updates every 3s · {history.length} samples</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant={paused ? 'warning' : 'success'} className="gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${paused ? 'bg-amber-500' : 'bg-emerald-500 animate-pulse'}`} />
            {paused ? 'Paused' : 'Live'}
          </Badge>
          <Button variant={paused ? 'default' : 'outline'} size="sm" onClick={()=>dispatch({ type:'SET_TELEMETRY_PAUSED', payload: !paused })}>
            {paused ? 'Resume' : 'Pause'}
          </Button>
          <Button variant="ghost" size="sm" onClick={()=>dispatch({ type:'SET_HARDWARE_HISTORY', payload: [] })} title="Clear history">Clear</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs flex items-center gap-2"><span className={`w-2 h-2 rounded-full ${paused ? 'bg-zinc-400' : 'bg-emerald-500 animate-pulse'}`} /> CPU</CardTitle></CardHeader>
          <CardContent>
            <div className="text-[22px] font-bold tracking-tight leading-none">{current?.cpu_percent?.toFixed(1) ?? '—'}<span className="text-sm font-medium text-muted-foreground">%</span></div>
            <div className="text-xs text-muted-foreground mt-1">Tick #{tick} · {paused ? 'paused' : 'updating'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs">System RAM</CardTitle></CardHeader>
          <CardContent>
            <div className="text-[18px] font-bold tracking-tight leading-none">{current ? `${current.ram_used_gb.toFixed(1)} / ${current.ram_total_gb.toFixed(1)} GB` : '—'}</div>
            <div className="text-xs text-muted-foreground mt-1">{current?.ram_percent?.toFixed(1) ?? '—'}% used</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs">GPU</CardTitle></CardHeader>
          <CardContent>
            <div className="text-[22px] font-bold tracking-tight leading-none">{gpuAvail ? `${current!.gpu_load.toFixed(1)}%` : 'N/A'}</div>
            <div className="text-xs text-muted-foreground truncate mt-1">{gpuAvail ? (current!.gpu_name || 'GPU detected') : 'No GPU — CPU/MPS fallback'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs">VRAM</CardTitle></CardHeader>
          <CardContent>
            <div className="text-[18px] font-bold tracking-tight leading-none">{gpuAvail ? `${current!.vram_used_mb.toFixed(0)} / ${current!.vram_total_mb.toFixed(0)} MB` : 'N/A'}</div>
            <div className="text-xs text-muted-foreground mt-1">{gpuAvail ? `${current!.vram_percent.toFixed(1)}% used` : '—'}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetricChart title="CPU usage" data={history.slice(-80)} dataKey="cpu" color="var(--chart-cpu)" unit="%" />
        <MetricChart title="RAM usage" data={history.slice(-80).map(p=>({ t:p.t, v:p.ram }))} color="var(--chart-ram)" unit="%" />
        <MetricChart title="GPU load" data={history.slice(-80).map(p=>({ t:p.t, v:p.gpu }))} color="var(--chart-gpu)" unit="%" />
        <MetricChart title="VRAM usage" data={history.slice(-80).map(p=>({ t:p.t, v:p.vram }))} color="var(--chart-vram)" unit="%" />
      </div>

      {!history.length && (
        <Card>
          <CardContent className="py-10 text-center">
            <div className="text-sm font-medium">Collecting telemetry…</div>
            <div className="text-xs text-muted-foreground mt-1">Charts appear after the first sample (3s). Keep this tab open or switch tabs — history persists.</div>
          </CardContent>
        </Card>
      )}


    </div>
  )
}
