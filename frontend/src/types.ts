/** 后端统一返回结构 {code, msg, data}（CONTEXT.md §4） */
export interface ApiResponse<T = unknown> {
  code: number
  msg: string
  data: T
}

export interface TokenData {
  token: string
  role: string
}

export interface UserInfo {
  id: number
  username: string
  role: string
  status: number
  created_at: string
}

export type TaskStatus = 'pending' | 'running' | 'success' | 'failed'

export interface TaskItem {
  id: number
  file_name: string
  total_rows: number
  attack_rows: number
  normal_rows: number
  status: TaskStatus
  error_msg: string | null
  cost_seconds: number | null
  created_at: string
  updated_at: string
}

export interface TaskCreatedData {
  task_id: number
  status: TaskStatus
}

export interface PageData<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface ResultItem {
  id: number
  row_no: number
  prediction: string
  attack_type: string | null
  confidence: number | null
}

export interface StatsData {
  task_id: number
  status: TaskStatus
  total_results: number
  prediction_distribution: Record<
    string,
    { count: number; avg_confidence: number | null }
  >
  task_rows: { total_rows: number; attack_rows: number; normal_rows: number }
  cost_seconds: number | null
}

// ---------- V2 告警（product 分支） ----------
export type AlertStatus = 'open' | 'acked' | 'dismissed'

export interface AlertItem {
  id: number
  task_id: number
  src_key: string
  confidence: number
  prediction: string
  rule_cmd: string | null
  status: AlertStatus
  created_at: string
}

export interface AlertCountData {
  open_count: number
}
