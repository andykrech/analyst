import { useTopicStore } from '@/app/store/topicStore'
import { LandscapeTab } from './LandscapeTab'

export function LandscapePage() {
  const activeTopicId = useTopicStore((s) => s.activeTopicId)

  if (!activeTopicId) {
    return (
      <div className="events-page">
        <p className="events-page__placeholder">
          Выберите или создайте тему для просмотра ландшафта
        </p>
      </div>
    )
  }

  return <LandscapeTab themeId={activeTopicId} />
}
