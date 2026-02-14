import { useEffect, useState } from 'react'
import { api } from '../api'
import type { MapInfo } from '../types'

export function useMapInfo(template: string | null) {
  const [mapInfo, setMapInfo] = useState<MapInfo | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!template) {
      setMapInfo(null)
      return
    }

    const fetchMapInfo = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await api.getMapByTemplate(template)
        setMapInfo(response.map)
      } catch {
        // Silently fail - map might not be in registry, will use raw template
        setMapInfo({
          name: template.replace('dayzOffline.', ''),
          description: 'Unknown map',
        })
      } finally {
        setIsLoading(false)
      }
    }

    fetchMapInfo()
  }, [template])

  return { mapInfo, isLoading, error }
}
