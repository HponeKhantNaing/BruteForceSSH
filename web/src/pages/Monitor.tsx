import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, useSearchParams } from 'react-router-dom'
import {
  fetchAlerts,
  fetchHealth,
  fetchLabSessions,
  fetchModel,
  fetchPredictions,
  fetchSummary,
} from '../api'
import {
  AttackCalendar,
  formatDayLabel,
  isAttackLabel,
  todayKey,
  toDayKey,
  type DayKey,
} from '../components/AttackCalendar'
import { BrandMark } from '../components/BrandMark'
import { LoginSessionsTable } from '../components/LoginSessionsTable'
import { StatusBadges } from '../components/StatusBadges'
import type {
  AlertRow,
  HealthResponse,
  LabSession,
  ModelResponse,
  Prediction,
  SummaryResponse,
} from '../types'

function shortTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso.slice(0, 19)
  }
}

function MonitorNav({
  health,
  summary,
}: {
  health: HealthResponse | null
  summary: SummaryResponse | null
}) {
  const [params] = useSearchParams()
  const tab = params.get('tab') || 'overview'
  const onOverview = tab !== 'predictions' && tab !== 'alerts'
  const onPredictions = tab === 'predictions'

  return (
    <aside className="sidebar">
      <div className="side-top">
        <div className="brand">
          <BrandMark size={30} inverted />
          <span>CONTROLLED-LAB V1</span>
        </div>

        <div className="side-section">
          <p className="side-label">Workspace</p>
          <nav className="nav">
            <NavLink to="/monitor" end className={() => (onOverview ? 'active' : '')}>
              Overview
            </NavLink>
            <NavLink to="/monitor?tab=predictions" className={() => (onPredictions ? 'active' : '')}>
              Predictions
            </NavLink>
            <NavLink to="/alerts" className={({ isActive }) => (isActive ? 'active' : '')}>
              Alerts
            </NavLink>
          </nav>
        </div>

        <div className="side-section">
          <p className="side-label">Lab</p>
          <nav className="nav">
            <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : '')}>
              Lab Login
            </NavLink>
          </nav>
        </div>
      </div>

      <div className="side-pulse">
        <p className="side-label">Live pulse</p>
        <ul className="side-stats">
          <li>
            <span>P12</span>
            <strong>{health?.p12_status ?? '—'}</strong>
          </li>
          <li>
            <span>P11</span>
            <strong>{health?.p11_status ?? '—'}</strong>
          </li>
          <li>
            <span>Discord</span>
            <strong>{health?.discord_status ?? '—'}</strong>
          </li>
          <li>
            <span>Predictions</span>
            <strong>{summary?.predictions_ingested ?? health?.predictions ?? '—'}</strong>
          </li>
          <li>
            <span>Alerts sent</span>
            <strong>{summary?.alerts_sent ?? health?.alerts_sent ?? '—'}</strong>
          </li>
        </ul>
      </div>

      <div className="side-foot">
        <div className="side-release">{health?.release_id || 'release pending'}</div>
      </div>
    </aside>
  )
}

export function MonitorPage({ focus = 'overview' }: { focus?: 'overview' | 'alerts' }) {
  const [params] = useSearchParams()
  const tab = params.get('tab') || focus
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [model, setModel] = useState<ModelResponse | null>(null)
  const [preds, setPreds] = useState<Prediction[]>([])
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [sessions, setSessions] = useState<LabSession[]>([])
  const [label, setLabel] = useState('')
  const [snapshot, setSnapshot] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [selectedDay, setSelectedDay] = useState<DayKey>(() => todayKey())
  const [calMonth, setCalMonth] = useState(() => {
    const t = new Date()
    return new Date(t.getFullYear(), t.getMonth(), 1)
  })

  useEffect(() => {
    let cancelled = false
    async function tick() {
      try {
        const [h, s, m, p, a, sess] = await Promise.all([
          fetchHealth(),
          fetchSummary(),
          fetchModel(),
          fetchPredictions({
            label: label || undefined,
            snapshot_type: snapshot || undefined,
            limit: 500,
          }),
          fetchAlerts(40),
          fetchLabSessions(80),
        ])
        if (cancelled) return
        setHealth(h)
        setSummary(s)
        setModel(m)
        setPreds(p.items)
        setAlerts(a.items)
        setSessions(sess.items)
        setError(null)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Poll failed — is P12 on :8080?')
        }
      }
    }
    void tick()
    const id = window.setInterval(() => void tick(), 1000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [label, snapshot])

  const title = useMemo(() => {
    if (tab === 'alerts') return 'Alerts'
    if (tab === 'predictions') return 'Predictions'
    return 'Activity'
  }, [tab])

  const attackCounts = useMemo(() => {
    const counts: Record<DayKey, number> = {}
    for (const p of preds) {
      if (!isAttackLabel(p.predicted_label)) continue
      const key = toDayKey(p.event_timestamp)
      if (!key) continue
      counts[key] = (counts[key] || 0) + 1
    }
    return counts
  }, [preds])

  const dayPreds = useMemo(() => {
    return preds.filter((p) => toDayKey(p.event_timestamp) === selectedDay)
  }, [preds, selectedDay])

  const isToday = selectedDay === todayKey()

  const timelineItems = useMemo(() => {
    return dayPreds.slice(0, 14).map((p) => ({
      id: `p-${p.id}`,
      time: p.event_timestamp,
      label: p.predicted_label,
      title: `${p.predicted_label} · ${p.snapshot_type === 'EPISODE_FINAL' ? 'Final' : 'Live'}`,
      body: `${p.attempt_count} attempts · ${p.alert_decision || 'dashboard'}`,
    }))
  }, [dayPreds])

  function selectDay(day: DayKey) {
    setSelectedDay(day)
    const [y, m] = day.split('-').map(Number)
    setCalMonth(new Date(y, m - 1, 1))
  }

  return (
    <div className="monitor-shell">
      <MonitorNav health={health} summary={summary} />

      <main className="workspace">
        <header className="work-head">
          <div className="work-head-text">
            <p className="eyebrow">Security workspace</p>
            <h1>{title}</h1>
          </div>
          <div className="work-head-actions">
            <StatusBadges health={health} />
            <Link className="btn btn-primary" to="/">
              Lab Login
            </Link>
          </div>
        </header>

        {error ? <div className="toast err">{error}</div> : null}
        {model ? (
          <p className="note note-compact" title={`${model.note} ${model.limitation}`}>
            {model.note}
          </p>
        ) : null}

        {tab !== 'alerts' ? (
          <div className="grid-kpi">
            <div className="kpi">
              <div className="label">Predictions</div>
              <div className="value">{summary?.predictions_ingested ?? '—'}</div>
            </div>
            <div className="kpi">
              <div className="label">Suspicious</div>
              <div className="value">{summary?.suspicious ?? '—'}</div>
            </div>
            <div className="kpi">
              <div className="label">Brute force</div>
              <div className="value">{summary?.brute_force ?? '—'}</div>
            </div>
            <div className="kpi">
              <div className="label">Alerts sent</div>
              <div className="value">{summary?.alerts_sent ?? '—'}</div>
            </div>
          </div>
        ) : null}

        {tab !== 'alerts' ? (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Login sessions</h2>
                <p className="panel-sub">Email · wrong attempts · location</p>
              </div>
            </div>
            <LoginSessionsTable sessions={sessions} />
          </section>
        ) : null}

        {tab !== 'alerts' ? (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Recent predictions</h2>
                <p className="panel-sub">
                  {formatDayLabel(selectedDay)}
                  {isToday ? ' · today' : ''}
                  {attackCounts[selectedDay] ? ` · ${attackCounts[selectedDay]} attacks` : ''}
                </p>
              </div>
              <div className="filters">
                {!isToday ? (
                  <button
                    type="button"
                    className="btn btn-ghost filter-today"
                    onClick={() => selectDay(todayKey())}
                  >
                    Today
                  </button>
                ) : null}
                <select value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Label filter">
                  <option value="">All labels</option>
                  <option value="NORMAL">NORMAL</option>
                  <option value="SUSPICIOUS">SUSPICIOUS</option>
                  <option value="BRUTE_FORCE">BRUTE_FORCE</option>
                </select>
                <select
                  value={snapshot}
                  onChange={(e) => setSnapshot(e.target.value)}
                  aria-label="Snapshot filter"
                >
                  <option value="">All snapshots</option>
                  <option value="ACTIVE_PREFIX">ACTIVE_PREFIX</option>
                  <option value="EPISODE_FINAL">EPISODE_FINAL</option>
                </select>
              </div>
            </div>
            <div className="pred-layout">
              <div className="pred-list-col">
                <div className="event-list scroll-cap">
                  {dayPreds.length === 0 ? (
                    <div className="event-empty">
                      {isToday
                        ? 'No predictions today yet. Use Lab Login to generate SSH activity.'
                        : `No predictions on ${formatDayLabel(selectedDay)}.`}
                    </div>
                  ) : (
                    dayPreds.map((p) => (
                      <article key={p.id} className="event-row">
                        <span className={`tag ${p.predicted_label}`}>{p.predicted_label}</span>
                        <div className="meta">
                          <div className="title-line">
                            <span className={`tag ${p.snapshot_type}`}>
                              {p.snapshot_type === 'EPISODE_FINAL' ? 'FINAL' : 'LIVE'}
                            </span>
                            <strong>{p.attempt_count} attempts</strong>
                          </div>
                          <div className="sub">
                            {p.episode_id}
                            {p.alert_decision ? ` · ${p.alert_decision}` : ''}
                          </div>
                        </div>
                        <div className="when">{shortTime(p.event_timestamp)}</div>
                      </article>
                    ))
                  )}
                </div>
              </div>
              <div className="pred-cal-col">
                <AttackCalendar
                  month={calMonth}
                  attackCounts={attackCounts}
                  selectedDay={selectedDay}
                  onSelectDay={selectDay}
                  onMonthChange={setCalMonth}
                />
              </div>
            </div>
          </section>
        ) : null}

        {tab === 'overview' || tab === 'alerts' ? (
          <section className="panel">
            <div className="panel-head">
              <h2>Alert outbox</h2>
            </div>
            <div className="event-list scroll-cap">
              {alerts.length === 0 ? (
                <div className="event-empty">No alerts yet.</div>
              ) : (
                alerts.map((a) => (
                  <article key={a.id} className="event-row">
                    <span className={`tag ${a.predicted_label}`}>{a.predicted_label}</span>
                    <div className="meta">
                      <div className="title-line">
                        <span className={`tag ${a.delivery_state}`}>{a.delivery_state}</span>
                        <strong>{a.severity || a.alert_phase}</strong>
                      </div>
                      <div className="sub">
                        {a.decision} · {a.episode_id}
                      </div>
                    </div>
                    <div className="when">{shortTime(a.sent_at || a.created_at)}</div>
                  </article>
                ))
              )}
            </div>
          </section>
        ) : null}
      </main>

      <aside className="timeline-rail" aria-label="Activity timeline">
        <div className="rail-head">
          <h2>Timeline</h2>
          <p className="rail-sub">{isToday ? 'Today' : formatDayLabel(selectedDay)}</p>
        </div>
        <ul className="timeline">
          {timelineItems.length === 0 ? (
            <li>
              <div className="t-title">Waiting for activity</div>
              <div className="t-body">Lab Login attempts appear here.</div>
            </li>
          ) : (
            timelineItems.map((item) => (
              <li key={item.id} className={`sev-${item.label}`}>
                <div className="t-time">{shortTime(item.time)}</div>
                <div className="t-title">{item.title}</div>
                <div className="t-body">{item.body}</div>
              </li>
            ))
          )}
        </ul>
      </aside>
    </div>
  )
}
