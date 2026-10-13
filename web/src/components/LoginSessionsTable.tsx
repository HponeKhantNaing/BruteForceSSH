import { useMemo, useState } from 'react'
import type { LabSession } from '../types'

function shortTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso.slice(0, 16)
  }
}

function initials(email: string): string {
  const local = email.split('@')[0] || '?'
  const parts = local.replace(/[^a-zA-Z0-9]+/g, ' ').trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return local.slice(0, 2).toUpperCase()
}

function avatarHue(email: string): string {
  let h = 0
  for (let i = 0; i < email.length; i++) h = (h + email.charCodeAt(i) * 17) % 360
  return `hsl(${h} 42% 42%)`
}

const PAGE_SIZE = 8

type Props = {
  sessions: LabSession[]
}

export function LoginSessionsTable({ sessions }: Props) {
  const [page, setPage] = useState(0)

  const pageCount = Math.max(1, Math.ceil(sessions.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const slice = useMemo(() => {
    const start = safePage * PAGE_SIZE
    return sessions.slice(start, start + PAGE_SIZE)
  }, [sessions, safePage])

  const from = sessions.length === 0 ? 0 : safePage * PAGE_SIZE + 1
  const to = Math.min((safePage + 1) * PAGE_SIZE, sessions.length)

  if (sessions.length === 0) {
    return (
      <div className="sess-empty-state">
        No login sessions yet. Sign in from Lab Login to populate this table.
      </div>
    )
  }

  return (
    <div className="sess-table-wrap">
      <div className="sess-table-scroll">
        <table className="sess-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Wrong attempts</th>
              <th>Location</th>
              <th>Status</th>
              <th>Signed in</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((s) => (
              <tr key={s.id}>
                <td>
                  <div className="sess-identity">
                    <span className="sess-avatar" style={{ background: avatarHue(s.email) }}>
                      {initials(s.email)}
                    </span>
                    <span className="sess-email">{s.email}</span>
                  </div>
                </td>
                <td>
                  <span className={`sess-wrong ${s.wrong_attempts > 0 ? 'hot' : ''}`}>
                    {s.wrong_attempts}
                  </span>
                </td>
                <td className="sess-loc">{s.location}</td>
                <td>
                  <span className={`sess-pill ${s.status}`}>{s.status}</span>
                </td>
                <td className="sess-when">{shortTime(s.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="sess-pager">
        <span>
          {from}–{to} of {sessions.length}
        </span>
        <div className="sess-pager-btns">
          <button
            type="button"
            disabled={safePage <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            aria-label="Previous page"
          >
            ‹
          </button>
          <button
            type="button"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            aria-label="Next page"
          >
            ›
          </button>
        </div>
      </div>
    </div>
  )
}
