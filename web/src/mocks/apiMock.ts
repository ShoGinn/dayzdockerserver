import type { ModListResponse, ServerStatus, SteamLoginStatus } from '../types'

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const MOCK_LATENCY = Number(import.meta.env.VITE_API_MOCK_LATENCY ?? 250)

const mockState: {
  status: ServerStatus
  mods: ModListResponse['mods']
  configContent: string
  structuredConfig: Record<string, unknown>
  configSchema: {
    success: boolean
    fields: Record<string, { type: string; default: unknown; description: string | null }>
    sections: Record<string, string[]>
    descriptions: Record<string, string>
  }
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
  steam: SteamLoginStatus
  storage: {
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
  }
} = {
  status: {
    installed: true,
    state: 'running',
    pid: 1234,
    uptime_seconds: 3600,
    uptime_text: '1h 0m',
    map: 'Chernarus',
    version: '1.25.0',
    auto_restart: true,
    maintenance: false,
    restart_count: 1,
    last_exit_code: null,
    message: 'Server running in mock mode',
    active_mods: [
      {
        id: '450907',
        name: 'BaseBuildingPlus',
        url: 'https://steam.example/450907',
        size: '120 MB',
        active: true,
      },
      {
        id: '302248',
        name: 'CodeLock',
        url: 'https://steam.example/302248',
        size: '25 MB',
        active: true,
      },
    ],
  },
  mods: [
    {
      id: '450907',
      name: 'BaseBuildingPlus',
      url: 'https://steam.example/450907',
      size: '120 MB',
      active: true,
    },
    {
      id: '302248',
      name: 'CodeLock',
      url: 'https://steam.example/302248',
      size: '25 MB',
      active: true,
    },
    {
      id: '778899',
      name: 'MassClothing',
      url: 'https://steam.example/778899',
      size: '180 MB',
      active: false,
    },
  ],
  configContent: '# Example server config\nhostname = "Mock Server";\nmaxPlayers = 60;\n',
  structuredConfig: {
    hostname: 'Mock Server',
    maxPlayers: 60,
    passwordAdmin: 'changeme',
  },
  configSchema: {
    success: true,
    fields: {
      hostname: { type: 'string', default: 'DayZ', description: 'Server name' },
      maxPlayers: { type: 'number', default: 60, description: 'Max players' },
      passwordAdmin: { type: 'string', default: '', description: 'Admin password' },
    },
    sections: { general: ['hostname', 'maxPlayers', 'passwordAdmin'] },
    descriptions: { general: 'Basic server settings' },
  },
  maps: [
    {
      workshop_id: '1602372402',
      name: 'Chernarus',
      description: 'Classic DayZ experience.',
      templates: ['chernarus', 'chernarus-winter'],
      default_template: 'chernarus',
      required_mods: ['BaseBuildingPlus'],
      installed: true,
      source: 'workshop',
    },
    {
      workshop_id: '1710977250',
      name: 'DeerIsle',
      description: 'Island survival scenario.',
      templates: ['deerisle'],
      default_template: 'deerisle',
      required_mods: ['CodeLock'],
      installed: false,
      source: 'workshop',
    },
  ],
  steam: {
    configured: true,
    masked_username: 'survivor***',
    note: 'Mock login active',
  },
  storage: {
    map: '/srv/dayz/maps',
    mission_dir: '/srv/dayz/missions',
    storage_dirs: [
      {
        name: 'profiles',
        path: '/srv/dayz/profiles',
        size_bytes: 1024 * 1024 * 256,
        size_human: '256 MB',
        file_count: 1200,
      },
      {
        name: 'logs',
        path: '/srv/dayz/logs',
        size_bytes: 1024 * 1024 * 64,
        size_human: '64 MB',
        file_count: 420,
      },
    ],
    total_size_bytes: 1024 * 1024 * 320,
    total_size_human: '320 MB',
  },
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export async function mockRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  await delay(MOCK_LATENCY)

  const method = (options.method ?? 'GET').toUpperCase()
  const path = endpoint.split('?')[0]

  // Status
  if (path === '/status' && method === 'GET') {
    return structuredClone(mockState.status) as T
  }

  if (path === '/server/start' && method === 'POST') {
    mockState.status.state = 'starting'
    mockState.status.message = 'Starting (mock)'
    return { success: true, message: 'Server starting (mock)' } as T
  }

  if (path === '/server/stop' && method === 'POST') {
    mockState.status.state = 'stopped'
    mockState.status.message = 'Stopped (mock)'
    return { success: true, message: 'Server stopped (mock)' } as T
  }

  if (path === '/server/restart' && method === 'POST') {
    mockState.status.state = 'running'
    mockState.status.restart_count += 1
    mockState.status.message = 'Restarted (mock)'
    return { success: true, message: 'Server restarted (mock)' } as T
  }

  if (path === '/server/auto-restart/enable' && method === 'POST') {
    mockState.status.auto_restart = true
    return { success: true, message: 'Auto-restart enabled (mock)' } as T
  }

  if (path === '/server/auto-restart/disable' && method === 'POST') {
    mockState.status.auto_restart = false
    return { success: true, message: 'Auto-restart disabled (mock)' } as T
  }

  if (path === '/server/maintenance/enable' && method === 'POST') {
    mockState.status.maintenance = true
    mockState.status.state = 'maintenance'
    return { success: true, message: 'Maintenance enabled (mock)' } as T
  }

  if (path === '/server/maintenance/disable' && method === 'POST') {
    mockState.status.maintenance = false
    mockState.status.state = 'running'
    return { success: true, message: 'Maintenance disabled (mock)' } as T
  }

  if (path === '/server/install' && method === 'POST') {
    mockState.status.installed = true
    return { success: true, message: 'Server installed (mock)' } as T
  }

  if (path === '/server/update' && method === 'POST') {
    return { success: true, message: 'Server updated (mock)' } as T
  }

  // Mods
  if (path === '/mods' && method === 'GET') {
    const isActiveOnly = endpoint.includes('active_only=true')
    const mods = isActiveOnly ? mockState.mods.filter(mod => mod.active) : mockState.mods
    return { mods, count: mods.length } as T
  }

  if (path.startsWith('/mods/install/') && method === 'POST') {
    const modId = path.split('/').pop() ?? 'new'
    mockState.mods.push({
      id: modId,
      name: `Mod ${modId}`,
      url: `https://steam.example/${modId}`,
      size: '50 MB',
      active: false,
    })
    return { success: true, message: `Installed mod ${modId} (mock)` } as T
  }

  if (path.match(/^\/mods\/\w+$/) && method === 'DELETE') {
    const modId = path.split('/').pop()
    mockState.mods = mockState.mods.filter(mod => mod.id !== modId)
    return { success: true, message: `Removed mod ${modId} (mock)` } as T
  }

  if (path.endsWith('/activate') && method === 'POST') {
    const modId = path.split('/')[2]
    mockState.mods = mockState.mods.map(mod => (mod.id === modId ? { ...mod, active: true } : mod))
    return { success: true, message: `Activated mod ${modId} (mock)` } as T
  }

  if (path.endsWith('/deactivate') && method === 'POST') {
    const modId = path.split('/')[2]
    mockState.mods = mockState.mods.map(mod => (mod.id === modId ? { ...mod, active: false } : mod))
    return { success: true, message: `Deactivated mod ${modId} (mock)` } as T
  }

  if (path === '/mods/update-all' && method === 'POST') {
    return { success: true, message: 'Updated all mods (mock)' } as T
  }

  // Config
  if (path === '/config' && method === 'GET') {
    return { success: true, content: mockState.configContent } as T
  }

  if (path === '/config' && method === 'PUT') {
    const body = options.body
      ? (JSON.parse(options.body.toString()) as { content: string })
      : { content: '' }
    mockState.configContent = body.content
    return { success: true, message: 'Config saved (mock)' } as T
  }

  if (path === '/config/structured' && method === 'GET') {
    return {
      success: true,
      message: 'Loaded (mock)',
      data: structuredClone(mockState.structuredConfig),
    } as T
  }

  if (path === '/config/structured' && method === 'PUT') {
    const body = options.body
      ? (JSON.parse(options.body.toString()) as Record<string, unknown>)
      : {}
    mockState.structuredConfig = { ...mockState.structuredConfig, ...body }
    return { success: true, message: 'Structured config saved (mock)' } as T
  }

  if (path === '/config/schema' && method === 'GET') {
    return structuredClone(mockState.configSchema) as T
  }

  // Maps
  if (path === '/maps' && method === 'GET') {
    return {
      success: true,
      maps: structuredClone(mockState.maps),
      installed_templates: ['chernarus'],
    } as T
  }

  if (path.startsWith('/maps/') && path.endsWith('/install') && method === 'POST') {
    const id = path.split('/')[2]
    mockState.maps = mockState.maps.map(map =>
      map.workshop_id === id ? { ...map, installed: true } : map
    )
    return { success: true, message: `Installed map ${id} (mock)` } as T
  }

  if (path.match(/^\/maps\/[^/]+$/) && method === 'DELETE') {
    const id = path.split('/')[2]
    mockState.maps = mockState.maps.map(map =>
      map.workshop_id === id ? { ...map, installed: false } : map
    )
    return { success: true, message: `Uninstalled map ${id} (mock)` } as T
  }

  if (path.match(/^\/maps\/[^/]+$/) && method === 'GET') {
    const id = path.split('/')[2]
    const map = mockState.maps.find(m => m.workshop_id === id)
    if (!map) throw new ApiError(404, 'Map not found (mock)')
    return { success: true, map } as T
  }

  if (path.startsWith('/maps/template/') && method === 'GET') {
    const template = path.split('/').pop() ?? ''
    const map = mockState.maps.find(m => m.templates.includes(template)) ?? mockState.maps[0]
    return {
      success: true,
      map: {
        name: map.name,
        description: map.description,
        workshop_id: map.workshop_id,
        templates: map.templates,
      },
    } as T
  }

  // Steam
  if (path === '/steam/status' && method === 'GET') {
    return structuredClone(mockState.steam) as T
  }

  if (path === '/steam/login' && method === 'POST') {
    const body = options.body
      ? (JSON.parse(options.body.toString()) as { username: string })
      : { username: '' }
    mockState.steam.masked_username = `${body.username}***`
    return { success: true, message: 'Steam login saved (mock)' } as T
  }

  if (path === '/steam/test' && method === 'POST') {
    return { success: true, message: 'Steam login verified (mock)' } as T
  }

  if (path === '/admin/storage' && method === 'GET') {
    return { success: true, ...structuredClone(mockState.storage) } as T
  }

  if (path.startsWith('/admin/storage') && method === 'DELETE') {
    return { success: true, message: 'Storage wiped (mock)' } as T
  }

  throw new ApiError(404, `Mock route not implemented: ${method} ${endpoint}`)
}
