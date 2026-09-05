import type { Metadata } from 'next'
import '@/styles/globals.css'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import AnimatedBackground from '@/components/layout/AnimatedBackground'

export const metadata: Metadata = {
  title: {
    default: 'BenchMax: Local LLM Benchmarking Suite',
    template: '%s | BenchMax',
  },
  description:
    'Evaluate any LLM against 30 standardized benchmarks: 40k samples across code, knowledge, math, reasoning, vision, tool use and more. Works with LM Studio, Ollama, OpenAI and any compatible service. Free and open source (AGPL v3).',
  keywords: [
    'LLM benchmark', 'LLM evaluation', 'HumanEval', 'MMLU', 'IFEval', 'BFCL',
    'LM Studio', 'Ollama', 'local LLM', 'open source', 'AGPL', 'BenchMax',
  ],
  authors: [{ name: 'Rando', url: 'https://github.com/7amzaRando' }],
  creator: 'Rando',
  metadataBase: new URL('https://7amzarando.github.io'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://7amzarando.github.io/BenchMax/',
    siteName: 'BenchMax',
    title: 'BenchMax: Local LLM Benchmarking Suite',
    description: '30 benchmarks, 40k samples, 8 providers, sandboxed code tests. Free and open source.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'BenchMax: Local LLM Benchmarking Suite',
    description: '30 benchmarks, 40k samples. Local-first LLM evaluation. Free and open source (AGPL v3).',
  },
  robots: { index: true, follow: true },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&family=Instrument+Sans:wght@600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body suppressHydrationWarning>
        <AnimatedBackground />
        <div className="relative z-10 min-h-screen flex flex-col">
          <Navbar />
          <main className="flex-1 pt-16">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  )
}
