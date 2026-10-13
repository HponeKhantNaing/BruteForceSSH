import { useMemo } from 'react'

export type DayKey = string // YYYY-MM-DD local

export function toDayKey(isoOrDate: string | Date): DayKey {
  const d = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate
  if (Number.isNaN(d.getTime())) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayKey(): DayKey {
  return toDayKey(new Date())
}

export function formatDayLabel(key: DayKey): string {
  if (!key) return ''
  const [y, m, d] = key.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return date.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function isAttackLabel(label: string): boolean {
  return label === 'SUSPICIOUS' || label === 'BRUTE_FORCE'
}

type AttackCalendarProps = {
  month: Date
  attackCounts: Record<DayKey, number>
  selectedDay: DayKey
  onSelectDay: (day: DayKey) => void
  onMonthChange: (month: Date) => void
}

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

export function AttackCalendar({
  month,
  attackCounts,
  selectedDay,
  onSelectDay,
  onMonthChange,
}: AttackCalendarProps) {
  const cells = useMemo(() => {
    const year = month.getFullYear()
    const mon = month.getMonth()
    const first = new Date(year, mon, 1)
    const startPad = first.getDay()
    const daysInMonth = new Date(year, mon + 1, 0).getDate()
    const today = todayKey()
    const out: Array<{
      key: DayKey | null
      dayNum: number | null
      attacks: number
      isToday: boolean
      isSelected: boolean
    }> = []

    for (let i = 0; i < startPad; i++) {
      out.push({ key: null, dayNum: null, attacks: 0, isToday: false, isSelected: false })
    }
    for (let d = 1; d <= daysInMonth; d++) {
      const key = toDayKey(new Date(year, mon, d))
      out.push({
        key,
        dayNum: d,
        attacks: attackCounts[key] || 0,
        isToday: key === today,
        isSelected: key === selectedDay,
      })
    }
    return out
  }, [month, attackCounts, selectedDay])

  const title = month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

  return (
    <div className="attack-cal">
      <div className="attack-cal-head">
        <button
          type="button"
          className="attack-cal-nav"
          aria-label="Previous month"
          onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
        >
          ‹
        </button>
        <strong>{title}</strong>
        <button
          type="button"
          className="attack-cal-nav"
          aria-label="Next month"
          onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
        >
          ›
        </button>
      </div>
      <div className="attack-cal-weekdays">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="attack-cal-grid">
        {cells.map((c, i) =>
          c.key == null ? (
            <div key={`pad-${i}`} className="attack-cal-cell empty" />
          ) : (
            <button
              key={c.key}
              type="button"
              className={[
                'attack-cal-cell',
                c.isToday ? 'today' : '',
                c.isSelected ? 'selected' : '',
                c.attacks > 0 ? 'has-attacks' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => onSelectDay(c.key!)}
            >
              <span className="cal-day">{c.dayNum}</span>
              {c.attacks > 0 ? <span className="cal-count">{c.attacks}</span> : <span className="cal-count muted">·</span>}
            </button>
          ),
        )}
      </div>
      <p className="attack-cal-legend">Number under each day = attack predictions (SUSPICIOUS + BRUTE_FORCE).</p>
    </div>
  )
}
