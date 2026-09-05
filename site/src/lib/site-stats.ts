import { TOTAL_BENCHMARKS, TOTAL_SAMPLES_DISPLAY } from './benchmarks-data'

// Single source of truth for hero / footer stats
export const SITE_STATS = [
  { value: String(TOTAL_BENCHMARKS), label: 'Benchmarks', sublabel: '12 categories' },
  { value: '8', label: 'Providers', sublabel: 'local or cloud services' },
  { value: TOTAL_SAMPLES_DISPLAY, label: 'Total Samples', sublabel: 'largest: MMLU-Pro 12k' },
  { value: '5', label: 'Sandboxed coding tests', sublabel: 'the rest need no setup' },
] as const
