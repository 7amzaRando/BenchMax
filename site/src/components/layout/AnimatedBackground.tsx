'use client'

export default function AnimatedBackground() {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden bg-background" aria-hidden>
      {/* base vignette */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-5%,rgba(99,102,241,0.14),transparent_55%),radial-gradient(ellipse_70%_45%_at_85%_75%,rgba(45,212,191,0.07),transparent_50%),radial-gradient(ellipse_50%_35%_at_15%_85%,rgba(99,102,241,0.06),transparent_50%)]" />

      {/* aurora blobs */}
      <div
        className="absolute -top-28 left-1/2 -translate-x-1/2 w-[900px] h-[520px] rounded-full blur-[110px] opacity-[0.45] animate-aurora-1"
        style={{ background: 'radial-gradient(ellipse at 50% 50%, rgba(99,102,241,0.35) 0%, rgba(79,70,229,0.18) 40%, transparent 72%)' }}
      />
      <div
        className="absolute top-[42%] -right-24 w-[560px] h-[560px] rounded-full blur-[100px] opacity-[0.18] animate-aurora-2"
        style={{ background: 'radial-gradient(circle, rgba(45,212,191,0.28), transparent 70%)' }}
      />
      <div
        className="absolute bottom-[8%] left-[12%] w-[420px] h-[420px] rounded-full blur-[90px] opacity-[0.12] animate-aurora-3"
        style={{ background: 'radial-gradient(circle, rgba(251,146,60,0.22), transparent 70%)' }}
      />

      {/* subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.9) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.9) 1px, transparent 1px)',
          backgroundSize: '72px 72px',
        }}
      />

      {/* top hairline glow */}
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />

      {/* bottom fade: ensures content legibility */}
      <div className="absolute inset-x-0 bottom-0 h-[28%] bg-gradient-to-t from-background to-transparent" />
    </div>
  )
}
