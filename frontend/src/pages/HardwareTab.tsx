import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getTelemetry } from '@/lib/api'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

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

      <div className="grid grid-cols-2 gap-4">
        <Card><CardHeader><CardTitle className="text-sm">CPU %</CardTitle></CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.slice(-80)}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="t" stroke="var(--chart-axis)" hide />
                <YAxis domain={[0, 100]} stroke="var(--chart-axis)" />
                <Tooltip />
                <Line type="monotone" dataKey="cpu" stroke="#3B82F6" dot={false} strokeWidth={2} name="CPU %" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card><CardHeader><CardTitle className="text-sm">RAM %</CardTitle></CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.slice(-80)}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="t" stroke="var(--chart-axis)" hide />
                <YAxis domain={[0, 100]} stroke="var(--chart-axis)" />
                <Tooltip />
                <Line type="monotone" dataKey="ram" stroke="#10B981" dot={false} strokeWidth={2} name="RAM %" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card><CardHeader><CardTitle className="text-sm">GPU Load %</CardTitle></CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.slice(-80)}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="t" stroke="var(--chart-axis)" hide />
                <YAxis domain={[0, 100]} stroke="var(--chart-axis)" />
                <Tooltip />
                <Line type="monotone" dataKey="gpu" stroke="#F59E0B" dot={false} strokeWidth={2} name="GPU %" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card><CardHeader><CardTitle className="text-sm">VRAM %</CardTitle></CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.slice(-80)}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="t" stroke="var(--chart-axis)" hide />
                <YAxis domain={[0, 100]} stroke="var(--chart-axis)" />
                <Tooltip />
                <Line type="monotone" dataKey="vram" stroke="#8B5CF6" dot={false} strokeWidth={2} name="VRAM %" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
