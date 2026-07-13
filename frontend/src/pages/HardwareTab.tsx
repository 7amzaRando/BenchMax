import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getTelemetry } from '@/lib/api'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

function MetricChart({ title, data, dataKey, color, unit }: {
    title: string;
    data: { t: number; v: number }[];
    dataKey?: string;
    color?: string;
    unit?: string;
}) {
    const chartColor = color || '#3b82f6'
    const key = dataKey || 'v'
    const gradId = `grad-${title.replace(/\s+/g, '')}`
    const latest = data.length ? data[data.length - 1][key] : 0
    const max = data.length ? Math.max(...data.map(d => d[key])) : 0
    const min = data.length ? Math.min(...data.map(d => d[key])) : 0
    return (
        <div className="relative bg-card border border-border rounded-xl p-4 overflow-hidden">
            <div
                className="absolute inset-0 opacity-[0.12] pointer-events-none"
                style={{ background: `radial-gradient(circle at top right, ${chartColor}, transparent 70%)` }}
            />
            <div className="relative flex items-start justify-between mb-1">
                <div>
                    <h3 className="text-sm font-medium text-foreground">{title}</h3>
                    <div className="text-2xl font-bold leading-tight" style={{ color: chartColor }}>
                        {latest.toFixed(1)}<span className="text-base font-medium text-muted-foreground ml-0.5">{unit}</span>
                    </div>
                </div>
                <div className="text-right text-[10px] text-muted-foreground font-mono space-y-0.5">
                    <div>max {max.toFixed(0)}{unit}</div>
                    <div>min {min.toFixed(0)}{unit}</div>
                </div>
            </div>
            <ResponsiveContainer width="100%" height={100}>
                <AreaChart data={data} margin={{ top: 6, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={chartColor} stopOpacity={0.4} />
                            <stop offset="100%" stopColor={chartColor} stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <XAxis dataKey="t" hide />
                    <YAxis hide domain={[0, 100]} />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: 'hsl(var(--card))',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: '8px',
                            fontSize: '12px',
                        }}
                        formatter={(value: number) => [`${value}${unit || ''}`, title]}
                        labelFormatter={() => ''}
                    />
                    <Area
                        type="monotone"
                        dataKey={key}
                        stroke={chartColor}
                        strokeWidth={2.5}
                        fill={`url(#${gradId})`}
                        isAnimationActive={false}
                        dot={false}
                        activeDot={{ r: 3, fill: chartColor, strokeWidth: 0 }}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}

export default function HardwareTab({ telemetryPaused, setTelemetryPaused }: { telemetryPaused?: boolean; setTelemetryPaused?: (v: boolean) => void }) {
  const [current, setCurrent] = useState<any>(null)
  const historyRef = useRef<any[]>([])
  const [history, setHistory] = useState<any[]>([])
  const tickRef = useRef(0)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    tickRef.current = 0
    historyRef.current = []
    setHistory([])
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    if (telemetryPaused) return
    const interval = setInterval(async () => {
      if (!mountedRef.current) return
      try {
        const t = await getTelemetry()
        if (!mountedRef.current) return
        setCurrent(t)
        const pt = {
          t: tickRef.current++,
          cpu: t.cpu_percent || 0,
          ram: t.ram_percent || 0,
          gpu: t.gpu_available ? (t.gpu_load || 0) : 0,
          vram: t.gpu_available ? (t.vram_percent || 0) : 0,
          ramUsed: t.ram_used_gb || 0,
          ramTotal: t.ram_total_gb || 0,
          vramUsed: t.gpu_available ? (t.vram_used_mb || 0) : 0,
          vramTotal: t.gpu_available ? (t.vram_total_mb || 0) : 0,
          gpuName: t.gpu_name,
          gpuAvailable: t.gpu_available,
        }
        historyRef.current = [...historyRef.current.slice(-149), pt]
        setHistory(historyRef.current)
      } catch { console.warn('Telemetry poll failed') }
    }, 3000)
    return () => clearInterval(interval)
  }, [telemetryPaused])

  const gpuAvail = current?.gpu_available

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Real-Time Host Telemetry</h2>
        <button
          onClick={() => setTelemetryPaused?.(!telemetryPaused)}
          className={`px-3 py-1 rounded text-sm font-medium ${
            telemetryPaused ? 'bg-green-600 hover:bg-green-700' : 'bg-amber-600 hover:bg-amber-700'
          } text-white transition-colors`}
        >
          {telemetryPaused ? '⏵ Resume' : '⏸ Pause'}
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Card variant="glow">
          <CardHeader className="pb-2"><CardTitle className="text-sm">CPU</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{current?.cpu_percent?.toFixed(1) ?? '—'}%</div>
          </CardContent>
        </Card>
        <Card variant="glow">
          <CardHeader className="pb-2"><CardTitle className="text-sm">System RAM</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {current ? `${current.ram_used_gb?.toFixed(1)} / ${current.ram_total_gb?.toFixed(1)} GB` : '—'}
            </div>
            <div className="text-xs text-muted-foreground">{current?.ram_percent?.toFixed(1)}%</div>
          </CardContent>
        </Card>
        <Card variant="glow">
          <CardHeader className="pb-2"><CardTitle className="text-sm">GPU Load</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {gpuAvail ? `${current.gpu_load?.toFixed(1)}%` : 'N/A'}
            </div>
            {gpuAvail && <div className="text-xs text-muted-foreground">{current.gpu_name}</div>}
          </CardContent>
        </Card>
        <Card variant="glow">
          <CardHeader className="pb-2"><CardTitle className="text-sm">VRAM</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {gpuAvail ? `${current.vram_used_mb?.toFixed(0)} / ${current.vram_total_mb?.toFixed(0)} MB` : 'N/A'}
            </div>
            {gpuAvail && <div className="text-xs text-muted-foreground">{current.vram_percent?.toFixed(1)}%</div>}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricChart title="CPU Usage" data={history.slice(-80)} dataKey="cpu" color="#3b82f6" unit="%" />
        <MetricChart title="RAM Usage" data={history.slice(-80).map(p => ({ t: p.t, v: p.ram }))} color="#10b981" unit="%" />
        <MetricChart title="GPU Load" data={history.slice(-80).map(p => ({ t: p.t, v: p.gpu }))} color="#f59e0b" unit="%" />
        <MetricChart title="VRAM Usage" data={history.slice(-80).map(p => ({ t: p.t, v: p.vram }))} color="#8b5cf6" unit="%" />
      </div>
    </div>
  )
}
