import { createContext, useContext, useReducer, useCallback, useEffect, useRef, useMemo, type ReactNode } from 'react'
import type { PollResponse, ModelMetadata } from './api'

export interface ConnectionState {
  apiUrl: string
  apiKey: string
  connected: boolean
  models: string[]
  selectedModel: string
  metadata: Record<string, ModelMetadata>
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

const defaultConnection: ConnectionState = {
  apiUrl: 'http://127.0.0.1:1234/v1',
  apiKey: '',
  connected: false,
  models: [],
  selectedModel: '',
  metadata: {},
}

const initialState: BenchMaxState = {
  activeTab: 'connection',
  activeRunId: null,
  activeBatchId: null,
  connection: defaultConnection,
  runStatus: null,
  darkMode: typeof window !== 'undefined' ? localStorage.getItem('benchmax-theme-dark') !== 'false' : true,
  telemetryPaused: false,
  serverOnline: true,
  sparkData: [],
  hardwareHistory: [],
  hardwareTick: 0,
  pendingRerun: null,
  historyRefreshKey: 0,
  showShortcuts: false,
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
  const value = useMemo(() => ({ state, dispatch }), [state, dispatch])
  return (
    <BenchMaxContext.Provider value={value}>
      {children}
    </BenchMaxContext.Provider>
  )
}
