import type {
  ModListResponse,
  OperationResponse,
  ServerStatus,
  SteamLoginStatus,
  VPPSuperAdminsResponse,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'
const USE_MOCK = import.meta.env.VITE_API_MOCK === 'true'

let mockRequestFn: null | typeof import('./mocks/apiMock')['mockRequest'] = null

async function getMockRequest() {
  if (!mockRequestFn) {
    try {
      const mod = await import('./mocks/apiMock.ts')
      mockRequestFn = mod.mockRequest
    } catch (error) {
      console.error('Failed to load mock API module', error)
      throw error
    }
  }
  return mockRequestFn
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  if (USE_MOCK) {
    const mockRequest = await getMockRequest()
    return mockRequest<T>(endpoint, options)
  }
  const token = localStorage.getItem('api_token')

  const headers = new Headers({
    'Content-Type': 'application/json',
    ...(options.headers as HeadersInit),
  })

  if (!headers.has('Authorization') && token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const text = await response.text()
    let message = text
    try {
      const json = JSON.parse(text)
      message = json.detail || json.message || text
    } catch {
      // Keep text as message
    }
    throw new ApiError(response.status, message)
  }

  return response.json()
}

// Server endpoints
export const api = {
  // Status
  getStatus: () => request<ServerStatus>('/status'),
  verifyToken: (token: string) =>
    request<ServerStatus>('/status', {
      headers: { Authorization: `Bearer ${token}` },
    }),

  // Server control
  startServer: () => request<OperationResponse>('/server/start', { method: 'POST' }),
  stopServer: () => request<OperationResponse>('/server/stop', { method: 'POST' }),
  restartServer: () => request<OperationResponse>('/server/restart', { method: 'POST' }),

  // Auto-restart
  enableAutoRestart: () =>
    request<OperationResponse>('/server/auto-restart/enable', {
      method: 'POST',
    }),
  disableAutoRestart: () =>
    request<OperationResponse>('/server/auto-restart/disable', {
      method: 'POST',
    }),

  // Maintenance
  enableMaintenance: () =>
    request<OperationResponse>('/server/maintenance/enable', {
      method: 'POST',
    }),
  disableMaintenance: () =>
    request<OperationResponse>('/server/maintenance/disable', {
      method: 'POST',
    }),

  // Installation
  installServer: () => request<OperationResponse>('/server/install', { method: 'POST' }),
  updateServer: () => request<OperationResponse>('/server/update', { method: 'POST' }),
  uninstallServer: () => request<OperationResponse>('/server/uninstall', { method: 'POST' }),

  // Mods
  getMods: (activeOnly = false) =>
    request<ModListResponse>(`/mods${activeOnly ? '?active_only=true' : ''}`),
  installMod: (modId: string) =>
    request<OperationResponse>(`/mods/install/${modId}`, { method: 'POST' }),
  removeMod: (modId: string) => request<OperationResponse>(`/mods/${modId}`, { method: 'DELETE' }),
  activateMod: (modId: string) =>
    request<OperationResponse>(`/mods/${modId}/activate`, { method: 'POST' }),
  deactivateMod: (modId: string) =>
    request<OperationResponse>(`/mods/${modId}/deactivate`, { method: 'POST' }),
  updateAllMods: () => request<OperationResponse>('/mods/update-all', { method: 'POST' }),
  setModMode: (modId: string, mode: 'server' | 'client') =>
    request<OperationResponse>(`/mods/${modId}/mode?mode=${mode}`, { method: 'POST' }),

  // Config
  getConfig: (raw = false) =>
    request<{ success: boolean; content: string }>(`/config${raw ? '?raw=true' : ''}`),
  updateConfig: (content: string) =>
    request<OperationResponse>('/config', {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
  getStructuredConfig: () =>
    request<{
      success: boolean
      message: string
      data: Record<string, unknown>
    }>('/config/structured'),
  updateStructuredConfig: (config: Record<string, unknown>) =>
    request<OperationResponse>('/config/structured', {
      method: 'PUT',
      body: JSON.stringify(config),
    }),
  getConfigSchema: () =>
    request<{
      success: boolean
      fields: Record<string, { type: string; default: unknown; description: string | null }>
      sections: Record<string, string[]>
      descriptions: Record<string, string>
    }>('/config/schema'),

  // Maps
  getMaps: () =>
    request<{
      success: boolean
      maps: Array<{
        workshop_id: string
        name: string
        description: string
        templates: string[]
        default_template: string
        required_mods: string[]
        installed: boolean
        source: string
      }>
      installed_templates: string[]
    }>('/maps'),
  getMapInfo: (workshopId: string) =>
    request<{
      success: boolean
      map: {
        workshop_id: string
        name: string
        description: string
        templates: string[]
        default_template: string
        required_mods: string[]
        repo_url: string
        installed: boolean
      }
    }>(`/maps/${workshopId}`),
  getMapByTemplate: (template: string) =>
    request<{
      success: boolean
      map: {
        name: string
        description: string
        workshop_id?: string
        templates?: string[]
      }
    }>(`/maps/template/${template}`),
  installMap: (workshopId: string) =>
    request<OperationResponse>(`/maps/${workshopId}/install`, {
      method: 'POST',
    }),
  uninstallMap: (workshopId: string) =>
    request<OperationResponse>(`/maps/${workshopId}`, { method: 'DELETE' }),

  // Steam
  getSteamStatus: () => request<SteamLoginStatus>('/steam/status'),
  setSteamLogin: (username: string) =>
    request<OperationResponse>('/steam/login', {
      method: 'POST',
      body: JSON.stringify({ username }),
    }),
  testSteamLogin: () => request<OperationResponse>('/steam/test', { method: 'POST' }),

  // Storage Management
  getStorageInfo: () =>
    request<{
      success: boolean
      map: string
      mission_dir: string
      storage_dirs: Array<{
        name: string
        path: string
        size_bytes: number
        size_human: string
        file_count: number
      }>
      total_size_bytes: number
      total_size_human: string
    }>('/admin/storage'),
  wipeStorage: (storageName?: string) =>
    request<OperationResponse>(
      `/admin/storage${storageName ? `?storage_name=${storageName}` : ''}`,
      { method: 'DELETE' }
    ),

  // Cleanup
  getCleanupInfo: () =>
    request<{
      success: boolean
      items: {
        core_dumps: Array<{
          name: string
          path: string
          size_bytes: number
          size_human: string
        }>
        crash_dumps: Array<{
          name: string
          path: string
          size_bytes: number
          size_human: string
        }>
        log_files: Array<{
          name: string
          path: string
          size_bytes: number
          size_human: string
        }>
        temp_files: Array<{
          name: string
          path: string
          size_bytes: number
          size_human: string
        }>
      }
      total_size_bytes: number
      total_size_human: string
      counts: Record<string, number>
    }>('/admin/cleanup'),
  cleanupServerFiles: (options?: {
    core_dumps?: boolean
    crash_dumps?: boolean
    log_files?: boolean
    temp_files?: boolean
  }) => {
    const params = new URLSearchParams()
    if (options) {
      if (options.core_dumps !== undefined) params.set('core_dumps', String(options.core_dumps))
      if (options.crash_dumps !== undefined) params.set('crash_dumps', String(options.crash_dumps))
      if (options.log_files !== undefined) params.set('log_files', String(options.log_files))
      if (options.temp_files !== undefined) params.set('temp_files', String(options.temp_files))
    }
    const query = params.toString()
    return request<OperationResponse>(`/admin/cleanup${query ? `?${query}` : ''}`, {
      method: 'POST',
    })
  },

  // Server params & channel
  getServerParams: () => request<{ success: boolean; params: string }>('/server/params'),
  setServerParams: (payload: {
    params?: string
    enable_logs?: boolean
    admin_log?: boolean
    net_log?: boolean
    port?: number
  }) =>
    request<OperationResponse>('/server/params', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getServerChannel: () => request<{ success: boolean; channel: string }>('/server/channel'),
  setServerChannel: (channel: 'stable' | 'experimental') =>
    request<OperationResponse>('/server/channel', {
      method: 'POST',
      body: JSON.stringify({ channel }),
    }),

  // Logs
  listLogFiles: () =>
    request<{
      success: boolean
      files: Array<{ name: string; path: string; size_bytes: number; size_human: string }>
    }>('/logs/files'),
  getLogTail: (filename?: string, bytesCount = 20000) =>
    request<{ success: boolean; message: string; content: string }>(
      `/logs${filename ? `?filename=${encodeURIComponent(filename)}` : ''}&bytes_count=${bytesCount}`
    ),

  // VPP Admin Tools
  getVppSuperadmins: () => request<VPPSuperAdminsResponse>('/vpp/superadmins'),
  setVppSuperadmins: (steam64_ids: string[], mode: 'overwrite' | 'add' = 'overwrite') =>
    request<OperationResponse>('/vpp/superadmins', {
      method: 'POST',
      body: JSON.stringify({ steam64_ids, mode }),
    }),
  setVppPassword: (password: string) =>
    request<OperationResponse>('/vpp/password', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
  resolveSteamId: (query: string) =>
    request<{ success: boolean; steam64_id: string | null; message: string }>(
      '/vpp/steam-id/resolve',
      {
        method: 'POST',
        body: JSON.stringify({ query }),
      }
    ),
  validateSteamId: (query: string) =>
    request<{ success: boolean; steam64_id: string | null; message: string }>(
      '/vpp/steam-id/validate',
      {
        method: 'POST',
        body: JSON.stringify({ query }),
      }
    ),
}

export { ApiError }
