import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { fetchLabStatus, postLabAttempt } from '../api'
import { BrandMark } from '../components/BrandMark'
import type { LabAttemptMode, LabStatus } from '../types'

type Toast = { kind: 'ok' | 'err' | 'info'; text: string }

function guessLocation(): string {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''
    const map: Record<string, string> = {
      'Asia/Yangon': 'Yangon, Myanmar',
      'Asia/Bangkok': 'Bangkok, Thailand',
      'Asia/Singapore': 'Singapore',
      'Asia/Tokyo': 'Tokyo, Japan',
      'Asia/Kolkata': 'Mumbai, India',
      'Europe/London': 'London, United Kingdom',
      'America/New_York': 'New York, United States',
      'America/Los_Angeles': 'Los Angeles, United States',
    }
    if (map[tz]) return map[tz]
    if (tz.includes('/')) {
      const city = tz.split('/').pop()!.replace(/_/g, ' ')
      return `${city} (approx.)`
    }
  } catch {
    /* ignore */
  }
  return 'Yangon, Myanmar (lab)'
}

export function LabLoginPage() {
  const [email, setEmail] = useState('testuser2222@gmail.com')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [burstCount, setBurstCount] = useState(5)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<Toast | null>(null)
  const [lab, setLab] = useState<LabStatus | null>(null)
  const [showLabTools, setShowLabTools] = useState(false)
  const [location] = useState(() => guessLocation())

  useEffect(() => {
    let cancelled = false
    fetchLabStatus()
      .then((s) => {
        if (!cancelled) setLab(s)
      })
      .catch(() => {
        if (!cancelled) {
          setLab(null)
          setToast({
            kind: 'err',
            text: 'Lab API unreachable. Start P12 on :8080, then refresh.',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function run(mode: LabAttemptMode) {
    setBusy(true)
    setToast({ kind: 'info', text: mode === 'once' ? 'Signing in…' : `Sending ${mode} to lab SSH…` })
    try {
      const res = await postLabAttempt({
        email,
        password,
        mode,
        burst_count: burstCount,
        location,
      })
      if (!res.ok) {
        setToast({ kind: 'err', text: res.error || res.detail || 'Sign-in failed' })
        return
      }
      if (mode === 'once') {
        const ok = res.last_result === 'accepted'
        setToast({
          kind: ok ? 'ok' : 'err',
          text: ok
            ? `Signed in from ${location}. Open Monitor to see your session.`
            : `Incorrect email or password. Session recorded (${res.session?.wrong_attempts ?? 1} wrong attempt(s)).`,
        })
      } else {
        setToast({
          kind: 'ok',
          text: `${mode}: ${res.attempt_count} attempt(s), last=${res.last_result}. Open Monitor.`,
        })
      }
    } catch (err) {
      setToast({ kind: 'err', text: err instanceof Error ? err.message : 'Request failed' })
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void run('once')
  }

  const labUp = Boolean(lab?.lab.container.ok && lab.lab.ssh_reachable)

  return (
    <div className="login-split">
      <section className="login-form-pane">
        <div className="top-row">
          <BrandMark size={36} />
          <span className={`pill-status ${labUp ? '' : 'down'}`}>
            <span className="dot" />
            {lab ? (labUp ? `Lab :${lab.lab.port}` : 'Lab offline') : 'Checking…'}
          </span>
        </div>

        <div className="login-form-center">
          <h1>Welcome back!</h1>
          <p className="sub">
            Sign in with any email — the lab password is shared. Activity is scored live by
            BruteWatch; wrong passwords and locations show up on the monitor.
          </p>

          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <div className="field-row">
                <label htmlFor="password">Password</label>
                <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Never stored</span>
              </div>
              <div className="password-wrap">
                <input
                  id="password"
                  name="password"
                  type={showPw ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="eye"
                  onClick={() => setShowPw((v) => !v)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            <p className="login-loc-hint">Signing in from {location}</p>

            <div className="actions">
              <button className="btn btn-primary" type="submit" disabled={busy} style={{ flex: 1 }}>
                Sign In
              </button>
            </div>
          </form>

          <button
            type="button"
            className="lab-tools-toggle"
            onClick={() => setShowLabTools((v) => !v)}
          >
            {showLabTools ? 'Hide lab tools' : 'Lab tools (burst / success)'}
          </button>

          {showLabTools ? (
            <div className="lab-tools">
              <div className="field">
                <label htmlFor="burst">Fail burst count</label>
                <input
                  id="burst"
                  type="number"
                  min={3}
                  max={10}
                  value={burstCount}
                  onChange={(e) => setBurstCount(Number(e.target.value) || 5)}
                />
              </div>
              <div className="actions">
                <button
                  className="btn btn-danger"
                  type="button"
                  disabled={busy || !email}
                  onClick={() => void run('burst')}
                >
                  Fail burst ({burstCount})
                </button>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={busy || !email}
                  onClick={() => void run('success')}
                >
                  Success session
                </button>
              </div>
            </div>
          ) : null}

          {toast ? <div className={`toast ${toast.kind}`}>{toast.text}</div> : null}

          <p className="login-foot">
            Controlled-lab only.{' '}
            <Link to="/monitor">Open activity monitor →</Link>
          </p>
        </div>
      </section>

      <aside className="login-visual-pane" aria-label="BruteWatch illustration">
        <img
          className="visual-art"
          src="/login-hero.jpg"
          alt="BruteWatch illustration: shield watch balloon with security timeline cards"
        />
        <div className="visual-caption">
          <div className="eyebrow">BruteWatch lab</div>
          <h2>See threats as they unfold</h2>
        </div>
      </aside>
    </div>
  )
}
