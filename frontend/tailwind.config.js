/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'var(--border-color)',
        input: 'var(--border-color)',
        ring: 'var(--primary-light)',
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        primary: {
          DEFAULT: 'rgb(var(--primary-rgb) / <alpha-value>)',
          light: 'rgb(var(--primary-light-rgb) / <alpha-value>)',
          border: 'var(--primary-border)',
          foreground: '#ffffff',
        },
        secondary: {
          DEFAULT: 'rgb(var(--secondary-rgb) / <alpha-value>)',
          foreground: '#ffffff',
        },
        destructive: {
          DEFAULT: 'rgb(var(--danger-rgb) / <alpha-value>)',
          foreground: '#ffffff',
        },
        muted: {
          DEFAULT: 'var(--muted-bg)',
          foreground: 'var(--muted-fg)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          foreground: '#ffffff',
        },
        card: {
          DEFAULT: 'var(--card-bg)',
          foreground: 'var(--foreground)',
        },
        popover: {
          DEFAULT: 'var(--card-bg)',
          foreground: 'var(--foreground)',
        },
        success: {
          DEFAULT: 'rgb(var(--success-rgb) / <alpha-value>)',
        },
        warning: {
          DEFAULT: 'rgb(var(--warning-rgb) / <alpha-value>)',
        },
        danger: {
          DEFAULT: 'rgb(var(--danger-rgb) / <alpha-value>)',
        },
      },
      borderRadius: {
        lg: '0.75rem',
        md: '0.5rem',
        sm: '0.375rem',
      },
    },
  },
  plugins: [],
}
