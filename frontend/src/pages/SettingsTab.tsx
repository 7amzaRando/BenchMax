import { useEffect, useState } from 'react'
import { useApp, type Action } from '@/lib/context'
import * as api from '@/lib/api'
import { useToast } from '@/components/ui/toast-provider'
import { CopyButton } from '@/components/ui/copy-button'

type SettingsPatch = Extract<Action, { type: 'SET_SETTINGS' }>['payload']

function Section({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
      <p className="text-xs text-muted-foreground mt-0.5 mb-4">{desc}</p>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium">{label}</span>
      {hint && <span className="block text-[11px] text-muted-foreground font-normal mt-0.5">{hint}</span>}
      <div className="mt-1.5">{children}</div>
    </label>
  )
}

const inputCls = 'flex h-9 w-full rounded-lg border border-border bg-card px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/40'

function mcpSnippet(mcp: api.McpInfo, client: string, origin: string): string {
  const [py, srv] = mcp.stdio_command
  const env = { BENCHMAX_URL: origin }
  if (client === 'opencode') {
    return JSON.stringify({ mcp: { benchmax: { type: 'local', command: [py, srv], environment: env, enabled: true } } }, null, 2)
  }
  if (client === 'vscode') {
    return JSON.stringify({ servers: { benchmax: { type: 'stdio', command: py, args: [srv], env } } }, null, 2)
  }
  return JSON.stringify({ mcpServers: { benchmax: { command: py, args: [srv], env } } }, null, 2)
}

export default function SettingsTab() {
  const { state, dispatch } = useApp()
  const { toast } = useToast()
  const s = state.settings
  const rd = s.runDefaults
  const set = (p: SettingsPatch) => dispatch({ type: 'SET_SETTINGS', payload: p })

  // — Access & secrets (server-backed, local state) —
  const [lanSet, setLanSet] = useState<boolean | null>(null)
  const [newPw, setNewPw] = useState('')
  const [newPw2, setNewPw2] = useState('')
  const [hfToken, setHfToken] = useState('')
  const [hfSaved, setHfSaved] = useState(false)
  const [lbKey, setLbKey] = useState('')
  const [lbSaved, setLbSaved] = useState(false)
  const [mcp, setMcp] = useState<api.McpInfo | null>(null)
  const [mcpClient, setMcpClient] = useState('claude')
  const [mcpInstalled, setMcpInstalled] = useState<string | null>(null)

  useEffect(() => {
    api.authStatus().then(r => setLanSet(r.password_set)).catch(() => setLanSet(null))
    api.getMcpInfo().then(setMcp).catch(() => setMcp(null))
    api.getHfToken().then(r => {
      const t = (r as { token?: string }).token || ''
      if (t.includes('*')) { setHfToken(''); setHfSaved(true) }
      else { setHfToken(t); setHfSaved(!!t) }
    }).catch(() => {})
    api.getLeaderboardSettings().then((d: { api_key?: string }) => {
      const k = d.api_key || ''
      if (k.includes('*')) { setLbKey(''); setLbSaved(true) }
      else { setLbKey(k); setLbSaved(!!k) }
    }).catch(() => {})
  }, [])

  const savePassword = async () => {
    if (!newPw || newPw !== newPw2) {
      toast({ title: 'Passwords do not match', description: 'Type the same password twice.', variant: 'error' })
      return
    }
    try {
      await api.authSetup(newPw)
      setLanSet(true); setNewPw(''); setNewPw2('')
      toast({ title: 'Password set', description: 'LAN visitors will now see the login screen.', variant: 'success' })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      toast({ title: 'Could not set password', description: msg.includes('403') ? 'Set the password from the server machine itself, not over the network.' : msg, variant: 'error' })
    }
  }

  const forgetToken = () => {
    try { localStorage.removeItem('bm_lan_token') } catch { /* ignore */ }
    toast({ title: 'Browser token forgotten', description: 'You will be asked to log in again on next visit.', variant: 'success' })
  }

  return (
    <div className="space-y-5 max-w-[860px]">
      <Section title="Run defaults" desc="Starting values for every new run. You can still override them per run on the Run tab.">
        <div className="grid sm:grid-cols-2 gap-4">
          <Row label="Temperature" hint="Applied only when Use custom temperature is on — otherwise the model default is used.">
            <div className="flex items-center gap-3">
              <input
                type="range" min={0} max={1} step={0.05} value={rd.temperature}
                onChange={e => set({ runDefaults: { temperature: parseFloat(e.target.value) } })}
                className="flex-1" aria-label="Default temperature"
              />
              <span className="text-xs font-mono w-10 text-right">{rd.temperature.toFixed(2)}</span>
            </div>
            <label className="mt-2 flex items-center gap-2 text-xs">
              <input type="checkbox" checked={rd.useCustomTemp} onChange={e => set({ runDefaults: { useCustomTemp: e.target.checked } })} />
              Use custom temperature
            </label>
          </Row>
          <Row label="Max tokens" hint="Upper bound per model answer.">
            <input
              type="number" min={256} max={131072} step={256} value={rd.maxTokens}
              onChange={e => set({ runDefaults: { maxTokens: Math.max(256, parseInt(e.target.value) || 8192) } })}
              className={inputCls} aria-label="Default max tokens"
            />
          </Row>
        </div>
        <Row label="System prompt" hint="Sent with every run unless you change it on the Run tab.">
          <textarea
            value={rd.systemPrompt} rows={2}
            onChange={e => set({ runDefaults: { systemPrompt: e.target.value } })}
            className={`${inputCls} h-auto py-2`} aria-label="Default system prompt"
          />
        </Row>
        <div className="grid sm:grid-cols-3 gap-4">
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={rd.quickTest} onChange={e => set({ runDefaults: { quickTest: e.target.checked } })} />
            Quick test by default
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={rd.disableRepDetection} onChange={e => set({ runDefaults: { disableRepDetection: e.target.checked } })} />
            Disable loop detection
          </label>
          <Row label="NIAHS context length">
            <input
              type="number" min={1000} max={250000} step={1000} value={rd.contextLength}
              onChange={e => set({ runDefaults: { contextLength: Math.min(250000, Math.max(1000, parseInt(e.target.value) || 65536)) } })}
              className={inputCls} aria-label="Default NIAHS context length"
            />
          </Row>
        </div>
      </Section>

      <Section title="Live updates" desc="How often the dashboard refreshes. Lower is livelier; higher saves CPU and database load. Applies instantly.">
        <div className="grid sm:grid-cols-3 gap-4">
          <Row label={`Run progress — ${s.runPollMs / 1000}s`} hint="Fallback when streaming is unavailable.">
            <input
              type="range" min={1000} max={10000} step={1000} value={s.runPollMs}
              onChange={e => set({ runPollMs: parseInt(e.target.value) })}
              className="w-full" aria-label="Run poll interval"
            />
          </Row>
          <Row label={`Hardware telemetry — ${s.hardwarePollMs / 1000}s`} hint="CPU/RAM/GPU gauges and history.">
            <input
              type="range" min={1000} max={30000} step={1000} value={s.hardwarePollMs}
              onChange={e => set({ hardwarePollMs: parseInt(e.target.value) })}
              className="w-full" aria-label="Hardware poll interval"
            />
          </Row>
          <Row label={`Server health — ${s.healthPollMs / 1000}s`} hint="Online/offline pill in the footer.">
            <input
              type="range" min={15000} max={120000} step={15000} value={s.healthPollMs}
              onChange={e => set({ healthPollMs: parseInt(e.target.value) })}
              className="w-full" aria-label="Health check interval"
            />
          </Row>
        </div>
        <Row label="Default export format" hint="Used by one-click exports across History and Leaderboard.">
          <select
            value={s.exportFormat}
            onChange={e => set({ exportFormat: e.target.value as 'CSV' | 'JSON' | 'XLSX' })}
            className={`${inputCls} max-w-[220px]`} aria-label="Default export format"
          >
            <option value="CSV">CSV</option>
            <option value="JSON">JSON</option>
            <option value="XLSX">Excel</option>
          </select>
        </Row>
      </Section>

      <Section title="Appearance" desc="Theme applies instantly and is remembered on this browser.">
        <div className="flex items-center gap-3">
          <button
            onClick={() => dispatch({ type: 'SET_DARK_MODE', payload: !state.darkMode })}
            className="px-4 py-2 rounded-lg border border-border bg-muted hover:bg-muted/70 text-sm font-medium"
          >
            Switch to {state.darkMode ? 'light' : 'dark'} mode
          </button>
          <span className="text-xs text-muted-foreground">Currently {state.darkMode ? 'dark' : 'light'}</span>
        </div>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox" checked={s.telemetryPausedByDefault}
            onChange={e => set({ telemetryPausedByDefault: e.target.checked })}
          />
          Pause hardware telemetry by default
        </label>
      </Section>

      <Section title="Provider" desc="Default server address for fresh sessions. Changing it also updates the Connection tab right now.">
        <Row label="Default provider URL" hint="LM Studio, Ollama, or any OpenAI-compatible endpoint.">
          <input
            value={s.providerUrl}
            onChange={e => {
              set({ providerUrl: e.target.value })
              dispatch({ type: 'SET_CONNECTION', payload: { apiUrl: e.target.value } })
            }}
            className={`${inputCls} max-w-[420px] font-mono`} aria-label="Default provider URL"
          />
        </Row>
      </Section>

      <Section title="Access & secrets" desc="Who can reach this server, and the keys it stores. Provider API keys are never stored — they travel in memory only.">
        <div>
          <span className="text-xs font-medium">LAN password</span>
          <span className="block text-[11px] text-muted-foreground mt-0.5">
            {lanSet === null ? 'Checking…' : lanSet ? 'Set — network visitors see a login screen.' : 'Not set — anyone on your network can use the server.'}
          </span>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <input
              type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
              placeholder="New password" className={`${inputCls} max-w-[220px]`} aria-label="New LAN password"
            />
            <input
              type="password" value={newPw2} onChange={e => setNewPw2(e.target.value)}
              placeholder="Repeat password" className={`${inputCls} max-w-[220px]`} aria-label="Repeat LAN password"
            />
            <button onClick={savePassword} className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-[var(--primary-dark)]">
              Set password
            </button>
            <button onClick={forgetToken} className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-muted">
              Forget this browser
            </button>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1.5">Setting works only from the server machine itself. Forgotten password? Stop the server, delete <code className="font-mono">records/.lan_password</code>, restart.</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <span className="text-xs font-medium">HuggingFace token {hfSaved && <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900">saved</span>}</span>
            <span className="block text-[11px] text-muted-foreground mt-0.5">Needed to download gated datasets.</span>
            <div className="mt-1.5 flex gap-2">
              <input
                type="password" value={hfToken} onChange={e => setHfToken(e.target.value)}
                placeholder={hfSaved ? 'Saved — type to replace' : 'hf_…'} className={inputCls} aria-label="HuggingFace token"
              />
              <button
                onClick={async () => { await api.setHfToken(hfToken); setHfSaved(!!hfToken); toast({ title: 'HuggingFace token saved', variant: 'success' }) }}
                className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-[var(--primary-dark)] shrink-0"
              >
                Save
              </button>
            </div>
          </div>
          <div>
            <span className="text-xs font-medium">Leaderboard key {lbSaved && <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900">saved</span>}</span>
            <span className="block text-[11px] text-muted-foreground mt-0.5">Needed for online leaderboard sync.</span>
            <div className="mt-1.5 flex gap-2">
              <input
                type="password" value={lbKey} onChange={e => setLbKey(e.target.value)}
                placeholder={lbSaved ? 'Saved — type to replace' : 'API key'} className={inputCls} aria-label="Leaderboard API key"
              />
              <button
                onClick={async () => { await api.saveLeaderboardSettings(lbKey); setLbSaved(!!lbKey); toast({ title: 'Leaderboard key saved', variant: 'success' }) }}
                className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-[var(--primary-dark)] shrink-0"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      </Section>

      <Section title="AI access (MCP)" desc="Let AI apps (Claude, Cursor, VS Code, OpenCode) drive BenchMax for you. One click connects them all.">
        <div>
          <span className="text-xs font-medium">Status</span>
          <span className="block text-[11px] text-muted-foreground mt-0.5">
            {mcp === null ? 'Checking…' : mcp.mounted
              ? `Live — ${mcp.tools.length} tools (${mcp.tools.join(', ')}).`
              : 'Not mounted — the server started without the MCP package; reinstall requirements.'}
          </span>
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={async () => {
                try {
                  const r = await api.installMcp({ clients: ['all'], url: window.location.origin })
                  const names = Object.keys(r.configs).join(', ')
                  setMcpInstalled(`Connected ${names}. Restart your AI app to pick it up.`)
                  toast({ title: 'MCP installed', description: `Wrote configs for ${names}.`, variant: 'success' })
                } catch (e: unknown) {
                  const msg = e instanceof Error ? e.message : String(e)
                  toast({ title: 'Install failed', description: msg.includes('403') ? 'Click this from the server machine itself, not over the network.' : msg, variant: 'error' })
                }
              }}
              className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-[var(--primary-dark)]"
            >
              Connect all my apps
            </button>
            {mcpInstalled && <span className="text-[11px] text-muted-foreground">{mcpInstalled}</span>}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1.5">Writes BenchMax into the settings of Claude Desktop, OpenCode, Cursor, and VS Code on this machine. Same as running <code className="font-mono">{mcp?.install_command ?? 'py cli.py install-mcp --client all'}</code>. Only works from the server machine itself.</p>
        </div>
        {mcp !== null && (
          <details>
            <summary className="text-xs font-medium cursor-pointer hover:text-foreground">Manual setup (paste the config yourself)</summary>
            <div className="mt-3 space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <span className="text-xs font-medium">Remote endpoint</span>
                  <span className="block text-[11px] text-muted-foreground mt-0.5">Streamable HTTP. LAN clients must send your Bearer token.</span>
                  <div className="mt-1.5 flex items-center gap-1">
                    <input readOnly value={`${window.location.origin}${mcp.endpoint}`} className={`${inputCls} font-mono`} aria-label="MCP endpoint URL" />
                    <CopyButton value={`${window.location.origin}${mcp.endpoint}`} />
                  </div>
                </div>
                <div>
                  <span className="text-xs font-medium">Local command (stdio)</span>
                  <span className="block text-[11px] text-muted-foreground mt-0.5">What the app launches on the server machine.</span>
                  <div className="mt-1.5 flex items-center gap-1">
                    <input readOnly value={mcp.stdio_command.join(' ')} className={`${inputCls} font-mono`} aria-label="MCP stdio command" />
                    <CopyButton value={mcp.stdio_command.join(' ')} />
                  </div>
                </div>
              </div>
              <div>
                <span className="text-xs font-medium">App config</span>
                <span className="block text-[11px] text-muted-foreground mt-0.5">Pick your app, copy into its MCP settings file.</span>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <select
                    value={mcpClient} onChange={e => setMcpClient(e.target.value)}
                    className={`${inputCls} max-w-[220px]`} aria-label="MCP client app"
                  >
                    <option value="claude">Claude Desktop</option>
                    <option value="opencode">OpenCode</option>
                    <option value="cursor">Cursor</option>
                    <option value="vscode">VS Code</option>
                  </select>
                  <CopyButton value={mcpSnippet(mcp, mcpClient, window.location.origin)} />
                </div>
                <pre className="mt-1.5 max-h-44 overflow-auto rounded-lg border border-border bg-muted/40 p-3 text-[11px] font-mono whitespace-pre-wrap">{mcpSnippet(mcp, mcpClient, window.location.origin)}</pre>
              </div>
            </div>
          </details>
        )}
      </Section>

      <Section title="Updates" desc="BenchMax checks GitHub releases for a newer version. No auto-install — you always choose.">
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox" checked={s.updateCheckEnabled}
            onChange={e => set({ updateCheckEnabled: e.target.checked })}
          />
          Check for updates automatically (at most once a day)
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={async () => {
              try {
                const v = await api.getVersion(true)
                try { localStorage.setItem('bm_update_last_check', String(Date.now())) } catch { /* ignore */ }
                toast({
                  title: v.update_available ? `v${v.latest} available` : 'Up to date',
                  description: v.update_available ? 'See the banner at the top of the page.' : `You are on v${v.current}.`,
                  variant: v.update_available ? 'success' : 'success',
                })
              } catch {
                toast({ title: 'Update check failed', description: 'Could not reach GitHub releases (offline?).', variant: 'error' })
              }
            }}
            className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-muted"
          >
            Check now
          </button>
          <span className="text-[11px] text-muted-foreground">Checking contacts api.github.com once a day at most. Turn it off for a fully offline app.</span>
        </div>
      </Section>

      <Section title="Data" desc="Your runs live in records/benchmax.db on the server machine.">
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={api.exportHistoryLink()}
            className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-[var(--primary-dark)]"
          >
            Download full history ({s.exportFormat})
          </a>
          <button
            onClick={() => { dispatch({ type: 'RESET_SETTINGS' }); toast({ title: 'Settings reset', description: 'All defaults restored.', variant: 'success' }) }}
            className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-muted"
          >
            Reset all settings
          </button>
        </div>
        <p className="text-[11px] text-muted-foreground">Back up by stopping the server and copying <code className="font-mono">records/benchmax.db</code>. Deleting runs happens on the History tab, where each row can be reviewed first.</p>
      </Section>

      <Section title="About" desc="What this is and where to get help.">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="font-mono font-medium text-foreground">BenchMax v2.0.3</span>
          <span>30 benchmarks · fully local</span>
          <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noreferrer" className="hover:text-foreground underline-offset-4 hover:underline">GitHub</a>
          <a href="https://7amzarando.github.io/BenchMax/docs/" target="_blank" rel="noreferrer" className="hover:text-foreground underline-offset-4 hover:underline">Docs</a>
          <span>License AGPL-3.0</span>
        </div>
      </Section>
    </div>
  )
}
