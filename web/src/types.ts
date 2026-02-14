// API Response Types

export interface ServerStatus {
  installed: boolean
  state: ServerState
  pid: number | null
  uptime_seconds: number
  uptime_text: string
  map: string
  version: string
  auto_restart: boolean
  maintenance: boolean
  restart_count: number
  last_exit_code: number | null
  message: string
  active_mods: ModInfo[]
}

export interface MapInfo {
  name: string
  description: string
  workshop_id?: string
  templates?: string[]
}

export type ServerState =
  | 'stopped'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'crashed'
  | 'disabled'
  | 'maintenance'

export interface ModInfo {
  id: string
  name: string
  url: string
  size: string
  active: boolean
}

export interface ModListResponse {
  mods: ModInfo[]
  count: number
}

export interface OperationResponse {
  success: boolean
  message: string
  details?: Record<string, unknown>
}

export interface HealthResponse {
  status: string
  server_state: ServerState
  message: string
}

export interface SteamLoginStatus {
  configured: boolean
  masked_username: string | null
  note: string | null
}

export interface VPPSuperAdminsResponse {
  steam64_ids: string[]
}
