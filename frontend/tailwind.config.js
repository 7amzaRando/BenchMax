/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        border: 'var(--border-color)',
        input: 'var(--border-color)',
        ring: 'var(--primary)',
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        primary: {
          DEFAULT: 'var(--primary)',
          light: 'var(--primary-light)',
          foreground: '#ffffff',
        },
        secondary: {
          DEFAULT: 'var(--secondary)',
          foreground: '#ffffff',
        },
        destructive: {
          DEFAULT: 'var(--danger)',
          foreground: '#ffffff',
        },
        muted: {
          DEFAULT: 'var(--muted-bg)',
          foreground: 'var(--muted-fg)',
        },
        card: {
          DEFAULT: 'var(--card-bg)',
          foreground: 'var(--foreground)',
        },
      },
      borderRadius: {
        lg: '0.75rem',
        md: '0.5rem',
        sm: '0.375rem',
      },
      boxShadow: {
        soft: '0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05)',
        card: '0 4px 16px -4px rgb(0 0 0 / 0.08), 0 2px 8px -2px rgb(0 0 0 / 0.06)',
        elevated: '0 12px 32px -8px rgb(0 0 0 / 0.12), 0 4px 16px -4px rgb(0 0 0 / 0.08)',
      },
      keyframes: {
        in: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-in': { from: { transform: 'translateX(-100%)' }, to: { transform: 'translateX(0)' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        pulse2: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.5' } },
      },
      animation: {
        in: 'in 0.35s ease-out forwards',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-in': 'slide-in 0.25s ease-out',
      },
    },
  },
  plugins: [],
}
