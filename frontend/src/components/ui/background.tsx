import React, { useRef, useEffect, useState } from 'react'

interface BackgroundProps {
  intensity?: 'subtle' | 'moderate' | 'animated';
}

const glow = 'rgba(99, 102, 241, 0.12)'
const accent = 'rgba(129, 140, 248, 0.08)'

const COLORS = [
  'rgba(99, 102, 241, 0.7)',
  'rgba(45, 212, 191, 0.6)',
  'rgba(251, 191, 36, 0.6)',
  'rgba(129, 140, 248, 0.7)',
  'rgba(248, 113, 113, 0.5)',
  'rgba(232, 121, 249, 0.5)',
]

const FIREFLIES = Array.from({ length: 35 }, (_, i) => ({
  id: i,
  top: `${Math.random() * 95 + 2}%`,
  left: `${Math.random() * 95 + 2}%`,
  size: 3 + Math.random() * 5,
  delay: `${Math.random() * 6}s`,
  duration: 10 + Math.random() * 12,
  color: COLORS[i % COLORS.length],
}))

export default function Background({ intensity = 'subtle' }: BackgroundProps) {
  const zoneRef = useRef<HTMLDivElement>(null)
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 })

  useEffect(() => {
    const el = zoneRef.current
    if (!el) return
    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      setMouse({
        x: (e.clientX - rect.left) / rect.width,
        y: (e.clientY - rect.top) / rect.height,
      })
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  const cx = mouse.x * 100
  const cy = mouse.y * 100

  return (
    <div className="ambient-bg" ref={zoneRef}>
      <div className="absolute top-[50%] left-[50%] -translate-x-1/2 -translate-y-1/2"
        style={{ width: '50rem', height: '50rem', background: `radial-gradient(circle, ${glow} 0%, transparent 70%)`, pointerEvents: 'none' }}
      />
      {intensity !== 'subtle' && (
        <>
          <div className="ambient-layer" style={{ top: '-15%', left: '-10%', width: '35rem', height: '35rem', background: glow, opacity: 0.5, animation: 'ambientShiftLayer1 14s ease-in-out infinite alternate' }} />
          <div className="ambient-layer" style={{ top: '25%', right: '-5%', width: '45rem', height: '45rem', background: accent, opacity: 0.5, animation: 'ambientShiftLayer2 18s ease-in-out infinite alternate' }} />
          <div className="ambient-layer" style={{ bottom: '-5%', left: '15%', width: '50rem', height: '50rem', background: glow, opacity: 0.5, animation: 'ambientShiftLayer3 16s ease-in-out infinite alternate 8s' }} />
        </>
      )}

      <div className="absolute inset-0"
        style={{ backgroundImage: `linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)`, backgroundSize: '80px 80px', pointerEvents: 'none' }}
      />

      <div className="firefly-zone" style={{ pointerEvents: 'none' }}>
        {FIREFLIES.map(f => {
          const dx = (parseFloat(f.left) - cx) * 0.15
          const dy = (parseFloat(f.top) - cy) * 0.15
          const dist = Math.sqrt(dx * dx + dy * dy)
          const pull = Math.max(0, 1 - dist / 20) * 30
          const sizeBoost = pull * 0.15
          return (
            <div key={f.id} className="firefly"
              style={{
                top: f.top, left: f.left,
                width: `${f.size + sizeBoost}px`, height: `${f.size + sizeBoost}px`,
                background: f.color,
                boxShadow: `0 0 ${(f.size + sizeBoost) * 3}px ${f.color}`,
                animationDelay: f.delay,
                animationDuration: `${f.duration}s`,
                transform: `translate(${dx}px, ${dy}px)`,
              }}
            />
          )
        })}
      </div>
    </div>
  )
}
