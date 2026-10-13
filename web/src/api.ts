import type {
  AlertRow,
  HealthResponse,
  LabAttemptMode,
  LabAttemptResponse,
  LabSession,
  LabStatus,
  ModelResponse,
  Prediction,
  SummaryResponse,
} from './types'

async function readJSON<T>(res: Response, path: string): Promise<T> {
  const text = await res.text()
  if (!text.trim()) {
    throw new Error(
      res.ok
        ? `${path}: empty response (is P12 on :8080?)`
        : `${path} failed (${res.status}) — empty body`,
    )
  }
  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(`${path}: invalid JSON (${res.status})`)
  }
}

async function getJSON<T>(path: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { headers: { Accept: 'application/json' } })
  } catch {
    throw new Error(`${path}: network error — start P12 on :8080`)
  }
  const data = await readJSON<T>(res, path)
  if (!res.ok) {
    throw new Error(`${path} failed (${res.status})`)
  }
  return data
}

export function fetchHealth() {
  return getJSON<HealthResponse>('/api/health')
}

export function fetchSummary() {
  return getJSON<SummaryResponse>('/api/summary')
}

export function fetchModel() {
  return getJSON<ModelResponse>('/api/model')
}

export function fetchPredictions(params: {
  label?: string
  snapshot_type?: string
  limit?: number
}) {
  const q = new URLSearchParams()
  if (params.label) q.set('label', params.label)
  if (params.snapshot_type) q.set('snapshot_type', params.snapshot_type)
  q.set('limit', String(params.limit ?? 100))
  return getJSON<{ items: Prediction[] }>(`/api/predictions?${q}`)
}

export function fetchAlerts(limit = 50) {
  return getJSON<{ items: AlertRow[] }>(`/api/alerts?limit=${limit}`)
}

export function fetchLabStatus() {
  return getJSON<LabStatus>('/api/lab/status')
}

export function fetchLabSessions(limit = 50) {
  return getJSON<{ ok: boolean; items: LabSession[] }>(`/api/lab/sessions?limit=${limit}`)
}

export async function postLabAttempt(body: {
  email: string
  password: string
  mode: LabAttemptMode
  burst_count?: number
  location?: string
}): Promise<LabAttemptResponse> {
  let res: Response
  try {
    res = await fetch('/api/lab/attempt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    return { ok: false, error: 'network error — start P12 on :8080' }
  }
  const text = await res.text()
  if (!text.trim()) {
    return {
      ok: false,
      error: res.ok
        ? 'empty response from lab API'
        : `HTTP ${res.status} — P12 may be down (empty proxy body)`,
    }
  }
  let data: LabAttemptResponse
  try {
    data = JSON.parse(text) as LabAttemptResponse
  } catch {
    return { ok: false, error: `invalid JSON from lab API (HTTP ${res.status})` }
  }
  if (!res.ok) {
    return { ...data, ok: false, error: data.error || `HTTP ${res.status}` }
  }
  return data
}
