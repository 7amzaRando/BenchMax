import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getTelemetry } from '@/lib/api'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

function MetricChart({ title, data, dataKey, color, unit }: {
    title: string;
    data: { t: number; v: number }[];
    dataKey?: string;
    color?: string;
    unit?: string;
}) {
    const chartColor = color || '#3b82f6';
    return (
        <div className="bg-card border border-border rounded-lg p-3">
            <h3 className="text-sm font-medium text-foreground mb-2">{title}</h3>
            <ResponsiveContainer width="100%" height={120}>
                <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="t" tick={false} axisLine={false} />
                    <YAxis tick={false} axisLine={false} domain={[0, 'auto']} />
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
                    <Line
                        type="monotone"
                        dataKey={dataKey || 'v'}
                        stroke={chartColor}
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}

export default function HardwareTab({ telemetryPaused, setTelemetryPaused }: { telemetryPaused?: boolean; setTelemetryPaused?: (v: boolean) => void }) {
  const [current, setCurrent] = useState<any>(null)
  const historyRef = useRef<any[]>([])
  const [history, setHistory] = useState<any[]>([])
  const tickRef = useRef(0)

  useEffect(() => {
    tickRef.current = 0
    historyRef.current = []
    setHistory([])
  }, [])

  useEffect(() => {
    if (telemetryPaused) return
    const interval = setInterval(async () => {
      try {
        const t = await getTelemetry()
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
