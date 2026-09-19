import { createContext, useContext, useReducer, type ReactNode } from 'react'
import type { PollResponse, ModelMetadata } from './api'

export interface ConnectionState {
  apiUrl: string
  apiKey: string
  connected: boolean
  models: string[]
  selectedModel: string
  metadata: Record<string, ModelMetadata>
}

export interface RunDefaults {
  temperature: number
  useCustomTemp: boolean
  maxTokens: number
  systemPrompt: string
  quickTest: boolean
  disableRepDetection: boolean
  contextLength: number
}

export interface Settings {
  runDefaults: RunDefaults
  exportFormat: 'CSV' | 'JSON' | 'XLSX'
  runPollMs: number
  hardwarePollMs: number
  healthPollMs: number
  providerUrl: string
  telemetryPausedByDefault: boolean
  updateCheckEnabled: boolean
}

export interface BenchMaxState {
  activeTab: string
  activeRunId: number | null
  activeBatchId: string | null
  connection: ConnectionState
  runStatus: PollResponse | null
  darkMode: boolean
  telemetryPaused: boolean
  serverOnline: boolean
  sparkData: { cpu: number; gpu: number }[]
  hardwareHistory: { t: number; cpu: number; ram: number; gpu: number; vram: number }[]
  hardwareTick: number
  pendingRerun: { model: string; benchmark: string; params: Record<string, unknown> } | null
  historyRefreshKey: number
  showShortcuts: boolean
  settings: Settings
}

export type Action =
  | { type: 'SET_ACTIVE_TAB'; payload: string }
  | { type: 'SET_ACTIVE_RUN_ID'; payload: number | null }
  | { type: 'SET_ACTIVE_BATCH_ID'; payload: string | null }
  | { type: 'SET_CONNECTION'; payload: Partial<ConnectionState> }
  | { type: 'SET_RUN_STATUS'; payload: PollResponse | null }
  | { type: 'SET_DARK_MODE'; payload: boolean }
  | { type: 'SET_TELEMETRY_PAUSED'; payload: boolean }
  | { type: 'SET_SERVER_ONLINE'; payload: boolean }
  | { type: 'SET_SPARK_DATA'; payload: { cpu: number; gpu: number }[] }
  | { type: 'SET_HARDWARE_HISTORY'; payload: { t: number; cpu: number; ram: number; gpu: number; vram: number }[] }
  | { type: 'APPEND_HARDWARE_TICK'; payload: { cpu: number; ram: number; gpu: number; vram: number } }
  | { type: 'SET_PENDING_RERUN'; payload: { model: string; benchmark: string; params: Record<string, unknown> } | null }
  | { type: 'INCREMENT_HISTORY_REFRESH' }
  | { type: 'SET_SHOW_SHORTCUTS'; payload: boolean }
  | { type: 'SET_SETTINGS'; payload: Omit<Partial<Settings>, 'runDefaults'> & { runDefaults?: Partial<RunDefaults> } }
  | { type: 'RESET_SETTINGS' }

const defaultConnection: ConnectionState = {
  apiUrl: 'http://127.0.0.1:1234/v1',
  apiKey: '',
  connected: false,
  models: [],
  selectedModel: '',
  metadata: {},
}

const SETTINGS_KEY = 'benchmax-settings'

export const DEFAULT_SETTINGS: Settings = {
  runDefaults: {
    temperature: 0.0,
    useCustomTemp: false,
    maxTokens: 8192,
    systemPrompt: 'You are a precise AI assistant. Follow instructions exactly. Give direct, concise answers without preamble or explanation.',
    quickTest: false,
    disableRepDetection: false,
    contextLength: 65536,
  },
  exportFormat: 'CSV',
  runPollMs: 3000,
  hardwarePollMs: 3000,
  healthPollMs: 30000,
  providerUrl: 'http://127.0.0.1:1234/v1',
  telemetryPausedByDefault: false,
  updateCheckEnabled: true,
}

function loadSettings(): Settings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return DEFAULT_SETTINGS
    const parsed = JSON.parse(raw) as Partial<Settings>
    return {
      ...DEFAULT_SETTINGS,
      ...parsed,
      runDefaults: { ...DEFAULT_SETTINGS.runDefaults, ...(parsed.runDefaults || {}) },
    }
  } catch {
    return DEFAULT_SETTINGS
  }
}

const loadedSettings = loadSettings()

const initialState: BenchMaxState = {
  activeTab: 'connection',
  activeRunId: null,
  activeBatchId: null,
  connection: { ...defaultConnection, apiUrl: loadedSettings.providerUrl || defaultConnection.apiUrl },
  runStatus: null,
  darkMode: typeof window !== 'undefined' ? localStorage.getItem('benchmax-theme-dark') !== 'false' : true,
  telemetryPaused: loadedSettings.telemetryPausedByDefault,
  serverOnline: true,
  sparkData: [],
  hardwareHistory: [],
  hardwareTick: 0,
  pendingRerun: null,
  historyRefreshKey: 0,
  showShortcuts: false,
  settings: loadedSettings,
}

function reducer(state: BenchMaxState, action: Action): BenchMaxState {
  switch (action.type) {
    case 'SET_ACTIVE_TAB':
      return { ...state, activeTab: action.payload }
    case 'SET_ACTIVE_RUN_ID':
      return { ...state, activeRunId: action.payload }
    case 'SET_ACTIVE_BATCH_ID':
      return { ...state, activeBatchId: action.payload }
    case 'SET_CONNECTION':
      return { ...state, connection: { ...state.connection, ...action.payload } }
    case 'SET_RUN_STATUS':
      return { ...state, runStatus: action.payload }
    case 'SET_DARK_MODE':
      return { ...state, darkMode: action.payload }
    case 'SET_TELEMETRY_PAUSED':
      return { ...state, telemetryPaused: action.payload }
    case 'SET_SERVER_ONLINE':
      return { ...state, serverOnline: action.payload }
    case 'SET_SPARK_DATA':
      return { ...state, sparkData: action.payload }
    case 'SET_HARDWARE_HISTORY':
      return { ...state, hardwareHistory: action.payload }
    case 'APPEND_HARDWARE_TICK':
      {
        const nextTick = state.hardwareTick + 1
        const next = [...state.hardwareHistory.slice(-149), { t: state.hardwareTick, ...action.payload }]
        return { ...state, hardwareHistory: next, hardwareTick: nextTick }
      }
    case 'SET_PENDING_RERUN':
      return { ...state, pendingRerun: action.payload }
    case 'INCREMENT_HISTORY_REFRESH':
      return { ...state, historyRefreshKey: state.historyRefreshKey + 1 }
    case 'SET_SHOW_SHORTCUTS':
      return { ...state, showShortcuts: action.payload }
    case 'SET_SETTINGS': {
      const { runDefaults, ...rest } = action.payload
      return {
        ...state,
        settings: {
          ...state.settings,
          ...rest,
          runDefaults: { ...state.settings.runDefaults, ...(runDefaults || {}) },
        },
      }
    }
    case 'RESET_SETTINGS':
      return { ...state, settings: DEFAULT_SETTINGS }
    default:
      return state
  }
}

interface BenchMaxContextValue {
  state: BenchMaxState
  dispatch: React.Dispatch<Action>
}

const BenchMaxContext = createContext<BenchMaxContextValue | null>(null)

export function useApp(): BenchMaxContextValue {
  const ctx = useContext(BenchMaxContext)
  if (!ctx) throw new Error('useApp must be used within BenchMaxProvider')
  return ctx
}

export function BenchMaxProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  return (
    <BenchMaxContext.Provider value={{ state, dispatch }}>
      {children}
    </BenchMaxContext.Provider>
  )
}
