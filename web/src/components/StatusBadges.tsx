import type { HealthResponse } from '../types'

function tone(status: string): 'ok' | 'warn' | 'crit' | 'info' {
  const s = status.toUpperCase()
  if (s.includes('HEALTHY') || s === 'ONLINE' || s === 'ENABLED' || s === 'OK' || s === 'SENT') {
    return 'ok'
  }
  if (s.includes('STALE') || s.includes('WARN') || s.includes('DISABLED') || s.includes('PENDING')) {
    return 'warn'
  }
  if (s.includes('OFFLINE') || s.includes('FAIL') || s.includes('CRIT') || s.includes('DEGRADED')) {
    return 'crit'
  }
  return 'info'
}

export function StatusBadges({ health }: { health: HealthResponse | null }) {
  if (!health) {
    return (
      <div className="badges">
        <span className="badge info">Loading…</span>
      </div>
    )
  }
  return (
    <div className="badges">
      <span className={`badge ${tone(health.p12_status)}`}>P12 {health.p12_status}</span>
      <span className={`badge ${tone(health.p11_status)}`}>P11 {health.p11_status}</span>
      <span className={`badge ${tone(health.discord_status)}`}>Discord {health.discord_status}</span>
    </div>
  )
}
