import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useTopicStore } from '@/app/store/topicStore'
import { uiStateApi } from '../api/uiStateApi'

const DEBOUNCE_MS = 1500
const TOPIC_PREFIX = '/topic'

function saveUiState() {
  const path = window.location.pathname
  if (!path.startsWith(TOPIC_PREFIX)) return
  const activeTopicId = useTopicStore.getState().activeTopicId
  uiStateApi
    .setState({
      active_theme_id: activeTopicId ?? null,
      url: path,
    })
    .catch(() => {})
}

export function useUiStateSave() {
  const location = useLocation()
  const activeTopicId = useTopicStore((s) => s.activeTopicId)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const path = location.pathname
    if (!path.startsWith(TOPIC_PREFIX)) return

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      debounceRef.current = null
      saveUiState()
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [activeTopicId, location.pathname])

  useEffect(() => {
    const onLeave = () => {
      if (!window.location.pathname.startsWith(TOPIC_PREFIX)) return
      saveUiState()
    }

    window.addEventListener('beforeunload', onLeave)
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') onLeave()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      window.removeEventListener('beforeunload', onLeave)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])
}
