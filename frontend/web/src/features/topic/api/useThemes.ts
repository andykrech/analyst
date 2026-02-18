import { useCallback, useEffect, useState } from 'react'
import { useTopicStore } from '@/app/store/topicStore'
import { themesApi } from './themesApi'

/** Загружает список тем и пишет в topicStore.themesForNav для TopicsNavProvider. */
export function useThemes() {
  const activeTopicId = useTopicStore((s) => s.activeTopicId)
  const setThemesForNav = useTopicStore((s) => s.setThemesForNav)
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const res = await themesApi.getThemes({ skip401Redirect: true })
      const themes = res.themes ?? []
      setThemesForNav(themes)
    } catch {
      setThemesForNav([])
    } finally {
      setLoading(false)
    }
  }, [setThemesForNav])

  useEffect(() => {
    refetch()
  }, [refetch, activeTopicId])

  return { loading, refetch }
}
