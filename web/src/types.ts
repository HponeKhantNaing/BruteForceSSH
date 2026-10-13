export type HealthResponse = {
  p12_status: string
  p11_status: string
  discord_status: string
  database_status: string
  release_id: string
  predictions: number
  alerts_sent: number
}

export type SummaryResponse = {
  predictions_ingested: number
  normal: number
  suspicious: number
  brute_force: number
  alerts_sent: number
  alerts_pending: number
  alerts_failed: number
}

export type ModelResponse = {
  release_id: string
  model: string
  representation: string
  feature_count: number
  maturity: string
  probability_type: string
  note: string
  limitation: string
}

export type Prediction = {
  id: number
  episode_id: string
  source_id: string
  snapshot_type: string
  predicted_label: string
  attempt_count: number
  event_timestamp: string
  provisional: number
  final: number
  severity: string | null
  alert_decision: string | null
  alert_status: string | null
  score_normal: number
  score_suspicious: number
  score_brute_force: number
}

export type AlertRow = {
  id: number
  episode_id: string
  source_id: string
  predicted_label: string
  severity: string | null
  decision: string
  delivery_state: string
  alert_phase: string
  created_at: string
  sent_at: string | null
  suppressed_reason: string | null
}

export type LabStatus = {
  ok: boolean
  lab: {
    host: string
    port: number
    container: { status: string; health: string; ok: boolean; error?: string }
    ssh_reachable: boolean
  }
  limits: {
    max_attempts_per_minute: number
    burst_min: number
    burst_max: number
  }
  disclaimer: string
}

export type LabAttemptMode = 'once' | 'success' | 'burst'

export type LabSession = {
  id: number
  email: string
  location: string
  wrong_attempts: number
  status: 'success' | 'failed' | 'unknown' | string
  mode: LabAttemptMode | string
  timestamp: string
}

export type LabAttemptResponse = {
  ok: boolean
  mode?: LabAttemptMode
  attempt_count?: number
  last_result?: string
  results?: Array<{ result: string; attempts: number }>
  email?: string
  location?: string
  session?: LabSession
  username?: string
  error?: string
  detail?: string
}
