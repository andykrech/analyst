import { useEffect } from 'react'
import { useTopicStore } from '@/app/store/topicStore'
import './LandscapeTab.css'

interface LandscapeTabProps {
  themeId: string
}

export function LandscapeTab({ themeId }: LandscapeTabProps) {
  const landscape = useTopicStore((s) => s.data.landscape)
  const loadLandscape = useTopicStore((s) => s.loadLandscape)

  useEffect(() => {
    if (themeId) {
      void loadLandscape()
    }
  }, [themeId, loadLandscape])

  const showLoading = landscape.isLoading && landscape.text == null

  return (
    <div className="landscape-tab">
      {(landscape.error || landscape.build.error) && (
        <div className="landscape-tab__error" role="alert">
          {landscape.build.error ?? landscape.error}
        </div>
      )}

      {showLoading ? (
        <p className="landscape-tab__loading">Загрузка…</p>
      ) : landscape.text == null || landscape.text === '' ? (
        <p className="landscape-tab__empty">
          Ландшафт ещё не построен. Нажмите «Построить ландшафт» на панели выше.
        </p>
      ) : (
        <pre className="landscape-tab__text">{landscape.text}</pre>
      )}
    </div>
  )
}
