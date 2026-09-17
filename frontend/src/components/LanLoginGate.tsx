import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { authLogin, authStatus } from '@/lib/api';

type GateState =
  | { kind: 'loading' }
  | { kind: 'open' }
  | { kind: 'no-password' }
  | { kind: 'login' };

export default function LanLoginGate({ children }: { children: ReactNode }) {
  const [gate, setGate] = useState<GateState>({ kind: 'loading' });
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const check = useCallback(async () => {
    setGate({ kind: 'loading' });
    setError('');
    try {
      const s = await authStatus();
      if (!s.lan_required || s.authenticated) {
        setGate({ kind: 'open' });
      } else if (!s.password_set) {
        setGate({ kind: 'no-password' });
      } else {
        setGate({ kind: 'login' });
      }
    } catch {
      // If the status endpoint is unreachable (e.g. server down), do not
      // block the app — the existing ServerStatusBanner covers that case.
      setGate({ kind: 'open' });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  const submit = useCallback(async () => {
    if (!password || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await authLogin(password);
      try {
        localStorage.setItem('bm_lan_token', res.token);
      } catch {
        /* storage unavailable — still unlock for this session */
      }
      setGate({ kind: 'open' });
    } catch (e) {
      setError(e instanceof Error && e.message.includes('HTTP 401') ? 'Wrong password — try again.' : 'Login failed — try again.');
    } finally {
      setSubmitting(false);
    }
  }, [password, submitting]);

  if (gate.kind === 'loading') {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (gate.kind === 'open') return <>{children}</>;

  if (gate.kind === 'no-password') {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-8">
        <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center shadow-sm space-y-4">
          <h1 className="text-xl font-bold font-display">LAN access locked</h1>
          <p className="text-sm text-muted-foreground">
            This BenchMax server is shared on the network and has no LAN password yet. Ask the server owner to run: py cli.py set-password
          </p>
          <button
            type="button"
            onClick={() => void check()}
            className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)]"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-8">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 shadow-sm space-y-4">
        <h1 className="text-xl font-bold font-display text-center">BenchMax LAN Login</h1>
        <p className="text-sm text-muted-foreground text-center">
          This BenchMax server is shared on the network. Enter the LAN password to continue.
        </p>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void submit();
          }}
          placeholder="LAN password"
          aria-label="LAN password"
          autoComplete="current-password"
          className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
        {error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400 text-center">
            {error}
          </p>
        )}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!password || submitting}
          className="w-full px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50"
        >
          {submitting ? 'Unlocking…' : 'Unlock'}
        </button>
      </div>
    </div>
  );
}
