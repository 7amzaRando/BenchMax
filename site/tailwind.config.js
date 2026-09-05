/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: 'var(--primary)', light: 'var(--primary-light)', border: 'var(--primary-border)' },
        secondary: { DEFAULT: 'var(--secondary)' },
        accent: { DEFAULT: 'var(--accent)' },
        success: { DEFAULT: 'var(--success)' },
        warning: { DEFAULT: 'var(--warning)' },
        danger: { DEFAULT: 'var(--danger)' },
        background: 'var(--background)',
        'background-elevated': 'var(--background-elevated)',
        foreground: 'var(--foreground)',
        muted: { DEFAULT: 'var(--muted-bg)', fg: 'var(--muted-fg)' },
        card: { DEFAULT: 'var(--card-bg)', hover: 'var(--card-bg-hover)' },
        border: { DEFAULT: 'var(--border-color)', strong: 'var(--border-strong)' },
      },
      borderRadius: { lg: '0.75rem', md: '0.5rem', sm: '0.375rem', xl: '1rem', '2xl': '1.25rem' },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Geist Mono', 'monospace'],
        display: ['Instrument Sans', 'Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'aurora-1': 'auroraShift1 18s ease-in-out infinite',
        'aurora-2': 'auroraShift2 22s ease-in-out infinite',
        'aurora-3': 'auroraShift3 16s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'fade-in-up': 'fadeInUp 500ms ease-out forwards',
        'shimmer': 'shimmer 2.5s ease-in-out infinite',
        'pulse-subtle': 'pulseSubtle 3s ease-in-out infinite',
        'grid-drift': 'gridDrift 30s linear infinite',
      },
      keyframes: {
        auroraShift1: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '50%': { transform: 'translate(4%, -2%) scale(1.08)' },
        },
        auroraShift2: {
          '0%, 100%': { transform: 'translate(-2%, 2%) scale(1.05)' },
          '50%': { transform: 'translate(3%, -4%) scale(0.95)' },
        },
        auroraShift3: {
          '0%, 100%': { transform: 'translate(2%, -1%) scale(0.9)' },
          '50%': { transform: 'translate(-3%, 3%) scale(1.12)' },
        },
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(14px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        gridDrift: {
          '0%': { transform: 'translate(0, 0)' },
          '100%': { transform: 'translate(80px, 80px)' },
        },
      },
    },
  },
  plugins: [],
}
