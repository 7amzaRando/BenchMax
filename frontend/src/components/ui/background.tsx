export default function Background() {
  return (
    <div className="ambient-bg" aria-hidden>
      {/* base */}
      <div className="absolute inset-0 bg-background" />
      {/* subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.035] dark:opacity-[0.06]"
        style={{
          backgroundImage:
            'linear-gradient(var(--border-color) 1px, transparent 1px), linear-gradient(90deg, var(--border-color) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />
      {/* radial accents */}
      <div
        className="absolute -top-[30%] left-1/2 -translate-x-1/2 w-[900px] h-[520px] rounded-full blur-[80px] opacity-[0.08] dark:opacity-[0.10]"
        style={{ background: 'radial-gradient(ellipse at center, var(--primary) 0%, transparent 70%)' }}
      />
      <div
        className="absolute top-[18%] right-[-8%] w-[560px] h-[560px] rounded-full blur-[90px] opacity-[0.06] dark:opacity-[0.08]"
        style={{ background: 'radial-gradient(circle, var(--secondary) 0%, transparent 70%)' }}
      />
      <div
        className="absolute bottom-[-12%] left-[-6%] w-[640px] h-[480px] rounded-full blur-[90px] opacity-[0.05] dark:opacity-[0.06]"
        style={{ background: 'radial-gradient(circle, #8b5cf6 0%, transparent 70%)' }}
      />
    </div>
  )
}
